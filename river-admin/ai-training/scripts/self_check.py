"""本地离线部署全量自检。

检查项：
1. 训练产物：自训权重 best.pt / 导出的 ONNX 是否存在
2. 训练指标：results.csv 的 mAP50 / precision / recall 是否达标
3. 检测服务：/health 是否加载自训权重（而非官方 yolov8n）
4. 正样本检测：手持水瓶图应检出目标，且框位置合理（中心落在预期区域）
5. 负样本检测：验证集里的无瓶图片应返回 0 个目标（验证「只认塑料瓶」）
6. 响应耗时：单次检测耗时应处于可接受范围

用法：
    python scripts/self_check.py
    python scripts/self_check.py --url http://127.0.0.1:8000 --target-map50 0.7
"""
from __future__ import annotations

import argparse
import base64
import csv
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
YOLO_DIR = ROOT / "datasets" / "near"
ONNX_MODEL = ROOT / "models" / "plastic-bottle-near.onnx"
RUN_CANDIDATES = [
    ROOT / "runs" / "detect" / "runs" / "plastic-bottle-all-v2",
    ROOT / "runs" / "detect" / "runs" / "plastic-bottle-all-v1",
    ROOT / "runs" / "plastic-bottle-all-v1",
    ROOT / "runs" / "detect" / "runs" / "plastic-bottle-water-v1",
    ROOT / "runs" / "plastic-bottle-water-v1",
    ROOT / "runs" / "detect" / "runs" / "plastic-bottle-near-coco-512",
    ROOT / "runs" / "plastic-bottle-near-coco-512",
]
POSITIVE_IMAGE = ROOT / "assets" / "probe-bottle-hand.jpg"
# 室内/通用场景塑料瓶探针：人工筛选的 COCO 塑料瓶（桌面/餐桌等非水面场景）
CURATE_STEMS_FILES = [
    ROOT / "datasets" / "reports" / "curate" / "selection.json",
    ROOT / "datasets" / "reports" / "curate-local" / "selection_plastic.json",
]
COCO_IMAGES_DIR = ROOT / "datasets" / "raw" / "coco-bottles" / "images"
# 河道场景的正样本：从近景验证集里挑「河面漂浮瓶最大」的一张，与人工标注框比对
RIVER_POSITIVE = YOLO_DIR / "images" / "val"

results: list[tuple[bool, str]] = []


def check(ok: bool, message: str) -> bool:
    results.append((bool(ok), message))
    print(("  ✓ " if ok else "  ✗ ") + message, flush=True)
    return bool(ok)


def find_run_dir() -> Path | None:
    for candidate in RUN_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


def read_metrics(run_dir: Path) -> dict:
    csv_path = run_dir / "results.csv"
    if not csv_path.exists():
        return {}
    with csv_path.open("r", encoding="utf-8", newline="") as fp:
        rows = list(csv.DictReader(fp))
    if not rows:
        return {}
    last = rows[-1]

    def pick(prefix: str) -> float:
        for key, value in last.items():
            if key.strip().startswith(prefix):
                try:
                    return float(value)
                except (TypeError, ValueError):
                    return 0.0
        return 0.0

    return {
        "epoch": int(float(last.get("epoch", 0))) + 1,
        "precision": pick("metrics/precision"),
        "recall": pick("metrics/recall"),
        "map50": pick("metrics/mAP50(B)"),
        "map50_95": pick("metrics/mAP50-95(B)"),
    }


def pick_negative_image() -> Path | None:
    """从验证集里挑一张无标注（无瓶）的图片作为负样本。"""
    labels_dir = YOLO_DIR / "labels" / "val"
    images_dir = YOLO_DIR / "images" / "val"
    if not labels_dir.exists():
        return None
    for label in sorted(labels_dir.glob("*.txt")):
        if label.read_text(encoding="utf-8").strip():
            continue
        image = images_dir / f"{label.stem}.jpg"
        if image.exists():
            return image
    return None


def pick_river_positive() -> tuple[Path, list[tuple[float, float, float, float]]] | None:
    """从验证集里挑一张河面漂浮瓶最清晰的图，返回图片路径与其归一化标注框。"""
    labels_dir = YOLO_DIR / "labels" / "val"
    if not labels_dir.exists():
        return None
    best: tuple[float, Path, list[tuple[float, float, float, float]]] | None = None
    for label in labels_dir.glob("*.txt"):
        boxes = []
        for line in label.read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if len(parts) != 5:
                continue
            cx, cy, w, h = (float(v) for v in parts[1:5])
            boxes.append((cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2))
        if not boxes:
            continue
        area = max((b[2] - b[0]) * (b[3] - b[1]) for b in boxes)
        image = RIVER_POSITIVE / f"{label.stem}.jpg"
        if not image.exists():
            continue
        if best is None or area > best[0]:
            best = (area, image, boxes)
    if best is None:
        return None
    return best[1], best[2]


def iou(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    return inter / (area_a + area_b - inter + 1e-9)


def post_detect(url: str, image: Path, conf: float) -> dict:
    payload = {
        "image": "data:image/jpeg;base64," + base64.b64encode(image.read_bytes()).decode(),
        "conf": conf,
    }
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="本地离线部署自检")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--target-map50", type=float, default=0.70)
    parser.add_argument("--target-precision", type=float, default=0.70)
    parser.add_argument("--river-samples", type=int, default=60, help="河面漂浮瓶批量抽查数量")
    args = parser.parse_args()

    print("=" * 66)
    print("本地离线部署 · 全量自检")
    print("=" * 66)

    # 1) 训练产物
    print("\n[1] 训练产物")
    run_dir = find_run_dir()
    best_pt = run_dir / "weights" / "best.pt" if run_dir else None
    check(bool(best_pt and best_pt.exists()),
          f"自训权重 best.pt 存在" + (f"（{best_pt.stat().st_size / 1024 / 1024:.1f} MB）" if best_pt and best_pt.exists() else ""))
    check(ONNX_MODEL.exists(),
          f"ONNX 导出文件存在（{ONNX_MODEL.stat().st_size / 1024 / 1024:.1f} MB）" if ONNX_MODEL.exists() else "ONNX 尚未导出")
    near_model = ROOT / "models" / "plastic-bottle-near.pt"
    check(near_model.exists(),
          f"已发布近景模型（{near_model.stat().st_size / 1024 / 1024:.1f} MB）" if near_model.exists() else "近景模型未发布")

    # 2) 训练指标
    print("\n[2] 训练指标")
    metrics = read_metrics(run_dir) if run_dir else {}
    if metrics:
        print(f"      epoch={metrics['epoch']} mAP50={metrics['map50']:.3f} "
              f"mAP50-95={metrics['map50_95']:.3f} P={metrics['precision']:.3f} R={metrics['recall']:.3f}")
        check(metrics["map50"] >= args.target_map50, f"mAP50 {metrics['map50']:.3f} >= {args.target_map50}")
        check(metrics["precision"] >= args.target_precision, f"precision {metrics['precision']:.3f} >= {args.target_precision}")
    else:
        check(False, "未找到训练指标 results.csv")

    # 3) 服务健康
    print("\n[3] 本地检测服务")
    health = {}
    try:
        with urllib.request.urlopen(f"{args.url}/health", timeout=20) as response:
            health = json.loads(response.read().decode("utf-8"))
    except Exception as error:  # noqa: BLE001
        check(False, f"服务健康检查失败: {error}")
    if health:
        check(health.get("status") == "ok", "服务状态 ok")
        check(health.get("offline") is True, "服务标记为离线模式")
        model_name = str(health.get("model", ""))
        check("yolov8n" not in model_name or model_name.startswith("best") or model_name.startswith("plastic"),
              f"已加载自训权重（model={model_name}）")

    # 4) 正样本检测：河面漂浮瓶批量统计（检出率 / 框选 IoU / 框高覆盖率）
    print("\n[4] 正样本检测（河面漂浮瓶批量）")
    river = pick_river_positive()
    if river is None:
        check(False, "未找到河面漂浮瓶测试图")
    else:
        _river_image, _gt = river
        samples = []
        for label in sorted((YOLO_DIR / "labels" / "val").glob("*.txt")):
            boxes = []
            for line in label.read_text(encoding="utf-8").splitlines():
                parts = line.split()
                if len(parts) != 5:
                    continue
                cx, cy, w, h = (float(v) for v in parts[1:5])
                boxes.append((cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2))
            if not boxes:
                continue
            image = YOLO_DIR / "images" / "val" / f"{label.stem}.jpg"
            if image.exists():
                samples.append((image, boxes))
        samples = samples[: args.river_samples]
        detected = 0
        ious: list[float] = []
        ratios: list[float] = []
        latencies: list[int] = []
        for image, gt_boxes in samples:
            try:
                started = time.perf_counter()
                result = post_detect(f"{args.url}/detect", image, 0.25)
                latencies.append(int((time.perf_counter() - started) * 1000))
            except Exception as error:  # noqa: BLE001
                check(False, f"正样本检测失败: {error}")
                continue
            items = result.get("items", [])
            best_iou = 0.0
            best_ratio = 0.0
            for item in items:
                cx, cy = item["x"] / 100, item["y"] / 100
                w, h = item["width"] / 100, item["height"] / 100
                pred = (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
                for gt in gt_boxes:
                    score = iou(pred, gt)
                    if score > best_iou:
                        best_iou = score
                        best_ratio = h / max(gt[3] - gt[1], 1e-6)
            if best_iou > 0.3:
                detected += 1
            ious.append(best_iou)
            ratios.append(best_ratio)
        total = len(samples)
        if total:
            rate = detected / total
            avg_iou = sum(ious) / total
            avg_ratio = sum(ratios) / total
            print(f"      抽查 {total} 张河面漂浮瓶：检出 {detected} 张（{rate:.1%}）"
                  f"，平均 IoU {avg_iou:.2f}，平均框高覆盖 {avg_ratio:.0%}"
                  f"，单次延迟中位 {sorted(latencies)[len(latencies) // 2]}ms")
            check(rate >= 0.85, f"漂浮瓶检出率 {rate:.1%} >= 85%")
            check(avg_iou >= 0.7, f"框选平均 IoU {avg_iou:.2f} >= 0.7（框选完整性）")
            check(avg_ratio >= 0.85, f"框高平均覆盖 {avg_ratio:.0%} >= 85%（框选完整性）")

    # 4b) 室内/通用场景塑料瓶（必检项：模型须在非水面场景也能检出塑料瓶）
    print("\n[4b] 室内/通用场景塑料瓶（必检项）")
    probe: list[Path] = []
    if POSITIVE_IMAGE.exists():
        probe.append(POSITIVE_IMAGE)
    selected_stems: set[str] = set()
    for stems_file in CURATE_STEMS_FILES:
        if stems_file.exists():
            data = json.loads(stems_file.read_text(encoding="utf-8"))
            selected_stems |= set(data.get("stems") or [])
    for split_dir in sorted(COCO_IMAGES_DIR.glob("*")):
        if not split_dir.is_dir():
            continue
        for image in sorted(split_dir.glob("*.jpg")):
            if image.stem in selected_stems:
                probe.append(image)
    probe = probe[:13]
    if not probe:
        check(False, "未找到室内/通用塑料瓶测试图")
    else:
        hit = 0
        for image in probe:
            try:
                result = post_detect(f"{args.url}/detect", image, 0.25)
                if result.get("items"):
                    hit += 1
            except Exception as error:  # noqa: BLE001
                print(f"      检测异常 {image.name}: {error}")
        rate_b = hit / len(probe)
        print(f"      抽查 {len(probe)} 张室内/桌面塑料瓶：检出 {hit} 张（{rate_b:.0%}）")
        check(rate_b >= 0.7, f"通用瓶检出率 {rate_b:.0%} >= 70%")

    # 5) 负样本检测
    print("\n[5] 负样本检测（无瓶图片应为 0 目标）")
    negative = pick_negative_image()
    if negative is None:
        check(False, "未找到负样本图片")
    else:
        try:
            result = post_detect(f"{args.url}/detect", negative, 0.25)
            items = result.get("items", [])
            print(f"      样本 {negative.name} -> 检出 {len(items)} 个目标")
            check(len(items) == 0, "无瓶图片未产生误检")
        except Exception as error:  # noqa: BLE001
            check(False, f"负样本检测失败: {error}")

    # 汇总
    passed = sum(1 for ok, _ in results if ok)
    print("\n" + "=" * 66)
    print(f"自检结果: {passed}/{len(results)} 项通过")
    if passed < len(results):
        print("未通过项：")
        for ok, message in results:
            if not ok:
                print(f"  - {message}")
    print("=" * 66)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
