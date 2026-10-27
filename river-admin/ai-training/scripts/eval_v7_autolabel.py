"""v7 自动标注合格判定：用部署生效的 ONNX 权重跑全量 webcap 图，与人工精标框对比。

判定口径：
    A. 人工精标集（用户修正过的图）：检出率、平均 IoU、框面积比（贴近 1 说明框更贴合）
    B. 全量 139 张：检出张数、漏检清单、框质量统计
"""
from __future__ import annotations

import datetime
import json
import statistics
from pathlib import Path

from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "datasets" / "handheld-bottles" / "images" / "webcap"
BACKUP = ROOT / "datasets" / "handheld-bottles" / "json-backup-before-v7"
ONNX = ROOT / "models" / "plastic-bottle-near.onnx"
CUTOFF = datetime.datetime(2026, 10, 23, 16, 54, 45).timestamp()
CONF = 0.15


def iou(a, b):
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


def main() -> int:
    model = YOLO(str(ONNX))
    files = sorted(WEB.glob("*.json"))
    edited, auto = [], []
    for f in files:
        (edited if f.stat().st_mtime > CUTOFF else auto).append(f)
    print(f"ONNX: {ONNX.name}  人工精标 {len(edited)} 张 / 自动标注 {len(auto)} 张")
    print("-" * 74)
    print(f"{'图片':<26}{'人工框':>7}{'v7框':>6}{'IoU':>7}{'面积比':>8}{'置信度':>8}")
    print("-" * 74)
    ious, ratios, hits, n_gt = [], [], 0, 0
    miss = []
    for jf in edited:
        gt_json = json.loads((BACKUP / jf.name).read_text(encoding="utf-8"))
        img_path = WEB / gt_json["imagePath"]
        W, H = gt_json["imageWidth"], gt_json["imageHeight"]
        gts = []
        for s in gt_json["shapes"]:
            xs = [p[0] for p in s["points"]]
            ys = [p[1] for p in s["points"]]
            gts.append((min(xs), min(ys), max(xs), max(ys)))
        r = model.predict(str(img_path), conf=CONF, imgsz=640, verbose=False)[0]
        preds = [tuple(b.xyxy[0].tolist()) + (float(b.conf[0]),) for b in r.boxes]
        n_gt += len(gts)
        if not preds:
            miss.append(jf.stem)
            print(f"{jf.stem:<26}{len(gts):>7}{0:>6}{'--':>7}{'--':>8}{'--':>8}")
            continue
        best_iou, best_ratio, best_conf = 0.0, 0.0, 0.0
        for g in gts:
            for p in preds:
                v = iou(p[:4], g)
                if v > best_iou:
                    best_iou = v
                    best_conf = p[4]
                    ga = (g[2] - g[0]) * (g[3] - g[1])
                    pa = (p[2] - p[0]) * (p[3] - p[1])
                    best_ratio = pa / ga if ga > 0 else 0.0
        if best_iou > 0:
            hits += 1
            ious.append(best_iou)
            ratios.append(best_ratio)
        print(f"{jf.stem:<26}{len(gts):>7}{len(preds):>6}{best_iou:>7.2f}{best_ratio:>8.2f}{best_conf:>8.2f}")
    print("-" * 74)
    recall = hits / len(edited) if edited else 0
    mean_iou = statistics.mean(ious) if ious else 0
    med_iou = statistics.median(ious) if ious else 0
    mean_ratio = statistics.mean(ratios) if ratios else 0
    print(f"人工精标集({len(edited)}张): 检出率 {recall:.3f} | 平均IoU {mean_iou:.3f} | 中位IoU {med_iou:.3f}")
    print(f"框面积比(v7框面积/人工框面积) 均值 {mean_ratio:.2f}（1.0=完全贴合，>1.3=偏松，<0.8=偏紧）")
    if miss:
        print(f"漏检: {miss}")
    # 全量统计
    total = 0
    det = 0
    confs = []
    for jf in files:
        gj = json.loads((BACKUP / jf.name).read_text(encoding="utf-8"))
        r = model.predict(str(WEB / gj["imagePath"]), conf=CONF, imgsz=640, verbose=False)[0]
        total += 1
        if len(r.boxes):
            det += 1
            confs.extend(float(b.conf[0]) for b in r.boxes)
    print(f"全量 {total} 张: 检出 {det} 张 ({det / total:.1%})，平均置信度 {statistics.mean(confs):.3f}")
    ok = recall >= 0.70 and mean_iou >= 0.70
    print("=" * 74)
    print(f"自动标注合格判定: {'合格（检出率与框贴合度均达 70%）' if ok else '不合格'}")
    print("=" * 74)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
