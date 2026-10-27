"""通用塑料瓶模型全量评测（datasets/all 域 + 跨场景探针 + 框选完整性）。

评测项：
1. datasets/all 验证集：mAP50 / 精确率 / 召回率（Ultralytics val）
2. 框选完整性：验证集逐图「预测框 vs GT」平均 IoU、框高覆盖率
3. ssz5 留出探针：训练抽样之外的 30 张水中瓶，验证瓶身外观泛化
4. COCO 塑料瓶探针：19 张桌面/餐桌场景塑料瓶（非水面域）
5. 负样本探针：coco-negatives 全量非瓶子容器（699 张），应为 0 误报

达标判据（与用户要求对齐）：
    mAP50 >= 0.80，召回率 >= 0.85
    平均 IoU >= 0.70，框高覆盖 >= 85%（框选必须完整）
    ssz5 留出召回 >= 0.85，COCO 通用瓶召回 >= 0.60，负样本误报 = 0

用法：
    python scripts/eval_all_model.py --weights runs/detect/runs/plastic-bottle-all-v1/weights/best.pt
"""
from __future__ import annotations

import argparse
import random
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import RAW_DIR, ROOT, parse_voc_xml  # noqa: E402

ALL_DIR = ROOT / "datasets" / "all"
SSZ5_DIR = RAW_DIR / "ssz5-plastic-bottles-in-water"
COCO_DIR = RAW_DIR / "coco-bottles"
CURATE_STEMS_FILES = [
    ROOT / "datasets" / "reports" / "curate" / "selection.json",
    ROOT / "datasets" / "reports" / "curate-local" / "selection_plastic.json",
]
BUILD_SEED = 20261022
SSZ5_LIMIT = 250


def xywhn_to_xyxy(box: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    cx, cy, w, h = box
    return (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)


def iou(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def reconstruct_ssz5_split() -> tuple[list[str], list[str]]:
    """按 build_all_dataset.py 同种子复现抽样，返回 (已抽样stems, 留出stems)。"""
    index: dict[str, Path] = {}
    for p in (SSZ5_DIR / "_images_tmp").rglob("*"):
        if p.suffix.lower() in (".bmp", ".jpg", ".png"):
            index.setdefault(p.stem, p)
    xml_files = sorted((SSZ5_DIR / "_labels_tmp" / "labels").glob("*.xml"))
    rng = random.Random(BUILD_SEED)
    rng.shuffle(xml_files)
    sampled: list[str] = []
    holdout: list[str] = []
    for xml_path in xml_files:
        if xml_path.stem not in index:
            continue
        try:
            boxes = [
                b for b in parse_voc_xml(xml_path, ["bottle"])
                if 0.004 < b.w <= 1 and 0.004 < b.h <= 1
            ]
        except Exception:  # noqa: BLE001
            continue
        if not boxes:
            continue
        if len(sampled) < SSZ5_LIMIT:
            sampled.append(xml_path.stem)
        elif len(holdout) < 30:
            holdout.append(xml_path.stem)
        else:
            break
    return sampled, holdout


def predict_boxes(model, image: Path, conf: float) -> list[tuple[float, float, float, float]]:
    results = model.predict(source=str(image), conf=conf, verbose=False)
    out = []
    for result in results:
        for box in result.boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            w, h = result.orig_shape[1], result.orig_shape[0]
            out.append((x1 / w, y1 / h, x2 / w, y2 / h))
    return out


def probe_recall(model, images: list[Path], conf: float) -> tuple[float, int, int]:
    hit = 0
    for image in images:
        if predict_boxes(model, image, conf):
            hit += 1
    return (hit / len(images) if images else 0.0), hit, len(images)


def main() -> int:
    parser = argparse.ArgumentParser(description="通用塑料瓶模型评测")
    parser.add_argument("--weights", required=True)
    parser.add_argument("--conf", type=float, default=0.25)
    args = parser.parse_args()

    from ultralytics import YOLO

    model = YOLO(args.weights)
    print("=" * 60)
    print("1) datasets/all 验证集指标")
    metrics = model.val(data=str(ALL_DIR / "data.yaml"), imgsz=512, verbose=False)
    map50 = float(metrics.box.map50)
    precision = float(metrics.box.mp)
    recall = float(metrics.box.mr)
    print(f"   mAP50={map50:.3f}  mAP50-95={float(metrics.box.map):.3f}  P={precision:.3f}  R={recall:.3f}")

    print("2) 框选完整性（验证集正样本逐图）")
    val_images = sorted((ALL_DIR / "images" / "val").glob("*.jpg"))
    checked = 0
    ious: list[float] = []
    ratios: list[float] = []
    detected = 0
    for image in val_images:
        label = ALL_DIR / "labels" / "val" / f"{image.stem}.txt"
        if not label.exists() or not label.read_text(encoding="utf-8").strip():
            continue
        gt = []
        for line in label.read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if len(parts) == 5:
                gt.append(xywhn_to_xyxy(tuple(float(v) for v in parts[1:5])))
        if not gt:
            continue
        preds = predict_boxes(model, image, args.conf)
        best_iou, best_ratio = 0.0, 0.0
        for pred in preds:
            for g in gt:
                score = iou(pred, g)
                if score > best_iou:
                    best_iou = score
                    ph = pred[3] - pred[1]
                    gh = max(g[3] - g[1], 1e-6)
                    best_ratio = ph / gh
        if best_iou > 0.3:
            detected += 1
        ious.append(best_iou)
        ratios.append(best_ratio)
        checked += 1
    avg_iou = sum(ious) / checked if checked else 0.0
    avg_ratio = sum(ratios) / checked if checked else 0.0
    recall_img = detected / checked if checked else 0.0
    print(f"   含瓶图 {checked}：按图召回 {recall_img:.1%}，平均 IoU {avg_iou:.2f}，框高覆盖 {avg_ratio:.0%}")

    print("3) ssz5 留出探针（30 张训练未见的水中瓶）")
    _sampled, holdout = reconstruct_ssz5_split()
    holdout_paths = []
    index: dict[str, Path] = {}
    for p in (SSZ5_DIR / "_images_tmp").rglob("*"):
        if p.suffix.lower() in (".bmp", ".jpg", ".png"):
            index.setdefault(p.stem, p)
    for stem in holdout:
        if stem in index:
            holdout_paths.append(index[stem])
    rate_h, hit_h, total_h = probe_recall(model, holdout_paths, args.conf)
    print(f"   检出 {hit_h}/{total_h}（{rate_h:.0%}）")

    print("4) COCO 通用场景塑料瓶探针（桌面/餐桌）")
    stems: set[str] = set()
    import json
    for path in CURATE_STEMS_FILES:
        if path.exists():
            stems |= set(json.loads(path.read_text(encoding="utf-8")).get("stems") or [])
    coco_probe = [
        p for split in sorted(COCO_DIR.glob("images/*")) if split.is_dir()
        for p in sorted(split.glob("*.jpg")) if p.stem in stems
    ]
    rate_c, hit_c, total_c = probe_recall(model, coco_probe, args.conf)
    print(f"   检出 {hit_c}/{total_c}（{rate_c:.0%}）")

    print("5) 负样本探针（非瓶子容器，全量负样本库）")
    neg_dir = RAW_DIR / "coco-negatives" / "images" / "train2017"
    negatives = sorted(neg_dir.glob("*.jpg"))
    fp = sum(1 for image in negatives if predict_boxes(model, image, args.conf))
    print(f"   误报 {fp}/{len(negatives)}")

    print("=" * 60)
    gates = [
        ("mAP50 >= 0.80", map50 >= 0.80),
        ("召回率 >= 0.85", recall >= 0.85),
        ("平均 IoU >= 0.70", avg_iou >= 0.70),
        ("框高覆盖 >= 85%", avg_ratio >= 0.85),
        ("ssz5 留出召回 >= 0.85", rate_h >= 0.85),
        ("COCO 通用瓶召回 >= 0.60", rate_c >= 0.60),
        ("负样本误报 = 0", fp == 0),
    ]
    failed = [name for name, ok in gates if not ok]
    for name, ok in gates:
        print(f"   {'✓' if ok else '✗'} {name}")
    if failed:
        print(f"未达标 {len(failed)} 项: {'、'.join(failed)} —— 建议续训")
        return 1
    print("全部达标")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
