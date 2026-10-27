"""把清洗后的标注转换为 Qwen2.5-VL 百炼 LoRA 微调格式（data.jsonl）并打包 zip。

百炼多模态 SFT 数据规格：
- 压缩包根目录必须直接是 data.jsonl（不可套文件夹）
- 图片与 data.jsonl 同处一个 zip，图片文件名全局唯一；data.jsonl 内只写文件名（如 img_000001.jpg）
- 每行一个 JSON：{"messages":[{"role":"user","content":[{"image":"x.jpg"},{"text":"..."}]},
                                {"role":"assistant","content":[{"text":"..."}]}]}

输出：
  datasets/output/data.jsonl              全部样本（调试用）
  datasets/output/images/                 图片（ASCII 全局唯一命名）
  datasets/output/qwen-plastic-bottle-train.zip
  datasets/output/qwen-plastic-bottle-eval.zip

用法：
    python scripts/build_qwen_jsonl.py
    python scripts/build_qwen_jsonl.py --val-ratio 0.15 --format openai
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    CONFIG_DIR,
    OUTPUT_DIR,
    PROCESSED_DIR,
    load_label_db,
)

PROMPTS_PATH = CONFIG_DIR / "prompts.json"
IMAGE_DIR = OUTPUT_DIR / "images"


def load_prompts() -> dict:
    with PROMPTS_PATH.open("r", encoding="utf-8") as fp:
        return json.load(fp)


def collect_samples() -> list[dict]:
    """读取各数据集 manifest，汇总为统一样本列表。"""
    samples: list[dict] = []
    for manifest_path in sorted(PROCESSED_DIR.glob("*/manifest.json")):
        dataset_dir = manifest_path.parent
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for item in manifest:
            image_path = dataset_dir / item["image"]
            if not image_path.exists():
                continue
            samples.append({**item, "abs_image": str(image_path), "dataset": dataset_dir.name})
    return samples


def build_answer(item: dict, target_cn: str) -> str:
    """构造 assistant 答案：仅塑料瓶类别 + 百分比坐标。"""
    objects = [
        {
            "target": target_cn,
            "confidence": 0.95,
            "x": box["x"],
            "y": box["y"],
            "width": box["width"],
            "height": box["height"],
        }
        for box in item.get("boxes", [])
    ]
    return json.dumps({"objects": objects}, ensure_ascii=False)


def build_record(item: dict, image_name: str, prompts: dict, fmt: str) -> dict:
    """构造单条训练数据。"""
    answer = build_answer(item, prompts["target_cn"])
    user_text = prompts["user_prompt"]
    if fmt == "openai":
        # 兼容 OpenAI 风格（部分平台要求 image_url + 文本）
        user_content = [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,<{image_name}>"}},
            {"type": "text", "text": user_text},
        ]
    else:
        # 百炼原生多模态格式：文件名（不含路径）
        user_content = [{"image": image_name}, {"text": user_text}]
    return {
        "messages": [
            {"role": "system", "content": [{"text": prompts["system_prompt"]}]},
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": [{"text": answer}]},
        ]
    }


def make_zip(records: list[dict], samples: list[dict], zip_path: Path) -> None:
    """打包 zip：根目录为 data.jsonl，图片平铺在根目录（文件名全局唯一）。"""
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("data.jsonl", "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n")
        for record, sample in zip(records, samples):
            archive.write(sample["abs_image"], arcname=sample["image_name"])


def main() -> int:
    parser = argparse.ArgumentParser(description="转换为百炼 Qwen2.5-VL LoRA 微调格式")
    parser.add_argument("--val-ratio", type=float, default=0.1, help="评测集比例")
    parser.add_argument("--format", choices=["bailian", "openai"], default="bailian")
    parser.add_argument("--min-eval", type=int, default=20, help="评测集最少样本数")
    args = parser.parse_args()

    prompts = load_prompts()
    label_db = load_label_db()
    target_cn = label_db["target_cn"]

    samples = collect_samples()
    if not samples:
        print("未找到清洗后的样本，请先执行: python scripts/clean_dataset.py")
        return 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if IMAGE_DIR.exists():
        shutil.rmtree(IMAGE_DIR)
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)

    # 图片平铺重命名 + 划分训练/评测集
    for index, sample in enumerate(samples):
        source = Path(sample["abs_image"])
        ext = source.suffix.lower() if source.suffix.lower() in (".jpg", ".jpeg", ".png") else ".jpg"
        name = f"img_{index:06d}{ext}"
        shutil.copyfile(source, IMAGE_DIR / name)
        sample["image_name"] = name

    eval_count = max(args.min_eval, int(len(samples) * args.val_ratio))
    eval_count = min(eval_count, len(samples) - 1) if len(samples) > 1 else 0
    eval_set = samples[:eval_count]
    train_set = samples[eval_count:]

    all_records = [build_record(s, s["image_name"], prompts, args.format) for s in samples]
    train_records = [build_record(s, s["image_name"], prompts, args.format) for s in train_set]
    eval_records = [build_record(s, s["image_name"], prompts, args.format) for s in eval_set]

    (OUTPUT_DIR / "data.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in all_records) + "\n", encoding="utf-8"
    )
    make_zip(train_records, train_set, OUTPUT_DIR / "qwen-plastic-bottle-train.zip")
    make_zip(eval_records, eval_set, OUTPUT_DIR / "qwen-plastic-bottle-eval.zip")

    positive = sum(1 for s in samples if s["boxes"])
    size_mb = (OUTPUT_DIR / "qwen-plastic-bottle-train.zip").stat().st_size / 1024 / 1024
    print(f"样本总数 {len(samples)}（正样本 {positive} / 负样本 {len(samples) - positive}）")
    print(f"训练集 {len(train_records)} 条 -> qwen-plastic-bottle-train.zip（{size_mb:.1f} MB）")
    print(f"评测集 {len(eval_records)} 条 -> qwen-plastic-bottle-eval.zip")
    print(f"格式: {args.format}；类别: 仅 {target_cn}")
    print("\n下一步: python scripts/submit_finetune.py --train-zip <train.zip> --eval-zip <eval.zip>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
