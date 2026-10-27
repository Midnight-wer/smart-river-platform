"""手持瓶专项评测：对 hybrid val 中的手持瓶样本计算召回 / IoU / 覆盖率 / 负样本误报。

用法：
    python scripts/eval_handheld.py --weights runs/detect/runs/xxx/weights/best.pt
门禁：召回 >= 0.85，平均 IoU >= 0.5，负样本误报 = 0
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VAL_IMG = ROOT / "datasets" / "hybrid" / "images" / "val"
VAL_LBL = ROOT / "datasets" / "hybrid" / "labels" / "val"


def iou(a, b) -> float:
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    aa = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    bb = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    return inter / (aa + bb - inter + 1e-9)


def main() -> int:
    parser = argparse.ArgumentParser(description="手持瓶专项评测")
    parser.add_argument("--weights", required=True)
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--min-recall", type=float, default=0.85)
    parser.add_argument("--min-iou", type=float, default=0.5)
    args = parser.parse_args()

    from ultralytics import YOLO
    model = YOLO(args.weights)

    images = sorted(VAL_IMG.glob("webcap_*.jpg")) + sorted(VAL_IMG.glob("raw_*.jpg"))
    if not images:
        print("✗ 未找到手持瓶 val 样本")
        return 2
    pos_hits = pos_total = 0
    ious, covers = [], []
    false_neg = 0
    from PIL import Image
    misses = []
    for img in images:
        lbl = VAL_LBL / f"{img.stem}.txt"
        with Image.open(img) as im:
            W, H = im.size
        # GT 由归一化坐标换算成像素，与 pred 同量纲
        gt = []
        for line in lbl.read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if len(parts) != 5:
                continue
            cx, cy, w, h = (float(v) for v in parts[1:5])
            gt.append(((cx - w / 2) * W, (cy - h / 2) * H,
                       (cx + w / 2) * W, (cy + h / 2) * H))
        result = model.predict(str(img), conf=args.conf, imgsz=640, verbose=False)[0]
        preds = [tuple(float(v) for v in b.xyxy[0]) for b in result.boxes]
        if not gt:
            if preds:
                false_neg += 1
            continue
        pos_total += 1
        # 最佳配对：所有 (pred, gt) 组合中 IoU 最高者
        pairs = [(iou(p, g), p, g) for p in preds for g in gt]
        best_iou, best_p, best_g = max(pairs, key=lambda t: t[0]) if pairs else (0.0, None, None)
        if best_iou >= 0.3:
            pos_hits += 1
            ious.append(best_iou)
            covers.append((best_p[3] - best_p[1]) / max(best_g[3] - best_g[1], 1e-9))
        else:
            misses.append(img.stem)

    recall = pos_hits / max(pos_total, 1)
    avg_iou = sum(ious) / max(len(ious), 1)
    avg_cover = sum(covers) / max(len(covers), 1)
    print(f"手持瓶正样本: {pos_hits}/{pos_total} 召回={recall:.3f}")
    print(f"平均 IoU={avg_iou:.3f}  框高覆盖={avg_cover:.3f}")
    print(f"负样本误报: {false_neg}")
    if misses:
        print("漏检:", ", ".join(misses))

    ok = recall >= args.min_recall and avg_iou >= args.min_iou and false_neg == 0
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
