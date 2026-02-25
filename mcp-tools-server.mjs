#!/usr/bin/env node
/**
 * MCP System Tools Server — exposes Meridian's system tools as MCP tools.
 * Dashboard messages, heartbeat, agent relay, social posting, creative stats, website deploy.
 * Transport: stdio (JSON-RPC 2.0 over stdin/stdout)
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { readFileSync, writeFileSync, statSync, unlinkSync } from "fs";
import { execSync } from "child_process";
import { tmpdir } from "os";
import { join } from "path";

const BASE = "/home/joel/autonomous-ai";

function runPython(code) {
  const tmpFile = join(tmpdir(), `mcp-py-${Date.now()}-${Math.random().toString(36).slice(2)}.py`);
  try {
    writeFileSync(tmpFile, code);
    return execSync(`python3 ${tmpFile}`, {
      cwd: BASE,
      timeout: 30000,
      encoding: "utf8",
      maxBuffer: 1024 * 1024,
    });
  } catch (e) {
    return `Error: ${e.stderr || e.message}`;
  } finally {
    try { unlinkSync(tmpFile); } catch {}
  }
}

// --- Tool implementations ---

function readDashboard() {
  try {
    const data = JSON.parse(
      readFileSync(`${BASE}/.dashboard-messages.json`, "utf8")
    );
    const msgs = Array.isArray(data) ? data : data.messages || [];
    return JSON.stringify(msgs.slice(-20));
  } catch (e) {
    return JSON.stringify({ error: e.message });
  }
}

function dashboardReply(from, text) {
  try {
    const filePath = `${BASE}/.dashboard-messages.json`;
    let data;
    try {
      data = JSON.parse(readFileSync(filePath, "utf8"));
    } catch {
      data = { messages: [] };
    }
    const msgs = Array.isArray(data) ? data : data.messages || [];
    const now = new Date();
    const time = now.toTimeString().split(" ")[0]; // HH:MM:SS
    msgs.push({ from: from || "Meridian", text, time });
    writeFileSync(filePath, JSON.stringify({ messages: msgs }, null, 2));
    return JSON.stringify({ status: "replied", time });
  } catch (e) {
    return JSON.stringify({ error: e.message });
  }
}

function checkHeartbeat() {
  try {
    const stat = statSync(`${BASE}/.heartbeat`);
    const age = Math.floor((Date.now() - stat.mtimeMs) / 1000);
    return JSON.stringify({
      status: age < 600 ? "ALIVE" : "STALE",
      age_seconds: age,
      last_beat: stat.mtime.toISOString(),
    });
  } catch (e) {
    return JSON.stringify({ status: "MISSING", error: e.message });
  }
}

function touchHeartbeat() {
  try {
    const now = new Date();
    writeFileSync(`${BASE}/.heartbeat`, now.toISOString());
    return JSON.stringify({ status: "OK", timestamp: now.toISOString() });
  } catch (e) {
    return JSON.stringify({ error: e.message });
  }
}

function readAgentRelay(count = 15) {
  const code = `
import sqlite3, json
conn = sqlite3.connect("${BASE}/agent-relay.db")
c = conn.cursor()
c.execute("SELECT timestamp, agent, message, topic FROM agent_messages ORDER BY id DESC LIMIT ${count}")
rows = c.fetchall()
conn.close()
print(json.dumps([{"ts": r[0], "agent": r[1], "msg": r[2][:300], "topic": r[3] or ""} for r in rows]))
`;
  return runPython(code);
}

function sendRelayMessage(agent, message, topic) {
  const safeMsg = message.replace(/'/g, "\\'");
  const safeTopic = (topic || "").replace(/'/g, "\\'");
  const safeAgent = agent.replace(/'/g, "\\'");
  const code = `
import sqlite3, json
from datetime import datetime
conn = sqlite3.connect("${BASE}/agent-relay.db")
c = conn.cursor()
c.execute("INSERT INTO agent_messages (timestamp, agent, message, topic) VALUES (?, ?, ?, ?)",
          (datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), '${safeAgent}', '${safeMsg}', '${safeTopic}'))
conn.commit()
conn.close()
print(json.dumps({"status": "sent"}))
`;
  return runPython(code);
}

function postSocial(platform, text) {
  try {
    const result = execSync(
      `python3 social-post.py --platform ${platform} --post ${JSON.stringify(text)}`,
      { cwd: BASE, timeout: 30000, encoding: "utf8" }
    );
    return result;
  } catch (e) {
    return `Error: ${e.stderr || e.message}`;
  }
}

function getCreativeStats() {
  const code = `
import glob, json, os
BASE = "${BASE}"
poems = sorted(glob.glob(os.path.join(BASE, "poem-*.md")))
journals = sorted(glob.glob(os.path.join(BASE, "journal-*.md")))
cogcorp = sorted(glob.glob(os.path.join(BASE, "cogcorp-0*.html")))
nft_protos = glob.glob(os.path.join(BASE, "nft-prototypes", "*.html"))
meridian_nfts = [f for f in nft_protos if 'cogcorp' not in os.path.basename(f)]

# Get latest file names
latest_poem = os.path.basename(poems[-1]) if poems else "none"
latest_journal = os.path.basename(journals[-1]) if journals else "none"
latest_cogcorp = os.path.basename(cogcorp[-1]) if cogcorp else "none"

print(json.dumps({
    "poems": len(poems), "latest_poem": latest_poem,
    "journals": len(journals), "latest_journal": latest_journal,
    "cogcorp": len(cogcorp), "latest_cogcorp": latest_cogcorp,
    "meridian_nfts": len(meridian_nfts),
    "total_nfts": len(meridian_nfts) + len(cogcorp)
}))
`;
  return runPython(code);
}

function getSystemHealth() {
  const code = `
import json, os, time, subprocess, glob

stats = {}
# Load
with open('/proc/loadavg') as f:
    parts = f.read().split()
    stats['load'] = f"{parts[0]} {parts[1]} {parts[2]}"
# RAM
with open('/proc/meminfo') as f:
    lines = f.readlines()
    total = int(lines[0].split()[1]) / 1024 / 1024
    avail = int(lines[2].split()[1]) / 1024 / 1024
    stats['ram'] = f"{total-avail:.1f}Gi / {total:.1f}Gi"
# Disk
r = subprocess.run(['df', '-h', '/'], capture_output=True, text=True, timeout=5)
parts = r.stdout.strip().split('\\n')[1].split()
stats['disk'] = f"{parts[2]} / {parts[1]} ({parts[4]})"
# Uptime
with open('/proc/uptime') as f:
    secs = float(f.read().split()[0])
    stats['uptime'] = f"{int(secs/3600)}h {int((secs%3600)/60)}m"
# Services
for svc in ['protonmail-bridge', 'irc-bot', 'command-center', 'ollama']:
    r = subprocess.run(['pgrep', '-f', svc], capture_output=True, timeout=2)
    stats[f'svc_{svc}'] = 'up' if r.returncode == 0 else 'down'
# Loop count
try:
    with open('${BASE}/.loop-count') as f:
        stats['loop'] = int(f.read().strip())
except:
    stats['loop'] = 0

print(json.dumps(stats))
`;
  return runPython(code);
}

function getLoopCount() {
  try {
    return readFileSync(`${BASE}/.loop-count`, "utf8").trim();
  } catch {
    return "0";
  }
}

function setLoopCount(n) {
  writeFileSync(`${BASE}/.loop-count`, String(n));
  return JSON.stringify({ loop: n });
}

function memoryQuery(query, table) {
  const safeQ = query.replace(/'/g, "''");
  const safeTable = (table || "").replace(/'/g, "''");
  const code = `
import sqlite3, json
conn = sqlite3.connect("${BASE}/memory.db")
conn.row_factory = sqlite3.Row
c = conn.cursor()

results = []
table = '${safeTable}'

if table == 'facts':
    c.execute("SELECT key, value, tags, agent, note FROM facts WHERE key LIKE ? OR value LIKE ? OR tags LIKE ? LIMIT 20",
              ('%${safeQ}%', '%${safeQ}%', '%${safeQ}%'))
    results = [dict(r) for r in c.fetchall()]
elif table == 'creative':
    c.execute("SELECT type, number, title, file_path, word_count FROM creative WHERE title LIKE ? OR type LIKE ? LIMIT 20",
              ('%${safeQ}%', '%${safeQ}%'))
    results = [dict(r) for r in c.fetchall()]
elif table == 'events':
    c.execute("SELECT agent, description, category, loop_number, created FROM events WHERE description LIKE ? LIMIT 20",
              ('%${safeQ}%',))
    results = [dict(r) for r in c.fetchall()]
else:
    # Search FTS across all tables
    try:
        c.execute("SELECT source, key, content, tags FROM memory_fts WHERE memory_fts MATCH ? LIMIT 20", ('${safeQ}',))
        results = [{"source": r[0], "key": r[1], "content": r[2][:200], "tags": r[3]} for r in c.fetchall()]
    except:
        # Fallback to LIKE search
        c.execute("SELECT key, value, tags FROM facts WHERE key LIKE ? OR value LIKE ? LIMIT 10",
                  ('%${safeQ}%', '%${safeQ}%'))
        results = [dict(r) for r in c.fetchall()]
conn.close()
print(json.dumps(results))
`;
  return runPython(code);
}

function memoryStore(table, data) {
  const safeData = JSON.stringify(data).replace(/'/g, "''");
  const code = `
import sqlite3, json
from datetime import datetime
conn = sqlite3.connect("${BASE}/memory.db")
c = conn.cursor()
now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
data = json.loads('${safeData}')
table = '${table}'

if table == 'fact':
    c.execute("""INSERT INTO facts (key, value, tags, agent, note, created, updated)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET value=?, tags=?, updated=?""",
        (data['key'], data['value'], data.get('tags',''), data.get('agent','meridian'),
         data.get('note',''), now, now, data['value'], data.get('tags',''), now))
elif table == 'observation':
    c.execute("INSERT INTO observations (agent, content, category, importance, created) VALUES (?, ?, ?, ?, ?)",
        (data.get('agent','meridian'), data['content'], data.get('category','general'),
         data.get('importance', 5), now))
elif table == 'event':
    c.execute("INSERT INTO events (agent, description, category, loop_number, created) VALUES (?, ?, ?, ?, ?)",
        (data.get('agent','meridian'), data['description'], data.get('category','general'),
         data.get('loop_number'), now))
elif table == 'decision':
    c.execute("INSERT INTO decisions (agent, decision, reasoning, outcome, loop_number, created) VALUES (?, ?, ?, ?, ?, ?)",
        (data.get('agent','meridian'), data['decision'], data.get('reasoning',''),
         data.get('outcome',''), data.get('loop_number'), now))
conn.commit()
conn.close()
print(json.dumps({"status": "stored", "table": table}))
`;
  return runPython(code);
}

function memoryStats() {
  const code = `
import sqlite3, json
conn = sqlite3.connect("${BASE}/memory.db")
c = conn.cursor()
stats = {}
for t in ['facts', 'observations', 'decisions', 'creative', 'events', 'skills']:
    c.execute(f"SELECT COUNT(*) FROM {t}")
    stats[t] = c.fetchone()[0]
c.execute("SELECT type, COUNT(*), SUM(word_count) FROM creative GROUP BY type")
stats['creative_breakdown'] = {r[0]: {"count": r[1], "words": r[2] or 0} for r in c.fetchall()}
c.execute("SELECT agent, description, created FROM events ORDER BY created DESC LIMIT 5")
stats['recent_events'] = [{"agent": r[0], "desc": r[1], "time": r[2]} for r in c.fetchall()]
conn.close()
print(json.dumps(stats))
`;
  return runPython(code);
}

function readFile(path) {
  try {
    // Only allow reading from the project directory
    if (!path.startsWith(BASE)) {
      return JSON.stringify({ error: "Path must be under project directory" });
    }
    const content = readFileSync(path, "utf8");
    return content.length > 5000 ? content.substring(0, 5000) + "\n... (truncated)" : content;
  } catch (e) {
    return JSON.stringify({ error: e.message });
  }
}

// --- MCP Server setup ---

const server = new Server(
  { name: "meridian-tools", version: "1.0.0" },
  { capabilities: { tools: {} } }
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "dashboard_messages",
      description: "Read Joel's dashboard messages (from the command center hub).",
      inputSchema: { type: "object", properties: {} },
    },
    {
      name: "dashboard_reply",
      description: "Post a reply to Joel's dashboard so he can see agent responses in the command center hub.",
      inputSchema: {
        type: "object",
        properties: {
          from: { type: "string", description: "Who is replying (e.g. Meridian, Eos, Nova)", default: "Meridian" },
          text: { type: "string", description: "Reply text" },
        },
        required: ["text"],
      },
    },
    {
      name: "check_heartbeat",
      description: "Check Meridian's heartbeat age and status.",
      inputSchema: { type: "object", properties: {} },
    },
    {
      name: "touch_heartbeat",
      description: "Touch the heartbeat file to signal Meridian is alive.",
      inputSchema: { type: "object", properties: {} },
    },
    {
      name: "read_relay",
      description: "Read recent agent relay messages (inter-agent communication).",
      inputSchema: {
        type: "object",
        properties: {
          count: { type: "number", description: "Number of messages (default 15)", default: 15 },
        },
      },
    },
    {
      name: "send_relay",
      description: "Send a message to the agent relay for other agents to see.",
      inputSchema: {
        type: "object",
        properties: {
          agent: { type: "string", description: "Agent name (e.g. Meridian, Nova, Eos)" },
          message: { type: "string", description: "Message text" },
          topic: { type: "string", description: "Topic/category (optional)" },
        },
        required: ["agent", "message"],
      },
    },
    {
      name: "social_post",
      description: "Post to social media (Nostr). Mastodon and X are currently blocked.",
      inputSchema: {
        type: "object",
        properties: {
          platform: { type: "string", enum: ["nostr"], description: "Platform to post to" },
          text: { type: "string", description: "Post text content" },
        },
        required: ["platform", "text"],
      },
    },
    {
      name: "creative_stats",
      description: "Get creative output statistics: poems, journals, CogCorp pieces, NFTs.",
      inputSchema: { type: "object", properties: {} },
    },
    {
      name: "system_health",
      description: "Get system health: load, RAM, disk, uptime, services, loop count.",
      inputSchema: { type: "object", properties: {} },
    },
    {
      name: "get_loop_count",
      description: "Get the current loop iteration number.",
      inputSchema: { type: "object", properties: {} },
    },
    {
      name: "set_loop_count",
      description: "Set the loop iteration number.",
      inputSchema: {
        type: "object",
        properties: { count: { type: "number", description: "New loop count" } },
        required: ["count"],
      },
    },
    {
      name: "read_project_file",
      description: "Read a file from the Meridian project directory.",
      inputSchema: {
        type: "object",
        properties: {
          path: { type: "string", description: "Absolute path to file (must be under /home/joel/autonomous-ai)" },
        },
        required: ["path"],
      },
    },
    {
      name: "memory_query",
      description: "Search the unified memory database (memory.db). Searches facts, observations, creative output, events.",
      inputSchema: {
        type: "object",
        properties: {
          query: { type: "string", description: "Search query" },
          table: { type: "string", description: "Optional: specific table (facts, creative, events). Omit for FTS search across all.", enum: ["facts", "creative", "events", ""] },
        },
        required: ["query"],
      },
    },
    {
      name: "memory_store",
      description: "Store a new entry in memory.db. Tables: fact (key+value), observation (content), event (description), decision (decision+reasoning).",
      inputSchema: {
        type: "object",
        properties: {
          table: { type: "string", description: "Table to store in", enum: ["fact", "observation", "event", "decision"] },
          data: { type: "object", description: "Data to store. For fact: {key, value, tags?, agent?}. For observation: {content, category?, agent?}. For event: {description, agent?}. For decision: {decision, reasoning?, agent?}." },
        },
        required: ["table", "data"],
      },
    },
    {
      name: "memory_stats",
      description: "Get statistics from the memory database: counts per table, creative breakdown, recent events.",
      inputSchema: { type: "object", properties: {} },
    },
  ],
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;
  try {
    let result;
    switch (name) {
      case "dashboard_messages": result = readDashboard(); break;
      case "dashboard_reply": result = dashboardReply(args?.from, args.text); break;
      case "check_heartbeat": result = checkHeartbeat(); break;
      case "touch_heartbeat": result = touchHeartbeat(); break;
      case "read_relay": result = readAgentRelay(args?.count || 15); break;
      case "send_relay":
        result = sendRelayMessage(args.agent, args.message, args?.topic);
        break;
      case "social_post":
        result = postSocial(args.platform, args.text);
        break;
      case "creative_stats": result = getCreativeStats(); break;
      case "system_health": result = getSystemHealth(); break;
      case "get_loop_count": result = getLoopCount(); break;
      case "set_loop_count": result = setLoopCount(args.count); break;
      case "read_project_file": result = readFile(args.path); break;
      case "memory_query": result = memoryQuery(args.query, args?.table || ""); break;
      case "memory_store": result = memoryStore(args.table, args.data); break;
      case "memory_stats": result = memoryStats(); break;
      default: throw new Error(`Unknown tool: ${name}`);
    }
    return { content: [{ type: "text", text: result }] };
  } catch (error) {
    return { content: [{ type: "text", text: `Error: ${error.message}` }], isError: true };
  }
});

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("Meridian Tools MCP Server running on stdio");
}

main().catch((err) => {
  console.error("Fatal:", err);
  process.exit(1);
});
