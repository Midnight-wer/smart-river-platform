"""构建混合数据集：现有 all 数据集 + 手持瓶专项样本（75 张）。

handheld 样本按 8:2 分入 train/val（正负样本同比例），其余原样保留。
产物：datasets/hybrid/{images,labels}/{train,val} + data.yaml

用法：
    python scripts/build_hybrid_dataset.py
"""
from __future__ import annotations

import random
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALL = ROOT / "datasets" / "all"
HAND = ROOT / "datasets" / "handheld-bottles"
OUT = ROOT / "datasets" / "hybrid"
VAL_RATIO = 0.2
SEED = 2026


def main() -> int:
    random.seed(SEED)
    if OUT.exists():
        shutil.rmtree(OUT)
    for split in ("train", "val"):
        (OUT / "images" / split).mkdir(parents=True)
        (OUT / "labels" / split).mkdir(parents=True)

    # 1) 复制 all 数据集：val 全量；train 的河面样本由下采样逻辑控制（50/50 均衡）
    counts = {}
    for split in ("train", "val"):
        if split == "train":
            counts[split] = 0
            continue
        images = list((ALL / "images" / split).glob("*"))
        for img in images:
            shutil.copy2(img, OUT / "images" / split / img.name)
            lbl = ALL / "labels" / split / f"{img.stem}.txt"
            if lbl.exists():
                shutil.copy2(lbl, OUT / "labels" / split / lbl.name)
        counts[split] = len(images)
    print(f"all 数据集: val={counts['val']}（train 河面走下采样）")

    # 2) 手持瓶样本按 8:2 分配（同前缀整组分配，避免同姿势泄漏）
    handheld = sorted(HAND.glob("images/raw_*.jpg")) + sorted(HAND.glob("images/webcap/*.jpg"))
    by_group: dict[str, list[Path]] = {}
    for p in handheld:
        # 组 = 动作批次（office/live/webcap）+ 编号取整十（相邻帧同一姿势）
        prefix = p.stem.split("_")[1]
        tail = p.stem.split("_")[-1]
        num = int(tail) if tail.isdigit() else abs(hash(tail)) % 1000
        by_group.setdefault(f"{prefix}{num // 5}", []).append(p)
    groups = sorted(by_group.values(), key=lambda g: g[0].name)
    random.shuffle(groups)
    n_val = max(1, round(len(groups) * VAL_RATIO))
    split_map = {id(g): ("val" if i < n_val else "train") for i, g in enumerate(groups)}

    stats = {"train": [0, 0], "val": [0, 0]}  # [正, 负]
    skipped = 0
    OVERSAMPLE = 16   # 手持正样本过采样倍数：用户要求手持占比 >= 50%
    BALANCE = True    # True = 河面下采样到与手持正样本等量（50/50）
    handheld_pos: list[tuple[Path, Path]] = []  # (img, lbl) train 正样本
    for group in groups:
        split = split_map[id(group)]
        for img in group:
            lbl = HAND / "labels" / f"{img.stem}.txt"
            if not lbl.exists():
                skipped += 1
                continue
            is_pos = bool(lbl.read_text(encoding="utf-8").strip())
            if split == "val" or not is_pos:
                name = img.name
                shutil.copy2(img, OUT / "images" / split / name)
                shutil.copy2(lbl, OUT / "labels" / split / f"{Path(name).stem}.txt")
                stats[split][0 if is_pos else 1] += 1
            else:
                handheld_pos.append((img, lbl))
    if skipped:
        print(f"跳过未标注帧 {skipped} 张（实时识别仍在存图，下轮纳入）")

    # 手持正样本过采样 ×OVERSAMPLE
    for img, lbl in handheld_pos:
        for k in range(OVERSAMPLE):
            name = img.name if k == 0 else f"{img.stem}__dup{k}.jpg"
            shutil.copy2(img, OUT / "images" / "train" / name)
            shutil.copy2(lbl, OUT / "labels" / "train" / f"{Path(name).stem}.txt")
            stats["train"][0] += 1

    # 河面（all train）下采样到与手持正样本等量 -> 50/50
    if BALANCE and handheld_pos:
        target = len(handheld_pos) * OVERSAMPLE
        river = sorted((ALL / "images" / "train").glob("*"))
        random.shuffle(river)
        river = river[:target]
        for img in river:
            lbl = ALL / "labels" / "train" / f"{img.stem}.txt"
            shutil.copy2(img, OUT / "images" / "train" / img.name)
            if lbl.exists():
                shutil.copy2(lbl, OUT / "labels" / "train" / lbl.name)
            stats["train"][1] += 1
        print(f"河面下采样: {len(river)} 张（原 2124），与手持 1:1")
    print(f"手持瓶: train 正{stats['train'][0]}/负{stats['train'][1]}, "
          f"val 正{stats['val'][0]}/负{stats['val'][1]}")

    # 3) data.yaml
    (OUT / "data.yaml").write_text(
        "# 混合数据集（通用瓶 + 手持瓶专项）\n"
        f"path: {OUT.as_posix()}\ntrain: images/train\nval: images/val\n"
        "nc: 1\nnames: {0: '塑料瓶'}\n", encoding="utf-8")
    total = sum(len(list((OUT / 'images' / s).glob('*'))) for s in ('train', 'val'))
    print(f"hybrid 总计 {total} 张")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
