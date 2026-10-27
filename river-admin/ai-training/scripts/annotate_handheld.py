"""手持瓶样本预标注：用现有模型低阈值推理生成候选框，叠加到对照图供人工核对。

用法：
    python scripts/annotate_handheld.py            # 预标 + 生成叠加对照图
    python scripts/annotate_handheld.py --conf 0.005 --imgsz 640

产物：
    datasets/handheld-bottles/labels/raw_office_NNN.txt   YOLO 标签（待人工核对修正）
    datasets/handheld-bottles/reports/annotated_XX.jpg    叠加对照图（红=预标框）
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
IMG_DIR = ROOT / "datasets" / "handheld-bottles" / "images"
LBL_DIR = ROOT / "datasets" / "handheld-bottles" / "labels"
REP_DIR = ROOT / "datasets" / "handheld-bottles" / "reports"


def main() -> int:
    parser = argparse.ArgumentParser(description="手持瓶预标注")
    parser.add_argument("--conf", type=float, default=0.005)
    parser.add_argument("--imgsz", type=int, default=640)
    args = parser.parse_args()

    from ultralytics import YOLO
    model = YOLO(str(ROOT / "models" / "plastic-bottle-near.pt"))
    LBL_DIR.mkdir(parents=True, exist_ok=True)
    REP_DIR.mkdir(parents=True, exist_ok=True)

    images = sorted(IMG_DIR.glob("raw_*.jpg"))
    annotated: list[tuple[str, Image.Image]] = []
    stats = {"box": 0, "empty": 0}
    for image_path in images:
        result = model.predict(str(image_path), conf=args.conf, imgsz=args.imgsz, verbose=False)[0]
        best = None
        for b in result.boxes:
            conf = float(b.conf[0])
            if best is None or conf > best[0]:
                best = (conf, [float(v) for v in b.xyxy[0]])
        with Image.open(image_path) as im:
            rgb = im.convert("RGB")
        W, H = rgb.size
        label_path = LBL_DIR / f"{image_path.stem}.txt"
        if best is None:
            stats["empty"] += 1
            label_path.write_text("", encoding="utf-8")
        else:
            conf, (x1, y1, x2, y2) = best
            stats["box"] += 1
            cx, cy = (x1 + x2) / 2 / W, (y1 + y2) / 2 / H
            bw, bh = (x2 - x1) / W, (y2 - y1) / H
            label_path.write_text(f"0 {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n", encoding="utf-8")
            draw = ImageDraw.Draw(rgb)
            draw.rectangle([x1, y1, x2, y2], outline=(255, 40, 40), width=5)
            draw.text((x1, max(0, y1 - 26)), f"{conf:.2f}", fill=(255, 40, 40))
        rgb.thumbnail((560, 560), Image.LANCZOS)
        annotated.append((image_path.stem.split("_")[-1], rgb))

    try:
        font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 22)
    except Exception:  # noqa: BLE001
        font = ImageFont.load_default()
    cols, per, cell = 5, 25, 570
    for si in range(0, len(annotated), per):
        chunk = annotated[si:si + per]
        rows = (len(chunk) + cols - 1) // cols
        sheet = Image.new("RGB", (cell * cols, cell * rows), (18, 18, 18))
        draw = ImageDraw.Draw(sheet)
        for i, (tag, tile) in enumerate(chunk):
            x, y = (i % cols) * cell + 4, (i // cols) * cell + 4
            sheet.paste(tile, (x, y))
            draw.rectangle([x, y, x + 46, y + 30], fill=(0, 0, 0))
            draw.text((x + 6, y + 2), tag, fill=(255, 255, 0), font=font)
        out = REP_DIR / f"annotated_{si // per + 1:02d}.jpg"
        sheet.save(out, quality=85)
        print("生成", out)

    print(f"预标完成：{stats['box']} 张有框 / {stats['empty']} 张空（无瓶或漏检）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
