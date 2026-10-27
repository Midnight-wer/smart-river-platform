"""训练实时监控 + 事件流：本地 HTTP 服务，事件驱动更新。

用法：python scripts/monitor_server.py   （浏览器打开 http://localhost:8010）
事件源：训练轮次、门禁体检、发布结果、中途实测哨兵、X-AnyLabeling 下载。
只读本地文件，不访问外网。
"""
from __future__ import annotations

import json
import re
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs" / "detect" / "plastic-bottle-hand-v1-2"
LOGS = ROOT / "logs"
DL = Path(r"D:\ZM\河道\ai-training-downloads")
EVENTS_FILE = LOGS / "events-hand-v1.jsonl"

# ---------- 事件引擎（内存状态 + jsonl 持久化） ----------
_state = {"rows": 0, "alive": False, "logs_seen": set(), "gate": "",
          "dl_size": -1, "dl_done": False, "sentinel": ""}


def _emit(out: dict, title: str, kind: str = "info") -> None:
    ev = {"t": time.strftime("%H:%M:%S"), "title": title, "kind": kind}
    out["new_events"].append(ev)
    with EVENTS_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(ev, ensure_ascii=False) + "\n")


def _detect_events(out: dict) -> None:
    st = _state
    # 训练启动/结束
    if out["alive"] != st["alive"]:
        if out["alive"]:
            _emit(out, "训练已启动（手持样本占比 50%）", "ok")
        else:
            _emit(out, "训练进程结束", "warn")
        st["alive"] = out["alive"]
    # 每轮完成（重启监控时不重放历史轮次）
    if len(out["rows"]) > st["rows"]:
        if st["rows"] == 0:
            st["rows"] = len(out["rows"])
        else:
            for r in out["rows"][st["rows"]:]:
                _emit(out, f"第 {r[0]} 轮完成：找瓶率 {r[2]}，准确度 {r[3]}", "ok")
            st["rows"] = len(out["rows"])
    # 门禁日志出现
    for fname, msg in [("eval_hand_all.log", "开始体检①：通用门禁评测（河面/跨场景/负样本）"),
                       ("eval_handheld.log", "开始体检②：手持瓶专项评测"),
                       ("export_hand_onnx.log", "正在导出 ONNX 部署文件"),
                       ("pipeline-hand-done.flag", "发布流水线结束")]:
        f = LOGS / fname
        if f.exists() and fname not in st["logs_seen"]:
            st["logs_seen"].add(fname)
            _emit(out, msg, "info")
    # 门禁B 结果
    hb = LOGS / "eval_handheld.log"
    if hb.exists() and "gateB" not in st["logs_seen"]:
        m = re.search(r"召回=([\d.]+)", hb.read_text(encoding="utf-8", errors="ignore"))
        if m:
            st["logs_seen"].add("gateB")
            v = float(m.group(1))
            _emit(out, f"手持瓶专项实测：召回 {v:.0%} " + ("✅ 达标" if v >= 0.85 else "❌ 未达标"),
                  "ok" if v >= 0.85 else "bad")
    # 发布结果（流水线完成标志）
    gate = LOGS / "pipeline-hand-done.flag"
    if gate.exists():
        g = gate.read_text(encoding="utf-8", errors="ignore").strip()
        if g != st["gate"]:
            st["gate"] = g
            if g.startswith("SUCCESS"):
                _emit(out, "🎉 新模型已发布上线！", "ok")
            else:
                _emit(out, f"发布未通过：{g}", "bad")
    # 中途哨兵
    sn = LOGS / "sentinel-v6.txt"
    if sn.exists():
        s = sn.read_text(encoding="utf-8", errors="ignore").strip()
        if s and s != st["sentinel"]:
            st["sentinel"] = s
            _emit(out, f"中途实测（第3轮）：{s}", "info" if "检出" in s else "warn")
    # X-AnyLabeling 下载
    if DL.exists():
        exes = list(DL.glob("X-AnyLabeling*.exe"))
        if exes:
            size = exes[0].stat().st_size
            if st["dl_size"] < 0:
                _emit(out, "开始下载 X-AnyLabeling 安装包", "info")
                st["dl_size"] = size
            elif size == st["dl_size"] and size > 50 * 1024 * 1024 and not st["dl_done"]:
                st["dl_done"] = True
                _emit(out, f"X-AnyLabeling 下载完成（{size // 1024 // 1024} MB）", "ok")
            st["dl_size"] = max(st["dl_size"], size)
            out["dl_size"] = size
            out["dl_done"] = st["dl_done"]


def collect() -> dict:
    out = {"alive": False, "stage": "wait", "epoch": None, "epochFrac": 0.0,
           "map50": None, "rec": None, "remain": None, "rows": [], "tail": "",
           "hand": None, "river": None, "checks": [], "plain_train": "",
           "plain_done": "", "published": False, "new_events": [],
           "events": [], "dl_size": None, "dl_done": False}

    tlog = LOGS / "train_hand_resume.log"
    if tlog.exists():
        out["alive"] = (time.time() - tlog.stat().st_mtime) < 120
    else:
        legacy = LOGS / "train_hand.log"
        if legacy.exists():
            out["alive"] = (time.time() - legacy.stat().st_mtime) < 120

    csv = RUN / "results.csv"
    if csv.exists():
        lines = csv.read_text(encoding="utf-8").strip().splitlines()[1:]
        for line in lines:
            c = line.split(",")
            out["rows"].append([c[0], f"{float(c[5]):.3f}", f"{float(c[6]):.3f}",
                                f"{float(c[7]):.3f}", f"{float(c[8]):.3f}",
                                f"{float(c[1]):.0f}"])
        if lines:
            last = lines[-1].split(",")
            out["epoch"] = int(last[0])
            out["map50"] = f"{float(last[7]):.3f}"
            out["rec"] = f"{float(last[6]):.3f}"
            out["remain"] = f"{max(0, 18 - int(last[0])) * 7} 分钟"
            if tlog.exists():
                tail = tlog.read_text(encoding="utf-8", errors="ignore")
                m = re.search(rf"^{out['epoch']}/18 .*?(\d+)/\d+", tail, re.M)
                if m:
                    out["epochFrac"] = int(m.group(1)) / 145

    all_log = LOGS / "eval_hand_all.log"
    hand_log = LOGS / "eval_handheld.log"
    done_flag = LOGS / "pipeline-hand-done.flag"
    if done_flag.exists():
        out["stage"] = "done"
        out["published"] = "SUCCESS" in done_flag.read_text(encoding="utf-8", errors="ignore")
    elif all_log.exists():
        out["stage"] = "gate"

    if all_log.exists():
        m = re.search(r"R=([\d.]+)", all_log.read_text(encoding="utf-8", errors="ignore"))
        if m:
            out["river"] = float(m.group(1))
    if hand_log.exists():
        m = re.search(r"召回=([\d.]+)",
                      hand_log.read_text(encoding="utf-8", errors="ignore"))
        if m:
            out["hand"] = float(m.group(1))

    checks = []
    if all_log.exists():
        txt = all_log.read_text(encoding="utf-8", errors="ignore")
        for key, human in {
            "mAP50 >= 0.80": "综合识别准确度达标",
            "召回率 >= 0.85": "河面找瓶成功率",
            "平均 IoU >= 0.70": "框得准（框贴住瓶身）",
            "框高覆盖 >= 85%": "框得全（框住完整瓶子）",
            "ssz5 留出召回 >= 0.85": "没见过的新河面图也认识",
            "COCO 通用瓶召回 >= 0.60": "普通生活场景也认识",
            "负样本误报 = 0": "不会把别的东西认成瓶",
        }.items():
            if key in txt:
                seg = txt.split(key)[0].splitlines()[-1]
                checks.append([human, "ok" if "✓" in seg else "bad"])
    out["checks"] = checks

    if out["stage"] not in ("done", "gate") and out["epoch"]:
        trend = ""
        if len(out["rows"]) >= 2:
            a, b = float(out["rows"][-2][2]), float(out["rows"][-1][2])
            trend = "（比上轮回落，学习率调整期正常）" if b < a else "（比上轮提升）"
        out["plain_train"] = (
            f"手持瓶照片已提到训练量的 50%（之前 3%）。已完成 {out['epoch']} 轮，"
            f"找瓶成功率 {out['rec']}{trend}。")

    if tlog.exists():
        tail = tlog.read_text(encoding="utf-8", errors="ignore").strip().splitlines()[-6:]
        out["tail"] = "\n".join(tail)

    # 事件检测 + 历史
    _detect_events(out)
    if EVENTS_FILE.exists():
        lines = EVENTS_FILE.read_text(encoding="utf-8").strip().splitlines()[-30:]
        out["events"] = [json.loads(x) for x in reversed(lines) if x.strip()]
    out["done"] = not out["alive"] and bool(out["rows"])
    return out


HTML = """<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>训练进度 · 事件流</title>
<style>
*{box-sizing:border-box}
body{background:#10141a;color:#e5e9f0;font-family:'Microsoft YaHei',sans-serif;margin:0;padding:24px;max-width:1000px;margin:0 auto}
h1{font-size:22px;margin:0 0 4px}
.sub{color:#8b98a5;font-size:13px;margin-bottom:18px}
.stage{background:linear-gradient(135deg,#1b2735,#2c3e50);border-radius:14px;padding:20px;margin-bottom:16px}
.stage .title{font-size:24px;font-weight:bold;display:flex;align-items:center;gap:10px}
.dot{width:13px;height:13px;border-radius:50%;background:#4c9aff;animation:pulse 1.5s infinite}
.dot.done{background:#2ecc71;animation:none}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
.bar{background:#0d1117;border-radius:10px;height:22px;margin-top:14px;overflow:hidden;position:relative}
.bar .fill{height:100%;background:linear-gradient(90deg,#2f81f7,#4c9aff);transition:width 1s}
.bar .txt{position:absolute;inset:0;text-align:center;font-size:13px;line-height:22px;color:#fff}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px;margin-bottom:16px}
.item{background:#161b22;border-radius:12px;padding:14px}
.item .k{font-size:13px;color:#8b98a5;margin-bottom:6px}
.item .v{font-size:22px;font-weight:bold}
.item .note{font-size:12px;color:#8b98a5;margin-top:4px}
.ok{color:#3fb950}.warn{color:#d29922}.bad{color:#f85149}
.card{background:#161b22;border-radius:12px;padding:16px;margin-bottom:16px}
.card .head{font-size:15px;font-weight:bold;margin-bottom:10px;color:#79c0ff}
.ev{display:flex;gap:10px;padding:7px 0;border-bottom:1px dashed #21262d;font-size:14px;align-items:baseline}
.ev:last-child{border-bottom:none}
.ev .t{color:#8b98a5;font-size:12px;min-width:62px}
.ev .badge{font-size:11px;border-radius:4px;padding:1px 6px;min-width:34px;text-align:center}
.badge.ok{background:#12331f;color:#3fb950}.badge.bad{background:#3d1418;color:#f85149}
.badge.warn{background:#33290f;color:#d29922}.badge.info{background:#1a2740;color:#79c0ff}
details{background:#161b22;border-radius:12px;padding:14px;margin-top:16px}
summary{cursor:pointer;color:#8b98a5;font-size:14px}
pre{background:#0d1117;border-radius:8px;padding:12px;font-size:12px;overflow:auto;max-height:200px;color:#9aa7b3}
svg text{font-family:'Microsoft YaHei'}
</style></head><body>
<h1>手持矿泉水瓶识别模型 · 训练进度</h1>
<div class="sub">事件实时推送 · 每 2 秒刷新 · 模型代号 hand-v1</div>

<div class="stage">
  <div class="title"><span class="dot" id="dot"></span><span id="stage">加载中…</span></div>
  <div class="bar"><div class="fill" id="fill" style="width:0%"></div><div class="txt" id="filltxt"></div></div>
</div>

<div class="grid">
  <div class="item"><div class="k">训练轮次</div><div class="v" id="m-epoch">-</div><div class="note" id="n-remain"></div></div>
  <div class="item"><div class="k">综合识别准确度</div><div class="v" id="m-map">-</div><div class="note">验证集 mAP50</div></div>
  <div class="item"><div class="k">找瓶成功率</div><div class="v" id="m-rec">-</div><div class="note">验证集召回</div></div>
</div>
<div class="grid">
  <div class="item"><div class="k">🎯 手持瓶专项（目标）</div><div class="v" id="m-hand">检测中</div><div class="note">手持瓶照片实测召回</div></div>
  <div class="item"><div class="k">🌊 河面漂浮瓶（保底）</div><div class="v" id="m-river">未评测</div><div class="note">确认没学新忘旧</div></div>
  <div class="item"><div class="k">📦 标注软件下载</div><div class="v" id="m-dl">-</div><div class="note">X-AnyLabeling 安装包</div></div>
</div>

<div class="card"><div class="head">⚡ 事件流（最新在上）</div><div id="events"></div></div>

<div class="card"><div class="head">✅ 发布前体检</div><div id="checks">训练完成后自动体检</div></div>

<details><summary>能力曲线与技术细节</summary>
<svg id="chart" width="100%" height="200" viewBox="0 0 900 200" preserveAspectRatio="none"></svg>
<pre id="tlog"></pre></details>
<script>
async function tick(){
  try{
    const s = await (await fetch('/api/status')).json();
    const dot=document.getElementById('dot'), stage=document.getElementById('stage');
    let st,pct;
    if(s.stage==='done'){st='🎉 完成，新模型已上线';pct=100;}
    else if(s.stage==='gate'){st='🧪 训练完成，体检评测中';pct=100;}
    else if(s.alive){st=`🏋️ 模型学习中 · 第 ${s.epoch||1} 轮 / 18 轮`;pct=Math.min(99,((s.epoch||1)-1+(s.epochFrac||0))/18*100);}
    else{st='等待训练启动';pct=0;}
    stage.textContent=st;
    document.getElementById('fill').style.width=pct+'%';
    document.getElementById('filltxt').textContent=s.alive?`整体进度 ${pct.toFixed(0)}%`:(s.stage==='done'?'100%':'');
    dot.className='dot'+(s.stage==='done'?' done':'');
    document.getElementById('m-epoch').textContent=s.epoch?`${s.epoch} / 18`:'-';
    document.getElementById('n-remain').textContent=s.remain&&s.alive?`预计还需 ${s.remain}`:'';
    document.getElementById('m-map').textContent=s.map50?(parseFloat(s.map50)*100).toFixed(0)+'%':'-';
    document.getElementById('m-rec').textContent=s.rec?(parseFloat(s.rec)*100).toFixed(0)+'%':'-';
    const h=document.getElementById('m-hand');
    if(s.hand==null){h.textContent='待体检';h.className='v warn';}
    else{h.textContent=(s.hand*100).toFixed(0)+'%';h.className='v '+(s.hand>=0.85?'ok':'bad');}
    const rv=document.getElementById('m-river');
    if(s.river==null){rv.textContent='未评测';rv.className='v';}
    else{rv.textContent=(s.river*100).toFixed(0)+'%';rv.className='v '+(s.river>=0.8?'ok':'warn');}
    const dl=document.getElementById('m-dl');
    if(s.dl_size==null){dl.textContent='未开始';dl.className='v';}
    else if(s.dl_done){dl.textContent='✓ 完成';dl.className='v ok';}
    else{dl.textContent=(s.dl_size/1048576).toFixed(0)+'MB';dl.className='v';}
    // 事件流
    document.getElementById('events').innerHTML = s.events.length ?
      s.events.map(e=>`<div class="ev"><span class="t">${e.t}</span><span class="badge ${e.kind}">${e.kind==='ok'?'完成':e.kind==='bad'?'问题':e.kind==='warn'?'注意':'进展'}</span><span>${e.title}</span></div>`).join('')
      : '<div class="ev"><span class="t">--</span><span>暂无事件，训练启动后自动记录</span></div>';
    // 体检清单
    document.getElementById('checks').innerHTML = s.checks.length ? s.checks.map(c=>
      `<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px dashed #21262d;font-size:14px"><span>${c[0]}</span><span class="${c[1]}">${c[1]==='ok'?'✓ 通过':'✗ 未过'}</span></div>`).join('')
      : '训练完成后自动体检';
    // 曲线
    const pts=s.rows, svg=document.getElementById('chart');
    if(pts.length){
      const W=900,H=190,P=30;
      const xs=i=>P+i*(W-2*P)/Math.max(pts.length-1,1);
      const ys=v=>H-P-(v/1.0)*(H-2*P);
      let g='';[0.25,0.5,0.75,1.0].forEach(v=>{g+=`<line x1="${P}" y1="${ys(v)}" x2="${W-P}" y2="${ys(v)}" stroke="#21262d"/><text x="2" y="${ys(v)-3}" fill="#4c566a" font-size="10">${v*100}%</text>`;});
      const line=(idx,color)=>{let d='';pts.forEach((r,i)=>{d+=(i?'L':'M')+xs(i)+','+ys(parseFloat(r[idx]));});return `<path d="${d}" stroke="${color}" fill="none" stroke-width="2.5"/>`;};
      svg.innerHTML=g+line(3,'#79c0ff')+line(2,'#ffd33b')+
        `<text x="${W-P-140}" y="16" fill="#79c0ff" font-size="12">● 综合准确度</text><text x="${W-P-40}" y="16" fill="#ffd33b" font-size="12">● 找瓶率</text>`;
    }
    document.getElementById('tlog').textContent=s.tail||'(暂无)';
  }catch(e){}
}
tick();setInterval(tick,2000);
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, body: bytes, ctype: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/api/status"):
            self._send(json.dumps(collect(), ensure_ascii=False).encode("utf-8"),
                       "application/json; charset=utf-8")
        else:
            self._send(HTML.encode("utf-8"), "text/html; charset=utf-8")

    def log_message(self, fmt: str, *args) -> None:  # noqa: N802
        return


def main() -> None:
    LOGS.mkdir(exist_ok=True)
    server = ThreadingHTTPServer(("0.0.0.0", 8010), Handler)
    print("[monitor] 实时监控页(事件流): http://localhost:8010", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
