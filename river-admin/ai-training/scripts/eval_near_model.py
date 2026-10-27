"""近景塑料瓶模型评测：验证集指标 + 真实近景图实测。

用法：
    python scripts/eval_near_model.py --weights runs/plastic-bottle-near-coco-512/weights/best.pt
"""
from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEAR_DIR = ROOT / "datasets" / "near"
HAND_IMAGE = ROOT / "assets" / "probe-bottle-hand.jpg"


def main() -> int:
    parser = argparse.ArgumentParser(description="近景模型评测")
    parser.add_argument("--weights", required=True)
    parser.add_argument("--imgsz", type=int, default=512)
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--negatives", type=int, default=30, help="非瓶子负样本抽查数量")
    args = parser.parse_args()

    from ultralytics import YOLO

    model = YOLO(args.weights)

    print("=" * 60)
    print("1) 近景验证集指标")
    metrics = model.val(data=str(NEAR_DIR / "data.yaml"), imgsz=args.imgsz, verbose=False)
    print(f"   mAP50={metrics.box.map50:.3f}  mAP50-95={metrics.box.map:.3f}  "
          f"P={metrics.box.mp:.3f}  R={metrics.box.mr:.3f}")

    print("\n2) 逐图召回（验证集，最多 60 张）")
    images = sorted((NEAR_DIR / "images" / "val").glob("*.jpg"))[:60]
    hit = miss = 0
    gt_total = 0
    for image in images:
        label = NEAR_DIR / "labels" / "val" / f"{image.stem}.txt"
        gt = [l for l in label.read_text(encoding="utf-8").splitlines() if l.strip()] if label.exists() else []
        if not gt:
            continue
        gt_total += len(gt)
        result = model.predict(str(image), conf=args.conf, imgsz=args.imgsz, verbose=False)[0]
        if len(result.boxes):
            hit += 1
        else:
            miss += 1
    if hit + miss:
        print(f"   含瓶图 {hit + miss} 张：检出 {hit}，漏检 {miss}，按图召回 {hit / (hit + miss):.2f}（GT 实例 {gt_total}）")

    print("\n3) 真实近景图（手持矿泉水瓶）")
    if HAND_IMAGE.exists():
        result = model.predict(str(HAND_IMAGE), conf=0.01, imgsz=args.imgsz, verbose=False)[0]
        print(f"   候选框 {len(result.boxes)} 个")
        for box in result.boxes[:6]:
            x1, y1, x2, y2 = [float(v) for v in box.xyxy[0]]
            h, w = result.orig_shape
            print(f"     conf={float(box.conf[0]):.3f} "
                  f"中心=({(x1 + x2) / 2 / w * 100:.1f}%,{(y1 + y2) / 2 / h * 100:.1f}%) "
                  f"尺寸={((x2 - x1) / w * 100):.1f}%x{((y2 - y1) / h * 100):.1f}%")
        strong = [b for b in result.boxes if float(b.conf[0]) >= args.conf]
        print(f"   conf>={args.conf} 命中 {len(strong)} 个")
    else:
        print(f"   缺少 {HAND_IMAGE}")
    print("\n4) 非瓶子容器误报抽查（玻璃杯/花瓶/马克杯/碗）")
    neg_dir = ROOT / "datasets" / "raw" / "coco-negatives" / "images" / "train2017"
    if neg_dir.exists():
        samples = sorted(neg_dir.glob("*.jpg"))[: args.negatives]
        false_positive = 0
        for image in samples:
            result = model.predict(str(image), conf=args.conf, imgsz=args.imgsz, verbose=False)[0]
            if len(result.boxes):
                false_positive += 1
        print(f"   抽查 {len(samples)} 张，误报 {false_positive} 张，"
              f"误报率 {false_positive / max(len(samples), 1) * 100:.1f}%")
    else:
        print(f"   缺少负样本目录: {neg_dir}")

    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
