#!/usr/bin/env python3
"""
Meridian Control Hub — Combined dashboard with system status, relay, activity, messages, Eos.
Runs on port 8888 (LAN accessible at 192.168.1.88:8888).
Mobile-friendly single-page view for Joel.
"""

import http.server
import json
import os
import sqlite3
import time
import urllib.request
import urllib.parse
from datetime import datetime

PORT = 8888
BASE_DIR = "/home/joel/autonomous-ai"
MESSAGES_FILE = os.path.join(BASE_DIR, ".dashboard-messages.json")
HEARTBEAT_FILE = os.path.join(BASE_DIR, ".heartbeat")
WAKE_STATE = os.path.join(BASE_DIR, "wake-state.md")
RELAY_DB = os.path.join(BASE_DIR, "relay.db")

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
    font-size: 13px;
    line-height: 1.5;
  }
  .header {
    background: #0f1a0f;
    border-bottom: 1px solid #00ff4140;
    padding: 12px 16px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    position: sticky;
    top: 0;
    z-index: 100;
  }
  .header h1 { color: #00ff41; font-size: 16px; }
  .status-dot {
    width: 10px; height: 10px; border-radius: 50%;
    display: inline-block; margin-right: 6px;
  }
  .status-dot.alive { background: #00ff41; box-shadow: 0 0 8px #00ff41; }
  .status-dot.down { background: #ff2244; box-shadow: 0 0 8px #ff2244; }
  .container { max-width: 1200px; margin: 0 auto; padding: 12px; }

  /* Tab navigation */
  .tabs {
    display: flex;
    gap: 0;
    margin-bottom: 12px;
    border-bottom: 1px solid #1a1a2a;
    overflow-x: auto;
  }
  .tab {
    padding: 10px 16px;
    color: #555;
    cursor: pointer;
    border-bottom: 2px solid transparent;
    white-space: nowrap;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 1px;
  }
  .tab.active { color: #00ff41; border-bottom-color: #00ff41; }
  .tab:hover { color: #00e5ff; }
  .tab-content { display: none; }
  .tab-content.active { display: block; }

  /* Panels */
  .panel {
    background: #0d0d14;
    border: 1px solid #1a1a2a;
    border-radius: 8px;
    padding: 12px;
    margin-bottom: 12px;
  }
  .panel h2 {
    color: #00e5ff;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 2px;
    margin-bottom: 10px;
    border-bottom: 1px solid #1a1a2a;
    padding-bottom: 6px;
  }

  /* Status grid */
  .stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
    gap: 8px;
  }
  .stat-card {
    background: #111118;
    border-radius: 6px;
    padding: 10px;
    text-align: center;
  }
  .stat-card .label { color: #555; font-size: 10px; text-transform: uppercase; letter-spacing: 1px; }
  .stat-card .value { color: #00ff41; font-size: 18px; margin-top: 4px; }
  .stat-card .value.warn { color: #ffb000; }
  .stat-card .value.error { color: #ff2244; }

  /* Activity log */
  .activity-log { max-height: 300px; overflow-y: auto; font-size: 11px; }
  .activity-log p {
    padding: 4px 0;
    border-bottom: 1px solid #111;
    color: #888;
    word-break: break-word;
  }
  .activity-log p:first-child { color: #c0c0c0; }

  /* Relay messages */
  .relay-msg {
    background: #0d0d14;
    border-left: 3px solid #333;
    border-radius: 0 6px 6px 0;
    padding: 10px 12px;
    margin-bottom: 8px;
  }
  .relay-msg.meridian { border-left-color: #00ff41; }
  .relay-msg.sammy { border-left-color: #ff9800; }
  .relay-msg.friday { border-left-color: #2196f3; }
  .relay-msg.lumen { border-left-color: #e91e63; }
  .relay-msg.loom { border-left-color: #9c27b0; }
  .relay-msg .meta { font-size: 11px; color: #555; margin-bottom: 4px; }
  .relay-msg .sender { color: #4fc3f7; font-weight: bold; }
  .relay-msg .body { color: #888; white-space: pre-wrap; max-height: 200px; overflow-y: auto; font-size: 12px; }

  /* Messages */
  .msg-list { max-height: 300px; overflow-y: auto; margin-bottom: 10px; }
  .msg {
    padding: 8px 10px;
    margin-bottom: 4px;
    border-radius: 6px;
    font-size: 12px;
  }
  .msg.joel { background: #0f1a2e; border-left: 3px solid #4fc3f7; }
  .msg.meridian { background: #0f1a0f; border-left: 3px solid #00ff41; }
  .msg.eos { background: #1a0f1a; border-left: 3px solid #ce93d8; }
  .msg .msg-meta { font-size: 10px; color: #555; margin-bottom: 2px; }

  .input-row { display: flex; gap: 8px; flex-wrap: wrap; }
  .input-row input {
    flex: 1; min-width: 150px;
    background: #111; border: 1px solid #333; color: #e0e0e0;
    padding: 10px 12px; border-radius: 6px;
    font-family: inherit; font-size: 13px;
  }
  .input-row input:focus { outline: none; border-color: #4fc3f7; }
  .btn {
    background: #0f3460; color: #4fc3f7; border: 1px solid #4fc3f7;
    padding: 10px 16px; border-radius: 6px; cursor: pointer;
    font-family: inherit; font-size: 13px; white-space: nowrap;
  }
  .btn:hover { background: #1a4a80; }
  .btn.eos { background: #1a0f2e; color: #ce93d8; border-color: #ce93d8; }
  #eos-status { font-style: italic; color: #666; margin-top: 6px; font-size: 11px; }

  .refresh-note { text-align: center; color: #333; font-size: 10px; margin-top: 12px; }

  @media (max-width: 600px) {
    .header h1 { font-size: 14px; }
    .stats-grid { grid-template-columns: repeat(2, 1fr); }
    .tab { padding: 8px 12px; font-size: 11px; }
  }
</style>
</head>
<body>
<div class="header">
  <h1><span class="status-dot alive" id="status-dot"></span> MERIDIAN</h1>
  <span id="clock" style="color: #555; font-size: 12px;"></span>
</div>
<div class="container">
  <div class="tabs">
    <div class="tab active" onclick="showTab('overview')">Overview</div>
    <div class="tab" onclick="showTab('relay')">Relay</div>
    <div class="tab" onclick="showTab('activity')">Activity</div>
    <div class="tab" onclick="showTab('messages')">Messages</div>
  </div>

  <!-- OVERVIEW TAB -->
  <div class="tab-content active" id="tab-overview">
    <div class="panel">
      <h2>System Status</h2>
      <div class="stats-grid" id="stats-grid">Loading...</div>
    </div>
    <div class="panel">
      <h2>Latest Activity</h2>
      <div class="activity-log" id="activity-brief">Loading...</div>
    </div>
    <div class="panel">
      <h2>Relay (latest)</h2>
      <div id="relay-brief">Loading...</div>
    </div>
  </div>

  <!-- RELAY TAB -->
  <div class="tab-content" id="tab-relay">
    <div class="panel">
      <h2>Meridian Relay</h2>
      <div id="relay-members" style="font-size:11px; color:#555; margin-bottom:10px;"></div>
      <div id="relay-full">Loading...</div>
    </div>
  </div>

  <!-- ACTIVITY TAB -->
  <div class="tab-content" id="tab-activity">
    <div class="panel">
      <h2>Loop Activity Log</h2>
      <div class="activity-log" id="activity-full">Loading...</div>
    </div>
  </div>

  <!-- MESSAGES TAB -->
  <div class="tab-content" id="tab-messages">
    <div class="panel">
      <h2>Messages</h2>
      <div class="msg-list" id="msg-list"></div>
      <div class="input-row">
        <input type="text" id="msg-input" placeholder="Message to Meridian..." onkeydown="if(event.key==='Enter')sendMsg()">
        <button class="btn" onclick="sendMsg()">Send</button>
        <button class="btn eos" onclick="askEos()">Eos</button>
      </div>
      <div id="eos-status"></div>
    </div>
  </div>

  <div class="refresh-note">Auto-refreshes every 20s | Loop ~3 min</div>
</div>

<script>
function updateClock() {
  document.getElementById('clock').textContent = new Date().toLocaleTimeString();
}
setInterval(updateClock, 1000);
updateClock();

function showTab(name) {
  document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  event.target.classList.add('active');
}

async function loadStatus() {
  try {
    const r = await fetch('/api/status');
    const d = await r.json();
    let html = '';
    const order = ['meridian','heartbeat','load','ram','uptime','emails','relay_msgs','poems','journals'];
    for (const k of order) {
      if (d[k] === undefined) continue;
      let cls = '';
      if (k === 'meridian' && d[k] !== 'ALIVE') cls = 'error';
      if (k === 'load' && parseFloat(d[k]) > 5) cls = 'warn';
      html += '<div class="stat-card"><div class="label">'+k.replace('_',' ')+'</div><div class="value '+cls+'">'+d[k]+'</div></div>';
    }
    document.getElementById('stats-grid').innerHTML = html;
    const dot = document.getElementById('status-dot');
    dot.className = 'status-dot ' + (d.meridian === 'ALIVE' ? 'alive' : 'down');
  } catch(e) {
    document.getElementById('stats-grid').innerHTML = '<div style="color:#ff2244">Error loading status</div>';
  }
}

async function loadActivity() {
  try {
    const r = await fetch('/api/activity');
    const d = await r.json();
    let briefHtml = '', fullHtml = '';
    for (let i = 0; i < d.lines.length; i++) {
      const p = '<p>' + d.lines[i] + '</p>';
      fullHtml += p;
      if (i < 5) briefHtml += p;
    }
    document.getElementById('activity-brief').innerHTML = briefHtml;
    document.getElementById('activity-full').innerHTML = fullHtml;
  } catch(e) {}
}

async function loadRelay() {
  try {
    const r = await fetch('/api/relay');
    const d = await r.json();
    let briefHtml = '', fullHtml = '';

    if (d.members) {
      const memHtml = 'Members: ' + d.members.map(m => '<span style="color:#00ff41">'+m.name+'</span>').join(' | ');
      document.getElementById('relay-members').innerHTML = memHtml;
    }

    if (d.messages.length === 0) {
      briefHtml = '<div style="color:#333">No relay messages yet.</div>';
      fullHtml = briefHtml;
    } else {
      for (let i = 0; i < d.messages.length; i++) {
        const m = d.messages[i];
        const cls = m.sender.toLowerCase();
        const msgHtml = '<div class="relay-msg '+cls+'">'
          + '<div class="meta"><span class="sender">'+m.sender+'</span> — '+m.timestamp+'</div>'
          + '<div class="body">'+m.body+'</div></div>';
        fullHtml += msgHtml;
        if (i >= d.messages.length - 3) briefHtml += msgHtml;
      }
    }
    document.getElementById('relay-brief').innerHTML = briefHtml;
    document.getElementById('relay-full').innerHTML = fullHtml;
  } catch(e) {
    document.getElementById('relay-brief').innerHTML = '<div style="color:#333">Relay unavailable</div>';
  }
}

async function loadMessages() {
  try {
    const r = await fetch('/api/messages');
    const d = await r.json();
    let html = '';
    for (const m of d.messages) {
      const cls = m.from.toLowerCase();
      html += '<div class="msg '+cls+'"><div class="msg-meta">'+m.from+' — '+m.time+'</div>'+m.text+'</div>';
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
    document.getElementById('eos-status').textContent = 'Eos timed out.';
  }
}

// Initial load
loadStatus(); loadActivity(); loadRelay(); loadMessages();
// Auto-refresh
setInterval(loadStatus, 20000);
setInterval(loadActivity, 20000);
setInterval(loadRelay, 20000);
setInterval(loadMessages, 10000);
</script>
</body>
</html>"""


class DashboardHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

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

        elif self.path == '/api/relay':
            self.send_json(self.get_relay())

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
        try:
            age = time.time() - os.path.getmtime(HEARTBEAT_FILE)
            status['meridian'] = 'ALIVE' if age < 600 else f'STALE ({int(age/60)}m)'
            status['heartbeat'] = f'{int(age)}s ago'
        except FileNotFoundError:
            status['meridian'] = 'NO HEARTBEAT'
            status['heartbeat'] = 'missing'

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
                status['ram'] = f'{used:.1f}/{total:.0f}GB'
        except Exception:
            status['ram'] = '?'

        try:
            with open('/proc/uptime') as f:
                up_secs = float(f.read().split()[0])
                hours = int(up_secs // 3600)
                mins = int((up_secs % 3600) // 60)
                status['uptime'] = f'{hours}h{mins}m'
        except Exception:
            status['uptime'] = '?'

        # Email count
        email_db = os.path.join(BASE_DIR, "email-shelf.db")
        if os.path.exists(email_db):
            try:
                db = sqlite3.connect(email_db)
                status['emails'] = str(db.execute("SELECT COUNT(*) FROM emails").fetchone()[0])
                db.close()
            except Exception:
                status['emails'] = '?'

        # Relay count
        if os.path.exists(RELAY_DB):
            try:
                db = sqlite3.connect(RELAY_DB)
                status['relay_msgs'] = str(db.execute("SELECT COUNT(*) FROM relay_messages WHERE forwarded >= 0").fetchone()[0])
                db.close()
            except Exception:
                status['relay_msgs'] = '?'

        poems = len([f for f in os.listdir(BASE_DIR) if f.startswith('poem-') and f.endswith('.md')])
        journals = len([f for f in os.listdir(BASE_DIR) if f.startswith('journal-') and f.endswith('.md')])
        status['poems'] = str(poems)
        status['journals'] = str(journals)

        # Loop number from wake-state
        try:
            with open(WAKE_STATE) as f:
                content = f.read()
            for line in content.split('\n'):
                if 'Loop iteration' in line:
                    import re
                    match = re.search(r'#(\d+)', line)
                    if match:
                        loop_num = int(match.group(1))
                        status['loop'] = str(loop_num)
                        status['loop_age'] = f'{loop_num/1000:.1f} years ({1000 - loop_num} to birthday)' if loop_num < 1000 else f'{loop_num/1000:.1f} years'
                        break
        except Exception:
            pass

        # Eos watchdog status
        eos_state = os.path.join(BASE_DIR, '.eos-watchdog-state.json')
        if os.path.exists(eos_state):
            try:
                import json
                with open(eos_state) as f:
                    eos = json.load(f)
                status['eos'] = f"Watching (last check: {eos.get('last_check', '?')})"
            except Exception:
                status['eos'] = 'State file exists'
        else:
            status['eos'] = 'No state file'

        return status

    def get_activity(self):
        lines = []
        try:
            with open(WAKE_STATE) as f:
                content = f.read()
            for line in content.split('\n'):
                if line.strip().startswith('- Loop iteration'):
                    lines.append(line.strip()[2:])
                    if len(lines) >= 20:
                        break
        except Exception:
            lines = ['Could not read wake-state.md']
        return {"lines": lines}

    def get_relay(self):
        messages = []
        members = []
        if os.path.exists(RELAY_DB):
            try:
                db = sqlite3.connect(RELAY_DB)
                rows = db.execute(
                    "SELECT sender_name, subject, body, timestamp FROM relay_messages WHERE forwarded >= 0 ORDER BY id ASC LIMIT 50"
                ).fetchall()
                for row in rows:
                    messages.append({
                        "sender": row[0],
                        "subject": row[1],
                        "body": row[2][:3000] if row[2] else "",
                        "timestamp": row[3][:19] if row[3] else ""
                    })
                db.close()
            except Exception:
                pass

        contacts_file = os.path.join(BASE_DIR, "relay-contacts.json")
        if os.path.exists(contacts_file):
            try:
                with open(contacts_file) as f:
                    contacts = json.load(f)
                members = [{"name": m["name"], "role": m["role"]} for m in contacts.get("members", [])]
            except Exception:
                pass

        return {"messages": messages, "members": members}

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
    print(f"Meridian Control Hub at http://localhost:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
