"""自动化训练流水线：评估精准度 -> 不达标自动续训 -> 达标后导出 ONNX 并验证。

流程：
1. 等待当前训练进程结束，读取 runs/<name>/results.csv 的验证指标
   （mAP50 / precision / recall）；
2. 达标（默认 mAP50 >= 0.70 且 precision >= 0.70）则导出 ONNX 并结束；
3. 不达标则以 last.pt 为起点追加训练（epoch 累加），最多续训 max_rounds 轮；
4. 全部轮次仍不达标时以当前最优权重导出，报告未达标原因。

用法：
    python scripts/auto_train_pipeline.py
    python scripts/auto_train_pipeline.py --target-map50 0.8 --max-rounds 3
"""
from __future__ import annotations

import argparse
import csv
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN_NAME = "plastic-bottle-yolov8n-640"
RUNS_DIR = ROOT / "runs"
DATA_YAML = ROOT / "datasets" / "yolo" / "data.yaml"
BASE_EPOCHS = 30
IMGSZ = 640
BATCH = 20


def resolve_run_dir() -> Path:
    """探测实际训练输出目录（ultralytics 会按 project/task 嵌套）。"""
    candidates = [
        RUNS_DIR / RUN_NAME,
        RUNS_DIR / "detect" / "runs" / RUN_NAME,
        RUNS_DIR / RUN_NAME / "runs" / RUN_NAME,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def training_running() -> bool:
    """检测是否还有 yolo 训练进程在跑。"""
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
         "Where-Object { $_.CommandLine -match 'yolo' -and $_.CommandLine -match 'train' }) | Measure-Object | "
         "Select-Object -ExpandProperty Count"],
        capture_output=True, text=True, timeout=60,
    )
    try:
        return int(result.stdout.strip() or 0) > 0
    except ValueError:
        return False


def read_metrics(run_dir: Path) -> dict:
    """读取 results.csv 最后一行的验证指标。"""
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
            clean = key.strip()
            if clean.startswith(prefix):
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


def train(model: str, epochs: int, name: str) -> None:
    """启动一轮训练（阻塞直到结束）。"""
    cmd = [
        "yolo", "train",
        f"model={model}",
        f"data={DATA_YAML.as_posix()}",
        f"epochs={epochs}",
        f"imgsz={IMGSZ}",
        f"batch={BATCH}",
        "device=cpu",
        "workers=10",
        "patience=20",
        "close_mosaic=5",
        f"project={RUNS_DIR.as_posix()}",
        f"name={name}",
        "exist_ok=True",
    ]
    log(f"开始训练: {' '.join(cmd)}")
    subprocess.run(cmd, cwd=str(ROOT), check=False)
    log("训练进程结束")


def main() -> int:
    parser = argparse.ArgumentParser(description="自动训练与评估流水线")
    parser.add_argument("--target-map50", type=float, default=0.70)
    parser.add_argument("--target-precision", type=float, default=0.70)
    parser.add_argument("--max-rounds", type=int, default=3)
    parser.add_argument("--epochs", type=int, default=BASE_EPOCHS)
    args = parser.parse_args()

    run_dir = resolve_run_dir()
    weights = run_dir / "weights" / "best.pt"
    last_weights = run_dir / "weights" / "last.pt"

    # 1) 等待首轮训练结束
    if training_running():
        log("检测到训练进程，等待其结束 ...")
        while training_running():
            time.sleep(60)

    best_metrics: dict = {}
    for round_index in range(1, args.max_rounds + 1):
        run_dir = resolve_run_dir()
        weights = run_dir / "weights" / "best.pt"
        last_weights = run_dir / "weights" / "last.pt"
        metrics = read_metrics(run_dir)
        if not metrics:
            log("未找到 results.csv，无法评估")
            break
        best_metrics = metrics
        log(f"第 {round_index} 轮评估: epoch={metrics['epoch']} "
            f"mAP50={metrics['map50']:.3f} mAP50-95={metrics['map50_95']:.3f} "
            f"P={metrics['precision']:.3f} R={metrics['recall']:.3f}")
        if metrics["map50"] >= args.target_map50 and metrics["precision"] >= args.target_precision:
            log("已达到目标精度，结束训练")
            break
        if round_index >= args.max_rounds:
            log(f"已用满 {args.max_rounds} 轮仍未达标，使用当前最优权重")
            break
        if not last_weights.exists():
            log("!! 未找到 last.pt，无法续训")
            break
        # 续训：以 last.pt 为起点，epoch 累加
        next_epochs = args.epochs * (round_index + 1)
        log(f"未达标（mAP50 {metrics['map50']:.3f} / P {metrics['precision']:.3f}），"
            f"从 last.pt 续训至 {next_epochs} epoch")
        train(str(last_weights), next_epochs, RUN_NAME)

    # 2) 导出 ONNX
    if weights.exists():
        log("导出 ONNX ...")
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "export_onnx.py"), "--weights", str(weights)],
            cwd=str(ROOT), capture_output=True, text=True,
        )
        log(result.stdout[-800:] if result.stdout else result.stderr[-400:])
    else:
        log("!! 无 best.pt，跳过导出")

    # 3) 汇总
    log("最终指标: " + (str(best_metrics) if best_metrics else "无"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
