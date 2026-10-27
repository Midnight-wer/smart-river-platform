"""更新 .env.local 中的百炼 API Key，并可一键重启开发服务器。

流程：备份 → 写入新 Key → 调用模型列表接口校验 → 失败自动回滚 → 可选重启 dev server。

用法：
    python scripts/update_api_key.py --key sk-xxx
    python scripts/update_api_key.py --key sk-xxx --restart
    python scripts/update_api_key.py --key sk-xxx --target https://xxx.cn-beijing.maas.aliyuncs.com

Key 可从环境变量 BAILIAN_API_KEY 读取（避免出现在命令历史里）：
    $env:BAILIAN_API_KEY="sk-xxx"; python scripts/update_api_key.py --key $env:BAILIAN_API_KEY
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env.local"
KEY_PATTERN = re.compile(r"^AI_API_KEY=.*$", re.MULTILINE)
TARGET_PATTERN = re.compile(r"^AI_API_TARGET=.*$", re.MULTILINE)


def mask(key: str) -> str:
    """脱敏显示：仅保留首尾 4 位。"""
    if len(key) <= 12:
        return "***"
    return f"{key[:4]}***{key[-4:]}"


def read_env(path: Path) -> str:
    if not path.exists():
        raise SystemExit(f"未找到 {path}")
    return path.read_text(encoding="utf-8")


def get_target(text: str) -> str:
    match = TARGET_PATTERN.search(text)
    return match.group(0).split("=", 1)[1].strip() if match else ""


def verify_key(key: str, target: str, timeout: int = 25) -> tuple[bool, str]:
    """调用模型列表接口校验 Key 是否可用。"""
    if not target:
        return False, "未配置 AI_API_TARGET"
    url = f"{target.rstrip('/')}/compatible-mode/v1/models"
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
        count = len(data.get("data", []))
        return True, f"校验通过，可用模型 {count} 个"
    except urllib.error.HTTPError as error:
        return False, f"校验失败 HTTP {error.code}: {error.read().decode('utf-8', 'ignore')[:160]}"
    except Exception as error:  # noqa: BLE001
        return False, f"校验失败: {error}"


def restart_dev_server(port: int = 5173) -> bool:
    """结束占用端口的 dev server 并重新启动。"""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"$c = Get-NetTCPConnection -LocalPort {port} -State Listen -ErrorAction SilentlyContinue; "
             f"if ($c) {{ $c | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object "
             f"{{ Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }} }}"],
            capture_output=True, timeout=60,
        )
        if result.returncode != 0:
            print(f"  ! 结束旧进程失败: {result.stderr.decode('utf-8', 'ignore')[:160]}")
    except Exception as error:  # noqa: BLE001
        print(f"  ! 结束旧进程异常: {error}")
    time.sleep(2)

    log = PROJECT_ROOT / "ai-training" / "datasets" / "dev-server.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w", encoding="utf-8") as handle:
        subprocess.Popen(
            ["npm", "run", "dev"], cwd=str(PROJECT_ROOT),
            stdout=handle, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
    time.sleep(6)
    try:
        with urllib.request.urlopen(f"http://localhost:{port}/", timeout=8) as response:
            return response.status == 200
    except Exception:  # noqa: BLE001
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="更新 .env.local 中的百炼 API Key")
    parser.add_argument("--key", default=os.environ.get("BAILIAN_API_KEY", ""), help="新的 API Key")
    parser.add_argument("--target", default="", help="同时更新 AI_API_TARGET（可选）")
    parser.add_argument("--restart", action="store_true", help="更新后重启 dev server")
    args = parser.parse_args()

    if not args.key:
        print("!! 请通过 --key 或环境变量 BAILIAN_API_KEY 提供新 Key")
        return 1
    if not args.key.startswith("sk-"):
        print("!! Key 格式异常（应以 sk- 开头）")
        return 1

    text = read_env(ENV_FILE)
    target = args.target or get_target(text)
    print(f"目标端点: {target}")
    print(f"新 Key   : {mask(args.key)}")

    ok, message = verify_key(args.key, target)
    print(f"校验     : {message}")
    if not ok:
        print("!! 校验未通过，.env.local 未做任何修改")
        return 1

    # 备份放在 datasets/ 下（已被 .gitignore 忽略），避免含密钥的备份被提交
    backup_dir = PROJECT_ROOT / "ai-training" / "datasets"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / ".env.local.bak"
    shutil.copyfile(ENV_FILE, backup)
    print(f"已备份   : {backup}")

    new_text = KEY_PATTERN.sub(f"AI_API_KEY={args.key}", text)
    if args.target:
        new_text = TARGET_PATTERN.sub(f"AI_API_TARGET={args.target}", new_text)
    ENV_FILE.write_text(new_text, encoding="utf-8")
    print("已写入   : .env.local")

    if args.restart:
        print("重启 dev server ...")
        if restart_dev_server():
            print("重启成功：http://localhost:5173/")
        else:
            print("! 重启后探测失败，请检查 ai-training/datasets/dev-server.log")
            return 1
    else:
        print("提示：加 --restart 可自动重启 dev server 使配置生效")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
