"""标注错位诊断：核查原始数据集的「图片 <-> 标注」是否对齐。

检查项：
1. 图片与标注配对率（缺标注 / 缺图片 / 标注为空）；
2. XML 中声明的图片尺寸与真实图片尺寸是否一致（0、999 等占位值单独统计）；
3. 框是否越界（像素框超出图片、归一化框超出 0-1）；
4. 框面积分布（识别过小/异常框）；
5. 非目标类别分布（塑料袋/垃圾等）；
6. 渲染抽样叠加图，供人工肉眼核对框是否真的框在瓶子上；
7. 校验已转换的 YOLO 数据集（datasets/yolo）标签与图片是否一一对应、坐标是否合法。

用法：
    python scripts/diag_alignment.py
    python scripts/diag_alignment.py --dataset m0n-plastic-bottles --samples 12
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
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
    read_image_size,
)

REPORT_DIR = ROOT / "datasets" / "reports" / "alignment"


def render_overlay(image: Path, boxes, out_path: Path, declared: tuple[int, int], actual: tuple[int, int],
                   max_edge: int = 900) -> None:
    """把归一化框画到图片上，输出 jpg 供人工核对。

    归一化框按「标注声明尺寸」换算成像素，再按实际图片尺寸缩放绘制：
    若声明尺寸与真实尺寸不同，可以直观看出框是否随之错位。
    """
    from PIL import Image, ImageDraw

    with Image.open(image) as im:
        im = im.convert("RGB")
        scale = min(1.0, max_edge / max(im.size))
        if scale < 1.0:
            im = im.resize((int(im.width * scale), int(im.height * scale)))
        draw = ImageDraw.Draw(im)
        for box in boxes:
            dw, dh = declared if declared[0] and declared[1] else actual
            # 归一化框 -> 声明尺寸像素 -> 实际图片像素（两套尺寸不同即可暴露错位）
            x1 = (box.cx - box.w / 2) * dw / actual[0] * im.width
            y1 = (box.cy - box.h / 2) * dh / actual[1] * im.height
            x2 = (box.cx + box.w / 2) * dw / actual[0] * im.width
            y2 = (box.cy + box.h / 2) * dh / actual[1] * im.height
            draw.rectangle([x1, y1, x2, y2], outline=(255, 0, 0), width=3)
            draw.text((max(0, x1 + 2), max(0, y1 + 2)), box.cls_name, fill=(255, 255, 0))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        im.save(out_path, quality=88)


def diagnose_raw(dataset_dir: Path, aliases: set[str], samples: int) -> dict:
    """诊断原始数据集：配对、尺寸一致性、框合法性，并抽样渲染。"""
    stats = {
        "dataset": dataset_dir.name,
        "pairs": 0,
        "images_without_label": 0,
        "empty_labels": 0,
        "declared_size_match": 0,
        "declared_size_zero": 0,
        "declared_size_999": 0,
        "declared_size_other": 0,
        "boxes_total": 0,
        "boxes_plastic": 0,
        "boxes_out_of_image_px": 0,
        "boxes_out_of_range_norm": 0,
        "boxes_tiny": 0,
        "box_areas": [],
        "non_target_classes": Counter(),
        "sample_renders": [],
    }

    # 统计无标注图片（iter_pairs 只产出成对样本）
    labeled_stems = set()
    unlabeled = 0
    for image in dataset_dir.rglob("*"):
        if image.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        if image.with_suffix(".xml").exists() or image.with_suffix(".txt").exists():
            labeled_stems.add(image.stem)
        else:
            unlabeled += 1
    stats["images_without_label"] = unlabeled

    positive_samples: list[tuple[Path, list, tuple[int, int], tuple[int, int]]] = []

    for image, label, class_names in iter_pairs(dataset_dir):
        stats["pairs"] += 1
        boxes = parse_voc_xml(label, class_names) if label.suffix.lower() == ".xml" else []
        actual = read_image_size(image)
        declared = (boxes[0].width, boxes[0].height) if boxes else (0, 0)

        if declared[0] and declared[1]:
            if declared == actual:
                stats["declared_size_match"] += 1
            elif declared[0] in (0, 999) or declared[1] in (0, 999):
                stats["declared_size_999"] += 1
            else:
                stats["declared_size_other"] += 1
        else:
            stats["declared_size_zero"] += 1

        plastic_boxes = []
        for box in boxes:
            stats["boxes_total"] += 1
            if is_plastic_bottle(box.cls_name, aliases):
                stats["boxes_plastic"] += 1
                plastic_boxes.append(box)
            else:
                stats["non_target_classes"][box.cls_name] += 1
            # 越界检查（按声明尺寸换算回像素）
            if declared[0] and declared[1]:
                x2 = (box.cx + box.w / 2) * declared[0]
                y2 = (box.cy + box.h / 2) * declared[1]
                if box.cx - box.w / 2 < -0.01 or box.cy - box.h / 2 < -0.01 or x2 > declared[0] * 1.01 or y2 > declared[1] * 1.01:
                    stats["boxes_out_of_image_px"] += 1
            if not (-0.01 <= box.cx <= 1.01 and -0.01 <= box.cy <= 1.01
                    and 0 < box.w <= 1.01 and 0 < box.h <= 1.01):
                stats["boxes_out_of_range_norm"] += 1
            if box.w * box.h < 0.0005:
                stats["boxes_tiny"] += 1
            if is_plastic_bottle(box.cls_name, aliases):
                stats["box_areas"].append(round(box.w * box.h * 100, 4))

        if not boxes:
            stats["empty_labels"] += 1
        if plastic_boxes:
            positive_samples.append((image, plastic_boxes, declared, actual))

    try:
        from PIL import Image  # noqa: F401
        render_ok = True
    except ImportError:
        render_ok = False

    if render_ok and samples > 0 and positive_samples:
        step = max(1, len(positive_samples) // samples)
        picked = positive_samples[::step][:samples]
        out_dir = REPORT_DIR / dataset_dir.name
        for image, boxes, declared, actual in picked:
            out_path = out_dir / f"{image.stem}_overlay.jpg"
            try:
                render_overlay(image, boxes, out_path, declared, actual)
                stats["sample_renders"].append(str(out_path))
            except Exception as exc:  # 渲染失败不影响诊断结论
                stats["sample_renders"].append(f"渲染失败 {image.name}: {exc}")

    areas = stats.pop("box_areas")
    if areas:
        stats["box_area_percent"] = {
            "min": min(areas),
            "median": round(statistics.median(areas), 4),
            "max": max(areas),
        }
    stats["non_target_classes"] = dict(stats["non_target_classes"].most_common(10))
    return stats


def diagnose_yolo(yolo_dir: Path) -> dict:
    """校验生成的 YOLO 数据集：图片/标签配对、坐标合法性、框数量。"""
    result = {"root": str(yolo_dir), "splits": {}, "problems": []}
    if not yolo_dir.exists():
        result["problems"].append("YOLO 数据集目录不存在")
        return result

    for split in ("train", "val", "test"):
        img_dir = yolo_dir / "images" / split
        lbl_dir = yolo_dir / "labels" / split
        if not img_dir.exists():
            continue
        images = {p.stem for p in img_dir.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES}
        labels = {p.stem for p in lbl_dir.glob("*.txt")} if lbl_dir.exists() else set()
        boxes = 0
        empty = 0
        invalid = 0
        aspect = []
        for label in (lbl_dir.glob("*.txt") if lbl_dir.exists() else []):
            lines = [ln for ln in label.read_text(encoding="utf-8", errors="ignore").splitlines() if ln.strip()]
            if not lines:
                empty += 1
            for line in lines:
                parts = line.split()
                if len(parts) != 5:
                    invalid += 1
                    continue
                try:
                    values = [float(v) for v in parts[1:]]
                except ValueError:
                    invalid += 1
                    continue
                boxes += 1
                cx, cy, w, h = values
                if not (0 <= cx <= 1 and 0 <= cy <= 1 and 0 < w <= 1 and 0 < h <= 1):
                    invalid += 1
                if w > 0 and h > 0:
                    aspect.append(round(h / w, 2))
        result["splits"][split] = {
            "images": len(images),
            "labels": len(labels),
            "positive": len(labels) - empty,
            "negative": empty,
            "boxes": boxes,
            "invalid_lines": invalid,
            "missing_labels": len(images - labels),
            "orphan_labels": len(labels - images),
            "box_hw_ratio_median": round(statistics.median(aspect), 2) if aspect else 0,
        }
        if images - labels:
            result["problems"].append(f"{split}: {len(images - labels)} 张图片缺标签")
        if labels - images:
            result["problems"].append(f"{split}: {len(labels - images)} 个标签缺图片")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="标注错位诊断")
    parser.add_argument("--dataset", default="m0n-plastic-bottles", help="原始数据集目录名（datasets/raw 下）")
    parser.add_argument("--samples", type=int, default=12, help="抽样渲染数量")
    args = parser.parse_args()

    dataset_dir = RAW_DIR / args.dataset
    if not dataset_dir.exists():
        print(f"!! 数据集目录不存在: {dataset_dir}")
        return 1

    label_db = load_label_db()
    aliases = alias_set(label_db)

    print(f"== 原始数据集诊断: {dataset_dir}")
    raw = diagnose_raw(dataset_dir, aliases, args.samples)
    print(f"配对样本 {raw['pairs']}，无标注图片 {raw['images_without_label']}，空标注 {raw['empty_labels']}")
    print(f"尺寸一致 {raw['declared_size_match']}｜声明为 0 {raw['declared_size_zero']}｜"
          f"声明为 999 {raw['declared_size_999']}｜其他不一致 {raw['declared_size_other']}")
    print(f"框 {raw['boxes_total']}（塑料瓶 {raw['boxes_plastic']}）：越界(像素) {raw['boxes_out_of_image_px']}，"
          f"越界(归一化) {raw['boxes_out_of_range_norm']}，过小 {raw['boxes_tiny']}")
    print(f"面积百分比分布: {raw.get('box_area_percent')}")
    print(f"非目标类别: {raw['non_target_classes']}")
    print(f"抽样叠加图: {len(raw['sample_renders'])} 张 -> {REPORT_DIR / args.dataset}")

    print("\n== YOLO 数据集校验: datasets/yolo")
    yolo = diagnose_yolo(ROOT / "datasets" / "yolo")
    for split, info in yolo["splits"].items():
        print(f"[{split}] 图片 {info['images']} 标签 {info['labels']}（正 {info['positive']} / 负 {info['negative']}），"
              f"框 {info['boxes']}，非法行 {info['invalid_lines']}，裸图 {info['missing_labels']}，"
              f"无图标签 {info['orphan_labels']}，高宽比中位 {info['box_hw_ratio_median']}")
    if yolo["problems"]:
        print("问题: " + "；".join(yolo["problems"]))

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / f"{args.dataset}-report.json"
    report_path.write_text(
        json.dumps({"raw": raw, "yolo": yolo}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n报告已写入: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
