"""对本地 coco-bottles 已下载图做「塑料瓶候选」筛选并生成编号对照图。

与 curate_coco_bottles.py（联网下载候选）不同，本脚本完全离线：
直接扫描 datasets/raw/coco-bottles/{images,labels}，按「最大瓶框高度占比」
过滤出近景候选，生成带编号的 contact-sheet 供人工/视觉模型勾选塑料瓶。

产物：
    datasets/reports/curate-local/candidates.json   候选清单（no -> stems/框）
    datasets/reports/curate-local/sheet_NN.jpg      对照图（每张 24 格）

用法：
    python scripts/curate_local_bottles.py --min-height 0.12
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
COCO_DIR = ROOT / "datasets" / "raw" / "coco-bottles"
OUT_DIR = ROOT / "datasets" / "reports" / "curate-local"


def main() -> int:
    parser = argparse.ArgumentParser(description="本地 COCO 瓶子候选筛选")
    parser.add_argument("--min-height", type=float, default=0.12,
                        help="瓶框高度占图高比例下限（近景才值得进训练集）")
    parser.add_argument("--limit", type=int, default=720, help="候选数量上限")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    pool: list[dict] = []
    for split_dir in sorted((COCO_DIR / "images").glob("*")):
        if not split_dir.is_dir():
            continue
        for image in sorted(split_dir.glob("*.jpg")):
            label = COCO_DIR / "labels" / split_dir.name / f"{image.stem}.txt"
            if not label.exists():
                continue
            boxes = []
            for line in label.read_text(encoding="utf-8").splitlines():
                parts = line.split()
                if len(parts) != 5:
                    continue
                cx, cy, w, h = (float(v) for v in parts[1:5])
                if 0 < w <= 1 and 0 < h <= 1:
                    boxes.append((cx, cy, w, h))
            if not boxes:
                continue
            best_h = max(b[3] for b in boxes)
            if best_h >= args.min_height:
                pool.append({
                    "stem": image.stem,
                    "split": split_dir.name,
                    "file": str(image),
                    "boxes": boxes,
                    "best_h": round(best_h, 4),
                })

    pool.sort(key=lambda item: -item["best_h"])
    pool = pool[: args.limit]
    print(f"候选 {len(pool)} 张（瓶高 ≥ {args.min_height:.0%}），生成对照图 ...")

    (OUT_DIR / "candidates.json").write_text(
        json.dumps([
            {"no": i + 1, "stem": p["stem"], "split": p["split"],
             "file": p["file"], "boxes": p["boxes"]}
            for i, p in enumerate(pool)
        ], ensure_ascii=False, indent=1),
        encoding="utf-8",
    )

    cell, cols, per_sheet = 320, 6, 24
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 26)
    except Exception:  # noqa: BLE001
        font = ImageFont.load_default()

    tiles = []
    for i, item in enumerate(pool):
        try:
            with Image.open(item["file"]) as im:
                tile = im.convert("RGB")
        except Exception as exc:  # noqa: BLE001
            print(f"  读取失败 {item['file']}: {exc}")
            continue
        tile.thumbnail((300, 300), Image.LANCZOS)
        tiles.append((i + 1, tile))

    for start in range(0, len(tiles), per_sheet):
        chunk = tiles[start:start + per_sheet]
        rows = (len(chunk) + cols - 1) // cols
        sheet = Image.new("RGB", (cell * cols, cell * rows), (18, 18, 18))
        draw = ImageDraw.Draw(sheet)
        for position, (number, tile) in enumerate(chunk):
            x = (position % cols) * cell + 8
            y = (position // cols) * cell + 8
            sheet.paste(tile, (x, y))
            draw.rectangle([x, y, x + 56, y + 34], fill=(0, 0, 0))
            draw.text((x + 8, y + 3), str(number), fill=(255, 255, 0), font=font)
        sheet_path = OUT_DIR / f"sheet_{start // per_sheet + 1:02d}.jpg"
        sheet.save(sheet_path, quality=88)

    print(f"共 {len(tiles)} 候选 / {(len(tiles) + per_sheet - 1) // per_sheet} 张对照图，目录: {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
