# 河面漂浮塑料瓶检测 · 本地离线部署工程

> **最终形态：完全离线运行。** 权重、推理服务、加速运行时全部在本机，图像不出本机、不访问任何外网。
> 目标场景：河道摄像头识别**水面漂浮的塑料瓶（矿泉水瓶等 PET 瓶）**，单类输出。

## 架构（离线模式）

```
浏览器摄像头 / 上传图片
      │  base64
      ▼
Vite dev server ──/detect──▶  本地检测服务 127.0.0.1:8000
                                   │  OpenVINO（设备自动选：GPU 核显 → NPU → CPU）
                                   ▼
                      models/plastic-bottle-near.onnx （12 MB，640 输入）
```

- 前端只请求同源 `/detect`，由 Vite 代理转发到本机服务，避免 CORS
- 推理后端优先 **OpenVINO**：Intel 核显 8 ms / NPU 15 ms / CPU 63 ms（640 输入裸推理）
  - 走完整 `/detect` 接口：OpenVINO 核显 **约 30~80 ms**，PyTorch CPU 约 296 ms
  - OpenVINO 不可用时自动回退到 PyTorch（Ultralytics）后端
- 模型只输出一个类别「塑料瓶」，界面不会出现其它目标

## 目录结构

```
ai-training/
├── config/                     # 标签库与提示词配置
├── datasets/
│   ├── raw/                    # 原始数据集（m0-n 河道瓶 / COCO 采样 / 非瓶子负样本）
│   ├── near/                   # 近景训练集（train 1520 / val 267，YOLO 格式 + data.yaml）
│   ├── processed/              # 清洗中间产物
│   └── reports/                # 诊断报告、标注抽检对照图
├── models/
│   ├── plastic-bottle-near.pt  # 当前上线权重（6.2 MB）
│   └── plastic-bottle-near.onnx
├── runs/                       # 训练产物（ Ultralytics 输出）
├── services/
│   ├── detect_server.py        # 本地检测服务（标准库 HTTP，无 Web 框架依赖）
│   └── openvino_detector.py    # OpenVINO 后端（GPU/NPU 推理 + letterbox + NMS）
└── scripts/
    ├── build_near_dataset.py   # 构建近景专用数据集（近景筛选 + ROI 裁剪 + 正负样本编排）
    ├── fetch_coco_bottles.py   # 抓取 COCO 瓶子样本
    ├── fetch_coco_negatives.py # 抓取「非瓶子容器」负样本（玻璃杯/花瓶/杯/碗）
    ├── curate_coco_bottles.py  # 生成候选图编号对照表，人工筛出 PET 瓶
    ├── export_onnx.py          # 导出 ONNX（并搬到指定输出路径）
    ├── eval_near_model.py      # 模型评测：指标 / 逐图召回 / 手持图 / 非瓶子误报率
    ├── self_check.py           # 后端全量自检（12 项）
    ├── browser_check.mjs       # 前端端到端自检（12 项，Playwright）
    ├── diag_alignment.py       # 标注错位诊断（尺寸一致性 / 越界 / 抽样叠加图）
    ├── clean_dataset.py        # 早期清洗脚本（保留）
    └── build_label_db.py       # 生成本地标签库 src/api/labelDb.ts
```

## 复现步骤

```powershell
cd ai-training

# 1) 近景数据集（河道近景瓶 + ROI 裁剪 + 人工筛选的 PET 瓶 + 非瓶子负样本）
python scripts/build_near_dataset.py --near-height 0.03 --max-crops 1 `
    --coco --coco-selection datasets/reports/curate/selection.json --hard-negatives

# 2) 训练（CPU；先全尺度预热，再做河道场景定向微调）
yolo train model=yolov8n.pt data=datasets/near/data.yaml epochs=50 imgsz=512 batch=24 `
    device=cpu workers=10 project=runs name=plastic-bottle-near-coco-512
yolo train model=models/plastic-bottle-near.pt data=datasets/near/data.yaml epochs=25 `
    imgsz=512 batch=24 device=cpu workers=10 lr0=0.003 patience=10 project=runs name=plastic-bottle-water-v1

# 3) 发布 + 导出 ONNX（640 输入，imgsz 烘焙在导出文件内，改分辨率必须重新导出）
Copy-Item runs\detect\runs\plastic-bottle-water-v1\weights\best.pt models\plastic-bottle-near.pt -Force
python scripts/export_onnx.py --weights models/plastic-bottle-near.pt --imgsz 640 `
    --output models/plastic-bottle-near.onnx

# 4) 启动本地检测服务
python services/detect_server.py --port 8000
```

前端 `.env.local` 中 `VITE_DETECT_MODE=local` 即为离线模式（默认值）。

## 数据集构成（近景定向版）

| 类别 | 数量 | 说明 |
|---|---|---|
| 河道近景原图（正） | 440 张 | m0-n 河道瓶数据中「框高 ≥3% 图高」的图 |
| ROI 放大裁剪（正） | 440 张 | 围绕近景瓶裁剪，补充不同背景/距离的近景视角 |
| 人工筛选 PET 瓶（正） | 8 张 | COCO 候选中逐张放大核对确认的塑料矿泉水瓶 |
| 非瓶子容器（负） | 699 张 | COCO 玻璃杯/花瓶/马克杯/碗，图中确认无瓶 |
| 河面无瓶图（负） | 200 张 | 河道实拍无瓶水面 |
| **训练集 / 验证集** | **1520 / 267** | 正 755 / 负 765，框 1452 / 233 |

关键取舍：
- COCO `bottle` 类混着玻璃酒瓶、啤酒瓶、番茄酱瓶，**整体当正样本会把非目标教会模型**，
  因此只保留人工确认的 8 张 PET 瓶，其余瓶子图直接剔除（不当负样本，避免矛盾标注）；
- 「只有远景小瓶」的图也**不能**当负样本，否则模型既学不会瓶身、验证分类损失还会爆掉。

## 当前模型指标（v7，2026-10-26 发布）

| 指标 | 数值 | 发布门禁 |
|---|---|---|
| 河面+混合验证集 mAP50（P / R） | **0.923**（0.932 / 0.850，v6 为 0.908） | mAP50 ≥ 0.7 → PASS |
| 人工精标集（57 张）逐图检出 / 平均 IoU | **98% / 0.95** | — |
| 手持诚实留出集（9 张）逐图检出 / 平均 IoU | **89% / 0.88** | 检出 ≥ 0.7 且 IoU ≥ 0.7 → PASS |
| 非瓶子容器误报 | 30 张抽查 0 张（v6 基线） | — |
| 单次识别端到端延迟 | 30~80 ms（OpenVINO 核显） | — |

> v7 采用人工精标紧框 + 河面 50/50 均衡数据配方，从 v6 冻结骨干微调 15 轮；
> 权重 [models/plastic-bottle-near.pt](models/plastic-bottle-near.pt)，ONNX 以 640 输入导出。
> 完整门禁记录见 [scripts/v7_gates_report.txt](scripts/v7_gates_report.txt)。

## 自检

```powershell
# 后端：训练产物 / 指标 / 服务 / 河面漂浮瓶批量检出 / 无瓶图不误检
python scripts/self_check.py

# 前端：登录 → 上传 → 只出塑料瓶 → 识别框在画面内 → 写入明细 → 关摄像头清空 → 无云端调用
$env:NODE_PATH='D:\Systemp\Temp\pwtest\node_modules'
node scripts\browser_check.mjs
```

自检的正样本改为**河面漂浮瓶验证集批量抽查**（检出率 ≥85%、平均 IoU ≥0.5、框高覆盖 ≥80%），
不再依赖单张室内图片。

## 已知边界

- 极小目标（框面积 <0.2% 图高）召回偏低，河道远景小瓶可能漏检；
- 多物体严重交叠、混有易拉罐等异物的极端场景存在漏检；
- 手持留出集 9 张中 1 张（细长小瓶）未检出，手持场景整体检出 89%。

## 云端链路（可选回退，非必需）

早期尝试过百炼 VL + LoRA 微调（`scripts/submit_finetune.py`、`build_qwen_jsonl.py`），
因最终目标改为**本地离线**而不再是必需依赖，相关脚本保留作为备选方案。
