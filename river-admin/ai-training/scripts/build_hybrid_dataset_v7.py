"""v7 混合数据集：人工精标 webcap 紧框（labels-xal）+ 河面 all，50/50 均衡。

与 v6 配方的差异：手持样本只取用户在 X-AnyLabeling 里修正过的图片
（labels-xal/corrected-list.txt），替代旧的宽松标签。
产物：datasets/hybrid-v7/{images,labels}/{train,val} + data.yaml

用法：
    python scripts/build_hybrid_dataset_v7.py
"""
from __future__ import annotations

import random
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALL = ROOT / "datasets" / "all"
HAND_IMG = ROOT / "datasets" / "handheld-bottles" / "images" / "webcap"
HAND_LBL = ROOT / "datasets" / "handheld-bottles" / "labels-xal"
OUT = ROOT / "datasets" / "hybrid-v7"
VAL_RATIO = 0.2
SEED = 2027
OVERSAMPLE = 16  # 精标紧框过采样，保持 50/50 均衡


def main() -> int:
    random.seed(SEED)
    if OUT.exists():
        shutil.rmtree(OUT)
    for split in ("train", "val"):
        (OUT / "images" / split).mkdir(parents=True)
        (OUT / "labels" / split).mkdir(parents=True)

    # 1) all 数据集 val 全量（河面验证不偏置）
    n_all_val = 0
    for img in (ALL / "images" / "val").glob("*"):
        shutil.copy2(img, OUT / "images" / "val" / img.name)
        lbl = ALL / "labels" / "val" / f"{img.stem}.txt"
        if lbl.exists():
            shutil.copy2(lbl, OUT / "labels" / "val" / lbl.name)
        n_all_val += 1

    # 2) 精标样本：按抓拍时间桶分组 8:2（相邻秒为同一姿势，防泄漏）
    stems = sorted(p.stem for p in HAND_LBL.glob("*.txt") if p.stem != "corrected-list")
    by_group: dict[int, list[str]] = {}
    for s in stems:
        ts = int(s.split("_")[1])
        by_group.setdefault(ts // 15, []).append(s)
    groups = sorted(by_group.values(), key=lambda g: g[0])
    random.shuffle(groups)
    n_val = max(1, round(len(groups) * VAL_RATIO))
    split_map = {id(g): ("val" if i < n_val else "train") for i, g in enumerate(groups)}

    handheld_pos: list[tuple[Path, Path]] = []
    n_neg = 0
    for group in groups:
        split = split_map[id(group)]
        for stem in group:
            img = HAND_IMG / f"{stem}.jpg"
            lbl = HAND_LBL / f"{stem}.txt"
            if not img.exists():
                continue
            if split == "val" or not lbl.read_text(encoding="utf-8").strip():
                shutil.copy2(img, OUT / "images" / "val" / img.name
                             if split == "val" else OUT / "images" / "train" / img.name)
                shutil.copy2(lbl, OUT / "labels" / "val" / f"{stem}.txt"
                             if split == "val" else OUT / "labels" / "train" / f"{stem}.txt")
                if split == "train":
                    n_neg += 1
            else:
                handheld_pos.append((img, lbl))

    # 3) 精标正样本过采样 ×OVERSAMPLE
    for img, lbl in handheld_pos:
        for k in range(OVERSAMPLE):
            name = img.name if k == 0 else f"{img.stem}__dup{k}.jpg"
            shutil.copy2(img, OUT / "images" / "train" / name)
            shutil.copy2(lbl, OUT / "labels" / "train" / f"{Path(name).stem}.txt")

    # 4) 河面 train 下采样到与精标正样本等量（50/50）
    river_all = sorted((ALL / "images" / "train").glob("*"))
    random.shuffle(river_all)
    river = river_all[: len(handheld_pos) * OVERSAMPLE]
    for img in river:
        shutil.copy2(img, OUT / "images" / "train" / img.name)
        lbl = ALL / "labels" / "train" / f"{img.stem}.txt"
        if lbl.exists():
            shutil.copy2(lbl, OUT / "labels" / "train" / lbl.name)

    # 5) data.yaml
    (OUT / "data.yaml").write_text(
        "# v7 混合数据集（河面 all + 人工精标手持紧框）\n"
        f"path: {OUT.as_posix()}\ntrain: images/train\nval: images/val\n"
        "nc: 1\nnames: {0: '塑料瓶'}\n", encoding="utf-8")

    n_hand_val = sum(1 for p in (OUT / "images" / "val").glob("webcap_*"))
    # 留存手持 val 清单供门禁评估（诚实留出集）
    val_stems = []
    for group in groups:
        if split_map[id(group)] == "val":
            val_stems.extend(group)
    (OUT / "val-handheld.txt").write_text("\n".join(sorted(val_stems)), encoding="utf-8")
    print(f"all val: {n_all_val} | 精标: train 正{len(handheld_pos) * OVERSAMPLE}"
          f"(原{len(handheld_pos)})/负{n_neg}, val 手持{n_hand_val}")
    print(f"河面 train 下采样: {len(river)} 张（原 {len(river_all)}）")
    total_train = len(list((OUT / "images" / "train").glob("*")))
    print(f"hybrid-v7 train 共 {total_train} 张")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
