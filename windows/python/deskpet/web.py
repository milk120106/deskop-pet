"""Local web dashboard on 127.0.0.1:8765..8775 (matching PowerShell's Web UI)."""
from __future__ import annotations

import json
import socket
import threading
import uuid
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .config import APP_DIR, PROV_NAMES, PROV_IDS, log

HTML_PAGE = """<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Desktop Pet / 餘額桌面寵物</title>
<style>
:root{--bg:#f4f5f7;--card:#fff;--ink:#1d1d1f;--sub:#6e6e73;--line:#e3e3e8;--acc:#2f6bff;--bad:#e5484d;--good:#2ea043}
@media (prefers-color-scheme:dark){:root{--bg:#161618;--card:#232326;--ink:#f2f2f4;--sub:#9a9aa2;--line:#35353a;--acc:#6b95ff;--bad:#ff6a6f;--good:#3fb950}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 "Microsoft YaHei UI","PingFang TC",system-ui,sans-serif}
main{max-width:980px;margin:0 auto;padding:20px 16px 40px;display:grid;gap:16px;grid-template-columns:260px 1fr}
@media (max-width:700px){main{grid-template-columns:1fr}}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px}
.pet{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px}.pet img{width:100%;max-width:240px;object-fit:contain}
.badge{display:inline-block;padding:2px 10px;border-radius:999px;font-size:13px;border:1px solid var(--line);color:var(--sub)}
.badge.api{color:var(--acc);border-color:var(--acc)}
.bal{font-size:52px;font-weight:700;letter-spacing:-1px;font-variant-numeric:tabular-nums;margin:6px 0 0}
.bal small{font-size:18px;font-weight:500;color:var(--sub);margin-left:8px}
.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.sub{color:var(--sub);font-size:13px}
.dot{width:9px;height:9px;border-radius:50%;background:var(--bad);display:inline-block}.dot.on{background:var(--good)}
svg{width:100%;height:110px;display:block;margin-top:10px}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:14px}
.stat{border:1px solid var(--line);border-radius:10px;padding:8px 10px}.stat b{display:block;font-size:20px;font-variant-numeric:tabular-nums}
button{font:inherit;border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:8px;padding:6px 12px;cursor:pointer}
button:hover{border-color:var(--acc);color:var(--acc)}
ul{list-style:none;margin:0;padding:0;max-height:260px;overflow:auto}
li{display:flex;justify-content:space-between;gap:10px;padding:7px 0;border-top:1px solid var(--line);font-variant-numeric:tabular-nums}
li:first-child{border-top:0}.neg{color:var(--bad)}.pos{color:var(--good)}
h2{font-size:14px;margin:0 0 8px;color:var(--sub);font-weight:600}
.wide{grid-column:1/-1}pre{margin:0;white-space:pre-wrap;font:12px/1.5 Consolas,monospace;color:var(--sub);max-height:220px;overflow:auto}
a{color:var(--acc);text-decoration:none}a:hover{text-decoration:underline}
</style></head><body><main>
<div class="card pet"><img id="pet" src="/sprite.png" alt=""><span id="char" class="sub">--</span><span id="info" class="sub"></span></div>
<div class="card">
 <div class="row"><span id="mode" class="badge">-</span><span class="row sub"><span id="dot" class="dot"></span><span id="status">--</span></span></div>
 <div class="bal"><span id="bal">--</span><small id="cur"></small></div>
 <svg id="chart" viewBox="0 0 500 100" preserveAspectRatio="none"><path id="line" fill="none" stroke="var(--acc)" stroke-width="2"/></svg>
 <div class="stats">
  <div class="stat"><span class="sub">今日已用</span><b id="s_used">0.00</b></div>
  <div class="stat"><span class="sub">今日充值</span><b id="s_top">0.00</b></div>
  <div class="stat"><span class="sub">在場飯盆</span><b id="s_bowls">0</b></div>
  <div class="stat"><span class="sub">最後更新</span><b id="s_up" style="font-size:15px;line-height:26px">--</b></div>
 </div>
 <div class="row" style="margin-top:14px">
  <button onclick="act('refresh')">立即刷新</button>
  <button onclick="act('mode')">切換模式</button>
  <button onclick="act('charge1')">模擬扣款 0.01</button>
  <button onclick="act('charge10')">模擬扣款 0.10</button>
  <button onclick="act('topup')">模擬充值</button>
  <button onclick="act('clearbowls')">清除飯盆</button>
  <a href="/history.csv" style="margin-left:auto">下載 CSV</a>
 </div>
</div>
<div class="card wide"><h2>最近變動紀錄</h2><ul id="events"></ul></div>
<div class="card wide"><h2>執行記錄</h2><pre id="log">載入中...</pre></div>
</main>
<script>
const TOKEN="@@TOKEN@@";
async function act(name){
  try{await fetch('/api/action?token='+TOKEN+'&name='+name,{method:'POST'})}catch(e){}
  poll();
}
function drawChart(pts){
  if(!pts||pts.length<2){document.getElementById('line').setAttribute('d','');return;}
  const vs=pts.map(p=>p.b),mn=Math.min(...vs),mx=Math.max(...vs),rng=(mx-mn)||1;
  const d=pts.map((p,i)=>{
    const x=(i/(pts.length-1)*500).toFixed(1);
    const y=(90-(p.b-mn)/rng*80).toFixed(1);
    return (i===0?'M':'L')+x+','+y;
  }).join(' ');
  document.getElementById('line').setAttribute('d',d);
}
async function poll(){
  try{
    const r=await fetch('/api/state');const d=await r.json();
    document.getElementById('mode').textContent=d.mode==='sim'?'模擬模式':d.provider;
    document.getElementById('mode').className='badge '+(d.mode==='api'?'api':'');
    document.getElementById('dot').className='dot '+(d.connected?'on':'');
    document.getElementById('status').textContent=d.connected?'已連線':(d.error||'離線');
    document.getElementById('bal').textContent=d.balance!==null?d.balance.toFixed(2):'--';
    document.getElementById('cur').textContent=d.currency;
    document.getElementById('char').textContent=d.character;
    document.getElementById('s_used').textContent=d.todayUsed.toFixed(2);
    document.getElementById('s_top').textContent=d.todayTopUp.toFixed(2);
    document.getElementById('s_bowls').textContent=d.bowls;
    document.getElementById('s_up').textContent=d.updated||'--';
    drawChart(d.events);
    const ul=document.getElementById('events');ul.innerHTML='';
    (d.events||[]).slice().reverse().slice(0,30).forEach(e=>{
      const li=document.createElement('li');
      li.innerHTML=`<span>${e.t}</span><span class="${e.d>=0?'pos':'neg'}">${e.d>=0?'+':''}${e.d.toFixed(2)}</span><b>${e.b.toFixed(2)}</b>`;
      ul.appendChild(li);
    });
    document.getElementById('log').textContent=(d.log||[]).join('\\n');
  }catch(e){}
}
poll();setInterval(poll,1500);
</script></body></html>
"""


class WebServer:
    def __init__(self, app):
        self.app = app
        self.port = 0
        self.token = uuid.uuid4().hex
        self.server: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None
        self.start()

    def start(self):
        for p in range(8765, 8776):
            try:
                s = ThreadingHTTPServer(("127.0.0.1", p), self._make_handler())
                self.server = s
                self.port = p
                break
            except OSError:
                continue

        if not self.server:
            log("Web: No free port in range 8765..8775")
            return

        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        log(f"Web: Running at http://127.0.0.1:{self.port}/")

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/" if self.port else ""

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None

    def _make_handler(self):
        ws = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass  # Quiet down terminal logging

            def do_GET(self):
                u = urlparse(self.path)
                path = u.path
                if path in ("/", "/index.html"):
                    page = HTML_PAGE.replace("@@TOKEN@@", ws.token)
                    self._send(200, "text/html; charset=utf-8", page.encode("utf-8"))
                elif path == "/api/state":
                    data = ws._build_state()
                    self._send(200, "application/json; charset=utf-8", json.dumps(data, ensure_ascii=False).encode("utf-8"))
                elif path == "/history.csv":
                    csv_data = ws._build_csv()
                    self._send(200, "text/csv; charset=utf-8", csv_data.encode("utf-8"))
                elif path == "/sprite.png":
                    # Serve current character sprite image
                    p = ws.app.pet._char_image_path("happy")
                    try:
                        with open(p, "rb") as f:
                            self._send(200, "image/png", f.read())
                    except OSError:
                        self._send(404, "text/plain", b"Not found")
                else:
                    self._send(404, "text/plain", b"Not found")

            def do_POST(self):
                u = urlparse(self.path)
                path = u.path
                if path not in ("/api/action", "/feed", "/topup"):
                    self._send(404, "text/plain", b"Not found")
                    return
                qs = parse_qs(u.query)
                tok = qs.get("token", [""])[0]
                name = qs.get("name", [""])[0]
                if path == "/feed":
                    name = "feed"
                elif path == "/topup":
                    name = "topup"
                if tok and tok != ws.token:
                    self._send(403, "application/json", b'{"ok":false,"error":"bad token"}')
                    return
                ok = ws._handle_action(name)
                self._send(200 if ok else 400, "application/json", json.dumps({"ok": ok}).encode("utf-8"))

            def _send(self, code: int, ctype: str, body: bytes):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

        return Handler

    def _build_state(self) -> dict:
        app = self.app
        led = app.ledger
        cfg = app.cfg
        prov_name = PROV_NAMES[PROV_IDS.index(cfg.get("provider", "deepseek"))] if cfg.get("provider") in PROV_IDS else "DeepSeek"

        tail_logs = []
        log_path = APP_DIR / "pet.log"
        if log_path.exists():
            try:
                lines = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
                tail_logs = lines[-16:]
            except Exception:
                pass

        return {
            "mode": cfg.get("mode", "sim"),
            "provider": prov_name,
            "currency": led.currency,
            "balance": led.shown,
            "connected": led.online,
            "error": led.error,
            "character": app.pet.character,
            "todayUsed": float(cfg.get("today_used", 0.0)),
            "todayTopUp": float(cfg.get("today_topup", 0.0)),
            "bowls": len(app.pet.props.rice()),
            "updated": datetime.now().strftime("%H:%M:%S"),
            "events": [{"t": t, "d": d, "b": b} for t, d, b in led.events],
            "log": tail_logs,
        }

    def _build_csv(self) -> str:
        lines = ["\ufefftime,delta,balance"]
        for t, d, b in self.app.ledger.events:
            lines.append(f"{t},{d:.2f},{b:.2f}")
        return "\n".join(lines) + "\n"

    def _handle_action(self, name: str) -> bool:
        app = self.app
        if name == "refresh":
            app.ledger.refresh()
            return True
        elif name == "mode":
            new_mode = "api" if app.cfg.get("mode") == "sim" else "sim"
            app.set_mode(new_mode)
            return True
        elif name == "charge1":
            app.ledger.sim_charge(1)
            return True
        elif name == "charge10":
            app.ledger.sim_charge(10)
            return True
        elif name == "topup":
            app.ledger.sim_topup(3.0)
            return True
        elif name == "feed":
            rices = app.pet.props.rice()
            if rices:
                b = rices[0]
                app.pet.props.remove(b)
                app.pet.feed(b.amount, b.pos)
            else:
                app.ledger.sim_topup(3.0)
            return True
        elif name == "clearbowls":
            app.pet.props.clear()
            return True
        return False
