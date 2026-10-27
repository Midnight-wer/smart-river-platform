"""向阿里云百炼提交 Qwen2.5-VL LoRA 微调任务，并查询训练状态。

接口（DashScope 原生 REST）：
  1) 上传训练/评测数据集（zip）：POST {base}/files            -> file_id
  2) 创建微调任务：        POST {base}/fine-tuning/jobs      -> job_id
  3) 查询任务状态：        GET  {base}/fine-tuning/jobs/{id}

默认 dry-run，仅打印将要发送的请求；加 --submit 才真正调用（会产生训练费用）。
API Key 从环境变量 DASHSCOPE_API_KEY 读取，或用 --api-key 指定。

用法：
    python scripts/submit_finetune.py --train-zip datasets/output/qwen-plastic-bottle-train.zip \
                                     --eval-zip  datasets/output/qwen-plastic-bottle-eval.zip
    python scripts/submit_finetune.py --submit --wait
    python scripts/submit_finetune.py --status <job_id>
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, OUTPUT_DIR  # noqa: E402

DEFAULT_BASE = "https://dashscope.aliyuncs.com/api/v1"
DEFAULT_MODEL = "qwen2.5-vl-7b-instruct"


def resolve_base_url(explicit: str) -> str:
    """未显式指定时，优先使用 .env.local 中的 AI_API_TARGET（workspace 专属端点）。"""
    if explicit:
        return explicit
    env_file = ROOT.parent / ".env.local"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("AI_API_TARGET="):
                target = line.split("=", 1)[1].strip().rstrip("/")
                if target:
                    return f"{target}/api/v1"
    return DEFAULT_BASE


def http_json(url: str, method: str, api_key: str, payload: dict | None = None, timeout: int = 60) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "river-admin-ai-training",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"HTTP {error.code}: {detail}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"网络错误: {error}") from error


def upload_file(path: Path, api_key: str, base_url: str, purpose: str = "fine-tune") -> str:
    """上传 zip 数据集，返回 file_id。"""
    boundary = f"----riveradmin{uuid.uuid4().hex}"
    body = b""
    body += (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
        "Content-Type: application/zip\r\n\r\n"
    ).encode("utf-8")
    body += path.read_bytes()
    body += (
        f"\r\n--{boundary}\r\n"
        f'Content-Disposition: form-data; name="purpose"\r\n\r\n{purpose}\r\n'
        f"--{boundary}--\r\n"
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url}/files",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": "river-admin-ai-training",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=1800) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"上传失败 HTTP {error.code}: {detail}") from error
    # 兼容三种响应格式：
    #   OpenAI 风格 {"id": "file-ft-xxx"}
    #   DashScope 风格 {"data": {"uploaded_files": [{"file_id": "xxx"}]}}
    data = result.get("data") if isinstance(result.get("data"), dict) else {}
    uploaded = data.get("uploaded_files") or []
    file_id = (
        result.get("id")
        or result.get("file_id")
        or data.get("id")
        or next((f.get("file_id") for f in uploaded if isinstance(f, dict) and f.get("file_id")), None)
        or next((f.get("id") for f in uploaded if isinstance(f, dict) and f.get("id")), None)
    )
    if not file_id:
        raise RuntimeError(f"上传响应缺少 file_id: {json.dumps(result, ensure_ascii=False)[:300]}")
    return file_id


def create_job(api_key: str, base_url: str, model: str, train_id: str, eval_id: str | None,
               epoch: int, lora_rank: int, learning_rate: float) -> dict:
    """创建 LoRA（efficient_sft）微调任务。

    百炼 /api/v1/fine-tunes 接口采用 OpenAI 兼容风格：超参平铺在请求体顶层
    （n_epochs / learning_rate / lora_rank / lora_alpha），dataset 走 training_file_ids。
    """
    payload: dict = {
        "model": model,
        "training_type": "efficient_sft",
        "training_file_ids": [train_id],
        "n_epochs": epoch,
        "learning_rate": learning_rate,
        "lora_rank": lora_rank,
        "lora_alpha": lora_rank * 2,
        "hyper_parameters": {
            "epoch_size": epoch,
            "n_epochs": epoch,
            "learning_rate": learning_rate,
            "lora_rank": lora_rank,
            "lora_alpha": lora_rank * 2,
        },
    }
    if eval_id:
        payload["validation_file_ids"] = [eval_id]
    # 百炼的微调任务接口路径为 /api/v1/fine-tunes
    return http_json(f"{base_url}/fine-tunes", "POST", api_key, payload)


def get_job(api_key: str, base_url: str, job_id: str) -> dict:
    return http_json(f"{base_url}/fine-tunes/{job_id}", "GET", api_key)


def main() -> int:
    parser = argparse.ArgumentParser(description="提交百炼 Qwen2.5-VL LoRA 微调任务")
    parser.add_argument("--train-zip", default=str(OUTPUT_DIR / "qwen-plastic-bottle-train.zip"))
    parser.add_argument("--eval-zip", default=str(OUTPUT_DIR / "qwen-plastic-bottle-eval.zip"))
    parser.add_argument("--base-url", default="", help="API 根地址，默认取 .env.local 的 AI_API_TARGET")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--api-key", default=os.environ.get("DASHSCOPE_API_KEY", ""))
    parser.add_argument("--epoch", type=int, default=2)
    parser.add_argument("--lora-rank", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=1e-5)
    parser.add_argument("--submit", action="store_true", help="真正提交（会产生费用），默认 dry-run")
    parser.add_argument("--wait", action="store_true", help="提交后轮询任务状态")
    parser.add_argument("--status", help="仅查询指定 job_id 状态")
    parser.add_argument("--train-file-id", default="", help="复用已上传的训练集 file_id（跳过上传）")
    parser.add_argument("--eval-file-id", default="", help="复用已上传的评测集 file_id（跳过上传）")
    args = parser.parse_args()
    base_url = resolve_base_url(args.base_url)

    api_key = args.api_key
    if not api_key:
        # 回退读取 .env.local 中的 AI_API_KEY
        env_file = ROOT.parent / ".env.local"
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if line.startswith("AI_API_KEY="):
                    api_key = line.split("=", 1)[1].strip()
                    break
    if not api_key:
        print("!! 未提供 API Key：请设置环境变量 DASHSCOPE_API_KEY 或在 .env.local 中配置 AI_API_KEY\n")

    if args.status:
        if not api_key:
            print("查询任务状态需要 API Key")
            return 1
        result = get_job(api_key, base_url, args.status)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    train_zip = Path(args.train_zip)
    eval_zip = Path(args.eval_zip)
    if not train_zip.exists():
        print(f"!! 训练集不存在: {train_zip}\n   请先执行: python scripts/build_qwen_jsonl.py")
        return 1

    print("== 训练配置 ==")
    print(f"api base        : {base_url}")
    print(f"base model      : {args.model}")
    print(f"training type   : efficient_sft (LoRA)")
    print(f"train zip       : {train_zip} ({train_zip.stat().st_size / 1024 / 1024:.1f} MB)")
    if eval_zip.exists():
        print(f"eval zip        : {eval_zip} ({eval_zip.stat().st_size / 1024 / 1024:.1f} MB)")
    print(f"hyper parameters: epoch={args.epoch} lora_rank={args.lora_rank} lr={args.learning_rate}")

    if not args.submit:
        print("\n[dry-run] 未实际提交。确认无误后追加 --submit 执行训练。")
        print("[dry-run] 将依次调用: POST /files -> POST /fine-tuning/jobs")
        return 0

    if not api_key:
        print("!! 实际提交需要 API Key")
        return 1

    try:
        train_id = args.train_file_id
        eval_id = args.eval_file_id
        if not train_id:
            print("\n上传训练集 ...")
            train_id = upload_file(train_zip, api_key, base_url)
            print(f"  train file_id = {train_id}")
        else:
            print(f"\n复用已上传训练集 file_id = {train_id}")
        if not eval_id and eval_zip.exists():
            print("上传评测集 ...")
            eval_id = upload_file(eval_zip, api_key, base_url)
            print(f"  eval  file_id = {eval_id}")

        print("创建微调任务 ...")
        job = create_job(api_key, base_url, args.model, train_id, eval_id,
                          args.epoch, args.lora_rank, args.learning_rate)
        job_id = job.get("id") or job.get("job_id")
        print(f"  job_id = {job_id}")
        print(json.dumps(job, ensure_ascii=False, indent=2)[:800])
        print("\n训练完成后，把自定义模型名填入 .env.local：")
        print(f"  VITE_AI_VISION_MODEL=<自定义模型名>")

        if args.wait and job_id:
            print("\n轮询任务状态 ...")
            while True:
                state = get_job(api_key, base_url, job_id)
                status = state.get("status") or state.get("data", {}).get("status")
                print(f"  [{time.strftime('%H:%M:%S')}] status={status}")
                if status in ("succeeded", "failed", "stopped", "cancelled"):
                    print(json.dumps(state, ensure_ascii=False, indent=2)[:1200])
                    break
                time.sleep(30)
    except RuntimeError as error:
        message = str(error)
        if "InsufficientBalance" in message or "insufficient balance" in message.lower():
            print("\n!! 阿里云账户余额不足，训练任务未创建（数据已上传，不会丢失）")
            print("   处理方式（二选一）：")
            print("   A. 充值后重跑本命令（复用已上传数据集，无需重新上传 227MB）：")
            print(f"      python scripts/submit_finetune.py --submit --wait "
                  f"--train-file-id {train_id}" + (f" --eval-file-id {eval_id}" if eval_id else ""))
            print("   B. 降低规模以减少费用：--epoch 1（成本约减半）、或减少训练样本后重新 build_qwen_jsonl.py")
            return 2
        print(f"!! {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
