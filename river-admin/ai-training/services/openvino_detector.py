"""OpenVINO 推理后端：优先用 Intel 核显 / NPU 做离线检测。

与 ultralytics 后端输出保持一致：目标框为「中心点 + 尺寸」，单位是图片宽高的百分比。
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

TARGET_CN = "塑料瓶"


class OpenVinoBottleDetector:
    """用 OpenVINO 编译 YOLO ONNX，并在 GPU / NPU / CPU 上做推理。"""

    def __init__(self, model_path: str | Path, device: str = "auto", conf: float = 0.25):
        import cv2
        import openvino as ov
        from openvino import Tensor

        self._cv2 = cv2
        self._Tensor = Tensor
        self.model_path = Path(model_path)
        self.core = ov.Core()

        available = self.core.available_devices
        if device == "auto":
            for candidate in ("GPU", "NPU", "CPU"):
                if candidate in available:
                    device = candidate
                    break
            else:
                device = "CPU"
        self.device = device
        self.model = self.core.compile_model(self.core.read_model(str(self.model_path)), device)
        self.input = self.model.input(0)
        shape = self.input.get_partial_shape()
        self.imgsz = self._static_dim(shape[3]) or 640
        self.default_conf = conf
        # 预热，避免首次调用编译开销
        dummy = np.zeros((1, 3, self.imgsz, self.imgsz), dtype=np.float32)
        self.model([dummy])

    # ------------------------------------------------------------------ 预处理
    @staticmethod
    def _static_dim(dimension) -> int:
        """读取 OpenVINO 维度值（不同版本 API 不一致，逐个尝试）。"""
        for getter in ("get_length",):
            method = getattr(dimension, getter, None)
            if callable(method):
                try:
                    value = method()
                    if value:
                        return int(value)
                except Exception:  # noqa: BLE001
                    pass
        try:
            return int(str(dimension))
        except (TypeError, ValueError):
            return 0

    def _letterbox(self, image):
        """等比缩放 + 灰边填充到 imgsz，返回 (blob, scale, pad_x, pad_y)。"""
        cv2 = self._cv2
        height, width = image.shape[:2]
        scale = min(self.imgsz / height, self.imgsz / width)
        new_w, new_h = int(round(width * scale)), int(round(height * scale))
        resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        canvas = np.full((self.imgsz, self.imgsz, 3), 114, dtype=np.uint8)
        pad_x = (self.imgsz - new_w) // 2
        pad_y = (self.imgsz - new_h) // 2
        canvas[pad_y:pad_y + new_h, pad_x:pad_x + new_w] = resized
        blob = cv2.dnn.blobFromImage(canvas, 1 / 255.0, (self.imgsz, self.imgsz),
                                     swapRB=True, crop=False)
        return blob, scale, pad_x, pad_y

    # ------------------------------------------------------------------ 推理
    def detect(self, image, conf: float | None = None) -> list[dict]:
        """image: numpy RGB 数组；返回百分比坐标的目标列表。"""
        cv2 = self._cv2
        conf = self.default_conf if conf is None else conf
        height, width = image.shape[:2]

        blob, scale, pad_x, pad_y = self._letterbox(image)
        result = self.model([self._Tensor(blob)])[0]
        output = np.asarray(result)
        if output.ndim == 3:
            output = output[0]
        if output.shape[0] < output.shape[1]:      # (5, N) -> (N, 5)
            output = output.T

        boxes = []
        scores = []
        for row in output:
            score = float(row[4])
            if score < conf:
                continue
            x, y, w, h = (float(v) for v in row[:4])
            boxes.append([x - w / 2, y - h / 2, x + w / 2, y + h / 2])
            scores.append(score)
        if not boxes:
            return []

        keep = cv2.dnn.NMSBoxes(boxes, scores, conf, 0.45)
        if isinstance(keep, tuple):
            keep = keep[0]
        keep = np.array(keep).reshape(-1).tolist() if len(keep) else []

        items: list[dict] = []
        for index in keep:
            x1, y1, x2, y2 = boxes[index]
            # 还原 letterbox：去掉 padding，再除以缩放比
            x1 = (x1 - pad_x) / scale
            x2 = (x2 - pad_x) / scale
            y1 = (y1 - pad_y) / scale
            y2 = (y2 - pad_y) / scale
            x1 = max(0.0, min(x1, width))
            x2 = max(0.0, min(x2, width))
            y1 = max(0.0, min(y1, height))
            y2 = max(0.0, min(y2, height))
            items.append({
                "target": TARGET_CN,
                "confidence": round(scores[index], 3),
                "x": round(((x1 + x2) / 2) / width * 100, 2),
                "y": round(((y1 + y2) / 2) / height * 100, 2),
                "width": round((x2 - x1) / width * 100, 2),
                "height": round((y2 - y1) / height * 100, 2),
            })
        return items
