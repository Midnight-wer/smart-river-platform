"""从 COCO 抽取「像瓶子但不是塑料瓶」的负样本（玻璃杯/花瓶/马克杯/碗等）。

目的：压掉模型把玻璃瓶、玻璃罐、调味瓶误认成塑料瓶的问题。
挑选条件：
  1. 图中含 wine glass / vase / cup / bowl 之一，且该物体面积占比 >= --min-area；
  2. 图中没有任何 bottle 标注（避免把真瓶子当负样本）。

产物：datasets/raw/coco-negatives/{images,labels}/train2017（标签为空文件）
用法：
    python scripts/fetch_coco_negatives.py --max-images 700
"""
from __future__ import annotations

import argparse
import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANN_DIR = ROOT / "datasets" / "raw" / "coco" / "annotations"
OUT_DIR = ROOT / "datasets" / "raw" / "coco-negatives"
IMG_URL = "http://images.cocodataset.org/train2017/{image_id:012d}.jpg"
NEG_CLASSES = ("wine glass", "vase", "cup", "bowl")


def download(image_id: int, path: Path) -> bool:
    if path.exists() and path.stat().st_size > 1024:
        return True
    try:
        with urllib.request.urlopen(IMG_URL.format(image_id=image_id), timeout=60) as response:
            data = response.read()
        path.write_bytes(data)
        return len(data) > 1024
    except Exception:  # noqa: BLE001
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="抓取瓶状非塑料容器负样本")
    parser.add_argument("--max-images", type=int, default=700)
    parser.add_argument("--min-area", type=float, default=0.02)
    args = parser.parse_args()

    ann_path = ANN_DIR / "instances_train2017.json"
    if not ann_path.exists():
        print(f"!! 缺少标注文件: {ann_path}")
        return 1

    print("解析 COCO train2017 标注 ...")
    data = json.loads(ann_path.read_text(encoding="utf-8"))
    names = {c["id"]: c["name"] for c in data["categories"]}
    neg_ids = {cid for cid, name in names.items() if name in NEG_CLASSES}
    bottle_id = next(cid for cid, name in names.items() if name == "bottle")

    images = {img["id"]: img for img in data["images"]}
    has_bottle: set[int] = set()
    hits: dict[int, float] = {}
    for ann in data["annotations"]:
        image_id = ann["image_id"]
        if ann["category_id"] == bottle_id:
            has_bottle.add(image_id)
        elif ann["category_id"] in neg_ids:
            info = images.get(image_id)
            if not info:
                continue
            ratio = ann["area"] / max(info["width"] * info["height"], 1)
            if ratio >= args.min_area:
                hits[image_id] = max(hits.get(image_id, 0), ratio)

    picked = [image_id for image_id in hits if image_id not in has_bottle]
    picked.sort(key=lambda i: -hits[i])
    picked = picked[: args.max_images]
    print(f"候选 {len(hits)} 张，去掉含真瓶子的，取 {len(picked)} 张")

    img_dir = OUT_DIR / "images" / "train2017"
    lbl_dir = OUT_DIR / "labels" / "train2017"
    img_dir.mkdir(parents=True, exist_ok=True)
    lbl_dir.mkdir(parents=True, exist_ok=True)

    saved = 0
    with ThreadPoolExecutor(max_workers=16) as pool:
        futures = {
            pool.submit(download, image_id, img_dir / f"neg_{image_id:012d}.jpg"): image_id
            for image_id in picked
        }
        for future in as_completed(futures):
            if not future.result():
                continue
            image_id = futures[future]
            (lbl_dir / f"neg_{image_id:012d}.txt").write_text("", encoding="utf-8")
            saved += 1

    print(f"已保存负样本 {saved} 张 -> {img_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
