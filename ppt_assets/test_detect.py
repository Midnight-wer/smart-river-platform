# 测试本地8000端口YOLO检测服务
import base64, json, urllib.request

img_path = r"D:\ZM\河道\river_plastic_detect\dataset\images\river_0013000066.jpg"
with open(img_path, "rb") as f:
    b64 = base64.b64encode(f.read()).decode()

payload = json.dumps({
    "image": "data:image/jpeg;base64," + b64,
    "conf": 0.35,
    "scene": "upload",
}).encode("utf-8")

req = urllib.request.Request(
    "http://127.0.0.1:8000/detect",
    data=payload,
    headers={"Content-Type": "application/json"},
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        print("HTTP", resp.status)
        print(json.dumps(data, ensure_ascii=False, indent=2)[:1500])
except Exception as e:
    print("ERROR:", repr(e))
