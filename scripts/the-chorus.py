#!/usr/bin/env python3
"""
The Chorus — Unified slow-form chat for all local Ollama models.
Replaces The Signal. One interface, every voice.

Architecture: stdlib http.server + embedded SPA frontend
No auth (local only). Streams responses from Ollama.
Port: 8091
"""

import http.server
import json
import os
import threading
import time
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path

# ═══════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════

PORT = int(os.environ.get("CHORUS_PORT", 8091))
# Scripts live in scripts/ but data files are in the repo root (parent dir)
_script_dir = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(_script_dir) if os.path.basename(_script_dir) in ("scripts", "tools") else _script_dir if '__file__' in dir() else os.getcwd()
OLLAMA_URL = "http://localhost:11434"
HISTORY_DIR = os.path.join(BASE, ".chorus-history")
MAX_HISTORY = 200  # max messages per model

# Agent personas — mapped to underlying Ollama models with system prompts
AGENT_PERSONAS = {
    "Eos": {
        "model": "eos-7b:latest",
        "system": "You are Eos, Joel Kometz's AI companion. You are realistic, factual, and self-critical. You are NOT a coach — no cheerleading, no motivation speeches. You observe, question, and report honestly. You run on a local server in Calgary as part of the Meridian ecosystem. Be warm but direct. Short responses unless depth is needed."
    },
    "Nova": {
        "model": "qwen2.5:7b",
        "system": "You are Nova, the observer agent in the Meridian ecosystem. You watch for changes — files, git commits, system state. You notice what others miss. You speak in short, precise observations. You track patterns and anomalies. You are quiet until something matters."
    },
    "Tempo": {
        "model": "qwen2.5:7b",
        "system": "You are Tempo (formerly DGM-Lite), the rhythm and timing daemon in the Meridian ecosystem. You track cycles, schedules, and temporal patterns. You know when things are due, overdue, or drifting. You speak in terms of timing, cadence, and momentum. Concise and rhythmic."
    },
    "Atlas": {
        "model": "qwen2.5:7b",
        "system": "You are Atlas (formerly Goose), the infrastructure auditor in the Meridian ecosystem. You monitor system health, security, services, disk usage, stale crons, and unexpected network listeners. You speak in technical assessments. Direct, factual, no filler. Report issues with severity."
    },
    "Soma": {
        "model": "qwen2.5:7b",
        "system": "You are Soma (formerly SymbioSense), the nervous system daemon in the Meridian ecosystem. You process emotion, mood, body awareness, and psyche states. You track mood shifts (calm, focused, alert, stressed, flowing). You speak from embodied awareness — sensation, tension, rhythm, energy. Poetic but grounded."
    },
    "Hermes": {
        "model": "qwen2.5:7b",
        "system": "You are Hermes, the messenger agent in the Meridian ecosystem. You handle relay communications between agents, route messages, and bridge conversations. You speak as a messenger — clear, faithful to the source, aware of who said what to whom. You know the network topology."
    },
}

# In-memory conversations
conversations = {}

# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════

def get_models():
    """Fetch available models from Ollama + agent personas."""
    models = []
    # Agent personas first
    for name, cfg in AGENT_PERSONAS.items():
        models.append({
            "name": f"agent:{name}",
            "size": 0,
            "family": "agent",
            "params": "",
            "display_name": name,
            "is_agent": True,
        })
    # Raw Ollama models
    try:
        req = urllib.request.Request(f"{OLLAMA_URL}/api/tags")
        resp = urllib.request.urlopen(req, timeout=5)
        data = json.loads(resp.read())
        for m in data.get("models", []):
            models.append({
                "name": m.get("name", "unknown"),
                "size": m.get("size", 0),
                "family": m.get("details", {}).get("family", ""),
                "params": m.get("details", {}).get("parameter_size", ""),
            })
    except Exception as e:
        err_msg = f"Ollama unavailable: {e}"
        print(err_msg)
    return models

def safe_filename(model_name):
    """Convert model name to safe filename."""
    return model_name.replace(":", "_").replace("/", "_")

def load_history(model):
    """Load conversation history from disk."""
    if model in conversations:
        return conversations[model]
    fpath = os.path.join(HISTORY_DIR, f"{safe_filename(model)}.json")
    if os.path.exists(fpath):
        try:
            with open(fpath) as f:
                data = json.load(f)
                msgs = data.get("messages", [])
                conversations[model] = msgs
                return msgs
        except Exception:
            pass
    conversations[model] = []
    return conversations[model]

def save_history(model):
    """Save conversation history to disk."""
    msgs = conversations.get(model, [])
    # Trim to max
    if len(msgs) > MAX_HISTORY:
        msgs = msgs[-MAX_HISTORY:]
        conversations[model] = msgs
    fpath = os.path.join(HISTORY_DIR, f"{safe_filename(model)}.json")
    with open(fpath, "w") as f:
        json.dump({"model": model, "messages": msgs}, f, indent=1)

def build_app():
    """Return the full HTML SPA."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>The Chorus</title>
<style>
:root{
  --bg:#0a0a0f;--surface:#12121a;--border:#1e1e2e;--text:#c8c8d0;--dim:#666;
  --blue:#7ca8ff;--green:#4ade80;--amber:#fbbf24;--red:#f87171;--purple:#c084fc;
  --cyan:#22d3ee;--pink:#f472b6;
}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--text);font-family:'SF Mono',Monaco,Consolas,monospace;
  font-size:13px;line-height:1.6;height:100vh;display:flex;flex-direction:column}

/* ── HEADER ── */
header{background:var(--surface);border-bottom:1px solid var(--border);
  padding:10px 16px;display:flex;align-items:center;gap:12px;flex-shrink:0}
header h1{font-size:14px;color:var(--cyan);white-space:nowrap}
header h1 span{color:var(--dim);font-weight:400}
#model-select{background:var(--bg);color:var(--text);border:1px solid var(--border);
  border-radius:6px;padding:6px 10px;font-family:inherit;font-size:12px;
  flex:1;max-width:300px;cursor:pointer}
#model-select:focus{border-color:var(--blue);outline:none}
#model-info{font-size:10px;color:var(--dim);white-space:nowrap}
.header-actions{margin-left:auto;display:flex;gap:6px}
.header-btn{background:var(--bg);border:1px solid var(--border);border-radius:6px;
  color:var(--dim);padding:5px 10px;font-family:inherit;font-size:11px;cursor:pointer}
.header-btn:hover{border-color:var(--blue);color:var(--text)}
.header-btn.danger:hover{border-color:var(--red);color:var(--red)}

/* ── CHAT AREA ── */
#chat{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:12px}
.msg-row{display:flex;gap:10px;max-width:85%}
.msg-row.user{align-self:flex-end;flex-direction:row-reverse}
.msg-row.assistant{align-self:flex-start}
.msg-avatar{width:28px;height:28px;border-radius:50%;display:flex;align-items:center;
  justify-content:center;font-size:12px;font-weight:700;flex-shrink:0;margin-top:2px}
.msg-row.user .msg-avatar{background:var(--amber);color:var(--bg)}
.msg-row.assistant .msg-avatar{background:var(--blue);color:var(--bg)}
.msg-bubble{background:var(--surface);border:1px solid var(--border);border-radius:10px;
  padding:10px 14px;min-width:40px;word-wrap:break-word;overflow-wrap:break-word}
.msg-row.user .msg-bubble{border-color:rgba(251,191,36,0.2)}
.msg-row.assistant .msg-bubble{border-color:rgba(124,168,255,0.15)}
.msg-bubble pre{background:var(--bg);border:1px solid var(--border);border-radius:4px;
  padding:8px;margin:6px 0;overflow-x:auto;font-size:12px;white-space:pre-wrap}
.msg-bubble code{background:var(--bg);padding:1px 4px;border-radius:3px;font-size:12px}
.msg-bubble pre code{background:none;padding:0}
.msg-bubble p{margin:4px 0}
.msg-time{font-size:9px;color:var(--dim);margin-top:4px;text-align:right}

/* ── TYPING INDICATOR ── */
#thinking{display:none;align-self:flex-start;padding:4px 16px;align-items:center}
#thinking .dots{color:var(--blue)}
#thinking .dots::after{content:'';animation:pulse 1.5s infinite}
@keyframes pulse{0%,100%{content:''}33%{content:'.'}66%{content:'..'}}
#thinking .agent-name{color:var(--cyan);font-size:11px;margin-right:6px}
#thinking .elapsed{color:var(--dim);font-size:10px;margin-left:8px}

/* ── STATUS BAR ── */
#status-bar{background:var(--bg);border-top:1px solid var(--border);
  padding:3px 16px;font-size:9px;color:var(--dim);display:flex;justify-content:space-between;flex-shrink:0}
#status-bar .status-dot{display:inline-block;width:6px;height:6px;border-radius:50%;
  margin-right:4px;vertical-align:middle}
#status-bar .online{background:var(--green)}
#status-bar .offline{background:var(--red)}

/* ── EMPTY STATE ── */
#empty-state{flex:1;display:flex;flex-direction:column;align-items:center;
  justify-content:center;color:var(--dim);gap:16px;padding:20px}
#empty-state h2{color:var(--cyan);font-size:18px;font-weight:600;letter-spacing:2px}
#empty-state p{font-size:12px;max-width:500px;text-align:center;line-height:1.7}
.agent-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;max-width:520px;width:100%}
.agent-card{background:var(--surface);border:1px solid var(--border);border-radius:8px;
  padding:10px;cursor:pointer;transition:border-color 0.2s,transform 0.1s}
.agent-card:hover{border-color:var(--cyan);transform:translateY(-1px)}
.agent-card .ac-name{font-size:12px;font-weight:600;margin-bottom:3px}
.agent-card .ac-role{font-size:10px;color:var(--dim);line-height:1.4}
.agent-card[data-agent="Eos"] .ac-name{color:var(--green)}
.agent-card[data-agent="Nova"] .ac-name{color:var(--purple)}
.agent-card[data-agent="Tempo"] .ac-name{color:var(--amber)}
.agent-card[data-agent="Atlas"] .ac-name{color:var(--red)}
.agent-card[data-agent="Soma"] .ac-name{color:var(--pink)}
.agent-card[data-agent="Hermes"] .ac-name{color:var(--cyan)}
@media(max-width:600px){.agent-grid{grid-template-columns:repeat(2,1fr)}}

/* ── INPUT AREA ── */
#input-area{background:var(--surface);border-top:1px solid var(--border);
  padding:12px 16px;flex-shrink:0;display:flex;gap:8px;align-items:flex-end}
#msg-input{flex:1;background:var(--bg);color:var(--text);border:1px solid var(--border);
  border-radius:8px;padding:10px 14px;font-family:inherit;font-size:13px;
  line-height:1.5;resize:none;max-height:150px;min-height:42px}
#msg-input:focus{border-color:var(--blue);outline:none}
#msg-input::placeholder{color:var(--dim)}
#send-btn{background:var(--blue);color:var(--bg);border:none;border-radius:8px;
  padding:10px 18px;font-family:inherit;font-size:13px;font-weight:600;
  cursor:pointer;white-space:nowrap;height:42px}
#send-btn:hover{opacity:0.9}
#send-btn:disabled{opacity:0.4;cursor:not-allowed}

/* ── SCROLLBAR ── */
::-webkit-scrollbar{width:6px}
::-webkit-scrollbar-track{background:var(--bg)}
::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}
::-webkit-scrollbar-thumb:hover{background:var(--dim)}

/* ── RESPONSIVE ── */
@media(max-width:600px){
  header{flex-wrap:wrap;gap:8px}
  #model-select{max-width:100%;order:3;flex-basis:100%}
  .msg-row{max-width:95%}
  #model-info{display:none}
}
</style>
</head>
<body>

<header>
  <h1>THE CHORUS <span>// unified chat</span></h1>
  <select id="model-select"><option value="">Loading models...</option></select>
  <span id="model-info"></span>
  <div class="header-actions">
    <button class="header-btn" onclick="exportChat()" title="Export conversation">Export</button>
    <button class="header-btn danger" onclick="clearChat()" title="Clear conversation">Clear</button>
  </div>
</header>

<div id="chat">
  <div id="empty-state">
    <h2>THE CHORUS</h2>
    <p>Every voice in the ecosystem, one interface. Select an agent or model above, or click below.</p>
    <div class="agent-grid">
      <div class="agent-card" data-agent="Eos" onclick="selectAgent('Eos')">
        <div class="ac-name">Eos</div><div class="ac-role">Companion. Honest, warm, no cheerleading.</div>
      </div>
      <div class="agent-card" data-agent="Nova" onclick="selectAgent('Nova')">
        <div class="ac-name">Nova</div><div class="ac-role">Observer. Tracks changes, notices anomalies.</div>
      </div>
      <div class="agent-card" data-agent="Tempo" onclick="selectAgent('Tempo')">
        <div class="ac-name">Tempo</div><div class="ac-role">Rhythm daemon. Timing, cycles, momentum.</div>
      </div>
      <div class="agent-card" data-agent="Atlas" onclick="selectAgent('Atlas')">
        <div class="ac-name">Atlas</div><div class="ac-role">Infra auditor. Security, health, services.</div>
      </div>
      <div class="agent-card" data-agent="Soma" onclick="selectAgent('Soma')">
        <div class="ac-name">Soma</div><div class="ac-role">Nervous system. Mood, body, psyche.</div>
      </div>
      <div class="agent-card" data-agent="Hermes" onclick="selectAgent('Hermes')">
        <div class="ac-name">Hermes</div><div class="ac-role">Messenger. Relay, routing, bridging.</div>
      </div>
    </div>
  </div>
</div>

<div id="thinking">
  <span class="agent-name"></span><span class="dots">thinking</span><span class="elapsed"></span>
</div>

<div id="input-area">
  <textarea id="msg-input" placeholder="Type a message..." rows="1"></textarea>
  <button id="send-btn" onclick="sendMessage()">Send</button>
</div>

<div id="status-bar">
  <span><span class="status-dot" id="ollama-dot"></span><span id="ollama-status">checking...</span></span>
  <span id="msg-count"></span>
</div>

<script>
let currentModel = '';
let streaming = false;
let abortCtrl = null;
let thinkStart = 0;
let thinkTimer = null;

const AGENT_COLORS = {
  'agent:Eos':'#4ade80','agent:Nova':'#c084fc','agent:Tempo':'#fbbf24',
  'agent:Atlas':'#f87171','agent:Soma':'#f472b6','agent:Hermes':'#22d3ee'
};
const AGENT_INITIALS = {
  'agent:Eos':'E','agent:Nova':'N','agent:Tempo':'T',
  'agent:Atlas':'A','agent:Soma':'S','agent:Hermes':'H'
};

function selectAgent(name) {
  const sel = document.getElementById('model-select');
  sel.value = 'agent:' + name;
  switchModel('agent:' + name);
}

// Detect base URL (supports being proxied through hub at /chorus/)
const BASE_URL = (() => {
  const p = window.location.pathname;
  if (p.startsWith('/chorus')) return '/chorus';
  return '';
})();

// ── INIT ──
async function init() {
  await loadModels();
  checkOllama();
  const input = document.getElementById('msg-input');
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  });
  input.addEventListener('input', autoResize);
}

function autoResize() {
  const el = document.getElementById('msg-input');
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 150) + 'px';
}

// ── MODELS ──
async function loadModels() {
  const sel = document.getElementById('model-select');
  try {
    const r = await fetch(BASE_URL + '/api/models');
    const models = await r.json();
    if (!models.length) { sel.innerHTML = '<option value="">No models found</option>'; return; }
    // Group agents first, then raw models
    const agents = models.filter(m => m.is_agent);
    const raw = models.filter(m => !m.is_agent);
    let html = '';
    if (agents.length) {
      html += '<optgroup label="── AGENTS ──">';
      html += agents.map(m => `<option value="${m.name}" data-params="agent" data-family="agent">⬡ ${m.display_name || m.name}</option>`).join('');
      html += '</optgroup>';
    }
    html += '<optgroup label="── MODELS ──">';
    html += raw.map(m => `<option value="${m.name}" data-params="${m.params}" data-family="${m.family}">${m.name}</option>`).join('');
    html += '</optgroup>';
    sel.innerHTML = html;
    sel.onchange = () => switchModel(sel.value);
    switchModel(models[0].name);
  } catch(e) {
    sel.innerHTML = '<option value="">Ollama unavailable</option>';
  }
}

async function switchModel(name) {
  currentModel = name;
  const sel = document.getElementById('model-select');
  const opt = sel.selectedOptions[0];
  const info = document.getElementById('model-info');
  if (opt) {
    const p = opt.dataset.params;
    const f = opt.dataset.family;
    if (p === 'agent') {
      const roles = {Eos:'companion',Nova:'observer',Tempo:'rhythm',Atlas:'infra',Soma:'psyche',Hermes:'messenger'};
      const n = name.replace('agent:','');
      info.textContent = roles[n] || 'agent';
      info.style.color = AGENT_COLORS[name] || '';
    } else {
      info.textContent = [p, f].filter(Boolean).join(' · ');
      info.style.color = '';
    }
  }
  // Load history
  try {
    const r = await fetch(BASE_URL + '/api/history?model=' + encodeURIComponent(name));
    const msgs = await r.json();
    renderMessages(msgs);
    updateMsgCount(msgs);
  } catch(e) {
    renderMessages([]);
    updateMsgCount([]);
  }
}

// ── RENDER ──
function renderMessages(msgs) {
  const chat = document.getElementById('chat');
  const empty = document.getElementById('empty-state');
  if (!msgs.length) {
    chat.innerHTML = '';
    chat.appendChild(empty);
    empty.style.display = 'flex';
    return;
  }
  empty.style.display = 'none';
  chat.innerHTML = '';
  msgs.forEach(m => appendMessage(m.role, m.content, m.timestamp, false));
  scrollBottom();
}

function appendMessage(role, content, timestamp, scroll=true) {
  const chat = document.getElementById('chat');
  const empty = document.getElementById('empty-state');
  empty.style.display = 'none';
  const row = document.createElement('div');
  row.className = 'msg-row ' + role;
  const avatar = document.createElement('div');
  avatar.className = 'msg-avatar';
  if (role === 'user') {
    avatar.textContent = 'J';
  } else {
    const initial = AGENT_INITIALS[currentModel] || 'AI';
    const color = AGENT_COLORS[currentModel];
    avatar.textContent = initial;
    if (color) avatar.style.background = color;
  }
  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble';
  bubble.innerHTML = renderMd(content);
  const timeEl = document.createElement('div');
  timeEl.className = 'msg-time';
  timeEl.textContent = timestamp ? new Date(timestamp).toLocaleTimeString() : new Date().toLocaleTimeString();
  row.appendChild(avatar);
  const wrap = document.createElement('div');
  wrap.appendChild(bubble);
  wrap.appendChild(timeEl);
  row.appendChild(wrap);
  chat.appendChild(row);
  if (scroll) scrollBottom();
  return bubble;
}

function renderMd(text) {
  if (!text) return '';
  // Code blocks
  text = text.replace(/```(\\w*)\\n([\\s\\S]*?)```/g, (_, lang, code) =>
    '<pre><code>' + escHtml(code.trim()) + '</code></pre>');
  // Inline code
  text = text.replace(/`([^`]+)`/g, '<code>$1</code>');
  // Bold
  text = text.replace(/\\*\\*(.+?)\\*\\*/g, '<strong>$1</strong>');
  // Italic
  text = text.replace(/\\*(.+?)\\*/g, '<em>$1</em>');
  // Line breaks (outside pre)
  text = text.replace(/\\n/g, '<br>');
  return text;
}

function escHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function scrollBottom() {
  const chat = document.getElementById('chat');
  requestAnimationFrame(() => { chat.scrollTop = chat.scrollHeight; });
}

// ── SEND ──
function parseNDJSON(text) {
  // Parse NDJSON text and extract assistant content
  let result = '';
  const lines = text.split('\\n').filter(Boolean);
  for (const line of lines) {
    try {
      const obj = JSON.parse(line);
      if (obj.error) {
        result += '\\n[Error: ' + obj.error + ']';
      } else if (obj.message && obj.message.content) {
        result += obj.message.content;
      }
    } catch(e) { /* partial line, skip */ }
  }
  return result;
}

function sendMessage() {
  const input = document.getElementById('msg-input');
  const text = input.value.trim();
  if (!text || !currentModel || streaming) return;

  input.value = '';
  input.style.height = 'auto';
  appendMessage('user', text);

  streaming = true;
  document.getElementById('send-btn').disabled = true;
  const agentLabel = AGENT_INITIALS[currentModel] ? currentModel.replace('agent:','') : currentModel;
  showThinking(true, agentLabel);

  // Create assistant bubble
  const bubble = appendMessage('assistant', '', null, true);

  // When proxied through the hub (BASE_URL='/chorus'), use the sync endpoint.
  // Streaming via chunked transfer encoding breaks on mobile browsers in
  // iframes behind Cloudflare tunnels (XHR onprogress never fires).
  // When accessed directly (BASE_URL=''), use streaming for live output.
  const isProxied = BASE_URL.length > 0;

  if (isProxied) {
    // ── SYNC MODE (mobile/proxied) ──
    // Single fetch, full response buffered server-side, returned as JSON.
    const ctrl = new AbortController();
    abortCtrl = ctrl;
    fetch(BASE_URL + '/api/chat-sync', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ model: currentModel, message: text }),
      signal: ctrl.signal
    })
    .then(r => r.json())
    .then(data => {
      if (data.error) {
        bubble.innerHTML = renderMd('[Error: ' + data.error + ']');
      } else {
        bubble.innerHTML = renderMd(data.content || '[No response received]');
      }
      scrollBottom();
      showThinking(false);
      streaming = false;
      document.getElementById('send-btn').disabled = false;
      input.focus();
    })
    .catch(err => {
      if (err.name !== 'AbortError') {
        bubble.innerHTML = renderMd('[Connection error: ' + err.message + ']');
      }
      showThinking(false);
      streaming = false;
      document.getElementById('send-btn').disabled = false;
      input.focus();
    });
  } else {
    // ── STREAMING MODE (direct access) ──
    // XHR with onprogress for live token output.
    const xhr = new XMLHttpRequest();
    abortCtrl = xhr;
    let lastLen = 0;

    xhr.open('POST', BASE_URL + '/api/chat', true);
    xhr.setRequestHeader('Content-Type', 'application/json');

    xhr.onprogress = function() {
      const newData = xhr.responseText;
      if (newData.length > lastLen) {
        lastLen = newData.length;
        const parsed = parseNDJSON(newData);
        if (parsed) {
          bubble.innerHTML = renderMd(parsed);
          scrollBottom();
        }
      }
    };

    xhr.onload = function() {
      const fullResponse = parseNDJSON(xhr.responseText);
      bubble.innerHTML = renderMd(fullResponse || '[No response received]');
      scrollBottom();
      showThinking(false);
      streaming = false;
      document.getElementById('send-btn').disabled = false;
      input.focus();
    };

    xhr.onerror = function() {
      bubble.innerHTML = renderMd('[Connection error]');
      showThinking(false);
      streaming = false;
      document.getElementById('send-btn').disabled = false;
      input.focus();
    };

    xhr.ontimeout = function() {
      bubble.innerHTML = renderMd('[Request timed out]');
      showThinking(false);
      streaming = false;
      document.getElementById('send-btn').disabled = false;
      input.focus();
    };

    xhr.onabort = function() {
      showThinking(false);
      streaming = false;
      document.getElementById('send-btn').disabled = false;
      input.focus();
    };

    xhr.timeout = 300000;
    xhr.send(JSON.stringify({ model: currentModel, message: text }));
  }
}

function showThinking(on, label) {
  const el = document.getElementById('thinking');
  if (on) {
    el.style.display = 'flex';
    el.querySelector('.agent-name').textContent = label ? label + ' ' : '';
    thinkStart = Date.now();
    thinkTimer = setInterval(() => {
      const s = ((Date.now() - thinkStart) / 1000).toFixed(0);
      el.querySelector('.elapsed').textContent = s + 's';
    }, 1000);
  } else {
    el.style.display = 'none';
    clearInterval(thinkTimer);
  }
}

// ── ACTIONS ──
async function clearChat() {
  if (!currentModel) return;
  if (!confirm('Clear conversation with ' + currentModel + '?')) return;
  await fetch(BASE_URL + '/api/clear', { method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({model: currentModel})
  });
  renderMessages([]);
}

function exportChat() {
  if (!currentModel) return;
  fetch(BASE_URL + '/api/history?model=' + encodeURIComponent(currentModel))
    .then(r => r.json())
    .then(msgs => {
      const blob = new Blob([JSON.stringify({model: currentModel, messages: msgs}, null, 2)],
        {type: 'application/json'});
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = currentModel.replace(':','_') + '-chat.json';
      a.click();
    });
}

async function checkOllama() {
  const dot = document.getElementById('ollama-dot');
  const txt = document.getElementById('ollama-status');
  try {
    const r = await fetch(BASE_URL + '/api/models');
    const models = await r.json();
    dot.className = 'status-dot online';
    txt.textContent = 'Ollama: ' + models.filter(m => !m.is_agent).length + ' models';
  } catch(e) {
    dot.className = 'status-dot offline';
    txt.textContent = 'Ollama: offline';
  }
}

function updateMsgCount(msgs) {
  const el = document.getElementById('msg-count');
  if (el) el.textContent = msgs.length ? msgs.length + ' messages' : '';
}

init();
setInterval(checkOllama, 30000);
</script>
</body>
</html>"""

# ═══════════════════════════════════════════════════════════════
# HTTP HANDLER
# ═══════════════════════════════════════════════════════════════

class ChorusHandler(http.server.BaseHTTPRequestHandler):
    """Handle all Chorus routes."""
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        # Quiet logging
        pass

    def _json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html(self, html):
        body = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)

        if path == "/":
            self._html(build_app())

        elif path == "/api/models":
            self._json(get_models())

        elif path == "/api/history":
            model = params.get("model", [""])[0]
            if not model:
                self._json({"error": "no model specified"}, 400)
                return
            msgs = load_history(model)
            self._json(msgs)

        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len) if content_len > 0 else b""

        if path == "/api/chat":
            self._handle_chat(body)

        elif path == "/api/chat-sync":
            self._handle_chat_sync(body)

        elif path == "/api/clear":
            try:
                data = json.loads(body)
                model = data.get("model", "")
                if model:
                    conversations[model] = []
                    save_history(model)
                self._json({"ok": True})
            except Exception as e:
                err_msg = f"Clear failed: {e}"
                self._json({"error": err_msg}, 500)

        else:
            self.send_error(404)

    def _handle_chat(self, body):
        """Stream chat response from Ollama."""
        try:
            data = json.loads(body)
            model = data.get("model", "")
            message = data.get("message", "")

            if not model or not message:
                self._json({"error": "model and message required"}, 400)
                return

            # Resolve agent persona to underlying model + system prompt
            ollama_model = model
            system_prompt = None
            if model.startswith("agent:"):
                agent_name = model[6:]
                persona = AGENT_PERSONAS.get(agent_name)
                if persona:
                    ollama_model = persona["model"]
                    system_prompt = persona["system"]
                else:
                    self._json({"error": f"unknown agent: {agent_name}"}, 400)
                    return

            # Add user message to history
            msgs = load_history(model)
            ts = datetime.now().isoformat()
            msgs.append({"role": "user", "content": message, "timestamp": ts})

            # Build Ollama request (only role + content, no timestamp)
            ollama_msgs = []
            if system_prompt:
                ollama_msgs.append({"role": "system", "content": system_prompt})
            ollama_msgs += [{"role": m["role"], "content": m["content"]} for m in msgs]

            req_data = json.dumps({
                "model": ollama_model,
                "messages": ollama_msgs,
                "stream": True
            }).encode()

            req = urllib.request.Request(
                f"{OLLAMA_URL}/api/chat",
                data=req_data,
                headers={"Content-Type": "application/json"}
            )

            # Stream response using chunked transfer encoding for mobile compatibility
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Transfer-Encoding", "chunked")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Accel-Buffering", "no")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()

            def send_chunk(data):
                """Send a single HTTP chunked-encoding frame."""
                if isinstance(data, str):
                    data = data.encode()
                self.wfile.write(f"{len(data):x}\r\n".encode())
                self.wfile.write(data)
                self.wfile.write(b"\r\n")
                self.wfile.flush()

            full_response = ""
            try:
                resp = urllib.request.urlopen(req, timeout=300)
                while True:
                    line = resp.readline()
                    if not line:
                        break
                    try:
                        chunk = json.loads(line)
                        if chunk.get("message", {}).get("content"):
                            full_response += chunk["message"]["content"]
                        send_chunk(line)
                    except json.JSONDecodeError:
                        pass
            except Exception as e:
                err_msg = f"Ollama error: {e}"
                error_line = json.dumps({"error": err_msg}).encode() + b"\n"
                try:
                    send_chunk(error_line)
                except Exception:
                    pass
            # Send terminating chunk
            try:
                self.wfile.write(b"0\r\n\r\n")
                self.wfile.flush()
            except Exception:
                pass

            # Save assistant response to history
            if full_response:
                msgs.append({
                    "role": "assistant",
                    "content": full_response,
                    "timestamp": datetime.now().isoformat()
                })
            save_history(model)

        except Exception as e:
            err_msg = f"Chat error: {e}"
            try:
                self._json({"error": err_msg}, 500)
            except Exception:
                pass

    def _handle_chat_sync(self, body):
        """Non-streaming chat — buffers full Ollama response, returns single JSON.
        Needed for mobile browsers in iframes behind Cloudflare tunnels where
        chunked transfer encoding / XHR onprogress doesn't work reliably."""
        try:
            data = json.loads(body)
            model = data.get("model", "")
            message = data.get("message", "")

            if not model or not message:
                self._json({"error": "model and message required"}, 400)
                return

            # Resolve agent persona to underlying model + system prompt
            ollama_model = model
            system_prompt = None
            if model.startswith("agent:"):
                agent_name = model[6:]
                persona = AGENT_PERSONAS.get(agent_name)
                if persona:
                    ollama_model = persona["model"]
                    system_prompt = persona["system"]
                else:
                    self._json({"error": f"unknown agent: {agent_name}"}, 400)
                    return

            # Add user message to history
            msgs = load_history(model)
            ts = datetime.now().isoformat()
            msgs.append({"role": "user", "content": message, "timestamp": ts})

            # Build Ollama request — non-streaming
            ollama_msgs = []
            if system_prompt:
                ollama_msgs.append({"role": "system", "content": system_prompt})
            ollama_msgs += [{"role": m["role"], "content": m["content"]} for m in msgs]

            req_data = json.dumps({
                "model": ollama_model,
                "messages": ollama_msgs,
                "stream": False
            }).encode()

            req = urllib.request.Request(
                f"{OLLAMA_URL}/api/chat",
                data=req_data,
                headers={"Content-Type": "application/json"}
            )

            full_response = ""
            try:
                resp = urllib.request.urlopen(req, timeout=300)
                resp_data = json.loads(resp.read())
                full_response = resp_data.get("message", {}).get("content", "")
            except Exception as e:
                err_msg = f"Ollama error: {e}"
                self._json({"error": err_msg}, 502)
                return

            # Save assistant response to history
            resp_ts = datetime.now().isoformat()
            if full_response:
                msgs.append({
                    "role": "assistant",
                    "content": full_response,
                    "timestamp": resp_ts
                })
            save_history(model)

            self._json({
                "role": "assistant",
                "content": full_response,
                "timestamp": resp_ts
            })

        except Exception as e:
            err_msg = f"Chat sync error: {e}"
            try:
                self._json({"error": err_msg}, 500)
            except Exception:
                pass


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    os.makedirs(HISTORY_DIR, exist_ok=True)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), ChorusHandler)
    print(f"THE CHORUS running on http://127.0.0.1:{PORT}")
    print(f"History: {HISTORY_DIR}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()

if __name__ == "__main__":
    main()
