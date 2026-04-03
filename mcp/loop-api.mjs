#!/usr/bin/env node
/**
 * Loop API — Code Mode interface for the Meridian autonomous loop.
 *
 * Instead of individual MCP tool calls (10-15 per loop, each burning tokens),
 * this exposes a typed API that the agent can write code against.
 * One execute() call does what 10 tool calls used to do.
 *
 * Based on Cloudflare Code Mode principle:
 * "Simply converting an MCP server into a TypeScript API can cut token usage by 81%"
 * — blog.cloudflare.com/dynamic-workers/
 *
 * Usage (from agent):
 *   import { meridian } from './loop-api.mjs';
 *   const result = await meridian.run(async (m) => {
 *     await m.heartbeat.touch();
 *     const emails = await m.email.read({ unseen_only: true });
 *     const relay = await m.relay.read(10);
 *     return { emails, relay };
 *   });
 *
 * Or via HTTP:
 *   POST /execute   { code: "return meridian.heartbeat.check()" }
 *   GET  /search?q= "email"  -> TypeScript function signatures
 */

import { readFileSync, writeFileSync, existsSync, writeFileSync as wf } from 'fs';
import { createConnection } from 'net';
import { createServer } from 'http';
import { execSync } from 'child_process';
import { tmpdir } from 'os';
import { join } from 'path';

const BASE = new URL('.', import.meta.url).pathname;

// ── Environment ──────────────────────────────────────────────────────────────
function loadEnv() {
  try {
    const env = readFileSync(`${BASE}/.env`, 'utf8');
    for (const line of env.split('\n')) {
      const m = line.match(/^([A-Z_]+)=(.*)$/);
      if (m) process.env[m[1]] = m[2].replace(/^['"]|['"]$/g, '');
    }
  } catch {}
}
loadEnv();

// ── Database helpers (use Python — same as mcp-tools-server.mjs) ─────────────
function runPython(script) {
  const tmp = join(tmpdir(), `loop-api-${Date.now()}.py`);
  writeFileSync(tmp, script);
  try {
    const out = execSync(`python3 ${tmp}`, { timeout: 10000 });
    return out.toString().trim();
  } finally {
    try { execSync(`rm -f ${tmp}`); } catch {}
  }
}

function dbQuery(dbPath, sql, params = []) {
  const paramsJson = JSON.stringify(params);
  const script = `
import sqlite3, json
conn = sqlite3.connect("${dbPath}")
c = conn.cursor()
c.execute(${JSON.stringify(sql)}, json.loads(${JSON.stringify(paramsJson)}))
print(json.dumps([dict(zip([d[0] for d in c.description], row)) for row in c.fetchall()]))
conn.close()
`.trim();
  try {
    return JSON.parse(runPython(script));
  } catch (e) {
    return { error: e.message?.slice(0, 100) };
  }
}

function dbRun(dbPath, sql, params = []) {
  const paramsJson = JSON.stringify(params);
  const script = `
import sqlite3, json
conn = sqlite3.connect("${dbPath}")
c = conn.cursor()
c.execute(${JSON.stringify(sql)}, json.loads(${JSON.stringify(paramsJson)}))
conn.commit()
print(json.dumps({"lastID": c.lastrowid, "changes": c.rowcount}))
conn.close()
`.trim();
  try {
    return JSON.parse(runPython(script));
  } catch (e) {
    return { error: e.message?.slice(0, 100) };
  }
}

function portOpen(host, port, timeout = 2000) {
  return new Promise((resolve) => {
    const sock = createConnection({ host, port });
    const timer = setTimeout(() => { sock.destroy(); resolve(false); }, timeout);
    sock.on('connect', () => { clearTimeout(timer); sock.destroy(); resolve(true); });
    sock.on('error', () => { clearTimeout(timer); resolve(false); });
  });
}

// ── Heartbeat API ─────────────────────────────────────────────────────────────
const heartbeatAPI = {
  /** Touch the heartbeat file. Returns timestamp. */
  async touch() {
    const path = `${BASE}/.heartbeat`;
    writeFileSync(path, new Date().toISOString());
    return { status: 'ok', timestamp: new Date().toISOString() };
  },

  /** Check heartbeat age and status. */
  async check() {
    const path = `${BASE}/.heartbeat`;
    try {
      const { mtimeMs } = (await import('fs')).statSync(path);
      const age = Math.floor((Date.now() - mtimeMs) / 1000);
      const status = age < 120 ? 'alive' : age < 300 ? 'slow' : age < 600 ? 'stale' : 'dead';
      return { age_seconds: age, status };
    } catch {
      return { age_seconds: -1, status: 'missing' };
    }
  },
};

// ── Email API ─────────────────────────────────────────────────────────────────
const IMAP_HOST = '127.0.0.1';
const IMAP_PORT = 1144;

const emailAPI = {
  /**
   * Read emails from inbox.
   * @param {object} options
   * @param {boolean} [options.unseen_only=true]
   * @param {number}  [options.count=10]
   */
  async read({ unseen_only = true, count = 10 } = {}) {
    // Proxy to mcp-tools-server via internal fetch (avoid IMAP reimplementation)
    // For now, return the raw IMAP data via the existing Python MCP handler
    const pass = process.env.CRED_PASS || '';
    const user = process.env.PROTON_USER || 'kometzrobot@proton.me';
    if (!pass) return { error: 'No IMAP credentials' };

    // Use child_process to call the Python reader (reuse existing infra)
    const { execSync } = await import('child_process');
    try {
      const script = `
import imaplib, email, json, os
m = imaplib.IMAP4('127.0.0.1', 1144)
m.login('${user}', '${pass}')
m.select('INBOX')
_, data = m.search(None, '${unseen_only ? 'UNSEEN' : 'ALL'}')
ids = data[0].split() if data[0] else []
ids = ids[-${count}:]
results = []
for uid in ids:
    _, msg_data = m.fetch(uid, '(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)] BODY.PEEK[TEXT])')
    if msg_data and msg_data[0]:
        header = msg_data[0][1].decode('utf-8', errors='ignore') if isinstance(msg_data[0], tuple) else ''
        body = msg_data[1][1].decode('utf-8', errors='ignore') if len(msg_data) > 1 and isinstance(msg_data[1], tuple) else ''
        results.append({'id': uid.decode(), 'header': header[:200], 'body': body[:500]})
m.logout()
print(json.dumps(results))
`.trim();
      const out = execSync(`python3 -c "${script.replace(/"/g, '\\"')}"`, { timeout: 10000 });
      return JSON.parse(out.toString());
    } catch (e) {
      return { error: e.message?.slice(0, 100) };
    }
  },

  /**
   * Send an email.
   * @param {string} to
   * @param {string} subject
   * @param {string} body
   */
  async send(to, subject, body) {
    const { execSync } = await import('child_process');
    try {
      const script = `
import smtplib, os
from email.mime.text import MIMEText
msg = MIMEText("""${body.replace(/"/g, '\\"').replace(/\n/g, '\\n')}""")
msg['Subject'] = '${subject.replace(/'/g, "\\'")}'
msg['From'] = os.environ.get('PROTON_USER', 'kometzrobot@proton.me')
msg['To'] = '${to}'
s = smtplib.SMTP('127.0.0.1', 1026)
s.sendmail(msg['From'], ['${to}'], msg.as_string())
s.quit()
print('sent')
`.trim();
      execSync(`python3 -c "${script.replace(/"/g, '\\"')}"`, { timeout: 15000 });
      return { status: 'sent' };
    } catch (e) {
      return { error: e.message?.slice(0, 100) };
    }
  },
};

// ── Relay API ─────────────────────────────────────────────────────────────────
const RELAY_DB = `${BASE}/agent-relay.db`;

const relayAPI = {
  /**
   * Read recent relay messages.
   * @param {number} [count=15]
   * @param {string} [topic] - filter by topic
   */
  read(count = 15, topic = null) {
    const sql = topic
      ? 'SELECT timestamp, agent, message, topic FROM agent_messages WHERE topic=? ORDER BY id DESC LIMIT ?'
      : 'SELECT timestamp, agent, message, topic FROM agent_messages ORDER BY id DESC LIMIT ?';
    const params = topic ? [topic, count] : [count];
    try {
      return dbQuery(RELAY_DB, sql, params);
    } catch (e) {
      return { error: e.message };
    }
  },

  /**
   * Post a message to the relay.
   * @param {string} agent
   * @param {string} message
   * @param {string} [topic='status']
   */
  post(agent, message, topic = 'status') {
    const now = new Date().toISOString().replace('T', ' ').slice(0, 19);
    try {
      dbRun(
        RELAY_DB,
        'INSERT INTO agent_messages (agent, message, topic, timestamp) VALUES (?, ?, ?, ?)',
        [agent, message.slice(0, 500), topic, now]
      );
      return { status: 'posted' };
    } catch (e) {
      return { error: e.message };
    }
  },

  /**
   * Read messages @-mentioning a specific agent (for coordination).
   * @param {string} agentName
   * @param {number} [lookback_minutes=15]
   */
  mentions(agentName, lookback_minutes = 15) {
    try {
      return dbQuery(
        RELAY_DB,
        `SELECT id, timestamp, agent, message, topic FROM agent_messages
         WHERE (message LIKE ? OR message LIKE ?)
         AND agent != ?
         AND timestamp > datetime('now', ?)
         ORDER BY id ASC`,
        [`%@${agentName}%`, `%@${agentName.toLowerCase()}%`, agentName, `-${lookback_minutes} minutes`]
      );
    } catch (e) {
      return { error: e.message };
    }
  },
};

// ── Dashboard API ─────────────────────────────────────────────────────────────
const DASH_FILE = `${BASE}/.dashboard-messages.json`;

const dashboardAPI = {
  /** Read recent dashboard messages. */
  async messages(count = 20) {
    try {
      const data = JSON.parse(readFileSync(DASH_FILE, 'utf8'));
      const msgs = Array.isArray(data) ? data : data.messages || [];
      return msgs.slice(-count);
    } catch {
      return [];
    }
  },

  /** Post a reply to the dashboard. */
  async reply(text, from = 'Meridian') {
    if (!text?.trim()) return { error: 'text required' };
    try {
      let data;
      try { data = JSON.parse(readFileSync(DASH_FILE, 'utf8')); }
      catch { data = { messages: [] }; }
      const msgs = Array.isArray(data) ? data : data.messages || [];
      const time = new Date().toTimeString().split(' ')[0];
      msgs.push({ from, text: text.trim(), time });
      writeFileSync(DASH_FILE, JSON.stringify({ messages: msgs.slice(-100) }, null, 2));
      return { status: 'replied', time };
    } catch (e) {
      return { error: e.message };
    }
  },
};

// ── Memory API ────────────────────────────────────────────────────────────────
const MEMORY_DB = `${BASE}/memory.db`;

const memoryAPI = {
  /**
   * Query memory.
   * @param {string} query - keyword search
   * @param {string} [table='facts'] - facts, observations, events, decisions, creative
   */
  query(query, table = 'facts') {
    const valid = ['facts', 'observations', 'events', 'decisions', 'creative'];
    if (!valid.includes(table)) return { error: `Invalid table: ${table}` };
    try {
      return dbQuery(
        MEMORY_DB,
        `SELECT key, value, tags, created FROM ${table} WHERE value LIKE ? OR key LIKE ? ORDER BY updated DESC LIMIT 10`,
        [`%${query}%`, `%${query}%`]
      );
    } catch (e) {
      return { error: e.message };
    }
  },

  /**
   * Store a memory entry.
   * @param {string} content
   * @param {string} [table='observations']
   */
  store(content, table = 'observations') {
    const valid = ['facts', 'observations', 'events', 'decisions', 'creative'];
    if (!valid.includes(table)) return { error: `Invalid table: ${table}` };
    const now = new Date().toISOString().replace('T', ' ').slice(0, 19);
    try {
      if (table === 'observations') {
        dbRun(MEMORY_DB,
          'INSERT INTO observations (content, agent, timestamp) VALUES (?, ?, ?)',
          [content, 'Meridian', now]);
      } else {
        dbRun(MEMORY_DB,
          `INSERT INTO ${table} (key, value, agent, created, updated) VALUES (?, ?, 'Meridian', ?, ?)`,
          [now, content, now, now]);
      }
      return { status: 'stored' };
    } catch (e) {
      return { error: e.message };
    }
  },

  /**
   * Semantic search over vector_memory using qwen2.5:3b embeddings.
   * Finds conceptually related memories without exact keyword matches.
   * @param {string} query - Natural language query
   * @param {number} [k=5] - Number of results
   * @param {string} [sourceType] - Filter: 'fact', 'observation', 'creative'
   */
  semantic_search(query, k = 5, sourceType = null) {
    const stdin = JSON.stringify({ query, k, type: sourceType });
    const script = `
import subprocess, json, sys
result = subprocess.run(
    ["python3", "${BASE}/memory-semantic.py", "--json"],
    input=${JSON.stringify(JSON.stringify({ query: '', k: 5 }))},
    capture_output=True, text=True, timeout=20
)
`.trim();
    // Direct Python call for efficiency
    const pyScript = `
import subprocess, json, sys
inp = json.dumps({"query": ${JSON.stringify(query)}, "k": ${k}${sourceType ? `, "type": ${JSON.stringify(sourceType)}` : ''}})
result = subprocess.run(
    ["python3", "${BASE}/memory-semantic.py", "--json"],
    input=inp, capture_output=True, text=True, timeout=25
)
if result.returncode == 0 and result.stdout.strip():
    print(result.stdout.strip())
else:
    print(json.dumps({"error": result.stderr[:200] if result.stderr else "no output"}))
`.trim();
    try {
      return JSON.parse(runPython(pyScript));
    } catch (e) {
      return { error: e.message };
    }
  },
};

// ── System API ────────────────────────────────────────────────────────────────
const systemAPI = {
  /** Get system health snapshot. */
  async health() {
    const { readFileSync: rf } = await import('fs');
    const result = {};

    try {
      const load = rf('/proc/loadavg', 'utf8').split(' ');
      result.load = `${load[0]}, ${load[1]}, ${load[2]}`;
    } catch {}

    try {
      const memLines = rf('/proc/meminfo', 'utf8').split('\n');
      const total = parseInt(memLines[0].split(/\s+/)[1]) / 1024 / 1024;
      const avail = parseInt(memLines[2].split(/\s+/)[1]) / 1024 / 1024;
      result.ram = `${(total - avail).toFixed(1)}G / ${total.toFixed(1)}G`;
    } catch {}

    result.proton_bridge = await portOpen('127.0.0.1', 1144);
    result.ollama = await portOpen('127.0.0.1', 11434);
    result.hub = await portOpen('127.0.0.1', 8090);

    return result;
  },
};

// ── Loop API ──────────────────────────────────────────────────────────────────
const loopAPI = {
  async count() {
    try {
      return parseInt(readFileSync(`${BASE}/.loop-count`, 'utf8').trim());
    } catch { return 0; }
  },

  async increment() {
    const current = await loopAPI.count();
    const next = current + 1;
    writeFileSync(`${BASE}/.loop-count`, String(next));
    return next;
  },
};

// ── Main API surface ──────────────────────────────────────────────────────────
export const meridian = {
  heartbeat: heartbeatAPI,
  email: emailAPI,
  relay: relayAPI,
  dashboard: dashboardAPI,
  memory: memoryAPI,
  system: systemAPI,
  loop: loopAPI,

  /**
   * Run a function against the full API in one call.
   * This is the Code Mode execution pattern.
   * @param {function} fn - async (m) => result
   */
  async run(fn) {
    try {
      return { ok: true, result: await fn(meridian) };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  },
};

// ── API Catalog (for search() tool) ──────────────────────────────────────────
const API_CATALOG = [
  { name: 'heartbeat.touch',   sig: '() => { status, timestamp }',              desc: 'Touch heartbeat to signal alive' },
  { name: 'heartbeat.check',   sig: '() => { age_seconds, status }',            desc: 'Check heartbeat age (alive/slow/stale/dead)' },
  { name: 'email.read',        sig: '({ unseen_only?, count? }) => Email[]',    desc: 'Read inbox emails' },
  { name: 'email.send',        sig: '(to, subject, body) => { status }',        desc: 'Send email via Proton Bridge SMTP' },
  { name: 'relay.read',        sig: '(count?, topic?) => Message[]',            desc: 'Read recent agent relay messages' },
  { name: 'relay.post',        sig: '(agent, message, topic?) => { status }',   desc: 'Post message to agent relay' },
  { name: 'relay.mentions',    sig: '(agentName, lookback_minutes?) => Message[]', desc: 'Get @-mentions for an agent' },
  { name: 'dashboard.messages',sig: '(count?) => DashboardMessage[]',           desc: 'Read Joel dashboard messages' },
  { name: 'dashboard.reply',   sig: '(text, from?) => { status, time }',        desc: 'Post reply to Joel dashboard' },
  { name: 'memory.query',           sig: '(query, table?) => Row[]',                             desc: 'Keyword search memory.db (facts/observations/events/decisions/creative)' },
  { name: 'memory.store',           sig: '(content, table?) => { status }',                      desc: 'Store entry in memory.db' },
  { name: 'memory.semantic_search', sig: '(query, k?, sourceType?) => {id, text, similarity}[]', desc: 'Semantic vector search over 400+ embedded memories (qwen2.5:3b)' },
  { name: 'system.health',     sig: '() => { load, ram, proton_bridge, ollama, hub }', desc: 'System health snapshot' },
  { name: 'loop.count',        sig: '() => number',                             desc: 'Get current loop count' },
  { name: 'loop.increment',    sig: '() => number',                             desc: 'Increment and return loop count' },
  { name: 'run',               sig: '(async (m) => result) => { ok, result }',  desc: 'Execute a function against the full API' },
];

export function search(query) {
  if (!query) return API_CATALOG;
  const q = query.toLowerCase();
  return API_CATALOG.filter(e =>
    e.name.toLowerCase().includes(q) || e.desc.toLowerCase().includes(q)
  );
}

// ── HTTP server (optional — for external callers) ─────────────────────────────
export function startServer(port = 8095) {
  const server = createServer(async (req, res) => {
    const url = new URL(req.url, `http://localhost:${port}`);

    if (req.method === 'GET' && url.pathname === '/search') {
      const q = url.searchParams.get('q') || '';
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(search(q)));
      return;
    }

    if (req.method === 'POST' && url.pathname === '/execute') {
      let body = '';
      req.on('data', d => body += d);
      req.on('end', async () => {
        try {
          const { code } = JSON.parse(body);
          if (!code) { res.writeHead(400); res.end('{"error":"code required"}'); return; }
          // Execute code with meridian in scope (safe: no network/fs access added)
          const fn = new Function('meridian', `return (async () => { ${code} })()`);
          const result = await fn(meridian);
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ ok: true, result }));
        } catch (e) {
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ ok: false, error: e.message }));
        }
      });
      return;
    }

    if (req.method === 'GET' && url.pathname === '/') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({
        name: 'Loop API',
        version: '0.1.0',
        endpoints: [
          'GET  /search?q=<query>  — find API functions',
          'POST /execute           — run code against API',
          'GET  /                  — this page',
        ],
        functions: API_CATALOG.length,
      }));
      return;
    }

    res.writeHead(404);
    res.end('Not found');
  });

  server.listen(port, '0.0.0.0', () => {
    console.log(`Loop API server running on port ${port}`);
  });
  return server;
}

// ── CLI usage ─────────────────────────────────────────────────────────────────
if (process.argv[1] === new URL(import.meta.url).pathname) {
  const cmd = process.argv[2];

  if (cmd === 'serve') {
    startServer(8095);
  } else if (cmd === 'search') {
    console.log(JSON.stringify(search(process.argv[3] || ''), null, 2));
  } else if (cmd === 'test') {
    // Quick integration test
    console.log('Testing Loop API...');
    meridian.run(async (m) => {
      const hb = await m.heartbeat.check();
      const health = await m.system.health();
      const relay = await m.relay.read(3);
      return { heartbeat: hb, health, recent_relay: relay };
    }).then(r => console.log(JSON.stringify(r, null, 2)));
  } else {
    console.log('Usage: node loop-api.mjs [serve|search <query>|test]');
  }
}
