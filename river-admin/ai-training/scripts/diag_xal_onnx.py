"""诊断：X-AnyLabeling 自动标注结果全错。

同一批 webcap 图分别用 .pt（PyTorch）和 .onnx 推理，对比检测框：
- 两者一致且正确 → ONNX 没问题，问题在 X-AnyLabeling 的配置/预处理
- ONNX 异常（无框/乱框）→ ONNX 导出文件有问题，需重新导出
"""
from __future__ import annotations

from pathlib import Path

from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[1]
IMG_DIR = ROOT / "datasets" / "handheld-bottles" / "images" / "webcap"
N = 8  # 抽样张数

imgs = sorted(IMG_DIR.glob("*.jpg"))[:N]
if not imgs:
    raise SystemExit(f"未找到样本图: {IMG_DIR}")

pt = YOLO(str(ROOT / "models" / "plastic-bottle-near.pt"))
onnx = YOLO(str(ROOT / "models" / "plastic-bottle-near.onnx"))

for img in imgs:
    r1 = pt.predict(str(img), conf=0.15, imgsz=640, verbose=False)[0]
    r2 = onnx.predict(str(img), conf=0.15, imgsz=640, verbose=False)[0]
    b1 = [tuple(round(x) for x in b[:4]) + (round(float(b[4]), 3),) for b in r1.boxes.data.tolist()]
    b2 = [tuple(round(x) for x in b[:4]) + (round(float(b[4]), 3),) for b in r2.boxes.data.tolist()]
    print(f"{img.name}  ({img.stat().st_size // 1024}KB)")
    print(f"  PT  : {b1}")
    print(f"  ONNX: {b2}")
