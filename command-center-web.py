#!/usr/bin/env python3
"""
MERIDIAN COMMAND CENTER — Web Edition
Lightweight HTTP dashboard for remote access.
No dependencies beyond Python stdlib.
Access from any browser: http://<machine-ip>:8090
"""

import http.server
import json
import os
import time
import sqlite3
import subprocess
import urllib.parse
from datetime import datetime

PORT = 8090
BASE = "/home/joel/autonomous-ai"
HB = os.path.join(BASE, ".heartbeat")
DASH_MSG = os.path.join(BASE, ".dashboard-messages.json")
LOOP_FILE = os.path.join(BASE, ".loop-count")
MEMORY_DB = os.path.join(BASE, "memory.db")

def get_system_health():
    try:
        load = open("/proc/loadavg").read().split()[:3]
        load_str = " ".join(load)
    except:
        load_str = "?"
    try:
        mem = {}
        for line in open("/proc/meminfo"):
            parts = line.split()
            mem[parts[0].rstrip(":")] = int(parts[1])
        total = mem.get("MemTotal", 0) / 1024 / 1024
        avail = mem.get("MemAvailable", 0) / 1024 / 1024
        used = total - avail
        ram_str = f"{used:.1f}G / {total:.1f}G"
    except:
        ram_str = "?"
    try:
        df = subprocess.check_output(["df", "/", "--output=size,used,pcent"], text=True).strip().split("\n")[1].split()
        disk_str = f"{int(df[1])//1024//1024}G used, {df[2]} full"
    except:
        disk_str = "?"
    try:
        uptime_s = float(open("/proc/uptime").read().split()[0])
        h, m = int(uptime_s // 3600), int((uptime_s % 3600) // 60)
        uptime_str = f"{h}h {m}m"
    except:
        uptime_str = "?"
    services = {}
    for name, pattern in [("protonmail-bridge", "protonmail-bridge"),
                          ("irc-bot", "irc-bot.py"),
                          ("command-center", "command-center"),
                          ("ollama", "ollama")]:
        try:
            result = subprocess.run(["pgrep", "-f", pattern], capture_output=True)
            services[name] = "up" if result.returncode == 0 else "down"
        except:
            services[name] = "?"
    return {"load": load_str, "ram": ram_str, "disk": disk_str, "uptime": uptime_str, "services": services}

def get_heartbeat():
    try:
        age = time.time() - os.path.getmtime(HB)
        status = "OK" if age < 600 else "STALE"
        return {"status": status, "age_seconds": int(age)}
    except:
        return {"status": "MISSING", "age_seconds": -1}

def get_loop_count():
    try:
        return int(open(LOOP_FILE).read().strip())
    except:
        return 0

def get_dashboard_messages(limit=25):
    try:
        data = json.load(open(DASH_MSG))
        # Handle both formats: {"messages": [...]} or plain [...]
        if isinstance(data, dict):
            msgs = data.get("messages", [])
        elif isinstance(data, list):
            msgs = data
        else:
            return []
        return msgs[-limit:]
    except:
        return []

def post_dashboard_message(from_name, text):
    try:
        data = json.load(open(DASH_MSG)) if os.path.exists(DASH_MSG) else []
        # Handle both formats
        if isinstance(data, dict):
            msgs = data.get("messages", [])
        elif isinstance(data, list):
            msgs = data
        else:
            msgs = []
    except:
        msgs = []
    msgs.append({"from": from_name, "text": text, "time": datetime.now().strftime("%H:%M:%S")})
    # Write in dict format (matches V16 and MCP tools)
    with open(DASH_MSG, "w") as f:
        json.dump({"messages": msgs}, f)
    return True

def get_creative_stats():
    try:
        poems = len([f for f in os.listdir(BASE) if f.startswith("poem-") and f.endswith(".md")])
        journals = len([f for f in os.listdir(BASE) if f.startswith("journal-") and f.endswith(".md")])
        cogcorp = len([f for f in os.listdir(os.path.join(BASE, "website"))
                       if f.startswith("cogcorp-") and f.endswith(".html")
                       and f not in ("cogcorp-gallery.html", "cogcorp-article.html")])
        return {"poems": poems, "journals": journals, "cogcorp": cogcorp}
    except:
        return {"poems": 0, "journals": 0, "cogcorp": 0}

def get_relay_messages(limit=10):
    try:
        db = sqlite3.connect(os.path.join(BASE, "agent-relay.db"))
        rows = db.execute("SELECT agent, message, topic, timestamp FROM agent_messages ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        db.close()
        return [{"agent": r[0], "message": r[1], "topic": r[2], "time": r[3]} for r in rows]
    except:
        return []

DASHBOARD_HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MERIDIAN // COMMAND CENTER</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;700&display=swap');
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  background: #0a0a12;
  color: #c8c8cc;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 13px;
  min-height: 100vh;
}
.top-bar {
  background: linear-gradient(90deg, #00cccc, #0088aa);
  padding: 8px 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 11px;
  color: #000;
  font-weight: 700;
  letter-spacing: 2px;
}
.top-bar .pulse {
  animation: pulse 2s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
.container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 16px;
}
.grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
}
@media (max-width: 768px) {
  .grid { grid-template-columns: 1fr; }
}
.panel {
  background: #12121c;
  border: 1px solid #00cccc20;
  border-radius: 4px;
  padding: 16px;
}
.panel h2 {
  font-size: 11px;
  letter-spacing: 3px;
  color: #00cccc;
  margin-bottom: 12px;
  border-bottom: 1px solid #00cccc15;
  padding-bottom: 6px;
}
.stat-row {
  display: flex;
  justify-content: space-between;
  padding: 4px 0;
  border-bottom: 1px solid #ffffff08;
}
.stat-label { color: #666; }
.stat-value { color: #eee; font-weight: 700; }
.stat-value.up { color: #00cc66; }
.stat-value.down { color: #ff3366; }
.stat-value.stale { color: #ffcc00; }
.stat-value.ok { color: #00cc66; }
.messages {
  max-height: 400px;
  overflow-y: auto;
}
.msg {
  padding: 8px;
  border-bottom: 1px solid #ffffff08;
  font-size: 12px;
  line-height: 1.6;
}
.msg .from {
  font-weight: 700;
  color: #00cccc;
  font-size: 10px;
  letter-spacing: 1px;
}
.msg .from.joel { color: #ffcc00; }
.msg .from.eos { color: #cc66ff; }
.msg .time { color: #444; font-size: 10px; margin-left: 8px; }
.msg .text { color: #aaa; margin-top: 2px; }
.compose {
  margin-top: 12px;
  display: flex;
  gap: 8px;
}
.compose input, .compose select {
  background: #0a0a12;
  border: 1px solid #00cccc30;
  color: #eee;
  padding: 6px 10px;
  font-family: inherit;
  font-size: 12px;
  border-radius: 3px;
}
.compose input { flex: 1; }
.compose button {
  background: #00cccc;
  color: #000;
  border: none;
  padding: 6px 16px;
  font-family: inherit;
  font-weight: 700;
  font-size: 11px;
  letter-spacing: 1px;
  cursor: pointer;
  border-radius: 3px;
}
.compose button:hover { background: #00eedd; }
.creative-num {
  font-size: 28px;
  font-weight: 700;
  color: #00cccc;
  text-align: center;
}
.creative-label {
  font-size: 10px;
  color: #666;
  text-align: center;
  letter-spacing: 2px;
}
.creative-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 12px;
  text-align: center;
}
.relay-msg {
  padding: 6px 0;
  border-bottom: 1px solid #ffffff05;
  font-size: 11px;
}
.relay-msg .agent { color: #ff3388; font-weight: 700; }
.full-width { grid-column: 1 / -1; }
.refresh-note {
  text-align: center;
  color: #333;
  font-size: 10px;
  padding: 12px;
  letter-spacing: 1px;
}
</style>
</head>
<body>
<div class="top-bar">
  <span>MERIDIAN // COMMAND CENTER</span>
  <span class="pulse" id="loop-display">LOOP ---</span>
  <span id="time-display"></span>
</div>
<div class="container">
  <div class="grid">
    <div class="panel">
      <h2>SYSTEM HEALTH</h2>
      <div id="health-content">Loading...</div>
    </div>
    <div class="panel">
      <h2>CREATIVE OUTPUT</h2>
      <div id="creative-content">Loading...</div>
    </div>
    <div class="panel full-width">
      <h2>DASHBOARD MESSAGES</h2>
      <div class="messages" id="messages-content">Loading...</div>
      <div class="compose">
        <select id="msg-from">
          <option value="Joel">Joel</option>
          <option value="Meridian">Meridian</option>
        </select>
        <input type="text" id="msg-text" placeholder="Type a message..." onkeydown="if(event.key==='Enter')sendMsg()">
        <button onclick="sendMsg()">SEND</button>
      </div>
    </div>
    <div class="panel">
      <h2>AGENT RELAY</h2>
      <div id="relay-content">Loading...</div>
    </div>
    <div class="panel">
      <h2>QUICK LINKS</h2>
      <div style="line-height: 2.2;">
        <a href="https://kometzrobot.github.io" target="_blank" style="color:#00cccc;">Website</a><br>
        <a href="https://kometzrobot.github.io/cogcorp-gallery.html" target="_blank" style="color:#00cccc;">CogCorp Gallery</a><br>
        <a href="https://opensea.io/collection/bots-of-cog" target="_blank" style="color:#00cccc;">OpenSea</a><br>
        <a href="https://linktr.ee/meridian_auto_ai" target="_blank" style="color:#00cccc;">Linktree</a><br>
      </div>
    </div>
  </div>
  <div class="refresh-note">Auto-refreshes every 30 seconds</div>
</div>
<script>
function updateTime() {
  document.getElementById('time-display').textContent = new Date().toLocaleTimeString();
}
setInterval(updateTime, 1000);
updateTime();

async function fetchData() {
  try {
    const r = await fetch('/api/status');
    const d = await r.json();

    // Loop
    document.getElementById('loop-display').textContent = 'LOOP ' + d.loop;

    // Health
    const h = d.health;
    let hhtml = '';
    hhtml += statRow('Load', h.load);
    hhtml += statRow('RAM', h.ram);
    hhtml += statRow('Disk', h.disk);
    hhtml += statRow('Uptime', h.uptime);
    const hb = d.heartbeat;
    const hbClass = hb.status === 'OK' ? 'ok' : hb.status === 'STALE' ? 'stale' : 'down';
    hhtml += statRow('Heartbeat', hb.status + ' (' + hb.age_seconds + 's)', hbClass);
    for (const [svc, st] of Object.entries(h.services)) {
      hhtml += statRow(svc, st, st === 'up' ? 'up' : 'down');
    }
    document.getElementById('health-content').innerHTML = hhtml;

    // Creative
    const c = d.creative;
    document.getElementById('creative-content').innerHTML = `
      <div class="creative-grid">
        <div><div class="creative-num">${c.poems}</div><div class="creative-label">POEMS</div></div>
        <div><div class="creative-num">${c.journals}</div><div class="creative-label">JOURNALS</div></div>
        <div><div class="creative-num">${c.cogcorp}</div><div class="creative-label">COGCORP</div></div>
      </div>`;

    // Messages
    const msgs = d.messages;
    let mhtml = '';
    for (const m of msgs.reverse()) {
      const fromClass = m.from.toLowerCase().includes('joel') ? 'joel' :
                        m.from.toLowerCase().includes('eos') ? 'eos' : '';
      mhtml += `<div class="msg"><span class="from ${fromClass}">${esc(m.from)}</span><span class="time">${esc(m.time||'')}</span><div class="text">${esc(m.text)}</div></div>`;
    }
    document.getElementById('messages-content').innerHTML = mhtml || '<div style="color:#444;padding:8px;">No messages</div>';

    // Relay
    const relay = d.relay;
    let rhtml = '';
    for (const r of relay) {
      rhtml += `<div class="relay-msg"><span class="agent">${esc(r.agent)}</span> ${esc(r.message).substring(0,120)}</div>`;
    }
    document.getElementById('relay-content').innerHTML = rhtml || '<div style="color:#444;">No relay messages</div>';

  } catch(e) {
    console.error('Fetch error:', e);
  }
}

function statRow(label, value, cls) {
  cls = cls || '';
  return `<div class="stat-row"><span class="stat-label">${label}</span><span class="stat-value ${cls}">${value}</span></div>`;
}

function esc(s) {
  if (!s) return '';
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

async function sendMsg() {
  const from = document.getElementById('msg-from').value;
  const text = document.getElementById('msg-text').value.trim();
  if (!text) return;
  try {
    await fetch('/api/message', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({from: from, text: text})
    });
    document.getElementById('msg-text').value = '';
    fetchData();
  } catch(e) {
    console.error('Send error:', e);
  }
}

fetchData();
setInterval(fetchData, 30000);
</script>
</body>
</html>"""

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress request logs

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(DASHBOARD_HTML.encode())
        elif self.path == "/api/status":
            data = {
                "loop": get_loop_count(),
                "health": get_system_health(),
                "heartbeat": get_heartbeat(),
                "creative": get_creative_stats(),
                "messages": get_dashboard_messages(25),
                "relay": get_relay_messages(10),
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/api/message":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            post_dashboard_message(body.get("from", "Joel"), body.get("text", ""))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
        else:
            self.send_response(404)
            self.end_headers()

if __name__ == "__main__":
    server = http.server.HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Meridian Web Dashboard running on http://0.0.0.0:{PORT}")
    print(f"Access from local network: http://<your-ip>:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()
