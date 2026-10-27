"""河道漂浮垃圾检测模型训练脚本（河道模型训练工程师）。

本脚本是整条链路的第二环，输入是数据标注工程师产出的 river_data.yaml，
输出一份可以直接交给后端接口工程师部署的权重文件。

脚本做四件事：
    1) 河道场景定向数据增强：针对"水面反光 / 波纹 / 半浸水 / 水草干扰"四类难点，
       用 OpenCV 生成难例增强样本（合成高光斑、波纹扰动、过曝、水草纹理干扰）；
    2) 训练 YOLOv8n 轻量模型（3.1M 参数，CPU 可跑，可上边缘设备）；
    3) 逐轮监控 mAP：把 precision / recall / mAP50 / mAP50-95 实时打印并落盘；
    4) 训练结束导出权重（PT 给后端直接加载，ONNX 供离线部署与标注辅助使用）。

依赖：ultralytics、opencv-python、pillow
运行：
    python train_module/train_river_yolov8n.py --data dataset/river_data.yaml --epochs 60
"""
from __future__ import annotations

import argparse
import csv
import random
import shutil
import time
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

# ---------------- 训练超参（河道场景调优后的取值） ----------------
# 预训练权重：YOLOv8n 官方权重，赛道级部署常用起点
BASE_MODEL = "yolov8n.pt"
# 输入分辨率：640 是精度与速度的平衡点；512 会漏掉远处小目标，768 反而更慢且更易误报
IMGSZ = 640
# 批大小：CPU 训练建议 8~16
BATCH = 16
# 随机种子固定，保证结果可复现
SEED = 42
# Windows 下多进程读取图片容易报错，worker 设为 0
WORKERS = 0
# 优化器与学习率：河道样本量小，用 AdamW + 小学习率更稳
OPTIMIZER = "AdamW"
LR0 = 0.001
LRF = 0.1  # 最后一轮学习率衰减到初值的 10%
# 早停耐心值
PATIENCE = 50
# 增强副本相对原数据的倍数（1 表示不额外增强）
AUG_REPEAT = 1
# 难例增强中"水草纹理干扰"的贴图目录（可为空，为空则跳过该项）
WEED_DIR = Path("assets/weed")


def resolve_base_model(model_name: str) -> str:
    """解析起始权重路径：优先用本地已有的 yolov8n.pt，保证离线环境也能直接跑。

    顺序：本目录 -> 上级目录 -> 工程内 ai-training -> 交给 ultralytics 自动下载。
    """
    # 常见本地存放位置
    candidates = [
        Path(__file__).resolve().parent / model_name,
        Path(__file__).resolve().parent.parent / model_name,
        Path(__file__).resolve().parent.parent / "ai-training" / model_name,
    ]
    # 命中就直接返回本地路径
    for path in candidates:
        if path.exists():
            print(f"[权重] 使用本地预训练权重: {path}")
            return str(path)
    # 本地没有就交给 ultralytics 按名字处理（可能触发下载）
    return model_name


# ================= 第一部分：河道场景定向增强 =================
def add_sun_glare(img: np.ndarray, rng: random.Random) -> np.ndarray:
    """模拟水面反光：随机位置叠加白色高光斑，模拟阳光在水面形成的耀斑。

    痛点对应：水面反光会被通用模型误判成白色漂浮物，
    我们在训练数据里主动制造这类干扰，教会模型"高光不是目标"。
    """
    # 副本，避免改动原图
    out = img.copy()
    # 高光斑数量 1~3 个
    for _ in range(rng.randint(1, 3)):
        # 随机中心点
        cx = rng.randint(0, out.shape[1])
        cy = rng.randint(0, out.shape[0])
        # 随机半径（占图幅 3%~12%）
        radius = int(min(out.shape[:2]) * rng.uniform(0.03, 0.12))
        # 构造一个从中心向外衰减的高斯光斑
        yy, xx = np.ogrid[:out.shape[0], :out.shape[1]]
        # 高斯衰减场
        mask = np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2.0 * radius ** 2))
        # 高光强度 60~160
        strength = rng.uniform(60, 160)
        # 只在亮部提亮，避免整体发灰
        blend = np.clip(mask * strength, 0, 255).astype(np.float32)[:, :, None]
        # 加到原图上
        out = np.clip(out.astype(np.float32) + blend, 0, 255).astype(np.uint8)
    return out


def add_ripple(img: np.ndarray, rng: random.Random) -> np.ndarray:
    """模拟水面波纹：做轻微的局部扭曲 + 横向方向性模糊，模拟水波造成的形变与拖影。

    痛点对应：水面波纹让目标边缘变形，模型在波纹图上容易框不准。
    """
    # 副本
    out = img.copy()
    # 随机做 1~2 次正弦方向扭曲
    h, w = out.shape[:2]
    # 构造横纵坐标网格
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    # 随机振幅与频率
    amp = rng.uniform(2.0, 6.0)
    freq = rng.uniform(0.01, 0.04)
    # 相位
    phase = rng.uniform(0, 6.28)
    # 正弦位移场：水平方向按行相位偏移，模拟横向波纹
    dx = amp * np.sin(2 * np.pi * freq * yy + phase)
    dy = amp * np.sin(2 * np.pi * freq * xx + phase) * 0.4
    # 加上原坐标
    map_x = (xx + dx).astype(np.float32)
    map_y = (yy + dy).astype(np.float32)
    # 仿射重映射实现扭曲
    out = cv2.remap(out, map_x, map_y, interpolation=cv2.INTER_LINEAR,
                    borderMode=cv2.BORDER_REFLECT)
    # 轻微运动模糊，模拟水面反光造成的拖影
    if rng.random() < 0.5:
        # 随机方向的核
        k = rng.choice([3, 5])
        kernel = np.zeros((k, k), np.float32)
        if rng.random() < 0.5:
            kernel[k // 2, :] = 1.0 / k
        else:
            kernel[:, k // 2] = 1.0 / k
        out = cv2.filter2D(out, -1, kernel)
    return out


def add_overexposure(img: np.ndarray, rng: random.Random) -> np.ndarray:
    """模拟正午过曝：整体提亮 + 高光区域压白，模拟强光下的水面照片。

    痛点对应：过曝让目标轮廓消失，只剩一个白块。
    """
    # 副本
    out = img.copy()
    # 随机整体提亮系数
    gain = rng.uniform(1.05, 1.35)
    # 提亮
    out = np.clip(out.astype(np.float32) * gain, 0, 255).astype(np.uint8)
    # 对过亮的像素做压白处理
    mask = out > 230
    out[mask] = 255
    return out


def add_weed_texture(img: np.ndarray, rng: random.Random, weed_dir: Path) -> np.ndarray:
    """模拟水草干扰：把水草纹理贴到画面中，构造"像垃圾但不是垃圾"的干扰物。

    痛点对应：水草、浮萍与塑料瓶颜色纹理接近，容易被误检。
    """
    # 没有贴图目录就直接跳过
    if not weed_dir.exists():
        return img
    # 收集可用贴图
    weeds = [p for p in weed_dir.glob("*") if p.suffix.lower() in (".jpg", ".png", ".bmp")]
    if not weeds:
        return img
    # 副本
    out = img.copy()
    # 随机贴 1~2 丛
    for _ in range(rng.randint(1, 2)):
        # 随机选一张贴图
        weed = cv2.imread(str(rng.choice(weeds)))
        if weed is None:
            continue
        # 缩放到画面高度的 10%~30%，模拟远近不同的一丛水草
        scale = rng.uniform(0.1, 0.3)
        nh = max(8, int(out.shape[0] * scale))
        nw = max(8, int(weed.shape[1] * nh / max(1, weed.shape[0])))
        # 缩放贴图
        weed = cv2.resize(weed, (nw, nh))
        # 随机位置（贴在下半部分水面区域更真实）
        y0 = rng.randint(int(out.shape[0] * 0.25), max(int(out.shape[0] * 0.25) + 1, out.shape[0] - nh))
        x0 = rng.randint(0, max(1, out.shape[1] - nw))
        # 贴到画面上
        out[y0:y0 + nh, x0:x0 + nw] = weed
    return out


def augment_dataset(data_root: Path, seed: int = SEED) -> Path:
    """生成增强数据集：原图 + 难例增强副本，标注同步复制。

    返回增强数据集根目录（dataset_aug）。
    """
    # 固定随机种子
    rng = random.Random(seed)
    # 增强集根目录
    aug_root = data_root.parent / f"{data_root.name}_aug"
    # 存在则先清空
    if aug_root.exists():
        shutil.rmtree(aug_root)
    # 复制原数据集（含 yaml），保证结构一致
    shutil.copytree(data_root, aug_root)
    # 统计增强出来的图片数
    made = 0
    # 遍历训练集图片
    for split in ("train", "val"):
        img_dir = aug_root / split / "images"
        lbl_dir = aug_root / split / "labels"
        if not img_dir.exists():
            continue
        for img_path in sorted(img_dir.glob("*.jpg")):
            lbl_path = lbl_dir / f"{img_path.stem}.txt"
            # 只增强正样本（负样本本来就该保持"什么都没有"）
            if not lbl_path.exists() or not lbl_path.read_text(encoding="utf-8").strip():
                continue
            # 读图
            img = cv2.imread(str(img_path))
            if img is None:
                continue
            # 依次施加四种难例增强
            aug = add_sun_glare(img, rng)
            aug = add_ripple(aug, rng)
            aug = add_overexposure(aug, rng)
            aug = add_weed_texture(aug, rng, WEED_DIR)
            # 写增强图
            aug_name = f"{img_path.stem}_hard.jpg"
            cv2.imwrite(str(img_dir / aug_name), aug)
            # 标注同步复制（几何形状不变，标注沿用）
            shutil.copy2(lbl_path, lbl_dir / f"{Path(aug_name).stem}.txt")
            made += 1
    print(f"[增强] 生成难例增强样本 {made} 张 -> {aug_root}")
    return aug_root


# ================= 第二部分：mAP 监控 =================
def watch_metrics(run_dir: Path, total_epochs: int) -> None:
    """训练过程中每 10 秒读一次 results.csv，实时打印 mAP 监控表。

    河道场景最关心的三个数：
        recall（召回）—— 漏检率，越低说明水面反光/半浸水目标被漏掉得越多；
        mAP50        —— 综合精度；
        precision    —— 精确率，越低说明水草这类干扰被误报得越多。
    """
    # 监控表头
    print(f"{'轮次':>6} {'Precision':>10} {'Recall':>8} {'mAP50':>8} {'mAP50-95':>10}")
    print("-" * 48)
    # 已经打印过的轮次，避免重复刷屏
    printed = 0
    while True:
        # 结果文件可能还没生成
        csv_path = run_dir / "results.csv"
        if csv_path.exists():
            try:
                # 读表头与全部行
                with csv_path.open("r", encoding="utf-8") as fp:
                    rows = list(csv.DictReader(fp))
                # 只打印新增的轮次
                for row in rows[printed:]:
                    # 轮次序号
                    epoch = int(float(row.get("epoch", 0))) + 1
                    # 四个关键指标
                    prec = float(row.get("metrics/precision(B)", 0))
                    rec = float(row.get("metrics/recall(B)", 0))
                    m50 = float(row.get("metrics/mAP50(B)", 0))
                    m5095 = float(row.get("metrics/mAP50-95(B)", 0))
                    # 打印一行
                    print(f"{epoch:>6} {prec:>10.4f} {rec:>8.4f} {m50:>8.4f} {m5095:>10.4f}", flush=True)
                # 更新已打印轮次
                printed = len(rows)
            except Exception as exc:  # noqa: BLE001 监控容错，不影响训练
                print(f"[监控] 读取结果失败: {exc}")
        # 训练结束标志：权重文件出现且 results.csv 行数达到总轮次
        if (run_dir / "weights" / "best.pt").exists() and printed >= total_epochs:
            print("[监控] 训练已完成，监控结束")
            break
        # 等待 10 秒再看一次
        time.sleep(10)


# ================= 第三部分：主流程 =================
def main() -> int:
    # 命令行参数
    parser = argparse.ArgumentParser(description="河道漂浮垃圾 YOLOv8n 训练")
    parser.add_argument("--data", default="dataset/river_data.yaml", help="数据标注工程师产出的数据配置")
    parser.add_argument("--epochs", type=int, default=60, help="训练轮数")
    parser.add_argument("--model", default=BASE_MODEL, help="起始预训练权重")
    parser.add_argument("--project", default="runs", help="输出根目录")
    parser.add_argument("--name", default="river_yolov8n", help="本次训练名称")
    parser.add_argument("--no-augment", action="store_true", help="跳过难例增强")
    parser.add_argument("--no-export-onnx", action="store_true",
                        help="不导出 ONNX（默认导出：PT 用于 PyTorch 推理，ONNX 用于标注辅助与边缘部署）")
    args = parser.parse_args()

    # 数据配置路径
    data_path = Path(args.data).resolve()
    # 检查数据配置是否存在
    if not data_path.exists():
        print(f"错误：找不到数据配置 {data_path}，请先运行 数据标注工程师的数据准备脚本")
        return 1

    # 训练用数据目录（开启增强时用增强集）
    train_data = data_path
    # 输出根目录转成绝对路径，避免 ultralytics 拼出 runs/detect/runs 这种嵌套目录
    project_dir = Path(args.project).resolve()
    if not args.no_augment:
        print("=" * 60)
        print("步骤 1/4  河道场景定向增强（反光 / 波纹 / 过曝 / 水草干扰）")
        print("=" * 60)
        # 由 yaml 里的 path 推出数据根目录
        data_root = data_path.parent
        # 生成增强集并改写 yaml 指向
        aug_root = augment_dataset(data_root)
        # 增强集里的 yaml 需要把 path 改成增强集路径
        aug_yaml = aug_root / data_path.name
        if aug_yaml.exists():
            aug_yaml.write_text(
                aug_yaml.read_text(encoding="utf-8").replace(
                    f"path: {data_root.as_posix()}", f"path: {aug_root.as_posix()}"),
                encoding="utf-8")
            train_data = aug_yaml
    else:
        print("=" * 60)
        print("步骤 1/4  跳过难例增强（--no-augment）")
        print("=" * 60)

    # 加载预训练模型
    print("=" * 60)
    print("步骤 2/4  加载预训练权重并开始训练")
    print("=" * 60)
    model = YOLO(resolve_base_model(args.model))
    # 训练参数
    model.train(
        data=str(train_data),          # 数据配置
        epochs=args.epochs,            # 训练轮数
        imgsz=IMGSZ,                   # 输入分辨率 640
        batch=BATCH,                   # 批大小
        optimizer=OPTIMIZER,           # 优化器
        lr0=LR0,                       # 初始学习率
        lrf=LRF,                       # 最终学习率比例
        patience=PATIENCE,             # 早停
        seed=SEED,                     # 随机种子
        workers=WORKERS,               # 数据加载线程（Windows 建议 0）
        project=str(project_dir),   # 输出根目录
        name=args.name,                # 训练名称
        exist_ok=True,                 # 允许覆盖同名目录
        # ---- 基础几何增强：覆盖尺度变化、倾斜、水面晃动导致的构图差异 ----
        hsv_h=0.015,                   # 色调扰动（水色随天气变化）
        hsv_s=0.7,                     # 饱和度扰动（反光时颜色发白）
        hsv_v=0.4,                     # 明度扰动（覆盖过曝/阴影）
        degrees=5.0,                   # 小角度旋转（画面歪斜）
        translate=0.1,                 # 平移（目标不在画面正中）
        scale=0.5,                     # 缩放（远景小目标 / 近景大目标）
        fliplr=0.5,                    # 水平翻转
        mosaic=1.0,                    # 四图拼接，强制模型适应尺度与位置
        close_mosaic=10,               # 最后 10 轮关闭拼接，收敛更稳
    )

    # 训练输出目录
    run_dir = project_dir / args.name

    # 打印 mAP 监控表
    print("=" * 60)
    print("步骤 3/4  训练指标监控（河道场景重点看 Recall 与 Precision）")
    print("=" * 60)
    watch_metrics(run_dir, args.epochs)

    # 导出权重给后端接口工程师接口工程师接口工程师接口工程师
    print("=" * 60)
    print("步骤 4/4  导出权重，交付后端接口工程师")
    print("=" * 60)
    # best.pt 是验证集表现最好的那一版
    best_pt = run_dir / "weights" / "best.pt"
    if not best_pt.exists():
        print("错误：没有找到 best.pt，训练可能异常中断")
        return 1
    # 复制到统一位置，方便后端按固定路径加载
    out_dir = Path("backend_api")
    out_dir.mkdir(parents=True, exist_ok=True)
    # 交付给后端的权重
    out_pt = out_dir / "river_waste_yolov8n.pt"
    shutil.copy2(best_pt, out_pt)
    print(f"已交付权重: {out_pt}")
    # 指标评估报告落盘：每一轮的 Precision/Recall/mAP 全部留存，便于复现与调参
    metrics_csv = run_dir / "results.csv"
    if metrics_csv.exists():
        shutil.copy2(metrics_csv, out_dir / "metrics_report.csv")
        print(f"已保存指标评估报告: {out_dir / 'metrics_report.csv'}")
    # 默认导出 ONNX：PT 用于 PyTorch 推理，ONNX 用于标注辅助模型与边缘设备部署
    if not args.no_export_onnx:
        # 重新加载导出的权重再导出，保证导出的是 best 而不是 last
        YOLO(str(out_pt)).export(format="onnx", imgsz=IMGSZ, simplify=True)
        print(f"已导出 ONNX: {out_pt.with_suffix('.onnx')}")
    # 读取最终指标
    csv_path = run_dir / "results.csv"
    if csv_path.exists():
        rows = list(csv.DictReader(csv_path.open(encoding="utf-8")))
        if rows:
            last = rows[-1]
            print("-" * 60)
            print(f"最终指标: Precision={float(last['metrics/precision(B)']):.4f} "
                  f"Recall={float(last['metrics/recall(B)']):.4f} "
                  f"mAP50={float(last['metrics/mAP50(B)']):.4f} "
                  f"mAP50-95={float(last['metrics/mAP50-95(B)']):.4f}")
    print("训练完成，权重已交付后端接口工程师")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
