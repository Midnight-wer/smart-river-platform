"""深度诊断：v6 训练集手持样本是否真的被学到。
1) train 集手持图（含过采样副本）直接 predict 看响应
2) 对应标签文件内容校验
3) results.csv 的召回走势
"""
from pathlib import Path

from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[1]
TR = ROOT / "datasets" / "hybrid" / "images" / "train"
TL = ROOT / "datasets" / "hybrid" / "labels" / "train"

print("=== 1. train 集手持图响应（训练应见过） ===")
m = YOLO(str(ROOT / "runs" / "detect" / "handheld-v6" / "weights" / "last.pt"))
samples = sorted(TR.glob("webcap_*.jpg"))[:3] + [p for p in sorted(TR.glob("webcap_*__dup3.jpg"))[:2]]
for p in samples:
    r = m.predict(str(p), conf=0.01, imgsz=640, verbose=False)[0]
    tops = sorted((round(float(b.conf), 3) for b in r.boxes), reverse=True)[:2]
    print(f"  {p.stem[:34]}: {len(r.boxes)} 个 {tops}")

print("=== 2. 标签内容校验 ===")
bad = 0
for lbl in sorted(TL.glob("webcap_*.txt"))[:200]:
    txt = lbl.read_text(encoding="utf-8").strip()
    if not txt:
        print(f"  空: {lbl.name}")
        bad += 1
        continue
    for line in txt.splitlines():
        parts = line.split()
        if len(parts) != 5:
            print(f"  格式错: {lbl.name}: {line}")
            bad += 1
            break
        vals = [float(v) for v in parts[1:5]]
        if any(v < 0 or v > 1 for v in vals):
            print(f"  越界: {lbl.name}: {line}")
            bad += 1
            break
print(f"  抽查 200 个，异常 {bad}")

print("=== 3. 图像-标签数量对齐 ===")
imgs = list(TR.glob("*.jpg"))
lbls = list(TL.glob("*.txt"))
print(f"  图像 {len(imgs)}，标签 {len(lbls)}")
missing = [p for p in imgs if not (TL / f"{p.stem}.txt").exists()][:5]
if missing:
    print(f"  缺标签样例: {[p.name for p in missing]}")

print("=== 4. results.csv 召回走势 ===")
csv = ROOT / "runs" / "detect" / "handheld-v6" / "results.csv"
if csv.exists():
    for line in csv.read_text(encoding="utf-8").strip().splitlines()[1:]:
        c = line.split(",")
        print(f"  epoch{c[0]}: R={float(c[6]):.3f} mAP50={float(c[7]):.3f}")
