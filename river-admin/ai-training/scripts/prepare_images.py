"""把数据集中的图片统一为 jpg（可缩放），压缩训练包体积。

默认把长边缩放到 1280（VL 微调常用分辨率），并以 JPEG q85 重新编码；
标注为像素坐标的 VOC 标注无需改动——清洗阶段会按实际图片尺寸自动校正框坐标。

用法：
    python scripts/prepare_images.py --dataset ssz5-plastic-bottles-in-water
    python scripts/prepare_images.py --dataset ssz5-plastic-bottles-in-water --max-edge 960 --quality 85
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import RAW_DIR  # noqa: E402


def normalize_images(images_dir: Path, max_edge: int, quality: int) -> tuple[int, int, list[str]]:
    """把所有图片统一为 jpg：超长边则缩放，重编码为指定质量。"""
    from PIL import Image

    converted = 0
    failed = 0
    errors: list[str] = []
    for path in sorted(images_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in (".bmp", ".jpg", ".jpeg", ".png"):
            continue
        jpg = path.with_suffix(".jpg")
        if jpg == path:
            # 已是 jpg：仅在需要缩放或换质量时重写
            with Image.open(path) as image:
                if max(image.size) <= max_edge and path.suffix.lower() == ".jpg":
                    continue
        try:
            with Image.open(path) as image:
                image = image.convert("RGB")
                if max(image.size) > max_edge:
                    ratio = max_edge / max(image.size)
                    image = image.resize(
                        (max(1, int(image.width * ratio)), max(1, int(image.height * ratio))),
                        Image.LANCZOS,
                    )
                image.save(jpg, "JPEG", quality=quality, optimize=True)
            if jpg != path:
                path.unlink()
            converted += 1
        except Exception as error:  # noqa: BLE001
            failed += 1
            if len(errors) < 5:
                errors.append(f"{path.name}: {error}")
    return converted, failed, errors


def main() -> int:
    parser = argparse.ArgumentParser(description="图片统一为 jpg（可缩放）")
    parser.add_argument("--dataset", required=True, help="datasets/raw 下的数据集 id")
    parser.add_argument("--max-edge", type=int, default=1280, help="长边上限，0 表示不缩放")
    parser.add_argument("--quality", type=int, default=85)
    args = parser.parse_args()

    dataset = RAW_DIR / args.dataset
    images_dir = dataset / "images"
    if not images_dir.exists():
        print(f"未找到图片目录: {images_dir}")
        return 1

    before = sum(f.stat().st_size for f in images_dir.rglob("*") if f.is_file())
    converted, failed, errors = normalize_images(images_dir, args.max_edge, args.quality)
    after = sum(f.stat().st_size for f in images_dir.rglob("*") if f.is_file())
    print(f"处理 {converted} 张，失败 {failed} 张（长边上限 {args.max_edge}，质量 {args.quality}）")
    print(f"体积: {before / 1024 / 1024:.0f} MB -> {after / 1024 / 1024:.0f} MB")
    for error in errors:
        print(f"  ! {error}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
