"""快速验证：把探针图片送入本地检测服务，打印检出与框选情况。

用法：
    python scripts/verify_probe.py                          # 默认验证手持瓶探针图
    python scripts/verify_probe.py a.jpg b.jpg             # 验证任意图片
    python scripts/verify_probe.py --conf 0.25
"""
from __future__ import annotations

import argparse
import base64
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URL = "http://127.0.0.1:8000/detect"
DEFAULT_PROBE = ROOT / "assets" / "probe-bottle-hand.jpg"


def detect(path: Path, conf: float) -> list[dict]:
    b = base64.b64encode(path.read_bytes()).decode()
    payload = {"image": "data:image/jpeg;base64," + b, "conf": conf}
    req = urllib.request.Request(
        URL, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read().decode())["items"]


def main() -> int:
    parser = argparse.ArgumentParser(description="探针图片快速验证")
    parser.add_argument("images", nargs="*", help="待验证图片（默认用手持瓶探针图）")
    parser.add_argument("--conf", type=float, default=0.25)
    args = parser.parse_args()

    paths = [Path(p) for p in args.images] or [DEFAULT_PROBE]
    for path in paths:
        if not path.exists():
            print(f"✗ 图片不存在: {path}")
            continue
        items = detect(path, args.conf)
        print(f"{path.name}: 检出 {len(items)} 个")
        for i in items:
            print(f"  conf={i['confidence']:.3f}  框 x={i['x']:.1f}% y={i['y']:.1f}% "
                  f"w={i['width']:.1f}% h={i['height']:.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
