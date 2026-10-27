"""TFLite 瓶检测器（Google ML Kit Object Detection 导出的 EfficientDet-Lite 模型）。

用于本地离线推理：单类「PlasticBottle」，输入 512x512 uint8，
输出归一化 bbox（ymin, xmin, ymax, xmax）、类别、置信度与有效框数量。

模型来源：https://github.com/m0-n/Plastic-Bottle-Detection-Models
（基于 5,592 个真实河道塑料瓶标注训练）
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

INPUT_SIZE = 512


class TfliteBottleDetector:
    """基于 tflite_runtime / tensorflow.lite 的单类塑料瓶检测器。"""

    def __init__(self, model_path: str | Path, class_name: str = "PlasticBottle") -> None:
        self.model_path = Path(model_path)
        self.class_name = class_name
        self.interpreter = self._load_interpreter()
        self.interpreter.allocate_tensors()
        self.input_details = self.interpreter.get_input_details()[0]
        self.output_details = self.interpreter.get_output_details()

    def _prepare_path(self) -> str:
        """TFLite 解释器用 C API 打开文件，Windows 下无法处理含中文的路径，
        因此把模型复制到纯 ASCII 临时目录后再加载。"""
        raw = str(self.model_path)
        if all(ord(char) < 128 for char in raw):
            return raw
        import shutil
        import tempfile

        target = Path(tempfile.gettempdir()) / "river-bottle-tflite" / self.model_path.name
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or target.stat().st_size != self.model_path.stat().st_size:
            shutil.copyfile(self.model_path, target)
        return str(target)

    def _load_interpreter(self):
        """按可用性依次尝试 LiteRT / tflite_runtime / TensorFlow 内的解释器。"""
        try:  # TensorFlow 2.16+ 拆出的独立 LiteRT 包
            from ai_edge_litert.interpreter import Interpreter  # type: ignore

            return Interpreter(model_path=self._prepare_path())
        except ImportError:
            pass
        try:  # 轻量的 tflite_runtime（Linux/macOS 官方提供）
            from tflite_runtime.interpreter import Interpreter  # type: ignore

            return Interpreter(model_path=self._prepare_path())
        except ImportError:
            pass
        from tensorflow.lite.python.interpreter import Interpreter  # type: ignore

        return Interpreter(model_path=self._prepare_path())

    def _quantize(self, image: np.ndarray) -> np.ndarray:
        """按输入张量的量化参数把 uint8 图像映射到模型输入域。"""
        params = self.input_details["quantization_parameters"]
        scales, zero_points = params["scales"], params["zero_points"]
        if not scales:
            return image.astype(np.float32)
        scale = float(scales[0])
        zero_point = int(zero_points[0])
        quantized = np.round(image.astype(np.float32) / scale) + zero_point
        return np.clip(quantized, 0, 255).astype(np.uint8)

    def detect(self, image, conf: float = 0.3) -> list[dict]:
        """执行检测，返回百分比坐标的目标列表。"""
        from PIL import Image

        rgb = image.convert("RGB").resize((INPUT_SIZE, INPUT_SIZE), Image.BILINEAR)
        array = np.asarray(rgb, dtype=np.uint8)[np.newaxis, ...]
        self.interpreter.set_tensor(self.input_details["index"], self._quantize(array))
        self.interpreter.invoke()
        outputs = [self.interpreter.get_tensor(d["index"]) for d in self.output_details]

        # 输出顺序：boxes / labels / scores / num（metadata 已声明）
        boxes = np.squeeze(outputs[0])
        scores = np.squeeze(outputs[2])
        count = int(np.squeeze(outputs[3])) if len(outputs) > 3 else len(scores)
        count = max(0, min(count, len(scores)))

        width, height = image.size
        items: list[dict] = []
        for i in range(count):
            score = float(scores[i])
            if score < conf:
                continue
            ymin, xmin, ymax, xmax = (float(v) for v in boxes[i])
            # 归一化 (0-1) -> 像素 -> 中心点百分比
            x1, x2 = xmin * width, xmax * width
            y1, y2 = ymin * height, ymax * height
            items.append({
                "target": "塑料瓶",
                "confidence": round(score, 3),
                "x": round((x1 + x2) / 2 / width * 100, 2),
                "y": round((y1 + y2) / 2 / height * 100, 2),
                "width": round((x2 - x1) / width * 100, 2),
                "height": round((y2 - y1) / height * 100, 2),
            })
        return items
