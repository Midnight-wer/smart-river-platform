"""从 COCO 2017 抽取「近景瓶子」样本，补齐室内/手持/桌面等近景场景。

COCO 的 bottle 类大多是矿泉水/饮料塑料瓶，正好补上 m0-n 缺少的近景域。
只取面积占比 >= --min-area 的实例（保证是近景），并按每张图最多 --max-per-image 个框。

产物：datasets/raw/coco-bottles/{images,labels}/<split>/ + manifest.json
用法：
    python scripts/fetch_coco_bottles.py --max-images 1200 --min-area 0.01
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT  # noqa: E402

COCO_ROOT = ROOT / "datasets" / "raw" / "coco"
ANN_DIR = COCO_ROOT / "annotations"
OUT_DIR = ROOT / "datasets" / "raw" / "coco-bottles"
IMAGE_URL = "http://images.cocodataset.org/{split}/{image_id:012d}.jpg"


def download(url: str, target: Path, timeout: int = 60) -> bool:
    if target.exists() and target.stat().st_size > 1024:
        return True
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            data = response.read()
        target.write_bytes(data)
        return len(data) > 1024
    except Exception:  # noqa: BLE001
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="抓取 COCO 近景瓶子样本")
    parser.add_argument("--max-images", type=int, default=1200)
    parser.add_argument("--min-area", type=float, default=0.01, help="瓶子面积占图比例下限")
    parser.add_argument("--max-per-image", type=int, default=4)
    parser.add_argument("--val-ratio", type=float, default=0.15)
    args = parser.parse_args()

    if not ANN_DIR.exists():
        print(f"!! 未找到 COCO 标注目录: {ANN_DIR}")
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest: list[dict] = []
    total = 0

    for split in ("val2017", "train2017"):
        ann_path = ANN_DIR / f"instances_{split}.json"
        if not ann_path.exists():
            continue
        print(f"解析 {ann_path.name} ...")
        data = json.loads(ann_path.read_text(encoding="utf-8"))
        cat_id = next(c["id"] for c in data["categories"] if c["name"] == "bottle")
        images = {img["id"]: img for img in data["images"]}
        grouped: dict[int, list] = defaultdict(list)
        for ann in data["annotations"]:
            if ann.get("category_id") != cat_id or ann.get("iscrowd"):
                continue
            info = images.get(ann["image_id"])
            if not info:
                continue
            ratio = ann["area"] / max(info["width"] * info["height"], 1)
            if ratio < args.min_area:
                continue
            grouped[ann["image_id"]].append((ann, info, ratio))

        pending: list[tuple] = []
        for image_id, items in grouped.items():
            if len(pending) >= args.max_images - total:
                break
            items.sort(key=lambda x: -x[2])
            items = items[: args.max_per_image]
            target_dir = OUT_DIR / "images" / split
            target_dir.mkdir(parents=True, exist_ok=True)
            image_path = target_dir / f"{image_id:012d}.jpg"
            url = IMAGE_URL.format(split=split, image_id=image_id)
            pending.append((image_id, items, split, image_path, url))

        # 并发下载图片
        with ThreadPoolExecutor(max_workers=16) as pool:
            futures = {pool.submit(download, url, path): (image_id, items, split, path)
                       for image_id, items, split, path, url in pending}
            for future in as_completed(futures):
                image_id, items, split, image_path = futures[future]
                if not future.result():
                    continue
                label_dir = OUT_DIR / "labels" / split
                label_dir.mkdir(parents=True, exist_ok=True)
                lines = []
                for ann, meta, _ratio in items:
                    x, y, w, h = ann["bbox"]
                    cx = (x + w / 2) / meta["width"]
                    cy = (y + h / 2) / meta["height"]
                    nw = w / meta["width"]
                    nh = h / meta["height"]
                    if 0 < nw <= 1 and 0 < nh <= 1 and 0 <= cx <= 1 and 0 <= cy <= 1:
                        lines.append(f"0 {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}")
                if not lines:
                    image_path.unlink(missing_ok=True)
                    continue
                (label_dir / f"{image_id:012d}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
                manifest.append({"image": f"images/{split}/{image_id:012d}.jpg",
                                 "label": f"labels/{split}/{image_id:012d}.txt",
                                 "split": split, "boxes": len(lines)})
                total += 1
        pending.clear()
        print(f"  {split}: 累计 {total} 张")

    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n共 {total} 张 COCO 近景瓶子图 -> {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
