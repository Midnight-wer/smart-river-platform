"""推理侧测试脚本：验证识别结果中只可能出现「塑料瓶」。

通过本地 dev server 的 /ai-api 代理调用真实视觉模型（Key 由代理注入），
使用与前端一致的提示词与本地标签库白名单，断言：
  - 模型输出中不存在塑料瓶以外的类别（提示词 + 白名单双重约束）；
  - 应用白名单过滤后，剩余目标全部为塑料瓶。

用法：
    python scripts/test_inference.py <图片路径> [更多图片...]
    python scripts/test_inference.py --url http://localhost:5173/ai-api
"""
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CONFIG_DIR, load_label_db, read_image_size  # noqa: E402

DEFAULT_URL = "http://localhost:5173/ai-api/chat/completions"


def normalize(name: str) -> str:
    return name.strip().lower().replace("-", "_").replace(" ", "_")


def data_url(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def call_model(url: str, model: str, image: Path, prompt: str, timeout: int = 90) -> str:
    payload = {
        "model": model,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": data_url(image)}},
                {"type": "text", "text": prompt},
            ],
        }],
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as error:
        raise RuntimeError(f"请求失败（dev server 是否已启动且配置了 AI_API_KEY？）: {error}") from error
    return result["choices"][0]["message"]["content"] or ""


def parse_objects(content: str) -> list[dict]:
    start, end = content.find("{"), content.rfind("}")
    if start == -1 or end <= start:
        return []
    try:
        parsed = json.loads(content[start:end + 1])
    except json.JSONDecodeError:
        return []
    objects = parsed.get("objects") if isinstance(parsed, dict) else None
    return objects if isinstance(objects, list) else []


def main() -> int:
    parser = argparse.ArgumentParser(description="推理侧测试：验证只识别塑料瓶")
    parser.add_argument("images", nargs="+", help="待测试图片路径")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--model", default="qwen3-vl-plus")
    args = parser.parse_args()

    label_db = load_label_db()
    aliases = {normalize(a) for a in label_db["aliases"]}
    prompts = json.loads((CONFIG_DIR / "prompts.json").read_text(encoding="utf-8"))
    prompt = prompts["inference_prompt"]

    passed = True
    for raw_path in args.images:
        image = Path(raw_path)
        if not image.exists():
            print(f"跳过（不存在）: {image}")
            continue
        print(f"\n=== {image.name} ===")
        try:
            content = call_model(args.url, args.model, image, prompt)
        except RuntimeError as error:
            print(f"  ✗ {error}")
            passed = False
            continue
        objects = parse_objects(content)
        raw_targets = [str(o.get("target", "")).strip() for o in objects]
        kept = [o for o in objects if normalize(str(o.get("target", ""))) in aliases]
        # 与前端一致：坐标单位自适应（模型偶尔返回像素坐标）
        width, height = read_image_size(image)
        print(f"  模型输出目标: {raw_targets or '（无）'}")
        for obj in kept:
            x, y, w, h = (float(obj.get(k, 0)) for k in ("x", "y", "width", "height"))
            if max(x, y) > 100 or max(w, h) > 60:
                if width and height:
                    x, y = x / width * 100, y / height * 100
                    w, h = w / width * 100, h / height * 100
            print(f"    ✓ 保留  {obj.get('target')} conf={obj.get('confidence')} "
                  f"@({x:.1f},{y:.1f}) {w:.1f}x{h:.1f}%")
        non_bottle = [t for t in raw_targets if normalize(t) not in aliases]
        if non_bottle:
            print(f"  ! 模型原始输出含非塑料瓶目标（已被本地标签库过滤）: {non_bottle}")
        passed &= check_result(len(kept) == len(objects),
                                f"过滤后全部为塑料瓶（{len(kept)}/{len(objects)}）")

    print("\n结果: " + ("全部通过" if passed else "存在失败项"))
    return 0 if passed else 1


def check_result(condition: bool, message: str) -> bool:
    print(("  ✓ " if condition else "  ✗ ") + message)
    return condition


if __name__ == "__main__":
    raise SystemExit(main())
