"""v3 端到端对比测试：v1 备份权重（离线推理） vs v3 线上服务，跑未入训练集的手持瓶图。

测试集：
  - assets/probe-bottle-hand.jpg        手持探针（v1 conf 0.566）
  - datasets/.../images/seed_office_01.png  用户实拍办公室斜握瓶（v1 时代 0 检出）
  - hybrid val 中手持瓶帧               未入训练集的抓拍帧
  - webcap 新增未标注帧                 最新抓拍

用法：python scripts/v3_test.py    （在 after_handheld_v3 流水线完成后运行）
产物：logs/v3-test.log 内容 + reports/v3_test_*.jpg 叠加图
"""
from __future__ import annotations

import base64
import json
import sys
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
V1 = ROOT / "models" / "plastic-bottle-handheld-v1.pt"
HYB_VAL = ROOT / "datasets" / "hybrid" / "images" / "val"
WEBCAP = ROOT / "datasets" / "handheld-bottles" / "images" / "webcap"
HAND_LBL = ROOT / "datasets" / "handheld-bottles" / "labels"
OUT = ROOT / "reports"


def service_detect(path: Path, conf: float = 0.25) -> list[dict]:
    b = base64.b64encode(path.read_bytes()).decode()
    req = urllib.request.Request(
        "http://127.0.0.1:8000/detect",
        data=json.dumps({"image": "data:image/jpeg;base64," + b, "conf": conf}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read().decode())["items"]


def offline_detect(model, path: Path, conf: float = 0.25) -> list[dict]:
    r = model.predict(str(path), conf=conf, imgsz=640, verbose=False)[0]
    W = r.orig_img.shape[1]
    H = r.orig_img.shape[0]
    items = []
    for b in r.boxes:
        x1, y1, x2, y2 = [float(v) for v in b.xyxy[0]]
        items.append({"confidence": round(float(b.conf), 3),
                      "x": (x1 + x2) / 2 / W * 100, "y": (y1 + y2) / 2 / H * 100,
                      "width": (x2 - x1) / W * 100, "height": (y2 - y1) / H * 100})
    return items


def save_overlay(path: Path, items: list[dict], tag: str) -> None:
    im = Image.open(path).convert("RGB")
    W, H = im.size
    d = ImageDraw.Draw(im)
    for i in items:
        x1 = (i["x"] - i["width"] / 2) / 100 * W
        y1 = (i["y"] - i["height"] / 2) / 100 * H
        x2 = (i["x"] + i["width"] / 2) / 100 * W
        y2 = (i["y"] + i["height"] / 2) / 100 * H
        d.rectangle([x1, y1, x2, y2], outline=(0, 220, 0), width=6)
        d.text((x1, max(0, y1 - 20)), f"{i['confidence']:.2f}", fill=(0, 220, 0))
    im.thumbnail((900, 900), Image.LANCZOS)
    OUT.mkdir(exist_ok=True)
    im.save(OUT / f"v3_test_{tag}.jpg", quality=88)


def main() -> int:
    from ultralytics import YOLO

    probes = [ROOT / "assets" / "probe-bottle-hand.jpg",
              ROOT / "datasets" / "handheld-bottles" / "images" / "seed_office_01.png"]
    # val 手持瓶帧（未入训练集）
    probes += sorted(HYB_VAL.glob("webcap_*.jpg"))[:10]
    probes += sorted(HYB_VAL.glob("raw_*.jpg"))[:6]
    # 新增未标注抓拍帧
    probes += [p for p in sorted(WEBCAP.glob("webcap_*.jpg"))
               if not (HAND_LBL / f"{p.stem}.txt").exists()][:6]
    probes = [p for p in probes if p.exists()]
    print(f"测试集 {len(probes)} 张（探针2 + val16 + 新抓拍若干）")

    v1_model = YOLO(str(V1)) if V1.exists() else None
    if v1_model is None:
        print("⚠ v1 备份权重缺失，只测 v3")

    v1_hits = v3_hits = total = 0
    for p in probes:
        try:
            v3_items = service_detect(p)
        except Exception as error:  # noqa: BLE001
            print(f"✗ 服务调用失败 {p.name}: {error}")
            return 2
        v1_items = offline_detect(v1_model, p) if v1_model else []
        total += 1
        v3_ok = bool(v3_items)
        v1_ok = bool(v1_items)
        v1_hits += v1_ok
        v3_hits += v3_ok
        flag = ""
        if v3_ok and not v1_ok:
            flag = "  ← v3 新检出"
        elif not v3_ok and v1_ok:
            flag = "  ← v3 丢失"
        v3c = max((i["confidence"] for i in v3_items), default=0)
        v1c = max((i["confidence"] for i in v1_items), default=0)
        print(f"{p.name[:28]:30s} v1={'✓' if v1_ok else '✗'}({v1c:.2f})  "
              f"v3={'✓' if v3_ok else '✗'}({v3c:.2f}){flag}")
        if v3_ok:
            save_overlay(p, v3_items, p.stem[:24])

    print(f"\n合计 {total} 张：v1 检出 {v1_hits}（{v1_hits/total:.0%}），"
          f"v3 检出 {v3_hits}（{v3_hits/total:.0%}）")
    print("PASS" if v3_hits >= max(v1_hits, int(total * 0.8)) else "NEED-MORE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
