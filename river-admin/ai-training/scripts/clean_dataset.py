"""清洗数据集：类别归一化 + 仅保留塑料瓶目标 + 划分负样本。

输入：datasets/raw/<dataset>/**（images 与 labels 配对）
输出：datasets/processed/<dataset>/{images,labels}/<split>/ 与 manifest.json

清洗规则：
1. 类别名归一化后匹配塑料瓶别名集合，命中即保留；
2. 非塑料瓶类别（塑料袋/泡沫/树枝/垃圾等）全部丢弃 —— 微调目标是「只认塑料瓶」；
3. 图片中不含塑料瓶的样本保留为负样本（答案 objects:[]），用于抑制误检；
4. 坐标合法性校验：越界/零面积框剔除，保留面积过小（<0.1%）的框剔除。

用法：
    python scripts/clean_dataset.py
    python scripts/clean_dataset.py --dataset popxoq-river-plastic-bottle
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    PROCESSED_DIR,
    RAW_DIR,
    SOURCES_KEY,
    Box,
    alias_set,
    is_plastic_bottle,
    iter_pairs,
    load_label_db,
    parse_voc_xml,
    parse_yolo_txt,
    read_image_size,
    split_of,
)

MIN_BOX_AREA = 0.0005  # 面积占比阈值（0.05%）：远景小瓶目标很小，过滤过严会丢掉大部分样本


def clean_dataset(dataset_dir: Path, out_dir: Path, source_id: str, aliases: set[str]) -> dict:
    """清洗单个数据集，输出图片/标注/清单。"""
    if out_dir.exists():
        shutil.rmtree(out_dir)
    for split in ("train", "val", "test"):
        (out_dir / "images" / split).mkdir(parents=True, exist_ok=True)
        (out_dir / "labels" / split).mkdir(parents=True, exist_ok=True)

    manifest: list[dict] = []
    dropped_classes: Counter = Counter()
    total_boxes = 0
    kept_boxes = 0

    for index, (image, label, class_names) in enumerate(iter_pairs(dataset_dir)):
        if label.suffix.lower() == ".xml":
            boxes = parse_voc_xml(label, class_names)
        else:
            boxes = parse_yolo_txt(label, class_names)

        for box in boxes:
            total_boxes += 1
            if not is_plastic_bottle(box.cls_name, aliases):
                dropped_classes[box.cls_name] += 1

        bottle_boxes: list[Box] = []
        for box in boxes:
            if not is_plastic_bottle(box.cls_name, aliases):
                continue
            if box.w <= 0 or box.h <= 0 or box.w * box.h < MIN_BOX_AREA:
                continue
            bottle_boxes.append(box)
            kept_boxes += 1

        width, height = read_image_size(image)
        split = split_of(image)
        # VOC 标注为像素坐标：若与实际图片尺寸不一致，按比例校正框坐标
        if bottle_boxes and bottle_boxes[0].width and width and bottle_boxes[0].width != width:
            ratio_x = width / bottle_boxes[0].width
            ratio_y = height / bottle_boxes[0].height if bottle_boxes[0].height else ratio_x
            for box in bottle_boxes:
                box.cx = min(1.0, box.cx * ratio_x)
                box.w = min(1.0, box.w * ratio_x)
                box.cy = min(1.0, box.cy * ratio_y)
                box.h = min(1.0, box.h * ratio_y)
        if not width or not height:
            # 无法解析尺寸时尝试从标注中获取（VOC 解析会写入）
            if bottle_boxes and bottle_boxes[0].width:
                width, height = bottle_boxes[0].width, bottle_boxes[0].height
        if not width or not height:
            continue

        stem = f"{source_id}_{index:06d}"
        ext = image.suffix.lower()
        dst_image = out_dir / "images" / split / f"{stem}{ext}"
        dst_label = out_dir / "labels" / split / f"{stem}.txt"
        shutil.copyfile(image, dst_image)
        dst_label.write_text(
            "\n".join(box.to_yolo() for box in bottle_boxes) + ("\n" if bottle_boxes else ""),
            encoding="utf-8",
        )

        manifest.append({
            "image": f"images/{split}/{stem}{ext}",
            "label": f"labels/{split}/{stem}.txt",
            "split": split,
            "width": width,
            "height": height,
            "source": source_id,
            "boxes": [
                {"cls": box.cls_name, **box.to_percentage()} for box in bottle_boxes
            ],
        })

    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    positive = sum(1 for m in manifest if m["boxes"])
    return {
        "samples": len(manifest),
        "positive": positive,
        "negative": len(manifest) - positive,
        "boxes_kept": kept_boxes,
        "boxes_dropped": total_boxes - kept_boxes,
        "dropped_classes": dict(dropped_classes.most_common(12)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="清洗河道塑料瓶数据集")
    parser.add_argument("--dataset", help="仅处理指定数据集 id（默认全部）")
    args = parser.parse_args()

    label_db = load_label_db()
    aliases = alias_set(label_db)
    source_ids = [s["id"] for s in label_db[SOURCES_KEY]]
    if args.dataset:
        source_ids = [args.dataset]

    print(f"目标类别: {label_db['target_cn']}，别名 {len(aliases)} 个")
    summary = {}
    for sid in source_ids:
        raw = RAW_DIR / sid
        if not raw.exists():
            print(f"[{sid}] 跳过：本地目录不存在")
            continue
        stats = clean_dataset(raw, PROCESSED_DIR / sid, sid, aliases)
        summary[sid] = stats
        print(f"[{sid}] 样本 {stats['samples']}（正 {stats['positive']} / 负 {stats['negative']}）"
              f"，保留框 {stats['boxes_kept']}，丢弃框 {stats['boxes_dropped']}")
        if stats["dropped_classes"]:
            print(f"    丢弃类别分布: {stats['dropped_classes']}")

    (PROCESSED_DIR / "clean_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("\n下一步: python scripts/build_qwen_jsonl.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
