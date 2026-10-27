"""把清洗后的数据整理为 YOLO 标准数据集结构（train/val 划分 + data.yaml）。

输入：datasets/processed/<dataset>/（images/ labels/ manifest.json）
输出：datasets/yolo/
        images/train, images/val
        labels/train, labels/val
        data.yaml

单一类别：塑料瓶（class 0）。

用法：
    python scripts/prepare_yolo_dataset.py --dataset ssz5-plastic-bottles-in-water --val-ratio 0.15
"""
from __future__ import annotations

import argparse
import json
import random
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATASETS_DIR, PROCESSED_DIR, load_label_db  # noqa: E402

YOLO_DIR = DATASETS_DIR / "yolo"


def main() -> int:
    parser = argparse.ArgumentParser(description="准备 YOLO 训练数据集")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--val-ratio", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    label_db = load_label_db()
    target_cn = label_db["target_cn"]
    source = PROCESSED_DIR / args.dataset
    manifest_path = source / "manifest.json"
    if not manifest_path.exists():
        print(f"未找到清洗结果: {manifest_path}")
        return 1

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    random.seed(args.seed)

    # 以目录实际内容为准扫描（便于额外补充负样本等），manifest 仅作参考
    scanned: list[dict] = []
    for split_dir in sorted((source / "images").iterdir()):
        if not split_dir.is_dir():
            continue
        for image in sorted(split_dir.rglob("*")):
            if image.suffix.lower() not in (".jpg", ".jpeg", ".png"):
                continue
            label = source / "labels" / split_dir.name / (image.stem + ".txt")
            has_boxes = label.exists() and bool(label.read_text(encoding="utf-8").strip())
            scanned.append({
                "image": f"images/{split_dir.name}/{image.name}",
                "label": f"labels/{split_dir.name}/{label.name}",
                "boxes": has_boxes,
            })
    if scanned:
        manifest = scanned
        print(f"扫描目录得到 {len(manifest)} 个样本（以磁盘内容为准）")

    # 正负样本分层划分，避免验证集缺少负样本
    positives = [m for m in manifest if m["boxes"]]
    negatives = [m for m in manifest if not m["boxes"]]
    random.shuffle(positives)
    random.shuffle(negatives)
    val_count = max(1, int(len(positives) * args.val_ratio))
    val_neg = max(1, int(len(negatives) * args.val_ratio))
    val_set = positives[:val_count] + negatives[:val_neg]
    train_set = positives[val_count:] + negatives[val_neg:]
    random.shuffle(train_set)
    random.shuffle(val_set)

    if YOLO_DIR.exists():
        shutil.rmtree(YOLO_DIR)
    for split in ("train", "val"):
        (YOLO_DIR / "images" / split).mkdir(parents=True, exist_ok=True)
        (YOLO_DIR / "labels" / split).mkdir(parents=True, exist_ok=True)

    for split, items in (("train", train_set), ("val", val_set)):
        for item in items:
            src_image = source / item["image"]
            src_label = source / item["label"]
            if not src_image.exists() or not src_label.exists():
                continue
            name = Path(item["image"]).name
            shutil.copyfile(src_image, YOLO_DIR / "images" / split / name)
            shutil.copyfile(src_label, YOLO_DIR / "labels" / split / (Path(name).stem + ".txt"))

    data_yaml = YOLO_DIR / "data.yaml"
    data_yaml.write_text(
        f"# 河道塑料瓶检测数据集（{target_cn}）\n"
        f"path: {YOLO_DIR.as_posix()}\n"
        "train: images/train\n"
        "val: images/val\n"
        f"nc: 1\n"
        f"names: {{0: '{target_cn}'}}\n",
        encoding="utf-8",
    )

    print(f"训练集 {len(train_set)} 张（正 {len(positives) - val_count} / 负 {len(negatives) - val_neg}）")
    print(f"验证集 {len(val_set)} 张（正 {val_count} / 负 {val_neg}）")
    print(f"类别: 1 类 —— {target_cn}")
    print(f"输出目录: {YOLO_DIR}")
    print(f"配置文件: {data_yaml}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
