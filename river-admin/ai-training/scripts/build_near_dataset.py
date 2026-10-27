"""构建「近景塑料瓶」专用数据集。

背景：通用数据集里 52% 的标注是远景小瓶（框高 <1% 占图高），模型把容量都花在
学小目标上，近景瓶反而认不出。本脚本只保留近景目标，并额外裁剪 ROI 放大样本，
让模型专注「近景瓶子」这一件事。

产物：datasets/near/{images,labels}/{train,val} + data.yaml
    - 原图样本：含近景瓶的原图，标签只保留近景框（丢掉远景小框，避免混淆）
    - ROI 样本：围绕近景瓶的放大裁剪，补充不同背景、不同距离的近景视角
    - 负样本：无瓶图片 + 只有远景小瓶的图片（让模型不把远处小点当成近景瓶）

用法：
    python scripts/build_near_dataset.py
    python scripts/build_near_dataset.py --near-height 0.05 --max-crops 2
"""
from __future__ import annotations

import argparse
import json
import random
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    IMAGE_SUFFIXES,
    RAW_DIR,
    ROOT,
    alias_set,
    is_plastic_bottle,
    iter_pairs,
    load_label_db,
    parse_voc_xml,
)

OUT_DIR = ROOT / "datasets" / "near"
NEGATIVE_DIR = ROOT / "datasets" / "processed" / "ssz5-plastic-bottles-in-water" / "images"
TARGET_CN = "塑料瓶"


def crop_around(image: Path, box, out_path: Path, min_edge: int = 320, max_edge: int = 1280, pad: float = 0.8):
    """以近景瓶为中心裁剪一块区域，放大瓶子占比；返回裁剪后的归一化框。"""
    from PIL import Image

    with Image.open(image) as im:
        W, H = im.size
        cx, cy = box.cx * W, box.cy * H
        bw, bh = box.w * W, box.h * H
        half_w = max(bw * (1 + pad) / 2, min_edge / 2)
        half_h = max(bh * (1 + pad) / 2, min_edge / 2)
        side = min(max(half_w, half_h) * 2, max_edge)
        left = min(max(cx - side / 2, 0), max(W - side, 0))
        top = min(max(cy - side / 2, 0), max(H - side, 0))
        right = min(left + side, W)
        bottom = min(top + side, H)
        crop = im.convert("RGB").crop((int(left), int(top), int(right), int(bottom)))
        crop.save(out_path, quality=92)

        cw, ch = crop.size
        nx = ((cx - left) / cw)
        ny = ((cy - top) / ch)
        nw = (bw / cw)
        nh = (bh / ch)
    if not (0 <= nx <= 1 and 0 <= ny <= 1 and 0 < nw <= 1 and 0 < nh <= 1):
        return None
    return nx, ny, nw, nh


def copy_scaled(src: Path, dst: Path, max_edge: int = 1400) -> None:
    """拷贝图片，超大图按最长边缩放（训练输入只有 512，原图 4000px 只会拖慢 IO）。"""
    from PIL import Image

    with Image.open(src) as im:
        im = im.convert("RGB")
        if max(im.size) > max_edge:
            scale = max_edge / max(im.size)
            im = im.resize((int(im.width * scale), int(im.height * scale)), Image.LANCZOS)
        im.save(dst, quality=90)


def main() -> int:
    parser = argparse.ArgumentParser(description="构建近景塑料瓶数据集")
    parser.add_argument("--near-height", type=float, default=0.03, help="近景判定：框高占图高比例下限")
    parser.add_argument("--max-crops", type=int, default=2, help="每张图最多裁剪几个 ROI 样本")
    parser.add_argument("--negatives", type=int, default=400, help="负样本数量上限")
    parser.add_argument("--include-tiny-negatives", action="store_true",
                        help="把「只有远景小瓶」的图也当负样本（会与真实语义冲突，默认关闭）")
    parser.add_argument("--val-ratio", type=float, default=0.15)
    parser.add_argument("--coco", action="store_true", help="合并 COCO 近景瓶子样本")
    parser.add_argument("--coco-selection", default="",
                        help="人工筛选结果 json：只有其中的图片当正样本，其余瓶子图转负样本")
    parser.add_argument("--hard-negatives", action="store_true",
                        help="并入玻璃杯/花瓶/马克杯/碗等「非瓶子容器」作为负样本")
    parser.add_argument("--seed", type=int, default=20261022)
    args = parser.parse_args()

    random.seed(args.seed)
    aliases = alias_set(load_label_db())

    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    for split in ("train", "val"):
        (OUT_DIR / "images" / split).mkdir(parents=True, exist_ok=True)
        (OUT_DIR / "labels" / split).mkdir(parents=True, exist_ok=True)

    samples: list[tuple[str, list]] = []   # (图片路径, [(cx,cy,w,h)...])
    crop_jobs: list[tuple[Path, object]] = []
    tiny_only = 0

    for image, label, names in iter_pairs(RAW_DIR / "m0n-plastic-bottles"):
        boxes = [b for b in parse_voc_xml(label, names) if is_plastic_bottle(b.cls_name, aliases)]
        if not boxes:
            continue
        near = [b for b in boxes if b.h >= args.near_height]
        if not near:
            tiny_only += 1
            continue
        samples.append((str(image), [(b.cx, b.cy, b.w, b.h) for b in near]))
        for box in sorted(near, key=lambda b: -b.h)[: args.max_crops]:
            crop_jobs.append((image, box))

    print(f"原图近景样本 {len(samples)} 张（仅远景小瓶而被排除的图片 {tiny_only} 张）")
    print(f"ROI 裁剪计划 {len(crop_jobs)} 个")

    # 生成 ROI 裁剪样本
    crops: list[tuple[str, list]] = []
    for index, (image, box) in enumerate(crop_jobs):
        out_path = OUT_DIR / "images" / "_tmp" / f"crop_{index:05d}.jpg"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            norm = crop_around(image, box, out_path)
        except Exception as exc:  # noqa: BLE001
            print(f"  裁剪失败 {image.name}: {exc}")
            continue
        if norm is None:
            out_path.unlink(missing_ok=True)
            continue
        crops.append((str(out_path), [norm]))

    # COCO 近景样本：只有人工核对为 PET 塑料瓶的图当正样本，
    # 其余瓶子图（玻璃瓶/啤酒瓶/番茄酱瓶等）转为负样本，避免模型把非目标当瓶子。
    coco_positives = 0
    coco_negatives: list[str] = []
    coco_dir = ROOT / "datasets" / "raw" / "coco-bottles"
    selected_stems: set[str] = set()
    if args.coco_selection:
        selection = json.loads(Path(args.coco_selection).read_text(encoding="utf-8"))
        selected_stems = set(selection.get("stems") or [f"{i:012d}" for i in selection.get("image_ids", [])])
        print(f"COCO 人工筛选：保留 {len(selected_stems)} 张 PET 瓶，其余转负样本")
    if args.coco and coco_dir.exists():
        for split_dir in sorted((coco_dir / "images").glob("*")):
            if not split_dir.is_dir():
                continue
            for image in sorted(split_dir.glob("*.jpg")):
                label = coco_dir / "labels" / split_dir.name / f"{image.stem}.txt"
                if not label.exists():
                    continue
                boxes = []
                for line in label.read_text(encoding="utf-8").splitlines():
                    parts = line.split()
                    if len(parts) != 5:
                        continue
                    boxes.append(tuple(float(v) for v in parts[1:5]))
                if not boxes:
                    continue
                if selected_stems and image.stem not in selected_stems:
                    # 未通过人工筛选的 COCO 瓶子图直接剔除：其中不少本身是 PET 瓶，
                    # 当负样本会造成矛盾标注；非瓶子容器已单独抓取为负样本
                    continue
                samples.append((str(image), boxes))
                coco_positives += 1
        print(f"COCO 正样本 {coco_positives} 张（未通过筛选的瓶子图已剔除）")

    # 负样本：只用「确实没有任何瓶子」的图片
    # 注意：仅含远景小瓶的图片不能当负样本 —— 那些图里真有瓶子，
    # 当成负样本会让模型既学不会近景瓶、又被强行压制小目标，验证集分类损失会爆掉。
    negatives: list[str] = list(coco_negatives)
    if NEGATIVE_DIR.exists():
        for split in ("train", "val", "test"):
            folder = NEGATIVE_DIR / split
            if folder.exists():
                negatives.extend(str(p) for p in sorted(folder.glob("*.jpg"))[:200])
    hard_dir = ROOT / "datasets" / "raw" / "coco-negatives" / "images" / "train2017"
    if args.hard_negatives and hard_dir.exists():
        hard = sorted(hard_dir.glob("*.jpg"))
        negatives.extend(str(p) for p in hard)
        print(f"非瓶子负样本 {len(hard)} 张已并入")
    if args.include_tiny_negatives:
        tiny_images = []
        for image, label, names in iter_pairs(RAW_DIR / "m0n-plastic-bottles"):
            boxes = [b for b in parse_voc_xml(label, names) if is_plastic_bottle(b.cls_name, aliases)]
            if boxes and all(b.h < args.near_height for b in boxes):
                tiny_images.append(str(image))
        negatives.extend(tiny_images[: args.negatives])
    negatives = list(dict.fromkeys(negatives))  # 去重，避免同一个文件重复进入数据集
    random.shuffle(negatives)
    print(f"负样本 {len(negatives)} 张（均为无瓶图 / 非瓶子容器）")

    # 划分 train/val
    positives = samples + crops
    negatives = [(path, []) for path in negatives]
    random.shuffle(positives)
    random.shuffle(negatives)
    val_pos = max(1, int(len(positives) * args.val_ratio))
    val_neg = max(1, int(len(negatives) * args.val_ratio))
    buckets = {
        "train": positives[val_pos:] + negatives[val_neg:],
        "val": positives[:val_pos] + negatives[:val_neg],
    }

    counter = 0
    for split, items in buckets.items():
        for item in items:
            src = Path(item[0])
            boxes = item[1]
            name = f"near_{split}_{counter:06d}.jpg"
            counter += 1
            dst_image = OUT_DIR / "images" / split / name
            copy_scaled(src, dst_image)
            lines = [f"0 {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}" for cx, cy, w, h in boxes]
            (OUT_DIR / "labels" / split / f"{Path(name).stem}.txt").write_text(
                "\n".join(lines) + ("\n" if lines else ""), encoding="utf-8"
            )
        # 清理临时裁剪目录
    tmp_dir = OUT_DIR / "images" / "_tmp"
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

    data_yaml = OUT_DIR / "data.yaml"
    data_yaml.write_text(
        f"# 近景塑料瓶检测数据集（{TARGET_CN}）\n"
        f"path: {OUT_DIR.as_posix()}\n"
        "train: images/train\n"
        "val: images/val\n"
        f"nc: 1\n"
        f"names: {{0: '{TARGET_CN}'}}\n",
        encoding="utf-8",
    )
    print(f"\n合计框 {total_boxes}，数据集: {OUT_DIR}")
    print(f"配置文件: {data_yaml}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
