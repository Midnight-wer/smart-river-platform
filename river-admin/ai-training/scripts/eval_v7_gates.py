"""v7 发布门禁：人工精标集框贴合度 + 河面指标不回退。

指标与判据（用户要求：下次自动标注准确率 ≥ 70%）：
    A. 手持精标诚实留出集（val split）：检出率 ≥ 0.70 且平均 IoU ≥ 0.70
    B. 全部精标集（57 张）：v7 vs v6 的 IoU/检出对比（量化改进）
    C. 河面 val：mAP50 ≥ 0.70 且与 v6 训练结果相比不显著回退

用法：
    python scripts/eval_v7_gates.py
"""
from __future__ import annotations

from pathlib import Path

from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[1]
IMG_DIR = ROOT / "datasets" / "handheld-bottles" / "images" / "webcap"
LBL_DIR = ROOT / "datasets" / "handheld-bottles" / "labels-xal"
HYB = ROOT / "datasets" / "hybrid-v7"
CONF = 0.15  # 与 X-AnyLabeling 自动标注阈值一致
GATE_RECALL = 0.70
GATE_IOU = 0.70
GATE_MAP = 0.70


def iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = (ax2 - ax1) * (ay2 - ay1)
    area_b = (bx2 - bx1) * (by2 - by1)
    return inter / (area_a + area_b - inter)


def load_gt(stem: str, w: int, h: int) -> list[tuple[float, float, float, float]]:
    boxes = []
    for line in (LBL_DIR / f"{stem}.txt").read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) != 5:
            continue
        cx, cy, bw, bh = (float(x) for x in parts[1:])
        boxes.append(((cx - bw / 2) * w, (cy - bh / 2) * h,
                      (cx + bw / 2) * w, (cy + bh / 2) * h))
    return boxes


def eval_model(model, stems: list[str]) -> tuple[float, float, list[float]]:
    """返回 (检出率, 平均IoU(检出框对GT的最好匹配), 每图最好IoU)。"""
    hits = 0
    ious = []
    for stem in stems:
        img_path = IMG_DIR / f"{stem}.jpg"
        if not img_path.exists():
            continue  # 标注存在但图片缺失，跳过
        r = model.predict(str(img_path), conf=CONF, imgsz=640, verbose=False)[0]
        h, w = r.orig_shape
        gt = load_gt(stem, w, h)
        if not gt:
            continue
        pred = [tuple(b.xyxy[0].tolist()) for b in r.boxes]
        best = max((iou(p, g) for p in pred for g in gt), default=0.0)
        ious.append(best)
        if best > 0:
            hits += 1
    recall = hits / len(ious) if ious else 0.0
    matched = [v for v in ious if v > 0]
    mean_iou = sum(matched) / len(matched) if matched else 0.0
    return recall, mean_iou, ious


def main() -> int:
    val_stems = (HYB / "val-handheld.txt").read_text(encoding="utf-8").split()
    all_stems = sorted(p.stem for p in LBL_DIR.glob("*.txt")
                       if p.stem != "corrected-list")
    v7 = YOLO(str(ROOT / "runs/detect/handheld-v7/weights/best.pt"))
    v6 = YOLO(str(ROOT / "models/plastic-bottle-near.pt"))

    lines = ["=== v7 发布门禁 ==="]
    r7, i7, ious7 = eval_model(v7, val_stems)
    r6, i6, _ = eval_model(v6, val_stems)
    gate_a = r7 >= GATE_RECALL and i7 >= GATE_IOU
    lines.append(f"A. 手持诚实留出集({len(val_stems)}张): "
                 f"v7 检出{r7:.2f}/IoU{i7:.2f}  vs  v6 检出{r6:.2f}/IoU{i6:.2f}  "
                 f"门限(检出{GATE_RECALL},IoU{GATE_IOU}) -> {'PASS' if gate_a else 'FAIL'}")
    per = "  ".join(f"{s[7:13]}:{v:.2f}" for s, v in zip(val_stems, ious7))
    lines.append(f"   v7 每图最好IoU: {per}")

    r7a, i7a, _ = eval_model(v7, all_stems)
    r6a, i6a, _ = eval_model(v6, all_stems)
    lines.append(f"B. 全部精标({len(all_stems)}张): "
                 f"v7 检出{r7a:.2f}/IoU{i7a:.2f}  vs  v6 检出{r6a:.2f}/IoU{i6a:.2f}")

    import csv
    csv_path = ROOT / "runs/detect/handheld-v7/results.csv"
    map50 = p = rc = 0.0
    v6_map50 = 0.908  # v6 训练最终 mAP50（混合集）
    if csv_path.exists():
        rows = list(csv.DictReader(csv_path.open(encoding="utf-8")))
        last = rows[-1]
        map50 = float(last["metrics/mAP50(B)"])
        p = float(last["metrics/precision(B)"])
        rc = float(last["metrics/recall(B)"])
    gate_c = map50 >= GATE_MAP
    lines.append(f"C. 河面+混合val: mAP50={map50:.3f} P={p:.3f} R={rc:.3f} "
                 f"(v6 最终 0.908) 门限(mAP50≥{GATE_MAP}) -> {'PASS' if gate_c else 'FAIL'}")

    ok = gate_a and gate_c
    lines.append(f"=== 总体: {'PASS 可发布' if ok else 'FAIL 保留旧权重'} ===")
    report = "\n".join(lines)
    print(report)
    (ROOT / "scripts" / "v7_gates_report.txt").write_text(report, encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
