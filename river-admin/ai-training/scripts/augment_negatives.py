"""从正样本图片中裁剪不含塑料瓶的区域，生成负样本（no-bottle）训练数据。

微调目标「只认塑料瓶」需要负样本教会模型「没有塑料瓶就报空」。
从含瓶子的原图裁剪瓶体之外的区域，得到的负样本与真实场景同分布，
且数量可控、无需额外数据来源。

裁剪区域严格避开所有标注框，若多次尝试均失败则跳过该图。

用法：
    python scripts/augment_negatives.py --dataset ssz5-plastic-bottles-in-water --per-image 0.5
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROCESSED_DIR  # noqa: E402


def crop_negative(image_path: Path, boxes: list[dict], out_path: Path, min_ratio: float = 0.45) -> bool:
    """裁剪一块不含任何标注框的区域并保存。"""
    from PIL import Image

    try:
        with Image.open(image_path) as image:
            image = image.convert("RGB")
            width, height = image.size
            # 标注框为百分比坐标，转像素
            rects = [
                (b["x"] / 100 * width - b["width"] / 100 * width / 2,
                 b["y"] / 100 * height - b["height"] / 100 * height / 2,
                 b["x"] / 100 * width + b["width"] / 100 * width / 2,
                 b["y"] / 100 * height + b["height"] / 100 * height / 2)
                for b in boxes
            ]
            for _ in range(24):
                crop_w = int(width * random.uniform(min_ratio, 0.9))
                crop_h = int(height * random.uniform(min_ratio, 0.9))
                if crop_w < 32 or crop_h < 32:
                    continue
                left = random.randint(0, max(0, width - crop_w))
                top = random.randint(0, max(0, height - crop_h))
                right, bottom = left + crop_w, top + crop_h
                # 与任一标注框相交则放弃
                if any(not (right <= r[0] or left >= r[2] or bottom <= r[1] or top >= r[3]) for r in rects):
                    continue
                image.crop((left, top, right, bottom)).save(out_path, "JPEG", quality=85, optimize=True)
                return True
    except Exception:  # noqa: BLE001
        return False
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="裁剪生成负样本")
    parser.add_argument("--dataset", required=True, help="processed 下的数据集 id")
    parser.add_argument("--per-image", type=float, default=0.5, help="每张正样本生成的负样本数量")
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    random.seed(args.seed)
    dataset_dir = PROCESSED_DIR / args.dataset
    manifest_path = dataset_dir / "manifest.json"
    if not manifest_path.exists():
        print(f"未找到清洗结果: {manifest_path}，请先执行 clean_dataset.py")
        return 1

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    positives = [item for item in manifest if item["boxes"]]
    target = int(len(positives) * args.per_image)

    images_dir = dataset_dir / "images" / "train"
    labels_dir = dataset_dir / "labels" / "train"
    images_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)

    negatives: list[dict] = []
    index = 0
    for item in positives:
        if len(negatives) >= target:
            break
        source = dataset_dir / item["image"]
        if not source.exists():
            continue
        count = 1 if random.random() < args.per_image else 0
        for _ in range(count):
            index += 1
            name = f"neg_{args.dataset}_{index:06d}.jpg"
            out_image = images_dir / name
            if not crop_negative(source, item["boxes"], out_image):
                continue
            (labels_dir / f"neg_{args.dataset}_{index:06d}.txt").write_text("", encoding="utf-8")
            from PIL import Image
            with Image.open(out_image) as im:
                neg_w, neg_h = im.size
            negatives.append({
                "image": f"images/train/{name}",
                "label": f"labels/train/neg_{args.dataset}_{index:06d}.txt",
                "split": "train",
                "width": neg_w,
                "height": neg_h,
                "source": f"{args.dataset}-neg",
                "boxes": [],
            })

    manifest.extend(negatives)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    total = len(manifest)
    print(f"新增负样本 {len(negatives)} 张（目标 {target}）")
    print(f"数据集合计 {total} 张，负样本占比 {len(negatives) / total * 100:.1f}%")
    print("下一步: python scripts/build_qwen_jsonl.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
