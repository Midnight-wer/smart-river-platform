"""河道漂浮垃圾检测后端推理接口（河道后端接口工程师）。

本脚本是整条链路的第三环：接收前端上传的河道巡检照片，
调用模型训练工程师训练好的 YOLOv8n 权重做推理，把检测框、类别、置信度
按统一 JSON 格式返回给前端展示工程师的页面渲染。

设计要点：
    1) 全离线：权重本地加载，推理过程不访问任何外网接口；
    2) 一次加载、长期复用：模型在服务启动时加载进内存，避免每次请求重新载入；
    3) 坐标统一用百分比：前端不管图片多大都能直接画框，缩放不失真；
    4) 异常兜底：没传图、传的不是图片、权重缺失，都有明确的中文提示。

依赖：flask、ultralytics、opencv-python、pillow
启动：
    python backend_api/app.py --weights backend_api/river_waste_yolov8n.pt --port 5000
"""

from __future__ import annotations

import argparse
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from pathlib import Path

import cv2
import numpy as np
from flask import Flask, jsonify, request, send_from_directory
from ultralytics import YOLO

# ================= 全局配置 =================
# 后端接口服务的监听地址与端口
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5000
# 权重文件的默认位置（模型训练工程师训练脚本会自动把 best.pt 复制到这里）
DEFAULT_WEIGHTS = Path(__file__).resolve().parent / "river_waste_yolov8n.pt"
# 默认置信度阈值：低于该值的框丢弃，兼顾漏检与误报
DEFAULT_CONF = 0.25
# 输入分辨率，与训练时保持一致
IMGSZ = 640
# 目标类别中文名（与 river_data.yaml 中的类别一致）
TARGET_CN = "漂浮垃圾"
# 前端展示工程师页面的存放目录，Flask 一并托管，省去跨域配置
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend_show"
# 单张图片大小上限（MB），防止超大图拖垮服务
MAX_UPLOAD_MB = 20

# 创建 Flask 应用
app = Flask(__name__)
# 限制上传体积
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024

# 模型句柄：服务启动时加载一次，之后所有请求复用
model: YOLO | None = None
# 模型实际使用的路径与加载时间
model_info: dict = {}


# ================= 工具函数 =================
def decode_image(raw: bytes) -> np.ndarray | None:
    """把上传的二进制图片解码成 OpenCV 的 BGR 图像数组。

    返回 None 表示数据不是一张能解析的图片。
    """
    # 空数据直接判定失败
    if not raw:
        return None
    # 用 numpy 把二进制转成数组，再交给 OpenCV 解码
    buffer = np.frombuffer(raw, dtype=np.uint8)
    # imdecode 负责解析 jpg/png 等格式
    img = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    # 解析失败返回 None
    return img


def to_percentage(x1: float, y1: float, x2: float, y2: float,
                  width: int, height: int) -> dict:
    """把像素坐标的外接矩形换算成图片宽高的百分比。

    前端按百分比画框，无论图片实际多大都能对齐。
    """
    # 宽高为 0 时保护，避免除零
    if width <= 0 or height <= 0:
        return {"x": 0.0, "y": 0.0, "width": 0.0, "height": 0.0}
    # 计算中心点
    cx = (x1 + x2) / 2 / width * 100
    cy = (y1 + y2) / 2 / height * 100
    # 计算框尺寸
    bw = (x2 - x1) / width * 100
    bh = (y2 - y1) / height * 100
    # 保留两位小数，减少传输体积
    return {
        "x": round(cx, 2),
        "y": round(cy, 2),
        "width": round(bw, 2),
        "height": round(bh, 2),
    }


# ================= 接口一：健康检查 =================
@app.get("/api/health")
def health():
    """健康检查：确认服务活着、模型是否加载成功。

    前端启动时先调这个接口，模型没起来就给出明确提示。
    """
    # 模型没加载时返回 503，让前端知道要等
    if model is None:
        return jsonify({
            "status": "starting",
            "message": "模型正在加载，请稍候重试",
            "offline": True,
        }), 503
    # 正常情况
    return jsonify({
        "status": "ok",
        "message": "河道漂浮垃圾检测服务运行中",
        "model": model_info,
        "classes": {0: TARGET_CN},
        "offline": True,
    })


# ================= 接口二：核心检测接口 =================
@app.post("/api/detect")
def detect():
    """核心接口：上传河道照片，返回漂浮垃圾的检测框、类别与置信度。

    请求：multipart/form-data，字段名 image；可选字段 conf。
    响应：{"taskId", "model", "elapsed", "image", "items", "summary"}
    """
    # 计时，用于统计单张推理耗时
    start = time.time()
    # 模型还没加载好，直接返回错误
    if model is None:
        return jsonify({"status": "error", "message": "模型未就绪，请稍后重试"}), 503
    # 取上传文件
    file = request.files.get("image")
    # 没传文件
    if file is None or not file.filename:
        return jsonify({"status": "error", "message": "请先选择要检测的河道照片"}), 400
    # 读取文件原始字节
    raw = file.read()
    # 解码图片
    img = decode_image(raw)
    # 解码失败（不是图片或已损坏）
    if img is None:
        return jsonify({"status": "error", "message": "图片无法解析，请换一张河道现场照片"}), 400
    # 取置信度阈值，前端没传就用默认值
    try:
        conf = float(request.form.get("conf", DEFAULT_CONF))
    except (TypeError, ValueError):
        conf = DEFAULT_CONF
    # 阈值夹在 0.01~1 之间，避免传 0 拉满一堆框
    conf = min(max(conf, 0.01), 1.0)
    # 图片高宽
    height, width = img.shape[:2]
    # ---- 推理超时保护：把推理放进独立线程，超时直接返回友好提示 ----
    # 避免某一张异常图占死推理线程，导致整个服务对所有巡检员不可用
    try:
        # 用单线程池提交推理任务，最多等 30 秒
        with ThreadPoolExecutor(max_workers=1) as pool:
            # 关键字参数传递，避免位置参数错位
            future = pool.submit(model.predict, img, conf=conf, imgsz=IMGSZ, verbose=False)
            # 阻塞等待推理结果，超时抛出 FuturesTimeoutError
            results = future.result(timeout=30)
    except FuturesTimeoutError:
        # 超时：返回 504，前端显示人话提示，服务本身不受影响
        return jsonify({
            "status": "error",
            "message": "推理超时，请压缩图片尺寸后重试",
        }), 504
    # 取第一个结果（单图推理只有一个）
    result = results[0]
    # 组装检测项
    items = []
    # 遍历所有检出的框
    for box in result.boxes:
        # 取出四个角点坐标
        x1, y1, x2, y2 = [float(v) for v in box.xyxy[0].tolist()]
        # 置信度
        score = float(box.conf[0])
        # 类别 id
        cls_id = int(box.cls[0])
        # 百分比坐标
        pos = to_percentage(x1, y1, x2, y2, width, height)
        # 组装一条
        items.append({
            "target": TARGET_CN,      # 目标类别（中文）
            "classId": cls_id,        # 类别 id
            "confidence": round(score, 4),  # 置信度
            **pos,                    # x / y / width / height 百分比
        })
    # 按置信度从高到低排序，前端第一条就是最可疑的目标
    items.sort(key=lambda it: it["confidence"], reverse=True)
    # 统计信息，给前端做展示
    summary = {
        "count": len(items),                       # 目标总数
        "maxConfidence": round(max((it["confidence"] for it in items), default=0.0), 4),
        "avgConfidence": round(
            sum(it["confidence"] for it in items) / len(items), 4) if items else 0.0,
    }
    # 返回完整结果
    return jsonify({
        "status": "ok",
        "taskId": uuid.uuid4().hex,       # 任务号，便于前端追溯
        "model": model_info,              # 模型信息
        "elapsed": round(time.time() - start, 3),  # 端到端耗时（秒）
        "image": {"width": width, "height": height, "name": file.filename},
        "items": items,                    # 检测框列表
        "summary": summary,                # 统计
    })


# ================= 接口三：前端页面托管 =================
@app.get("/")
def index():
    """把 前端展示工程师的前端页面直接由后端托管，避免跨域问题。"""
    # 首页文件
    page = FRONTEND_DIR / "index.html"
    # 文件不存在时给出提示
    if not page.exists():
        return jsonify({"status": "error", "message": "前端页面未找到"}), 404
    return send_from_directory(str(FRONTEND_DIR), "index.html")


# ================= 服务启动 =================
def main() -> int:
    """启动服务：先加载模型，再开端口。"""
    # 命令行参数
    parser = argparse.ArgumentParser(description="河道漂浮垃圾检测后端接口")
    parser.add_argument("--weights", default=str(DEFAULT_WEIGHTS), help="模型权重路径")
    parser.add_argument("--host", default=DEFAULT_HOST, help="监听地址")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="监听端口")
    parser.add_argument("--conf", type=float, default=DEFAULT_CONF, help="默认置信度阈值")
    args = parser.parse_args()

    # 加载模型（全局变量，供各接口复用）
    global model, model_info
    # 权重路径
    weights_path = Path(args.weights)
    # 权重不存在时直接报错退出，避免服务起来了却不能用
    if not weights_path.exists():
        print(f"错误：找不到模型权重 {weights_path}")
        print("请先运行 模型训练工程师的训练脚本生成权重")
        return 1
    # 加载耗时
    t0 = time.time()
    # 真正把模型读进内存
    model = YOLO(str(weights_path))
    # 记录模型信息
    model_info = {
        "name": weights_path.name,
        "backend": "ultralytics(pytorch)",
        "imgsz": IMGSZ,
        "conf": args.conf,
        "loadSeconds": round(time.time() - t0, 2),
        "offline": True,
    }
    print(f"模型加载完成: {weights_path.name}（{model_info['loadSeconds']}s）")
    print(f"接口地址: http://{args.host}:{args.port}/api/detect")
    print(f"健康检查: http://{args.host}:{args.port}/api/health")
    # 启动 HTTP 服务
    app.run(host=args.host, port=args.port, debug=False, threaded=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
