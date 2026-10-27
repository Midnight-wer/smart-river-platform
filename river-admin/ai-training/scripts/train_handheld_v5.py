"""v5：冻结骨干网络，只微调检测头——针对手持瓶响应被河面梯度淹没的问题。"""
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
        freeze=10,          # 冻结前 10 层骨干，只训检测头
        name="handheld-v5",
        exist_ok=True,
        patience=50,
        seed=2026,
    )


if __name__ == "__main__":
    train()
