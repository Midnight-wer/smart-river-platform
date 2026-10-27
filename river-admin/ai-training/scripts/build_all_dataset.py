"""构建「通用塑料瓶」数据集（河面 + 水中 + 室内/桌面场景）。

在 build_near_dataset.py 基础上扩展三个正样本源，目标是让模型学到
「塑料瓶本身的外观」而非「水面场景」，从而在室内手持等任意场景也能检出：

    1. m0n 河道近景原图 + ROI 放大裁剪（沿用近景数据集逻辑）
    2. COCO 人工筛选塑料瓶（旧 8 张 PET + 新 11 张通用塑料瓶），各 + 1 张 ROI 裁剪
    3. ssz5 水中塑料瓶抽样（VOC 标注，BMP 转存 JPG），各 + 1 张 ROI 裁剪

负样本沿用：无瓶水面图（processed/ssz5）+ 非瓶子容器（coco-negatives）。
所有正样本框做合法性校验（尺寸/中心越界剔除），保证「框选完整」的标注前提。

产物：datasets/all/{images,labels}/{train,val} + data.yaml

用法：
    python scripts/build_all_dataset.py
    python scripts/build_all_dataset.py --ssz5-limit 250 --near-height 0.03
"""
from __future__ import annotations

import argparse
import json
import random
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_near_dataset import NEGATIVE_DIR, ROOT, crop_around, copy_scaled  # noqa: E402
from common import (  # noqa: E402
    RAW_DIR,
    alias_set,
    is_plastic_bottle,
    iter_pairs,
    load_label_db,
    parse_voc_xml,
)

OUT_DIR = ROOT / "datasets" / "all"
COCO_DIR = RAW_DIR / "coco-bottles"
SSZ5_DIR = RAW_DIR / "ssz5-plastic-bottles-in-water"
CURATE_OLD = ROOT / "datasets" / "reports" / "curate" / "selection.json"
CURATE_NEW = ROOT / "datasets" / "reports" / "curate-local" / "selection_plastic.json"
TARGET_CN = "塑料瓶"


def valid_box(box: tuple[float, float, float, float]) -> bool:
    """框合法性校验：尺寸与中心必须在 [0,1] 内且不能退化成小点。"""
    cx, cy, w, h = box
    if not all(0 <= v <= 1 for v in (cx, cy)):
        return False
    return 0.004 < w <= 1 and 0.004 < h <= 1


def main() -> int:
    parser = argparse.ArgumentParser(description="构建通用塑料瓶数据集")
    parser.add_argument("--near-height", type=float, default=0.03)
    parser.add_argument("--max-crops", type=int, default=1, help="每图 ROI 裁剪数")
    parser.add_argument("--ssz5-limit", type=int, default=250, help="ssz5 抽样上限")
    parser.add_argument("--val-ratio", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=20261022)
    args = parser.parse_args()

    random.seed(args.seed)
    aliases = alias_set(load_label_db())

    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    for split in ("train", "val"):
        (OUT_DIR / "images" / split).mkdir(parents=True, exist_ok=True)
        (OUT_DIR / "labels" / split).mkdir(parents=True, exist_ok=True)

    # source -> list[(图片路径, [box...], 是否做ROI裁剪)]
    sources: dict[str, list[tuple[str, list, bool]]] = {"m0n": [], "coco": [], "ssz5": []}

    # ---- 1) m0n 河道近景（沿用近景逻辑）----
    for image, label, names in iter_pairs(RAW_DIR / "m0n-plastic-bottles"):
        boxes = [b for b in parse_voc_xml(label, names) if is_plastic_bottle(b.cls_name, aliases)]
        near = [b for b in boxes if b.h >= args.near_height]
        if not near:
            continue
        boxes_norm = [(b.cx, b.cy, b.w, b.h) for b in near]
        sources["m0n"].append((str(image), boxes_norm, True))

    # ---- 2) COCO 人工筛选塑料瓶（旧 + 新）----
    stems: set[str] = set()
    for path in (CURATE_OLD, CURATE_NEW):
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            stems |= set(data.get("stems") or [])
    coco_used = 0
    for split_dir in sorted((COCO_DIR / "images").glob("*")):
        if not split_dir.is_dir():
            continue
        for image in sorted(split_dir.glob("*.jpg")):
            if image.stem not in stems:
                continue
            label = COCO_DIR / "labels" / split_dir.name / f"{image.stem}.txt"
            if not label.exists():
                continue
            boxes = []
            for line in label.read_text(encoding="utf-8").splitlines():
                parts = line.split()
                if len(parts) != 5:
                    continue
                box = tuple(float(v) for v in parts[1:5])
                if valid_box(box):
                    boxes.append(box)
            if not boxes:
                continue
            sources["coco"].append((str(image), boxes, True))
            coco_used += 1

    # ---- 3) ssz5 水中塑料瓶抽样 ----
    ssz5_index: dict[str, Path] = {}
    for p in (SSZ5_DIR / "_images_tmp").rglob("*"):
        if p.suffix.lower() in (".bmp", ".jpg", ".png"):
            ssz5_index.setdefault(p.stem, p)
    xml_files = sorted((SSZ5_DIR / "_labels_tmp" / "labels").glob("*.xml"))
    random.shuffle(xml_files)
    ssz5_used = 0
    for xml_path in xml_files:
        if ssz5_used >= args.ssz5_limit:
            break
        image = ssz5_index.get(xml_path.stem)
        if not image:
            continue
        try:
            boxes = [
                (b.cx, b.cy, b.w, b.h)
                for b in parse_voc_xml(xml_path, ["bottle"])
                if valid_box((b.cx, b.cy, b.w, b.h))
            ]
        except Exception as exc:  # noqa: BLE001
            print(f"  ssz5 标注解析失败 {xml_path.name}: {exc}")
            continue
        if not boxes:
            continue
        sources["ssz5"].append((str(image), boxes, True))
        ssz5_used += 1

    # ---- 生成正样本条目（原图 + ROI 裁剪）----
    positives: list[tuple[str, list]] = []
    crop_jobs: list[tuple[Path, object]] = []
    for source, items in sources.items():
        for path, boxes, do_crop in items:
            positives.append((path, boxes))
            if do_crop:
                for cx, cy, w, h in sorted(boxes, key=lambda b: -b[3])[: args.max_crops]:
                    crop_jobs.append((Path(path), SimpleNamespace(cx=cx, cy=cy, w=w, h=h)))
        print(f"[{source}] 原图正样本 {len(items)}，ROI 计划 +{min(len(items) * args.max_crops, sum(len(i[1]) for i in items))}")

    crops: list[tuple[str, list]] = []
    tmp_dir = OUT_DIR / "images" / "_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    for index, (image, box) in enumerate(crop_jobs):
        out_path = tmp_dir / f"crop_{index:05d}.jpg"
        try:
            norm = crop_around(image, box, out_path)
        except Exception as exc:  # noqa: BLE001
            print(f"  裁剪失败 {image.name}: {exc}")
            continue
        if norm is None:
            out_path.unlink(missing_ok=True)
            continue
        crops.append((str(out_path), [norm]))

    # ---- 负样本：无瓶水面图 + 非瓶子容器 ----
    negatives: list[str] = []
    if NEGATIVE_DIR.exists():
        for split in ("train", "val", "test"):
            folder = NEGATIVE_DIR / split
            if folder.exists():
                negatives.extend(str(p) for p in sorted(folder.glob("*.jpg"))[:200])
    hard_dir = RAW_DIR / "coco-negatives" / "images" / "train2017"
    if hard_dir.exists():
        negatives.extend(str(p) for p in sorted(hard_dir.glob("*.jpg")))
    negatives = list(dict.fromkeys(negatives))
    random.shuffle(negatives)
    print(f"负样本 {len(negatives)} 张（无瓶水面 + 非瓶子容器）")

    # ---- 按比例划分 train/val（正负样本各切 15% 进 val，互不重叠）----
    all_pos = positives + crops
    random.shuffle(all_pos)
    val_pos = all_pos[: max(1, int(len(all_pos) * args.val_ratio))]
    train_pos = all_pos[len(val_pos):]
    neg_val = max(1, int(len(negatives) * args.val_ratio))
    buckets = {
        "train": train_pos + [(p, []) for p in negatives[neg_val:]],
        "val": val_pos + [(p, []) for p in negatives[:neg_val]],
    }

    counter = 0
    for split, items in buckets.items():
        for src, boxes in items:
            name = f"all_{split}_{counter:06d}.jpg"
            counter += 1
            copy_scaled(Path(src), OUT_DIR / "images" / split / name)
            lines = [f"0 {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}" for cx, cy, w, h in boxes]
            (OUT_DIR / "labels" / split / f"{Path(name).stem}.txt").write_text(
                "\n".join(lines) + ("\n" if lines else ""), encoding="utf-8"
            )
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)

    total_boxes = 0
    for split in ("train", "val"):
        count = len(list((OUT_DIR / "images" / split).glob("*.jpg")))
        pos = sum(1 for p in (OUT_DIR / "labels" / split).glob("*.txt") if p.read_text(encoding="utf-8").strip())
        boxes = sum(len([l for l in p.read_text(encoding="utf-8").splitlines() if l.strip()])
                    for p in (OUT_DIR / "labels" / split).glob("*.txt"))
        total_boxes += boxes
        print(f"[{split}] 图片 {count}（正 {pos} / 负 {count - pos}），框 {boxes}")

    (OUT_DIR / "data.yaml").write_text(
        f"# 通用塑料瓶检测数据集（{TARGET_CN}，河面/水中/室内）\n"
        f"path: {OUT_DIR.as_posix()}\n"
        "train: images/train\n"
        "val: images/val\n"
        "nc: 1\n"
        f"names: {{0: '{TARGET_CN}'}}\n",
        encoding="utf-8",
    )
    print(f"\n合计框 {total_boxes}，数据集: {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
