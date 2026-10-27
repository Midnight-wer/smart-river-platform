"""摄像头实测脚本：本地摄像头取流 -> 检测服务 -> 可视化落盘。

用法：
    python scripts/cam_test.py                # 连续采样 20 秒
    python scripts/cam_test.py --seconds 60   # 采样 60 秒
    python scripts/cam_test.py --conf 0.25    # 指定置信度阈值

产物（reports/camtest/）：
    hitNN.jpg     检出目标的原始帧
    hitvisNN.jpg  画出检测框的叠加帧
控制台输出每帧检出数量、最高置信度，结束时汇总检出率。
"""
from __future__ import annotations

import argparse
import base64
import json
import time
import urllib.request
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "camtest"
URL = "http://127.0.0.1:8000/detect"


def save(path: Path, img) -> None:
    """OpenCV 的 imwrite 在含中文路径下会静默失败，改走 imencode + 二进制写。"""
    ok, buf = cv2.imencode(".jpg", img)
    if not ok:
        raise RuntimeError(f"encode failed: {path}")
    path.write_bytes(buf.tobytes())


def find_camera(preferred: int) -> cv2.VideoCapture:
    """同 collect_handheld：黑占位（虚拟摄像头）时自动换真实设备。"""
    import numpy as np
    cap = cv2.VideoCapture(preferred, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    time.sleep(0.8)
    ok, frame = cap.read()
    if ok and frame is not None and float(np.mean(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))) > 50:
        return cap
    cap.release()
    for idx in range(5):
        if idx == preferred:
            continue
        cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        time.sleep(0.8)
        ok, frame = cap.read()
        if ok and frame is not None and float(np.mean(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))) > 50:
            print(f"默认索引 {preferred} 无信号，改用摄像头 {idx}")
            return cap
        cap.release()
    return cv2.VideoCapture(preferred, cv2.CAP_DSHOW)


def detect(img, conf: float) -> list[dict]:
    ok, buf = cv2.imencode(".jpg", img)
    payload = {
        "image": "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode(),
        "conf": conf,
    }
    req = urllib.request.Request(
        URL, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())["items"]


def draw(frame, items: list[dict]):
    vis = frame.copy()
    h, w = frame.shape[:2]
    for i in items:
        x1 = int((i["x"] - i["width"] / 2) / 100 * w)
        y1 = int((i["y"] - i["height"] / 2) / 100 * h)
        x2 = int((i["x"] + i["width"] / 2) / 100 * w)
        y2 = int((i["y"] + i["height"] / 2) / 100 * h)
        cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 255, 0), 4)
        cv2.putText(vis, f"{i['confidence']:.2f}", (x1, max(30, y1 - 12)),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)
    return vis


def main() -> int:
    parser = argparse.ArgumentParser(description="摄像头实测")
    parser.add_argument("--seconds", type=int, default=20, help="采样时长（秒）")
    parser.add_argument("--conf", type=float, default=0.25, help="置信度阈值")
    parser.add_argument("--interval", type=float, default=0.4, help="采样间隔（秒）")
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    cap = find_camera(0)
    if not cap.isOpened():
        print("✗ 无法打开摄像头 0")
        return 1
    time.sleep(1.0)

    deadline = time.time() + args.seconds
    index = hits = 0
    best_conf = 0.0
    probe_saved = False
    while time.time() < deadline:
        ok, frame = cap.read()
        if not ok:
            continue
        index += 1
        if not probe_saved:
            # 每次运行保存首帧探针，便于排查现场光照/画面内容
            save(OUT / "probe.jpg", frame)
            import numpy as np
            bright = float(np.mean(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)))
            print(f"首帧平均亮度 {bright:.1f}/255"
                  + ("（过暗，建议开灯）" if bright < 50 else ""), flush=True)
            probe_saved = True
        try:
            items = detect(frame, args.conf)
        except Exception as error:  # noqa: BLE001
            print(f"帧{index}: 检测服务调用失败 {error}", flush=True)
            break
        if items:
            hits += 1
            conf = max(i["confidence"] for i in items)
            best_conf = max(best_conf, conf)
            print(f"帧{index}: 检出 {len(items)} 个，最高置信度 {conf:.3f}", flush=True)
            save(OUT / f"hit{index}.jpg", frame)
            save(OUT / f"hitvis{index}.jpg", draw(frame, items))
        time.sleep(args.interval)
    cap.release()

    print(f"共采样 {index} 帧，检出帧 {hits}"
          + (f"，最高置信度 {best_conf:.3f}" if hits else ""), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
