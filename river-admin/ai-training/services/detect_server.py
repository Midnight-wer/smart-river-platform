"""本地离线塑料瓶检测服务（Ultralytics YOLO + Python 标准库 HTTP 服务）。

完全离线运行：模型权重在本地，推理不访问任何外部网络。
仅依赖 ultralytics + torch（不依赖任何 Web 框架），便于拷贝到任意机器直接启动。

接口：
    GET  /health  -> {status, model, classes, offline}
    POST /detect  -> {taskId, model, elapsed, image, items}
    请求体：{"image": "<dataURL 或纯 base64>", "conf": 0.3}
    响应体 items 元素：{target, confidence, x, y, width, height}
        x/y 为目标中心点、width/height 为目标框尺寸，单位均为图片宽高百分比。

启动：
    python services/detect_server.py --port 8000
    python services/detect_server.py --weights runs/plastic-bottle-yolov8n/weights/best.pt
"""
from __future__ import annotations

import argparse
import base64
import binascii
import io
import json
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN_NAME = "plastic-bottle-yolov8n-640"
# 训练输出目录（ultralytics 会按 project/task 嵌套，逐一探测）
RUN_CANDIDATES = [
    ROOT / "runs" / RUN_NAME,
    ROOT / "runs" / "detect" / "runs" / RUN_NAME,
    ROOT / "runs" / RUN_NAME / "runs" / RUN_NAME,
    ROOT / "runs" / "detect" / "runs" / "plastic-bottle-yolov8n",
    ROOT / "runs" / "plastic-bottle-yolov8n",
]
ONNX_MODEL = ROOT / "models" / "plastic-bottle.onnx"
# 近景专用模型（当前目标：只识别近景塑料瓶），存在时优先加载
NEAR_MODEL = ROOT / "models" / "plastic-bottle-near.pt"
NEAR_ONNX = ROOT / "models" / "plastic-bottle-near.onnx"
TFLITE_MODEL = ROOT / "models" / "model-export_iod_tflite-pbset2_20200812060539-2020-08-20T11_27_42.436Z_model.tflite"
FALLBACK_WEIGHTS = Path("yolov8n.pt")
TARGET_CN = "塑料瓶"

_model = None
_model_path: Path | None = None
_model_name = "unknown"
_backend = "ultralytics"
_device = "cpu"


def load_model(weights: Path | None = None, backend: str = "auto") -> None:
    """加载检测模型。

    backend:
        auto       —— 优先 OpenVINO（Intel 核显/NPU 加速），其次自训 best.pt，最后官方 yolov8n.pt
        openvino   —— 强制使用 OpenVINO 推理（GPU -> NPU -> CPU 自动选择）
        tflite     —— 强制使用 TFLite 模型（加载失败则回退到 YOLO）
        ultralytics—— 强制使用 YOLO (.pt/.onnx)
    """
    global _model, _model_path, _model_name, _backend, _device
    from ultralytics import YOLO

    if backend == "tflite" and TFLITE_MODEL.exists():
        try:
            from tflite_detector import TfliteBottleDetector

            _model = TfliteBottleDetector(TFLITE_MODEL)
            _model_path = TFLITE_MODEL
            _model_name = "tflite-plastic-bottle"
            _backend = "tflite"
            print(f"[detect] 已加载 TFLite 模型: {TFLITE_MODEL}", flush=True)
            return
        except Exception as exc:  # TFLite 运行时不可用时回退，不影响服务启动
            print(f"[detect] TFLite 模型加载失败，回退到 YOLO: {exc}", flush=True)

    if backend in ("auto", "openvino"):
        onnx_candidates = [p for p in (NEAR_ONNX, ONNX_MODEL) if p.exists()]
        if weights and Path(weights).suffix == ".onnx":
            onnx_candidates.insert(0, Path(weights))
        for candidate in onnx_candidates:
            try:
                from openvino_detector import OpenVinoBottleDetector

                _model = OpenVinoBottleDetector(candidate)
                _model_path = candidate
                _model_name = f"openvino:{candidate.stem}"
                _backend = "openvino"
                _device = _model.device
                print(f"[detect] 已加载 OpenVINO 模型: {candidate}（设备 {_model.device}，输入 {_model.imgsz}）", flush=True)
                return
            except Exception as exc:  # noqa: BLE001
                print(f"[detect] OpenVINO 加载失败，回退到 PyTorch: {exc}", flush=True)

    candidates: list[Path] = []
    if weights:
        candidates.append(Path(weights))
    candidates.append(NEAR_MODEL)
    for run_dir in RUN_CANDIDATES:
        candidates.append(run_dir / "weights" / "best.pt")
    candidates.append(ONNX_MODEL)
    candidates.append(FALLBACK_WEIGHTS)

    for candidate in candidates:
        if candidate.exists():
            _model = YOLO(str(candidate))
            _model_path = candidate
            _model_name = candidate.stem
            _backend = "ultralytics"
            print(f"[detect] 已加载 YOLO 模型: {candidate}", flush=True)
            return
    raise SystemExit("未找到模型权重，请先训练或用 --weights 指定")


def decode_image(payload: str, max_edge: int = 1280):
    """解析 dataURL 或纯 base64 图片；超大图按最长边缩放（提速，不影响目标比例）。"""
    from PIL import Image

    raw = payload.strip()
    if raw.startswith("data:"):
        raw = raw.split(",", 1)[1]
    raw = raw.replace("\n", "")
    padding = (-len(raw)) % 4
    try:
        data = base64.b64decode(raw + "=" * padding)
    except (binascii.Error, ValueError) as error:
        raise ValueError(f"图片 base64 解码失败: {error}") from error
    image = Image.open(io.BytesIO(data)).convert("RGB")
    if max_edge and max(image.size) > max_edge:
        ratio = max_edge / max(image.size)
        image = image.resize(
            (max(1, int(image.width * ratio)), max(1, int(image.height * ratio))),
            Image.LANCZOS,
        )
    return image


def detect(image, conf: float) -> list[dict]:
    """执行推理并返回百分比坐标的目标列表。"""
    if _backend == "tflite":
        return _model.detect(image, conf)
    if _backend == "openvino":
        import cv2
        import numpy as np

        array = np.asarray(image)  # PIL 为 RGB，OpenCV 需要 BGR
        bgr = cv2.cvtColor(array, cv2.COLOR_RGB2BGR)
        return _model.detect(bgr, conf)
    width, height = image.size
    results = _model.predict(source=image, conf=conf, verbose=False)
    items: list[dict] = []
    for result in results:
        for box in result.boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            items.append({
                "target": TARGET_CN,
                "confidence": round(float(box.conf), 3),
                "x": round(((x1 + x2) / 2) / width * 100, 2),
                "y": round(((y1 + y2) / 2) / height * 100, 2),
                "width": round((x2 - x1) / width * 100, 2),
                "height": round((y2 - y1) / height * 100, 2),
            })
    return items


class DetectHandler(BaseHTTPRequestHandler):
    server_version = "RiverBottleDetect/1.0"

    def _send(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/health"):
            self._send({
                "status": "ok",
                "model": _model_name,
                "weights": str(_model_path) if _model_path else None,
                "backend": _backend,
                "device": _device,
                "classes": [TARGET_CN],
                "offline": True,
            })
        else:
            self._send({"error": "接口不存在"}, 404)

    def do_POST(self) -> None:  # noqa: N802
        if not self.path.startswith("/detect"):
            self._send({"error": "接口不存在"}, 404)
            return
        length = int(self.headers.get("Content-Length") or 0)
        try:
            request = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            self._send({"error": "请求体不是合法 JSON"}, 400)
            return

        started = time.perf_counter()
        try:
            image = decode_image(str(request.get("image", "")))
        except Exception as error:  # noqa: BLE001
            self._send({"error": f"图片解析失败: {error}", "items": []}, 400)
            return

        conf = float(request.get("conf") or 0.35)
        items = detect(image, conf)
        width, height = image.size
        self._save_capture(image, request.get("scene"))
        self._send({
            "taskId": f"LOCAL{uuid.uuid4().hex[:6].upper()}",
            "model": _model_name,
            "elapsed": int((time.perf_counter() - started) * 1000),
            "image": {"width": width, "height": height},
            "items": items,
        })

    CAPTURE_DIR = Path(__file__).resolve().parents[1] / "datasets" / "handheld-bottles" / "images" / "webcap"
    _capture_lock = threading.Lock()
    _capture_last = 0.0
    CAPTURE_INTERVAL = 3.0  # 限频：每 3 秒最多保存 1 帧

    def _save_capture(self, image, scene) -> None:
        """把实时识别帧落盘作标注素材（webcap 目录，仅 scene=camera，3 秒 1 帧限频）。"""
        try:
            if str(scene or "") != "camera":
                return
            now = time.time()
            with DetectHandler._capture_lock:
                if now - DetectHandler._capture_last < DetectHandler.CAPTURE_INTERVAL:
                    return
                DetectHandler._capture_last = now
            self.CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
            stamp = time.strftime("%H%M%S")
            name = f"webcap_{stamp}_{uuid.uuid4().hex[:4]}.jpg"
            image.convert("RGB").save(self.CAPTURE_DIR / name, quality=90)
        except Exception:  # noqa: BLE001
            pass

    def log_message(self, fmt: str, *args) -> None:  # 静音默认访问日志
        return


def main() -> None:
    parser = argparse.ArgumentParser(description="本地离线塑料瓶检测服务")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--weights", default="", help="模型权重路径（默认用训练产物）")
    parser.add_argument("--backend", default="auto",
                        choices=["auto", "openvino", "tflite", "ultralytics"],
                        help="推理后端：auto 优先 OpenVINO（Intel 核显/NPU）")
    args = parser.parse_args()

    load_model(Path(args.weights) if args.weights else None, args.backend)
    server = ThreadingHTTPServer((args.host, args.port), DetectHandler)
    print(f"[detect] 本地离线服务已启动: http://{args.host}:{args.port}  (不访问外网)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[detect] 服务已停止")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
