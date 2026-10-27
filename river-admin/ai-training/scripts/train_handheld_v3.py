"""手持瓶专项微调训练（v3）：从已发布 v1 权重在 hybrid 数据集上低学习率微调。

训练目录 runs/detect/handheld-v3。Windows 多进程 dataloader 需要 __main__ 守卫。
"""
from pathlib import Path

from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[1]


def train() -> None:
    model = YOLO(str(ROOT / "models" / "plastic-bottle-near.pt"))
    model.train(
        data=str(ROOT / "datasets" / "hybrid" / "data.yaml"),
        epochs=10,
        imgsz=640,
        lr0=0.001,
        lrf=0.01,
        batch=-1,
        workers=4,
        name="handheld-v3",
        exist_ok=True,
        patience=50,
        seed=2026,
    )


if __name__ == "__main__":
    train()
