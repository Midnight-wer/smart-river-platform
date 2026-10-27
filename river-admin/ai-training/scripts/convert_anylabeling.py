"""把 X-AnyLabeling 的 json 标注批量转换成 YOLO txt 标签。

规则：
- json 为准（用户亲手标注），同名旧 txt 被覆盖
- rectangle shape -> class 0（塑料瓶），像素坐标按图片尺寸归一化
- 无 shapes（空标注）-> 空 txt（负样本）
- json 的 imagePath 对应图片不存在时跳过并告警

用法：
    python scripts/convert_anylabeling.py
"""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
IMG_DIR = ROOT / "datasets" / "handheld-bottles" / "images" / "webcap"
LBL_DIR = ROOT / "datasets" / "handheld-bottles" / "labels"
TARGET_CN = "塑料瓶"


def main() -> int:
    LBL_DIR.mkdir(parents=True, exist_ok=True)
    jsons = sorted(IMG_DIR.glob("*.json"))
    if not jsons:
        print("未找到 json 标注")
        return 1

    converted = empty = skipped = 0
    for jf in jsons:
        stem = jf.stem
        img_path = IMG_DIR / f"{stem}.jpg"
        if not img_path.exists():
            print(f"⚠ {jf.name} 无对应图片，跳过")
            skipped += 1
            continue
        data = json.loads(jf.read_text(encoding="utf-8"))
        with Image.open(img_path) as im:
            W, H = im.size
        shapes = [s for s in data.get("shapes", [])
                  if s.get("label") == TARGET_CN and len(s.get("points", [])) >= 2]
        out = LBL_DIR / f"{stem}.txt"
        if not shapes:
            out.write_text("", encoding="utf-8")
            empty += 1
            continue
        lines = []
        for s in shapes:
            pts = s["points"]
            xs = [float(p[0]) for p in pts]
            ys = [float(p[1]) for p in pts]
            x1, x2 = max(0.0, min(xs)), min(float(W), max(xs))
            y1, y2 = max(0.0, min(ys)), min(float(H), max(ys))
            if x2 - x1 < 4 or y2 - y1 < 4:
                continue  # 过小无效框丢弃
            cx, cy = (x1 + x2) / 2 / W, (y1 + y2) / 2 / H
            bw, bh = (x2 - x1) / W, (y2 - y1) / H
            lines.append(f"0 {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
        out.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        converted += 1

    print(f"转换完成: 有框 {converted} / 空标注 {empty} / 跳过 {skipped}")
    # 校验图片标签配对
    imgs = list(IMG_DIR.glob("*.jpg"))
    missing = [p.stem for p in imgs if not (LBL_DIR / f"{p.stem}.txt").exists()]
    print(f"webcap 图片 {len(imgs)} 张，缺标签 {len(missing)} 张"
          + (f": {missing[:5]}" if missing else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
