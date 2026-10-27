"""v6：手持/河面 50:50 均衡数据 + 冻结骨干，从 v3 best 训练。"""
from pathlib import Path

from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[1]


def train() -> None:
    model = YOLO(str(ROOT / "runs" / "detect" / "handheld-v3" / "weights" / "best.pt"))
    model.train(
        data=str(ROOT / "datasets" / "hybrid" / "data.yaml"),
        epochs=10,
        imgsz=640,
        lr0=0.001,
        lrf=0.1,
        batch=-1,
        workers=4,
        freeze=10,          # 冻结骨干，只训检测头
        name="handheld-v6",
        exist_ok=True,
        patience=50,
        seed=2026,
    )


if __name__ == "__main__":
    train()
