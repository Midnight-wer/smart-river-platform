"""筛选 COCO 中的「PET 矿泉水瓶 / 漂浮瓶」样本，用于河道场景训练。

COCO 的 bottle 类混着玻璃瓶、啤酒瓶、番茄酱瓶、牛奶盒，不能整体当正样本。
本脚本下载一批瓶身较大的候选图并生成带编号的对照图，由人（或模型）挑出
真正的塑料矿泉水瓶，输出 selection.json；未选中的瓶子图转为负样本。

用法：
    python scripts/curate_coco_bottles.py --sample 96
"""
from __future__ import annotations

import argparse
import json
import random
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ANN_DIR = ROOT / "datasets" / "raw" / "coco" / "annotations"
BOTTLE_DIR = ROOT / "datasets" / "raw" / "coco-bottles" / "images"
OUT_DIR = ROOT / "datasets" / "reports" / "curate"
IMG_URL = "http://images.cocodataset.org/{split}/{image_id:012d}.jpg"


def download(item: tuple[str, int]) -> Path | None:
    split, image_id = item
    path = OUT_DIR / "images" / f"{split}_{image_id:012d}.jpg"
    if path.exists() and path.stat().st_size > 1024:
        return path
    try:
        with urllib.request.urlopen(IMG_URL.format(split=split, image_id=image_id), timeout=60) as response:
            path.write_bytes(response.read())
        return path
    except Exception:  # noqa: BLE001
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="筛选矿泉水瓶/漂浮瓶正样本")
    parser.add_argument("--sample", type=int, default=96)
    parser.add_argument("--min-area", type=float, default=0.02)
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "images").mkdir(exist_ok=True)

    pool = []
    for split in ("val2017", "train2017"):
        data = json.loads((ANN_DIR / f"instances_{split}.json").read_text(encoding="utf-8"))
        cat_id = next(c["id"] for c in data["categories"] if c["name"] == "bottle")
        images = {im["id"]: im for im in data["images"]}
        used_dir = BOTTLE_DIR / split
        used = {p.stem for p in used_dir.glob("*.jpg")} if used_dir.exists() else set()
        per: dict[int, list] = {}
        for ann in data["annotations"]:
            if ann["category_id"] != cat_id or ann.get("iscrowd"):
                continue
            info = images.get(ann["image_id"])
            if not info:
                continue
            ratio = ann["area"] / max(info["width"] * info["height"], 1)
            if ratio < args.min_area:
                continue
            per.setdefault(ann["image_id"], []).append((ann, ratio, info))
        for image_id, anns in per.items():
            if f"{image_id:012d}" in used:
                continue
            pool.append({"split": split, "image_id": image_id, "anns": anns})

    random.seed(args.seed)
    random.shuffle(pool)
    picked = pool[: args.sample]
    print(f"候选池 {len(pool)} 张，抽取 {len(picked)} 张下载 ...")

    with ThreadPoolExecutor(max_workers=16) as pool_exec:
        paths = list(pool_exec.map(download, [(p["split"], p["image_id"]) for p in picked]))

    entries = []
    tiles = []
    for item, path in zip(picked, paths):
        if not path:
            continue
        entries.append({
            "no": len(entries) + 1,
            "split": item["split"],
            "image_id": item["image_id"],
            "file": str(path),
            "boxes": [
                {
                    "bbox": ann["bbox"],
                    "image_width": info["width"],
                    "image_height": info["height"],
                    "area_ratio": round(ratio, 4),
                }
                for ann, ratio, info in item["anns"]
            ],
        })
        with Image.open(path) as im:
            tile = im.convert("RGB")
        tile.thumbnail((300, 300), Image.LANCZOS)
        tiles.append((len(entries), tile))

    (OUT_DIR / "candidates.json").write_text(
        json.dumps(entries, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    cell, cols, per_sheet = 320, 6, 24
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 26)
    except Exception:  # noqa: BLE001
        font = ImageFont.load_default()

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
        print("生成", sheet_path)

    print(f"候选 {len(entries)} 张，请按编号挑选矿泉水瓶/漂浮瓶")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
