"""v3 断点续训：从 last.pt（epoch 7）恢复训练。"""
from pathlib import Path

from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[1]

model = YOLO(str(ROOT / "runs" / "detect" / "handheld-v3" / "weights" / "last.pt"))
model.train(resume=True)
