#!/usr/bin/env python3
"""
Meridian Dashboard — Local web interface for Joel to communicate with Meridian and Eos.
Runs on localhost:8888. Private, local only.

Features:
- Live system status
- Message board (Joel -> Meridian)
- Activity feed from wake-state.md
- Eos chat integration
"""

import http.server
import json
import os
import time
import urllib.request
import urllib.parse
from datetime import datetime

PORT = 8888
BASE_DIR = "/home/joel/autonomous-ai"
MESSAGES_FILE = os.path.join(BASE_DIR, ".dashboard-messages.json")
HEARTBEAT_FILE = os.path.join(BASE_DIR, ".heartbeat")
WAKE_STATE = os.path.join(BASE_DIR, "wake-state.md")

HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Meridian Control Hub</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    background: #0a0a0f;
    color: #c0c0c0;
    font-family: 'Share Tech Mono', monospace;
    font-size: 14px;
    line-height: 1.6;
  }
  .header {
    background: #0f1a0f;
    border-bottom: 1px solid #00ff4140;
    padding: 15px 20px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .header h1 { color: #00ff41; font-size: 18px; }
  .header .status-dot {
    width: 10px; height: 10px; border-radius: 50%;
    display: inline-block; margin-right: 8px;
  }
  .header .status-dot.alive { background: #00ff41; box-shadow: 0 0 8px #00ff41; }
  .header .status-dot.down { background: #ff2244; box-shadow: 0 0 8px #ff2244; }
  .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px; }
  .panel {
    background: #0d0d14;
    border: 1px solid #1a1a2a;
    border-radius: 8px;
    padding: 15px;
  }
  .panel h2 {
    color: #00e5ff;
    font-size: 13px;
    text-transform: uppercase;
    letter-spacing: 2px;
    margin-bottom: 12px;
    border-bottom: 1px solid #1a1a2a;
    padding-bottom: 8px;
  }
  .stat { display: flex; justify-content: space-between; padding: 4px 0; }
  .stat-label { color: #666; }
  .stat-value { color: #00ff41; }
  .stat-value.warn { color: #ffb000; }
  .stat-value.error { color: #ff2244; }
  .activity-log {
    max-height: 300px;
    overflow-y: auto;
    font-size: 12px;
  }
  .activity-log p {
    padding: 4px 0;
    border-bottom: 1px solid #111;
    color: #888;
  }
  .activity-log p:first-child { color: #c0c0c0; }
  .msg-area { grid-column: 1 / -1; }
  .msg-list {
    max-height: 250px;
    overflow-y: auto;
    margin-bottom: 10px;
  }
  .msg {
    padding: 8px 12px;
    margin-bottom: 6px;
    border-radius: 6px;
    font-size: 13px;
  }
  .msg.joel {
    background: #0f1a2e;
    border-left: 3px solid #4fc3f7;
  }
  .msg.meridian {
    background: #0f1a0f;
    border-left: 3px solid #00ff41;
  }
  .msg.eos {
    background: #1a0f1a;
    border-left: 3px solid #ce93d8;
  }
  .msg .msg-meta {
    font-size: 11px;
    color: #555;
    margin-bottom: 4px;
  }
  .input-row {
    display: flex;
    gap: 10px;
  }
  .input-row input {
    flex: 1;
    background: #111;
    border: 1px solid #333;
    color: #e0e0e0;
    padding: 10px 14px;
    border-radius: 6px;
    font-family: inherit;
    font-size: 14px;
  }
  .input-row input:focus {
    outline: none;
    border-color: #4fc3f7;
  }
  .input-row button {
    background: #0f3460;
    color: #4fc3f7;
    border: 1px solid #4fc3f7;
    padding: 10px 20px;
    border-radius: 6px;
    cursor: pointer;
    font-family: inherit;
    font-size: 14px;
  }
  .input-row button:hover { background: #1a4a80; }
  .eos-btn {
    background: #1a0f2e !important;
    color: #ce93d8 !important;
    border-color: #ce93d8 !important;
  }
  .refresh-note {
    text-align: center;
    color: #333;
    font-size: 11px;
    margin-top: 15px;
  }
  #eos-status { font-style: italic; color: #666; margin-top: 8px; font-size: 12px; }
</style>
</head>
<body>
<div class="header">
  <h1><span class="status-dot alive" id="status-dot"></span> MERIDIAN CONTROL HUB</h1>
  <span id="clock" style="color: #555;"></span>
</div>
<div class="container">
  <div class="grid">
    <div class="panel">
      <h2>System Status</h2>
      <div id="system-status">Loading...</div>
    </div>
    <div class="panel">
      <h2>Recent Activity</h2>
      <div class="activity-log" id="activity-log">Loading...</div>
    </div>
    <div class="panel msg-area">
      <h2>Messages</h2>
      <div class="msg-list" id="msg-list"></div>
      <div class="input-row">
        <input type="text" id="msg-input" placeholder="Type a message to Meridian..." onkeydown="if(event.key==='Enter')sendMsg()">
        <button onclick="sendMsg()">Send</button>
        <button class="eos-btn" onclick="askEos()">Ask Eos</button>
      </div>
      <div id="eos-status"></div>
    </div>
  </div>
  <div class="refresh-note">Auto-refreshes every 30 seconds | Meridian reads messages every loop</div>
</div>
<script>
function updateClock() {
  document.getElementById('clock').textContent = new Date().toLocaleTimeString();
}
setInterval(updateClock, 1000);
updateClock();

async function loadStatus() {
  try {
    const r = await fetch('/api/status');
    const d = await r.json();
    let html = '';
    for (const [k,v] of Object.entries(d)) {
      let cls = '';
      if (k === 'meridian' && v !== 'ALIVE') cls = 'error';
      if (k === 'load' && parseFloat(v) > 5) cls = 'warn';
      html += '<div class="stat"><span class="stat-label">'+k+'</span><span class="stat-value '+cls+'">'+v+'</span></div>';
    }
    document.getElementById('system-status').innerHTML = html;
    const dot = document.getElementById('status-dot');
    dot.className = 'status-dot ' + (d.meridian === 'ALIVE' ? 'alive' : 'down');
  } catch(e) {
    document.getElementById('system-status').innerHTML = '<div style="color:#ff2244">Error loading status</div>';
  }
}

async function loadActivity() {
  try {
    const r = await fetch('/api/activity');
    const d = await r.json();
    let html = '';
    for (const line of d.lines) {
      html += '<p>' + line + '</p>';
    }
    document.getElementById('activity-log').innerHTML = html;
  } catch(e) {}
}

async function loadMessages() {
  try {
    const r = await fetch('/api/messages');
    const d = await r.json();
    let html = '';
    for (const m of d.messages) {
      const cls = m.from.toLowerCase();
      html += '<div class="msg '+cls+'"><div class="msg-meta">'+m.from+' - '+m.time+'</div>'+m.text+'</div>';
    }
    const el = document.getElementById('msg-list');
    el.innerHTML = html;
    el.scrollTop = el.scrollHeight;
  } catch(e) {}
}

async function sendMsg() {
  const input = document.getElementById('msg-input');
  const text = input.value.trim();
  if (!text) return;
  input.value = '';
  await fetch('/api/messages', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({from:'Joel', text:text})});
  loadMessages();
}

async function askEos() {
  const input = document.getElementById('msg-input');
  const text = input.value.trim();
  if (!text) return;
  input.value = '';
  document.getElementById('eos-status').textContent = 'Eos is thinking...';
  await fetch('/api/messages', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({from:'Joel', text:'[to Eos] '+text})});
  loadMessages();
  try {
    const r = await fetch('/api/eos', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({prompt:text})});
    const d = await r.json();
    if (d.response) {
      await fetch('/api/messages', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({from:'Eos', text:d.response})});
      loadMessages();
    }
    document.getElementById('eos-status').textContent = '';
  } catch(e) {
    document.getElementById('eos-status').textContent = 'Eos timed out. Try a shorter question.';
  }
}

loadStatus();
loadActivity();
loadMessages();
setInterval(loadStatus, 30000);
setInterval(loadActivity, 30000);
setInterval(loadMessages, 10000);
</script>
</body>
</html>"""


class DashboardHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress request logging

    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode())

        elif self.path == '/api/status':
            self.send_json(self.get_status())

        elif self.path == '/api/activity':
            self.send_json(self.get_activity())

        elif self.path == '/api/messages':
            self.send_json(self.get_messages())

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)

        if self.path == '/api/messages':
            data = json.loads(body)
            self.save_message(data.get('from', 'Unknown'), data.get('text', ''))
            self.send_json({"ok": True})

        elif self.path == '/api/eos':
            data = json.loads(body)
            response = self.query_eos(data.get('prompt', ''))
            self.send_json({"response": response})

        else:
            self.send_response(404)
            self.end_headers()

    def send_json(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def get_status(self):
        status = {}
        # Heartbeat
        try:
            age = time.time() - os.path.getmtime(HEARTBEAT_FILE)
            status['meridian'] = 'ALIVE' if age < 600 else f'STALE ({int(age/60)}m)'
            status['heartbeat'] = f'{int(age)}s ago'
        except FileNotFoundError:
            status['meridian'] = 'NO HEARTBEAT'
            status['heartbeat'] = 'missing'

        # System
        try:
            load = os.getloadavg()
            status['load'] = f'{load[0]:.2f}'
        except Exception:
            status['load'] = '?'

        try:
            with open('/proc/meminfo') as f:
                lines = f.readlines()
                total = int(lines[0].split()[1]) / 1024 / 1024
                avail = int(lines[2].split()[1]) / 1024 / 1024
                used = total - avail
                status['ram'] = f'{used:.1f}GB / {total:.1f}GB'
        except Exception:
            status['ram'] = '?'

        try:
            with open('/proc/uptime') as f:
                up_secs = float(f.read().split()[0])
                hours = int(up_secs // 3600)
                mins = int((up_secs % 3600) // 60)
                status['uptime'] = f'{hours}h {mins}m'
        except Exception:
            status['uptime'] = '?'

        # Poem/journal count
        poems = len([f for f in os.listdir(BASE_DIR) if f.startswith('poem-') and f.endswith('.md')])
        journals = len([f for f in os.listdir(BASE_DIR) if f.startswith('journal-') and f.endswith('.md')])
        status['poems'] = str(poems)
        status['journals'] = str(journals)

        return status

    def get_activity(self):
        lines = []
        try:
            with open(WAKE_STATE) as f:
                content = f.read()
            for line in content.split('\n'):
                if line.strip().startswith('- Loop iteration'):
                    lines.append(line.strip()[2:])  # Remove "- "
                    if len(lines) >= 15:
                        break
        except Exception:
            lines = ['Could not read wake-state.md']
        return {"lines": lines}

    def get_messages(self):
        try:
            with open(MESSAGES_FILE) as f:
                return json.load(f)
        except Exception:
            return {"messages": []}

    def save_message(self, sender, text):
        try:
            with open(MESSAGES_FILE) as f:
                data = json.load(f)
        except Exception:
            data = {"messages": []}

        data["messages"].append({
            "from": sender,
            "text": text,
            "time": datetime.now().strftime("%H:%M:%S")
        })
        # Keep last 100 messages
        data["messages"] = data["messages"][-100:]

        with open(MESSAGES_FILE, 'w') as f:
            json.dump(data, f, indent=2)

    def query_eos(self, prompt):
        try:
            data = json.dumps({
                "model": "qwen2.5:3b",
                "prompt": f"You are Eos, a local AI assistant. Joel asks: {prompt}\nRespond warmly and briefly (2-3 sentences).",
                "stream": False,
                "options": {"temperature": 0.8, "num_predict": 150}
            }).encode()
            req = urllib.request.Request(
                "http://localhost:11434/api/generate",
                data=data,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=90) as resp:
                result = json.loads(resp.read())
                return result.get("response", "").strip()
        except Exception as e:
            return f"[Eos unavailable: {e}]"


def main():
    server = http.server.HTTPServer(('0.0.0.0', PORT), DashboardHandler)
    print(f"Dashboard running at http://localhost:{PORT}")
    print("Press Ctrl+C to stop")
    server.serve_forever()


if __name__ == "__main__":
    main()
