# 摄像头识别接入 YOLO 推理服务 · 接口方案

> 适用模块：排污口指纹识别页「摄像头实时识别」卡片
> 前置现状：识别接口 `POST /api/ai/camera/recognize` 由前端 Mock 适配器（`src/mock/server.ts`）模拟，
> 返回随机的 bbox 坐标。本方案定义真实推理链路的接口契约、前端改造点与切换步骤。

---

## 1. 总体架构

```
┌──────────────┐  抓拍/上传图片   ┌──────────────┐  转发图片   ┌──────────────────────┐
│ 浏览器前端    │ ──────────────→ │ 业务后端网关  │ ─────────→ │ YOLO 推理微服务        │
│ Vue3 + axios │  multipart     │ (现有后台服务) │  multipart │ FastAPI + Ultralytics │
│              │ ←────────────── │              │ ←───────── │  YOLOv8-sewer 权重     │
└──────────────┘  业务 JSON      └──────────────┘  bbox JSON  └──────────────────────┘
                                        │
                                        └─ 职责：JWT 鉴权、图片校验、类别→业务字段映射、
                                           像素 bbox→百分比换算、风险值/建议生成
```

三层分工的理由：

| 层 | 职责 | 不负责 |
|---|---|---|
| 前端 | 采集画面、压缩、上传、渲染识别框 | 任何识别逻辑 |
| 业务后端 | 鉴权、参数校验、结果加工（映射/换算/风险值） | 模型推理 |
| 推理服务 | 纯推理：图片进 → bbox 出 | 鉴权（内网可信）、业务语义 |

推理服务部署在内网，只接受业务后端调用，不暴露公网，因此无需处理用户鉴权。

---

## 2. 推理服务接口契约（detection-service）

### 2.1 目标检测 `POST /v1/detect`

**请求**：`multipart/form-data`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `image` | binary | 是 | jpg / png，≤ 5MB |
| `conf_threshold` | float | 否 | 置信度阈值，默认 `0.45`，范围 0.1–0.9 |
| `max_objects` | int | 否 | 单图最大目标数，默认 `20` |
| `imgsz` | int | 否 | 推理分辨率（长边像素），默认 `640`，可选 640/1280 |

**响应**：`application/json`

```json
{
  "model": "yolov8s-sewer",
  "version": "1.3.0",
  "elapsed_ms": 412,
  "inference_ms": 286,
  "image": { "width": 1280, "height": 720 },
  "objects": [
    {
      "label": "outfall",
      "confidence": 0.87,
      "bbox": { "x1": 0.21, "y1": 0.53, "x2": 0.37, "y2": 0.71 }
    }
  ]
}
```

**契约要点**：

- `bbox` 使用 **0–1 归一化坐标**（相对图片宽高），与图片分辨率解耦，前端换算不受压缩/缩放影响
- `label` 为训练时的英文类别 ID（见 §5 映射表），中文文案由业务后端翻译，**推理服务永远不返回中文业务术语**
- `objects` 已按 confidence 降序排列

**错误码**（HTTP status + body）：

| status | code | 场景 |
|---|---|---|
| 400 | INVALID_IMAGE | 图片解码失败 / 超 5MB |
| 422 | INVALID_PARAM | conf_threshold 超范围等 |
| 429 | RATE_LIMITED | 超过服务并发上限（配合排队时返回） |
| 500 | INFERENCE_ERROR | 推理异常（含栈信息仅入日志） |
| 503 | MODEL_LOADING | 模型冷启动加载中，建议重试 |

### 2.2 健康检查 `GET /v1/health`

```json
{ "status": "ok", "model_loaded": true, "gpu": "cuda:0", "uptime_s": 86400 }
```

### 2.3 模型信息 `GET /v1/model`

```json
{ "name": "yolov8s-sewer", "version": "1.3.0", "classes": ["outfall", "pipe", "oil_film", "floatage", "seepage"], "warmup_ms": 300 }
```

---

## 3. 业务后端接口契约（前端调用）

### 3.1 `POST /api/ai/camera/recognize`（改造现有接口）

**请求**：`multipart/form-data`（原 Mock 为 JSON，需调整）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `image` | binary | 是 | 抓拍/上传的图片 |
| `scene` | string | 是 | `camera` / `upload`，用于审计与统计 |
| `width` | int | 否 | 原始画面宽（审计用，bbox 换算不依赖它） |
| `height` | int | 否 | 原始画面高 |
| `river_id` | string | 否 | 关联河道（可选，便于结果归档） |

**响应**：**保持现有 `CameraRecognitionResult` 结构完全不变**（`src/api/ai.ts` 已定义）：

```json
{
  "taskId": "CT924807",
  "scene": "camera",
  "model": "yolov8s-sewer v1.3.0",
  "capturedAt": "2026-10-21 10:50:35",
  "elapsed": 412,
  "items": [
    {
      "id": "CT924807-1",
      "target": "疑似排污口",
      "confidence": 0.87,
      "x": 29.0, "y": 62.0, "width": 16.0, "height": 18.0,
      "risk": 82,
      "source": "生活污水",
      "suggestion": "建议现场核查"
    }
  ]
}
```

**设计原则：响应 schema 冻结**。前端渲染逻辑（识别框百分比定位、结果列表、加入指纹清单）零改动，接入成本集中在请求侧。

**后端处理流水线**：

1. JWT 鉴权（复用现有 `Authorization: Bearer <token>` 机制）
2. 图片校验（类型白名单 jpg/png、≤5MB）
3. 调用推理服务 `POST /v1/detect`（服务端超时 8s，含 1 次重试）
4. 类别映射（英文 label → 中文 target + source + suggestion，§5）
5. 坐标换算：`(x1+x2)/2*100 → x`、`(y1+y2)/2*100 → y`、`(x2-x1)*100 → width`、`(y2-y1)*100 → height`
6. 风险值计算：`risk = round(confidence * 60 + prior_risk[label])`，封顶 99（保持现有 0–100 语义与配色阈值不变）
7. 空结果时返回 `items: []`（前端已处理"未识别到"提示）

### 3.2 接口级错误约定

复用现有 `ApiResult { code, message, data }` 包装。新增业务错误码：

| code | message 示例 | 前端表现 |
|---|---|---|
| 4601 | 图片格式不支持，请上传 jpg/png | ElMessage.error |
| 4602 | 图片超过 5MB 限制 | ElMessage.error |
| 4603 | 识别服务繁忙，请稍后重试 | ElMessage.error |
| 4604 | 识别服务暂不可用，请联系管理员 | ElMessage.error |

---

## 4. 前端改造清单

| # | 文件 | 改动 | 说明 |
|---|---|---|---|
| 1 | `src/api/ai.ts` | `recognizeCamera()` 入参改为 `{ file: Blob; scene: string; width?: number; height?: number }`，内部构造 FormData 调用 | 接口签名变更，调用方仅 2 处 |
| 2 | `src/api/ai.ts` | 类型定义保持 `CameraRecognitionItem/Result` 不变 | 渲染层零改动 |
| 3 | `src/api/request.ts` | 新增 `postForm<T>()`：per-request 覆盖 `Content-Type`（删掉实例默认的 `application/json`，让浏览器自动生成含 boundary 的 multipart 头） | 实例默认头写死了 JSON（L20），直接发 FormData 会导致 boundary 丢失 |
| 4 | `src/mock/server.ts` | mockAdapter 增加**路由排除列表** `REAL_API_ROUTES = ['/api/ai/camera/recognize']`，命中即 `return null` 透传给真实 HTTP——避免"接一个真实接口必须全部接口脱离 mock" | 现有 `VITE_USE_MOCK` 是全局开关（request.ts L14），不能为了识别接口把其他 40+ 接口全部切真实后端 |
| 5 | `src/views/ai/Fingerprint.vue` | `captureAndRecognize()`：`canvas.toDataURL` → `canvas.toBlob`（减少 base64 体积），限制最长边 1280 重采样后上传；`handleFile()`：File 原样透传（后端限制 5MB，超大图前端先用 canvas 压缩） | 上行体积与推理速度 |
| 6 | `src/views/ai/Fingerprint.vue` | `recognize()` 换用新签名；抓拍后 `recognizing` 状态下按钮已有 loading，无需额外改 | |
| 7 | `.env.development` | 新增 `VITE_AI_DETECT_BASE=/api`（可指向独立网关域名） | 部署灵活 |
| 8 | UI 文案 | 去掉「模拟识别」标签：由后端响应新增 `mock: true/false` 字段驱动（Mock 服务返回 true，真实接口返回 false），前端据此条件渲染标签 | 单一事实来源，避免文案硬编码 |

抓拍压缩伪代码（改动点 5）：

```ts
async function compressToBlob(source: HTMLVideoElement | HTMLImageElement, maxEdge = 1280): Promise<Blob> {
  const w = source instanceof HTMLVideoElement ? source.videoWidth : source.naturalWidth
  const h = source instanceof HTMLVideoElement ? source.videoHeight : source.naturalHeight
  const scale = Math.min(1, maxEdge / Math.max(w, h))
  const canvas = document.createElement('canvas')
  canvas.width = Math.round(w * scale)
  canvas.height = Math.round(h * scale)
  canvas.getContext('2d')!.drawImage(source, 0, 0, canvas.width, canvas.height)
  return new Promise((resolve) => canvas.toBlob((blob) => resolve(blob!), 'image/jpeg', 0.85))
}
```

---

## 5. 类别映射与业务字段规则（业务后端配置）

| 推理 label | 中文 target | 来源预判 source（示例） | prior_risk | suggestion |
|---|---|---|---|---|
| `outfall` | 疑似排污口 | 按河道档案区域配置 | 25 | 建议现场核查 |
| `pipe` | 暗管排放 | 工业废水 | 30 | 建议调取排污许可 |
| `oil_film` | 水面油污 | 工业废水 | 20 | 建议取样检测 |
| `floatage` | 水面漂浮物 | 生活污水 | 10 | 建议属地河长复核 |
| `seepage` | 岸边渗排 | 农业面源 | 22 | 建议取样检测 |

- 映射表做成后端配置（DB 或 YAML），**训练新增类别无需发版前端**
- `source` 当前 Mock 为随机值；真实接入后建议按 `label + 河道所在区域产业结构` 计算，至少按 label 固定映射，消除"同一目标来源预判漂移"
- 风险值公式保持 `round(confidence × 60 + prior_risk[label])`，与现有 HIGH≥80 / MID≥60 阈值体系一致

---

## 6. 非功能设计

| 项 | 取值 | 理由 |
|---|---|---|
| 前端抓拍压缩 | 最长边 1280、JPEG q=0.85 | YOLOv8 常用 imgsz=640/1280，再大无收益，徒增上行带宽 |
| 上传体积限制 | 5MB | 覆盖 1280 边长 JPEG 极端情况 |
| 前端超时 | 识别接口单独 20s（request.ts 全局 15s，per-request 覆盖） | GPU 推理 0.3–1s，但冷启动/排队场景需要余量 |
| 推理服务超时 | 业务后端→推理 8s + 1 次重试 | 覆盖模型冷启动 |
| 并发控制 | 推理服务信号量限并发（CPU=1×核数，GPU=1×卡数），超出排队 60s 超时 | 防止突发抓拍压垮服务 |
| 幂等/防抖 | 前端 `recognizing` 状态已互斥连续抓拍；`taskId` 由后端生成用于审计 | |
| 可观测 | 推理服务输出 elapsed/inference_ms；业务后端记录 scene、target 分布、失败率到现有日志模块 | |
| 安全 | 推理服务仅内网监听；业务接口沿用 JWT；图片即传即焚不入库（归档仅存 bbox 与 taskId） | 隐私合规 |

---

## 7. 推理服务参考实现（FastAPI + Ultralytics）

```python
# main.py — detection-service
import io, time, uuid
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from PIL import Image
from ultralytics import YOLO

app = FastAPI(title="sewer-detection-service")
model = YOLO("weights/yolov8s-sewer.pt")   # 启动时加载并 warmup
CLASSES = ["outfall", "pipe", "oil_film", "floatage", "seepage"]

@app.post("/v1/detect")
async def detect(
    image: UploadFile = File(...),
    conf_threshold: float = Form(0.45),
    max_objects: int = Form(20),
    imgsz: int = Form(640),
):
    raw = await image.read()
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(400, "INVALID_IMAGE")
    try:
        img = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception:
        raise HTTPException(400, "INVALID_IMAGE")

    start = time.perf_counter()
    result = model.predict(img, conf=conf_threshold, imgsz=imgsz, verbose=False)[0]
    inference_ms = round((time.perf_counter() - start) * 1000)

    W, H = img.size
    objects = []
    for box in result.boxes[: max_objects]:
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        objects.append({
            "label": CLASSES[int(box.cls)],
            "confidence": round(float(box.conf), 2),
            "bbox": {"x1": x1 / W, "y1": y1 / H, "x2": x2 / W, "y2": y2 / H},
        })
    objects.sort(key=lambda o: -o["confidence"])

    return {
        "model": "yolov8s-sewer", "version": "1.3.0",
        "elapsed_ms": inference_ms + 30, "inference_ms": inference_ms,
        "image": {"width": W, "height": H}, "objects": objects,
    }
```

启动：`uvicorn main:app --host 0.0.0.0 --port 9100`（仅内网）。
生产建议：gunicorn/uvicorn workers + Docker 部署，权重文件走版本目录挂载，模型更新 = 换权重 + 滚动重启。

---

## 8. 切换与联调步骤

1. **推理服务先行**：部署 detection-service，`GET /v1/health` 通，用样例图验证 `/v1/detect` 的 bbox 与置信度
2. **业务后端**：实现 §3.1 流水线（映射表先用 §5 默认值），与推理服务联调
3. **前端改造**：按 §4 清单改 8 处（Mock 排除机制保证其余接口继续可用）
4. **联调验证**：`VITE_USE_MOCK` 保持 true + 路由排除生效 → 识别走真实链路、其他页面仍 Mock
5. **验收用例**：
   - 高置信目标图 → 框准确贴合目标边缘（百分比坐标误差 < 2%）
   - 无目标图 → `items: []`，前端提示"未识别到"
   - 关闭摄像头 → 识别框/快照清空（已修复的行为不回归）
   - 推理服务停机 → 前端收到 4604 文案提示
6. **全量切真实后端**（可选）：`VITE_USE_MOCK=false`，此时删除 mockAdapter 排除列表逻辑

## 9. 备选方案对比（未采用的路线）

| 方案 | 结论 | 原因 |
|---|---|---|
| 浏览器端推理（ONNX Runtime Web / yolo.js） | 不推荐为主链路 | 200MB+ 权重下载、低端机推理 2–5s、模型更新依赖前端发版；仅适合弱网离线巡查的补充形态 |
| 第三方视觉 API（云厂商） | 可作为降级通道 | 按次计费、排污口垂直类别不支持需自训练，且河道图片含地理信息不宜外发 |
| 前端直连推理服务 | 不推荐 | 推理服务需暴露公网 + 前端处理映射逻辑，鉴权与业务语义下沉到客户端，不可控 |
