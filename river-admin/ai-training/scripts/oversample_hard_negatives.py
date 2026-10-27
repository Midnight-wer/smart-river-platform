"""把负样本误报图作为硬负样本过采样，加入 datasets/all 训练集。

扫描 coco-negatives 全量负样本，用当前最优模型以门禁阈值 conf=0.25 预测，
凡误报图片复制多份进 datasets/all/images/train（空标注），让续训重点压制
这些难例。用于 plastic-bottle-all-v2 补强续训。

用法：
    python scripts/oversample_hard_negatives.py --weights runs/detect/runs/plastic-bottle-all-v1/weights/best.pt
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEG_DIR = ROOT / "datasets" / "raw" / "coco-negatives" / "images" / "train2017"
TRAIN_IMG = ROOT / "datasets" / "all" / "images" / "train"
TRAIN_LBL = ROOT / "datasets" / "all" / "labels" / "train"


def main() -> int:
    parser = argparse.ArgumentParser(description="硬负样本过采样")
    parser.add_argument("--weights", required=True)
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--copies", type=int, default=20)
    args = parser.parse_args()

    from ultralytics import YOLO

    model = YOLO(args.weights)
    negatives = sorted(NEG_DIR.glob("*.jpg"))
    false_positives: list[Path] = []
    for image in negatives:
        results = model.predict(source=str(image), conf=args.conf, verbose=False)
        if any(len(r.boxes) for r in results):
            false_positives.append(image)
    print(f"负样本 {len(negatives)} 张，conf={args.conf} 误报 {len(false_positives)} 张")
    for image in false_positives:
        print(f"  误报: {image.name}")

    TRAIN_IMG.mkdir(parents=True, exist_ok=True)
    TRAIN_LBL.mkdir(parents=True, exist_ok=True)
    existing = len(list(TRAIN_IMG.glob("hardneg_*.jpg")))
    for index, image in enumerate(false_positives):
        for copy in range(args.copies):
            name = f"hardneg_{existing + index * args.copies + copy:04d}.jpg"
            shutil.copyfile(image, TRAIN_IMG / name)
            (TRAIN_LBL / f"{Path(name).stem}.txt").write_text("", encoding="utf-8")
    print(f"已过采样 {len(false_positives)} x {args.copies} -> {TRAIN_IMG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
