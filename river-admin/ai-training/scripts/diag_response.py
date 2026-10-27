"""诊断：对比 v3/v4 权重对手持 val 图的弱响应，判断学习方向。"""
from ultralytics import YOLO

p = 'datasets/hybrid/images/val/webcap_093841_c9d6.jpg'
for name, w in [('v3(10轮)', 'runs/detect/handheld-v3/weights/last.pt'),
                ('v4(3轮)', 'runs/detect/handheld-v4/weights/last.pt')]:
    m = YOLO(w)
    r = m.predict(p, conf=0.01, imgsz=640, verbose=False)[0]
    tops = sorted((round(float(b.conf), 3) for b in r.boxes), reverse=True)[:3]
    print(f'{name} conf=0.01 弱响应: {tops}')
