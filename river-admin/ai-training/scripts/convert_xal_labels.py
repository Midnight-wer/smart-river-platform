"""将 X-AnyLabeling 人工修正的 webcap 标注（labelme JSON）转为 YOLO txt。

判定「人工修正」：JSON 修改时间晚于自动标注批次结束（2026-10-23 16:54:45）。
输出：
    datasets/handheld-bottles/labels-xal/{stem}.txt   YOLO 格式，单类 0=塑料瓶
    datasets/handheld-bottles/labels-xal/corrected-list.txt  清单（复现用）

用法：
    python scripts/convert_xal_labels.py
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMG_DIR = ROOT / "datasets" / "handheld-bottles" / "images" / "webcap"
OUT = ROOT / "datasets" / "handheld-bottles" / "labels-xal"
# 自动标注批次于 16:54:26~30 写盘，人工修正最早 16:54:51
CUTOFF = datetime.datetime(2026, 10, 23, 16, 54, 45).timestamp()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    names: list[str] = []
    n_pos = 0
    for jf in sorted(IMG_DIR.glob("*.json")):
        if jf.stat().st_mtime <= CUTOFF:
            continue  # 未修正的自动标注，不入 v7
        j = json.loads(jf.read_text(encoding="utf-8"))
        w_img, h_img = j["imageWidth"], j["imageHeight"]
        lines = []
        for s in j["shapes"]:
            if s["label"] != "塑料瓶":
                continue
            xs = [p[0] for p in s["points"]]
            ys = [p[1] for p in s["points"]]
            x1, x2, y1, y2 = min(xs), max(xs), min(ys), max(ys)
            bw, bh = (x2 - x1) / w_img, (y2 - y1) / h_img
            if bw <= 0 or bh <= 0:
                continue
            cx, cy = (x1 + x2) / 2 / w_img, (y1 + y2) / 2 / h_img
            lines.append(f"0 {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
        (OUT / f"{jf.stem}.txt").write_text(
            "\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        names.append(jf.stem)
        if lines:
            n_pos += 1
    (OUT / "corrected-list.txt").write_text("\n".join(names), encoding="utf-8")
    print(f"转换完成：{len(names)} 张（正样本 {n_pos}，负样本 {len(names) - n_pos}）")
    print(f"输出目录：{OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
