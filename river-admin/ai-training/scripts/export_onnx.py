"""导出训练好的 YOLO 权重为 ONNX，并用 onnxruntime 做一次冒烟验证。

ONNX 版推理更快、依赖更少（仅 onnxruntime），适合离线部署到目标机器。

用法：
    python scripts/export_onnx.py
    python scripts/export_onnx.py --weights runs/plastic-bottle-yolov8n/weights/best.pt --imgsz 640
"""
from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))


def main() -> int:
    parser = argparse.ArgumentParser(description="导出 YOLO 权重为 ONNX")
    parser.add_argument("--weights", default=str(ROOT / "runs" / "plastic-bottle-yolov8n" / "weights" / "best.pt"))
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--output", default=str(ROOT / "models" / "plastic-bottle.onnx"))
    args = parser.parse_args()

    weights = Path(args.weights)
    if not weights.exists():
        print(f"未找到权重: {weights}\n请先完成训练")
        return 1

    from ultralytics import YOLO

    model = YOLO(str(weights))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    print(f"导出 ONNX: {weights} -> {output}")
    exported = model.export(format="onnx", imgsz=args.imgsz, opset=12, simplify=True)
    # ultralytics 会把 onnx 落在权重同目录，这里统一搬到 --output 指定位置
    exported_path = Path(str(exported)) if exported else weights.with_suffix(".onnx")
    if exported_path.exists() and exported_path.resolve() != output.resolve():
        shutil.copyfile(exported_path, output)
    if not output.exists():
        print("!! 导出未生成文件")
        return 1
    print(f"ONNX 大小: {output.stat().st_size / 1024 / 1024:.1f} MB")

    # 用 onnxruntime 跑一次推理，确认可用
    try:
        import numpy as np
        import onnxruntime as ort

        session = ort.InferenceSession(str(output), providers=["CPUExecutionProvider"])
        input_name = session.get_inputs()[0].name
        shape = session.get_inputs()[0].shape
        height = int(shape[2]) if isinstance(shape[2], int) else args.imgsz
        width = int(shape[3]) if isinstance(shape[3], int) else args.imgsz
        dummy = np.zeros((1, 3, height, width), dtype=np.float32)
        started = time.perf_counter()
        session.run(None, {input_name: dummy})
        print(f"onnxruntime 冒烟通过（输入 {height}x{width}，单次推理 {int((time.perf_counter() - started) * 1000)}ms）")
    except Exception as error:  # noqa: BLE001
        print(f"! onnxruntime 验证失败: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
