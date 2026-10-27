"""公共工具：YOLO/VOC 标注解析、类别归一化、图片尺寸、路径处理。

全部使用 Python 标准库，无第三方依赖。
"""
from __future__ import annotations

import json
import os
import struct
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"
DATASETS_DIR = ROOT / "datasets"
RAW_DIR = DATASETS_DIR / "raw"
PROCESSED_DIR = DATASETS_DIR / "processed"
OUTPUT_DIR = DATASETS_DIR / "output"
LABEL_DB_PATH = CONFIG_DIR / "label_db.json"
# label_db.json 中数据集源列表的键名
SOURCES_KEY = "dataset_sources"

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
SPLITS = ("train", "val", "test", "valid", "validation")


def load_label_db() -> dict[str, Any]:
    with LABEL_DB_PATH.open("r", encoding="utf-8") as fp:
        return json.load(fp)


def alias_set(label_db: dict[str, Any]) -> set[str]:
    """归一化后的塑料瓶别名集合（小写、去空格与下划线差异）。"""
    return {normalize_name(a) for a in label_db["aliases"]}


def normalize_name(name: str) -> str:
    """类别名归一化：小写、空格/连字符/下划线统一，便于跨数据集匹配。"""
    return str(name).strip().lower().replace("-", "_").replace(" ", "_")


def is_plastic_bottle(name: str, aliases: set[str]) -> bool:
    return normalize_name(name) in aliases


@dataclass
class Box:
    """归一化框（0-1 比例）与像素信息。"""

    cls_name: str
    cx: float
    cy: float
    w: float
    h: float
    width: int = 0
    height: int = 0

    def to_percentage(self) -> dict[str, float]:
        """转为前端渲染所需百分比：中心点 + 尺寸。"""
        return {
            "x": round(self.cx * 100, 2),
            "y": round(self.cy * 100, 2),
            "width": round(self.w * 100, 2),
            "height": round(self.h * 100, 2),
        }

    def to_yolo(self) -> str:
        return "0 " + " ".join(f"{v:.6f}" for v in (self.cx, self.cy, self.w, self.h))


@dataclass
class Sample:
    """一条样本：图片路径 + 归一化后的目标框。"""

    image: str
    split: str
    width: int = 0
    height: int = 0
    boxes: list[Box] = field(default_factory=list)
    source: str = ""

    @property
    def is_negative(self) -> bool:
        """负样本：图中不存在塑料瓶目标。"""
        return not self.boxes

    def to_dict(self) -> dict[str, Any]:
        return {
            "image": self.image,
            "split": self.split,
            "width": self.width,
            "height": self.height,
            "source": self.source,
            "boxes": [
                {"cls": b.cls_name, **b.to_percentage()} for b in self.boxes
            ],
        }


def read_image_size(path: Path) -> tuple[int, int]:
    """读取图片尺寸（纯标准库解析 PNG / JPEG / GIF 头）。"""
    try:
        with path.open("rb") as fp:
            head = fp.read(26)
            if len(head) < 16:
                return 0, 0
            if head[:8] == b"\x89PNG\r\n\x1a\n":
                width, height = struct.unpack(">II", head[16:24])
                return int(width), int(height)
            if head[:3] == b"GIF":
                width, height = struct.unpack("<HH", head[6:10])
                return int(width), int(height)
            if head[:2] == b"\xff\xd8":
                fp.seek(2)
                while True:
                    marker = fp.read(2)
                    if len(marker) < 2 or marker[0] != 0xFF:
                        break
                    if marker[1] in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                                     0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                        fp.read(3)
                        height, width = struct.unpack(">HH", fp.read(4))
                        return int(width), int(height)
                    length = struct.unpack(">H", fp.read(2))[0]
                    fp.seek(length - 2, os.SEEK_CUR)
    except Exception:
        return 0, 0
    return 0, 0


def parse_yolo_txt(path: Path, class_names: list[str]) -> list[Box]:
    """解析 YOLO 标注：cls cx cy w h（归一化）。class_names 为空时统一记为 class_0。"""
    boxes: list[Box] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return boxes
    for line in lines:
        parts = line.strip().split()
        if len(parts) < 5:
            continue
        try:
            cls_idx = int(float(parts[0]))
            cx, cy, w, h = (float(v) for v in parts[1:5])
        except ValueError:
            continue
        name = class_names[cls_idx] if 0 <= cls_idx < len(class_names) else f"class_{cls_idx}"
        boxes.append(Box(cls_name=name, cx=cx, cy=cy, w=w, h=h))
    return boxes


def parse_voc_xml(path: Path, class_names: list[str]) -> list[Box]:
    """解析 Pascal VOC xml：像素坐标 -> 归一化框。"""
    import xml.etree.ElementTree as ET

    boxes: list[Box] = []
    try:
        tree = ET.parse(path)
    except Exception:
        return boxes
    size = tree.getroot().find("size")
    width = int(float(size.find("width").text)) if size is not None and size.find("width") is not None else 0
    height = int(float(size.find("height").text)) if size is not None and size.find("height") is not None else 0
    for obj in tree.getroot().findall("object"):
        name_node = obj.find("name")
        name = name_node.text.strip() if name_node is not None and name_node.text else ""
        bnd = obj.find("bndbox")
        if bnd is None or not width or not height:
            continue
        try:
            xmin = float(bnd.find("xmin").text)
            ymin = float(bnd.find("ymin").text)
            xmax = float(bnd.find("xmax").text)
            ymax = float(bnd.find("ymax").text)
        except (AttributeError, TypeError, ValueError):
            continue
        boxes.append(Box(
            cls_name=name,
            cx=((xmin + xmax) / 2) / width,
            cy=((ymin + ymax) / 2) / height,
            w=(xmax - xmin) / width,
            h=(ymax - ymin) / height,
            width=width,
            height=height,
        ))
    return boxes


def load_class_names(dataset_dir: Path) -> list[str]:
    """读取 data.yaml / classes.txt 中的类别名。"""
    for candidate in ("data.yaml", "data.yml", "classes.txt"):
        path = dataset_dir / candidate
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if candidate == "classes.txt":
            return [line.strip() for line in text.splitlines() if line.strip()]
        names: list[str] = []
        in_names = False
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("names:"):
                in_names = True
                inline = stripped[len("names:"):].strip()
                if inline.startswith("["):
                    inline = inline.strip("[]")
                    names = [n.strip().strip("'\"") for n in inline.split(",") if n.strip()]
                    in_names = False
                continue
            if in_names:
                if stripped.startswith("-"):
                    names.append(stripped.lstrip("- ").strip().strip("'\""))
                else:
                    in_names = False
        if names:
            return names
    return []


def split_of(path: Path) -> str:
    """从路径中识别数据划分（train/val/test）。"""
    for part in reversed(path.parts):
        key = normalize_name(part)
        if key in ("train", "training"):
            return "train"
        if key in ("val", "valid", "validation"):
            return "val"
        if key == "test":
            return "test"
    return "train"


def iter_pairs(dataset_dir: Path) -> Iterable[tuple[Path, Path, str]]:
    """遍历数据集内的 (图片, 标注, 类别名来源) 配对。

    兼容两种结构：
      1. images/xxx 与 labels/xxx 平行目录（popxoq、通用 YOLO）
      2. 单一目录下图片与 .txt 标注混放（部分数据集）
    """
    images_dirs = [p for p in dataset_dir.rglob("images") if p.is_dir()]
    labels_dirs = {p.parent: p for p in dataset_dir.rglob("labels") if p.is_dir()}

    for img_dir in images_dirs:
        label_dir = labels_dirs.get(img_dir.parent)
        if label_dir is None:
            continue
        class_names = load_class_names(img_dir.parent)
        # 标注索引：文件名 stem -> 标注路径（兼容标注在多级子目录中的情况）
        index: dict[str, Path] = {}
        for ext in (".txt", ".xml"):
            for item in label_dir.rglob(f"*{ext}"):
                index.setdefault(item.stem, item)
        for image in sorted(img_dir.rglob("*")):
            if image.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            rel = image.relative_to(img_dir)
            # 优先同名同目录标注，其次按文件名索引查找
            label = label_dir / rel.with_suffix(".txt")
            if not label.exists():
                label = label_dir / rel.with_suffix(".xml")
            if not label.exists():
                label = index.get(image.stem)
            if label is not None and label.exists():
                yield image, label, class_names

    if not images_dirs:
        for image in sorted(dataset_dir.rglob("*")):
            if image.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            label = image.with_suffix(".txt")
            if not label.exists():
                label = image.with_suffix(".xml")
            if label.exists():
                yield image, label, load_class_names(dataset_dir)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fp:
        for row in rows:
            fp.write(json.dumps(row, ensure_ascii=False) + "\n")
