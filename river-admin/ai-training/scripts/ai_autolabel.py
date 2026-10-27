"""视觉大模型自动标注：对难标注帧调用 qwen3-vl-plus 输出塑料瓶外接框，生成 YOLO 标签。

用法：
    python scripts/ai_autolabel.py                    # 标注所有缺标签帧
    python scripts/ai_autolabel.py path/to/a.jpg ...  # 指定图片

流程：读 .env.local 的 AI_API_KEY -> MaaS OpenAI 兼容接口 -> JSON 框坐标 -> YOLO 标签
产物：labels/<stem>.txt + reports/ai_autolabel_<stem>.jpg（叠加核对图）
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
IMG_DIRS = [ROOT / "datasets" / "handheld-bottles" / "images",
            ROOT / "datasets" / "handheld-bottles" / "images" / "webcap"]
LBL = ROOT / "datasets" / "handheld-bottles" / "labels"
REP = ROOT / "datasets" / "handheld-bottles" / "reports"
ENV_FILE = ROOT.parent / ".env.local"

API_BASE = "https://ws-sam2wv6vqkfzq8rp.cn-beijing.maas.aliyuncs.com"
MODEL = "qwen3-vl-plus"

PROMPT = (
    "检测图中人物手持的塑料瓶/矿泉水瓶。注意：瓶子一定在人物手中（与手相连），"
    "瓶身为透明或带标签的细长塑料瓶。严禁把墙上的标牌、盾形标识、显示器、"
    "装饰物、人脸当目标。输出 JSON："
    '{"boxes":[{"bbox_2d":[x1,y1,x2,y2]}]}，'
    "坐标为原图像素，框须完整贴紧瓶身（从瓶盖到瓶底）。没有瓶子输出 {\"boxes\":[]}，"
    "只输出 JSON。"
)


def load_api_key() -> str:
    if os.environ.get("AI_API_KEY"):
        return os.environ["AI_API_KEY"]
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^AI_API_KEY=(.+)$", line.strip())
            if m:
                return m.group(1).strip()
    sys.exit("✗ 未找到 AI_API_KEY（环境变量或 river-admin/.env.local）")


def call_vlm(image_path: Path, key: str) -> list[tuple[float, float, float, float]]:
    data = base64.b64encode(image_path.read_bytes()).decode()
    body = json.dumps({
        "model": MODEL,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url",
                 "image_url": {"url": f"data:image/jpeg;base64,{data}"}},
                {"type": "text", "text": PROMPT},
            ],
        }],
    }).encode()
    req = urllib.request.Request(
        f"{API_BASE}/compatible-mode/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {key}"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read().decode())
    text = result["choices"][0]["message"]["content"]
    payload = json.loads(re.sub(r"^```json\s*|```$", "", text.strip()))
    return [tuple(float(v) for v in b["bbox_2d"]) for b in payload.get("boxes", [])]


def main() -> int:
    parser = argparse.ArgumentParser(description="视觉大模型自动标注")
    parser.add_argument("images", nargs="*", help="待标注图片（默认全部缺标签帧）")
    args = parser.parse_args()

    key = load_api_key()
    if args.images:
        todo = [Path(p) for p in args.images]
    else:
        all_imgs = [p for d in IMG_DIRS for p in sorted(d.glob("*.jpg"))]
        todo = [p for p in all_imgs if not (LBL / f"{p.stem}.txt").exists()]
    if not todo:
        print("没有缺标签的图片")
        return 0

    LBL.mkdir(parents=True, exist_ok=True)
    REP.mkdir(parents=True, exist_ok=True)
    print(f"待 AI 标注 {len(todo)} 张")
    for path in todo:
        try:
            boxes = call_vlm(path, key)
        except Exception as error:  # noqa: BLE001
            print(f"✗ {path.name}: {error}")
            continue
        with Image.open(path) as im:
            rgb = im.convert("RGB")
        W, H = rgb.size
        lines = []
        for x1, y1, x2, y2 in boxes:
            x1, x2 = sorted((max(0, min(x1, W)), max(0, min(x2, W))))
            y1, y2 = sorted((max(0, min(y1, H)), max(0, min(y2, H))))
            if x2 - x1 < 8 or y2 - y1 < 8:
                continue
            lines.append(f"0 {(x1+x2)/2/W:.6f} {(y1+y2)/2/H:.6f} "
                         f"{(x2-x1)/W:.6f} {(y2-y1)/H:.6f}")
            draw = ImageDraw.Draw(rgb)
            draw.rectangle([x1, y1, x2, y2], outline=(255, 40, 40), width=5)
        (LBL / f"{path.stem}.txt").write_text("\n".join(lines) + ("\n" if lines else ""),
                                              encoding="utf-8")
        rgb.thumbnail((760, 760), Image.LANCZOS)
        rgb.save(REP / f"ai_autolabel_{path.stem}.jpg", quality=88)
        print(f"✓ {path.name}: {len(lines)} 个框")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
