"""端到端测试脚本：验证「标注 -> 清洗 -> 百炼 jsonl -> zip」全链路。

使用合成的最小数据集（自造图片与 YOLO 标注），不依赖任何外部下载，
覆盖以下断言：
  1. 清洗后只保留塑料瓶框，塑料袋/泡沫/树枝等类别被丢弃；
  2. 不含塑料瓶的样本保留为负样本；
  3. data.jsonl 每行结构符合百炼多模态 SFT 规范（messages + image/text/assistant）；
  4. assistant 答案中目标类别只有「塑料瓶」；
  5. zip 根目录直接是 data.jsonl，图片平铺且文件名全局唯一。

用法：
    python scripts/test_pipeline.py
"""
from __future__ import annotations

import json
import shutil
import struct
import sys
import tempfile
import zipfile
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import alias_set, load_label_db  # noqa: E402
from build_qwen_jsonl import build_answer, build_record  # noqa: E402
from clean_dataset import clean_dataset  # noqa: E402

# 合成数据集类别表：0 塑料瓶（目标），其余为需忽略的干扰物
CLASSES = ["plastic_bottle", "plastic_bag", "foam", "branch"]
# 每张图的 (类别索引, 归一化 cx, cy, w, h)
SAMPLES = [
    [(0, 0.30, 0.60, 0.10, 0.20)],
    [(0, 0.55, 0.62, 0.08, 0.15), (1, 0.20, 0.70, 0.12, 0.10)],
    [(2, 0.40, 0.50, 0.20, 0.12), (3, 0.70, 0.58, 0.15, 0.08)],
    [(0, 0.45, 0.66, 0.09, 0.18), (2, 0.80, 0.52, 0.10, 0.08)],
    [(1, 0.33, 0.44, 0.10, 0.10)],
    [(0, 0.62, 0.71, 0.11, 0.16), (3, 0.15, 0.66, 0.10, 0.06)],
]
EXPECTED_BOTTLES = 4  # 4 张图含塑料瓶，共 4 个框


def write_png(path: Path, width: int, height: int, color: tuple[int, int, int]) -> None:
    """生成最小合法 PNG（标准库实现）。"""
    raw = b"".join(b"\x00" + bytes(color) * width for _ in range(height))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 6))
    png += chunk(b"IEND", b"")
    path.write_bytes(png)


def build_fake_dataset(root: Path) -> Path:
    """构造合成 YOLO 数据集。"""
    dataset = root / "fake-river-plastic-bottle"
    images = dataset / "images" / "train"
    labels = dataset / "labels" / "train"
    images.mkdir(parents=True, exist_ok=True)
    labels.mkdir(parents=True, exist_ok=True)
    for index, boxes in enumerate(SAMPLES):
        name = f"river_{index:03d}.jpg"
        write_png(images / name.replace(".jpg", ".png"), 640, 360, (40, 90, 150))
        lines = [f"{cls} {cx} {cy} {w} {h}" for cls, cx, cy, w, h in boxes]
        (labels / name.replace(".jpg", ".txt")).write_text("\n".join(lines) + "\n", encoding="utf-8")
    (dataset / "data.yaml").write_text(
        "nc: 4\nnames: ['plastic_bottle', 'plastic_bag', 'foam', 'branch']\n", encoding="utf-8"
    )
    return dataset


def check(condition: bool, message: str) -> bool:
    print(("  ✓ " if condition else "  ✗ ") + message)
    return condition


def main() -> int:
    label_db = load_label_db()
    aliases = alias_set(label_db)
    passed = True

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        raw = build_fake_dataset(root)
        out = root / "processed"
        prompts = json.loads((Path(__file__).resolve().parents[1] / "config" / "prompts.json").read_text(encoding="utf-8"))

        print("[1] 清洗：仅保留塑料瓶")
        stats = clean_dataset(raw, out, "fake", aliases)
        passed &= check(stats["samples"] == len(SAMPLES), f"样本数 {stats['samples']} == {len(SAMPLES)}")
        passed &= check(stats["boxes_kept"] == EXPECTED_BOTTLES,
                        f"保留塑料瓶框 {stats['boxes_kept']} == {EXPECTED_BOTTLES}")
        passed &= check(stats["boxes_dropped"] == 6, f"丢弃其他类别框 {stats['boxes_dropped']} == 6")
        passed &= check(stats["negative"] == 2, f"负样本 {stats['negative']} == 2（无塑料瓶的图片保留）")
        passed &= check(set(stats["dropped_classes"]) == {"plastic_bag", "foam", "branch"},
                        f"丢弃类别 {sorted(stats['dropped_classes'])}")

        print("[2] 训练样本：结构与类别")
        manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
        records = []
        for item in manifest:
            image_name = Path(item["image"]).name
            records.append(build_record(item, image_name, prompts, "bailian"))
        passed &= check(all("messages" in r and len(r["messages"]) == 3 for r in records),
                        "每条记录含 system/user/assistant 三段")
        user_content = records[0]["messages"][1]["content"]
        passed &= check(isinstance(user_content, list) and "image" in user_content[0],
                        "user 段含 image 字段（百炼多模态格式）")
        passed &= check("text" in user_content[1], "user 段含 text 字段")
        targets = set()
        for record in records:
            answer = json.loads(record["messages"][2]["content"][0]["text"])
            for obj in answer.get("objects", []):
                targets.add(obj["target"])
        passed &= check(targets <= {"塑料瓶"}, f"答案目标类别仅含塑料瓶：{sorted(targets)}")
        negatives = [r for r in records
                     if json.loads(r["messages"][2]["content"][0]["text"]).get("objects") == []]
        passed &= check(len(negatives) == 2, f"负样本答案为空 objects（{len(negatives)} 条）")

        print("[3] zip 打包：根目录 data.jsonl + 图片平铺唯一")
        images_dir = root / "images"
        images_dir.mkdir(exist_ok=True)
        zip_path = root / "train.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("data.jsonl", "\n".join(json.dumps(r, ensure_ascii=False) for r in records))
            for item, record in zip(manifest, records):
                src = out / item["image"]
                archive.write(src, arcname=Path(item["image"]).name)
        with zipfile.ZipFile(zip_path) as archive:
            names = archive.namelist()
            passed &= check("data.jsonl" in names, "data.jsonl 位于压缩包根目录")
            passed &= check(all("/" not in n for n in names), "图片平铺在根目录（无子目录路径）")
            image_names = [n for n in names if n != "data.jsonl"]
            passed &= check(len(image_names) == len(set(image_names)), "图片文件名全局唯一")
            passed &= check(len(image_names) == len(records), f"图片数 {len(image_names)} == 样本数 {len(records)}")

        print("[4] 标签库：白名单过滤")
        from_label_db = json.loads(
            (Path(__file__).resolve().parents[1] / "config" / "label_db.json").read_text(encoding="utf-8")
        )
        passed &= check("plastic_bottle" in from_label_db["aliases"], "塑料瓶别名在白名单中")
        passed &= check(not any(a in from_label_db["aliases"] for a in ("plastic_bag", "foam", "branch")),
                        "干扰类别不在白名单中（识别后将被丢弃）")

    print("\n结果: " + ("全部通过" if passed else "存在失败项"))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
