"""v7 训练：从 v6 best 继续微调，用人工精标紧框修正框回归。

关键设定（沿用 v6 成功配方）：
    - freeze=10 冻结骨干，只训检测头
    - lr0=0.001 低学习率，专修框的松紧而非重学特征
    - 50/50 均衡 + 精标样本过采样 ×16

用法：
    python scripts/train_handheld_v7.py
"""
from __future__ import annotations

from pathlib import Path

from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    model = YOLO(str(ROOT / "runs/detect/handheld-v6/weights/best.pt"))
    model.train(
        data=str(ROOT / "datasets/hybrid-v7/data.yaml"),
        epochs=15,
        imgsz=640,
        batch=16,
        freeze=10,
        lr0=0.001,
        lrf=0.1,
        patience=50,
        project=str(ROOT / "runs/detect"),
        name="handheld-v7",
        exist_ok=True,
        seed=2027,
        workers=0,
        verbose=True,
    )
    print("=== v7 训练结束 ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
