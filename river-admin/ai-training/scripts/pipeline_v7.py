"""v7 流水线：训练 -> 门禁评测 -> 报告落盘。

由 Start-Process 脱离终端启动，日志重定向到 v7_train.log / v7_train.err。
门禁不达标时保留 v6 线上权重，报告见 scripts/v7_gates_report.txt。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(label: str, script: str) -> int:
    print(f"\n########## {label}: {script} ##########", flush=True)
    r = subprocess.run([sys.executable, script], cwd=str(ROOT))
    print(f"########## {label} 退出码 {r.returncode} ##########", flush=True)
    return r.returncode


def main() -> int:
    rc_train = run("训练", "scripts/train_handheld_v7.py")
    if rc_train != 0:
        print("训练失败，跳过门禁", flush=True)
        return rc_train
    return run("门禁", "scripts/eval_v7_gates.py")


if __name__ == "__main__":
    raise SystemExit(main())
