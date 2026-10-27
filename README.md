# 智慧河长协同治理平台 · Smart River Platform

> 河长制协同治理后台管理系统 + 河道漂浮物 AI 检测系统，全链路本地离线运行。
>
> 技术栈：Vue 3 · TypeScript · Vite · TailwindCSS · Element Plus · YOLOv8 · OpenVINO · Flask

## 项目简介

本项目包含两大组成部分：

1. **智慧河长协同治理平台**（`river-admin/`）—— 河长制业务后台管理系统，覆盖河道档案、河长管理、巡查、水质监测、事件中心、考核、公众服务、系统管理等完整业务模块，并集成 AI 智能溯源（污染扩散模拟、目标检测、水质预测、污染溯源等 8 个页面）。
2. **河道漂浮物检测系统**（`river_plastic_detect/`）—— 面向河道水面漂浮垃圾（塑料瓶等）的目标检测独立交付包，含数据标注、模型训练、后端接口、前端展示四个可独立运行的模块。

**核心特点：完全离线。** 模型权重、推理服务、加速运行时全部在本机，图像不出本机、不访问任何外网。

## 功能特性

### 平台端（river-admin）

- 30+ 业务页面：工作台（省/市/县/乡四级）、河道档案、河长画像、巡查管理、水质监测、事件中心、考核管理、公众服务、系统管理（用户/组织/角色/字典/日志/设备）、数据大屏
- AI 目标检测页接入本地 YOLO 推理服务：摄像头实时识别 / 图片上传识别，自动截帧留痕
- RBAC 权限体系 + 路由守卫；Element Plus / ECharts 按需引入；生产构建含 vendor 分包

### AI 检测链路（river-admin/ai-training）

| 指标 | 数值 |
|---|---|
| 验证集 mAP50（P / R） | **0.923**（0.932 / 0.850） |
| 人工精标集逐图检出 / 平均 IoU | 98% / 0.95 |
| 单次识别端到端延迟 | 30~80 ms（OpenVINO 核显） |
| 推理后端 | OpenVINO（GPU 核显 → NPU → CPU 自动回退） |

- 同源代理转发（`/detect` → 127.0.0.1:8000），无 CORS、密钥不出本机
- 完整工程脚本：数据集构建 / 训练 / 评测 / ONNX 导出 / 发布门禁 / 自检（后端 12 项 + 浏览器端到端 12 项）

## 目录结构

```
├── river-admin/               # 平台前端 + 本地 AI 服务
│   ├── src/                   #   Vue 3 源码（views/api/router/stores/mock）
│   ├── ai-training/           #   数据集、训练脚本、检测服务、发布流水线
│   └── dist/                  #   生产构建产物
├── river_plastic_detect/      # 大赛独立交付包（四模块，每行中文注释）
│   ├── data_label/            #   数据标注工程师：清洗 + 划分脚本
│   ├── train_module/          #   模型训练工程师：训练脚本
│   ├── backend_api/           #   后端接口工程师：Flask 推理服务
│   └── frontend_show/         #   前端展示工程师：单文件巡检看板
├── 演讲稿/                     # 四岗位路演演讲稿 + 答辩演示脚本
└── start_all.ps1              # 一键启动脚本（检测服务 + 前端 + 健康自检）
```

## 环境要求

- Node.js ≥ 18、npm ≥ 9
- Python ≥ 3.10
- 依赖：`ultralytics`、`flask`、`opencv-python`、`pillow`、`openvino`（见 `river_plastic_detect/requirements.txt`）

## 安装步骤

```powershell
# 1. 前端依赖
cd river-admin
npm ci

# 2. Python 依赖（AI 推理）
pip install -r ../river_plastic_detect/requirements.txt
pip install openvino ultralytics
```

## 使用说明

### 方式一：平台版（推荐）

```powershell
# 一键启动：AI 检测服务(8000) + 前端开发服务器(5173)，含健康自检
powershell -ExecutionPolicy Bypass -File start_all.ps1
```

| 入口 | 地址 |
|---|---|
| 管理后台 | http://localhost:5173 |
| AI 目标检测 | http://localhost:5173/ai/detection |
| 数据大屏 | http://localhost:5173/large-screen |

### 方式二：大赛独立演示包

```powershell
cd river_plastic_detect
python backend_api/app.py --port 5000
# 浏览器打开 http://127.0.0.1:5000/
```

### 模型复现（可选）

```powershell
cd river-admin/ai-training
python scripts/build_near_dataset.py --near-height 0.03 --max-crops 1 --coco --hard-negatives
yolo train model=yolov8n.pt data=datasets/near/data.yaml epochs=50 imgsz=640 device=cpu
python scripts/export_onnx.py --weights models/plastic-bottle-near.pt --imgsz 640 --output models/plastic-bottle-near.onnx
python services/detect_server.py --port 8000
```

完整复现步骤与自检命令见 [river-admin/ai-training/README.md](river-admin/ai-training/README.md)。

## 贡献指南

1. Fork 本仓库并创建特性分支（`git checkout -b feature/xxx`）
2. 提交遵循语义化提交格式（`feat:` / `fix:` / `docs:` / `chore:`）
3. 前端改动需通过 `npm run check`（vue-tsc）与 `npm run lint`
4. AI 链路改动需通过 `python scripts/self_check.py` 发布门禁（mAP50 ≥ 0.7）
5. 发起 Pull Request 并描述改动动机与验证方式

## 开源协议

本项目基于 [MIT License](LICENSE) 开源。
