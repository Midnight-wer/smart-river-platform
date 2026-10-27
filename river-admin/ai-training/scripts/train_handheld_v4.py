"""v4 强化训练：手持样本过采样 + 更高学习率，从 v3 best 继续加码。"""
from pathlib import Path

from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[1]


def train() -> None:
    model = YOLO(str(ROOT / "runs" / "detect" / "handheld-v3" / "weights" / "best.pt"))
    model.train(
        data=str(ROOT / "datasets" / "hybrid" / "data.yaml"),
        epochs=15,
        imgsz=640,
        lr0=0.002,
        lrf=0.05,
        batch=-1,
        workers=4,
        name="handheld-v4",
        exist_ok=True,
        patience=50,
        seed=2026,
    )


if __name__ == "__main__":
    train()
