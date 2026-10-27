"""测 conf=0.15 时负样本误报量（全量 699 张）——决定部署阈值是否可降。"""
import sys
from pathlib import Path

from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[1]
m = YOLO(str(ROOT / "runs" / "detect" / "handheld-v6" / "weights" / "best.pt"))
neg_dir = ROOT / "datasets" / "all" / "images" / "val"
lbl_dir = ROOT / "datasets" / "all" / "labels" / "val"
conf = float(sys.argv[1]) if len(sys.argv) > 1 else 0.15
fps = 0
total = 0
for lbl in sorted(lbl_dir.glob("*.txt")):
    if lbl.read_text(encoding="utf-8").strip():
        continue  # 只测负样本
    img = neg_dir / f"{lbl.stem}.jpg"
    if not img.exists():
        continue
    total += 1
    r = m.predict(str(img), conf=conf, imgsz=640, verbose=False)[0]
    if r.boxes:
        fps += 1
print(f"conf={conf}: 负样本误报 {fps}/{total}")
