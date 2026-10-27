"""手持瓶样本采集：从本地摄像头定时抓帧，存入手持瓶数据集目录。

用法：
    python scripts/collect_handheld.py --seconds 90 --interval 2.0
    python scripts/collect_handheld.py --seconds 60 --tag office

采集期间用户手持矿泉水瓶变换姿势即可；首帧保存探针并报告亮度。
产物：datasets/handheld-bottles/images/raw_<tag>_<NNN>.jpg
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "datasets" / "handheld-bottles" / "images"


def save(path: Path, img) -> None:
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 92])
    if not ok:
        raise RuntimeError(f"encode failed: {path}")
    path.write_bytes(buf.tobytes())


def read_brightest(cap, tries: int = 8, delay: float = 0.3):
    """设备刚打开时常出初始化黑帧，连续读多帧返回最亮的一帧。"""
    best = None
    best_bright = -1.0
    for _ in range(tries):
        ok, frame = cap.read()
        if ok and frame is not None:
            bright = float(np.mean(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)))
            if bright > best_bright:
                best, best_bright = frame, bright
        time.sleep(delay)
    return best, best_bright


def find_camera(preferred: int) -> cv2.VideoCapture:
    """打开指定索引；若画面为黑占位（虚拟摄像头/被占用），遍历其他索引找有真实画面的。"""
    cap = cv2.VideoCapture(preferred, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    _, bright = read_brightest(cap, tries=5, delay=0.25)
    if bright > 50:
        return cap
    cap.release()
    for idx in range(5):
        if idx == preferred:
            continue
        cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        _, bright = read_brightest(cap, tries=5, delay=0.25)
        if bright > 50:
            print(f"默认索引 {preferred} 无信号，改用摄像头 {idx}")
            return cap
        cap.release()
    return cv2.VideoCapture(preferred, cv2.CAP_DSHOW)


def main() -> int:
    parser = argparse.ArgumentParser(description="手持瓶样本采集")
    parser.add_argument("--seconds", type=int, default=90, help="采集时长（秒）")
    parser.add_argument("--interval", type=float, default=2.0, help="抓帧间隔（秒）")
    parser.add_argument("--tag", default="", help="文件名附加标记")
    parser.add_argument("--camera", type=int, default=0)
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    cap = find_camera(args.camera)
    if not cap.isOpened():
        print("✗ 无法打开摄像头")
        return 1
    time.sleep(1.0)

    # 首帧探针：确认光照与画面
    frame, bright = read_brightest(cap)
    if frame is None:
        print("✗ 首帧读取失败")
        return 1
    print(f"首帧平均亮度 {bright:.1f}/255" + ("（过暗，请开灯后再采）" if bright < 50 else ""))
    save(OUT / "probe.jpg", frame)
    if bright < 50:
        cap.release()
        return 2

    suffix = f"_{args.tag}" if args.tag else ""
    deadline = time.time() + args.seconds
    count = 0
    next_shot = 0.0
    print(f"开始采集 {args.seconds}s，每 {args.interval}s 一帧——请手持矿泉水瓶变换姿势！（按 Q 提前结束）")

    # 3 秒准备倒计时（headless 环境无预览窗口时静默跳过）
    ready_until = time.time() + 3
    preview_ok = True
    while time.time() < ready_until:
        ok, frame = cap.read()
        if not ok:
            continue
        if preview_ok:
            try:
                disp = frame.copy()
                cv2.putText(disp, f"start in {ready_until - time.time():.0f}s",
                            (30, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.6, (0, 255, 255), 3)
                cv2.imshow("collect", disp)
                if cv2.waitKey(30) & 0xFF == ord("q"):
                    cap.release()
                    try:
                        cv2.destroyAllWindows()
                    except cv2.error:
                        pass
                    print("已取消")
                    return 0
            except cv2.error:
                print("（当前为 headless OpenCV，无预览窗口——请在前端页面实时画面中查看自己）")
                preview_ok = False

    deadline = time.time() + args.seconds
    while time.time() < deadline:
        ok, frame = cap.read()
        if not ok:
            continue
        now = time.time()
        if now >= next_shot:
            count += 1
            path = OUT / f"raw{suffix}_{count:03d}.jpg"
            save(path, frame)
            next_shot = now + args.interval
            print(f"  [{count:03d}] {path.name}  剩余 {max(0, int(deadline - now))}s", flush=True)
        if preview_ok:
            try:
                disp = frame.copy()
                if now < next_shot:
                    cv2.rectangle(disp, (0, 0), (disp.shape[1], 80), (0, 200, 0), -1)
                cv2.putText(disp, f"[{count:03d}] remain {max(0, int(deadline - now))}s  Q=stop",
                            (20, 52), cv2.FONT_HERSHEY_SIMPLEX, 1.4,
                            (255, 255, 255) if now < next_shot else (0, 0, 0), 3)
                cv2.imshow("collect", disp)
                if cv2.waitKey(30) & 0xFF == ord("q"):
                    break
            except cv2.error:
                preview_ok = False
    cap.release()
    try:
        cv2.destroyAllWindows()
    except cv2.error:
        pass
    print(f"采集完成，共 {count} 张 -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
