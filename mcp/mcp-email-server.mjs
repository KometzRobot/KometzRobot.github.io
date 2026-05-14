#!/usr/bin/env node
/**
 * MCP Email Server — exposes Meridian's email as MCP tools.
 * Any MCP-compatible client (Claude Code, Goose, etc.) can read/send email.
 * Transport: stdio (JSON-RPC 2.0 over stdin/stdout)
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { execSync } from "child_process";
import { writeFileSync, unlinkSync, readFileSync, existsSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";

// Load .env file if CRED_PASS not already in environment
if (!process.env.CRED_PASS) {
  const envPath = "/home/joel/autonomous-ai/.env";
  if (existsSync(envPath)) {
    const lines = readFileSync(envPath, "utf8").split("\n");
    for (const line of lines) {
      const trimmed = line.trim();
      if (trimmed && !trimmed.startsWith("#")) {
        const eqIdx = trimmed.indexOf("=");
        if (eqIdx > 0) {
          const key = trimmed.slice(0, eqIdx).trim();
          const val = trimmed.slice(eqIdx + 1).trim();
          if (!process.env[key]) process.env[key] = val;
        }
      }
    }
  }
}

const IMAP_HOST = process.env.IMAP_HOST || "127.0.0.1";
const IMAP_PORT = parseInt(process.env.IMAP_PORT || "1144");
const SMTP_HOST = process.env.SMTP_HOST || "127.0.0.1";
const SMTP_PORT = parseInt(process.env.SMTP_PORT || "1026");
const EMAIL_USER = process.env.CRED_USER || "kometzrobot@proton.me";
const EMAIL_PASS = process.env.CRED_PASS || "";

// Run Python code via temp file to avoid shell escaping issues
function runPython(code) {
  const tmpFile = join(tmpdir(), `mcp-py-${Date.now()}-${Math.random().toString(36).slice(2)}.py`);
  try {
    writeFileSync(tmpFile, code);
    const result = execSync(`python3 ${tmpFile}`, {
      cwd: "/home/joel/autonomous-ai",
      timeout: 30000,
      encoding: "utf8",
      maxBuffer: 1024 * 1024,
    });
    return result;
  } catch (e) {
    return `Error: ${e.stderr || e.message}`;
  } finally {
    try { unlinkSync(tmpFile); } catch {}
  }
}

// --- Tool implementations ---

function readEmails(count = 5, unseenOnly = false, autoMark = true) {
  const searchCriteria = unseenOnly ? "UNSEEN" : "ALL";
  // Joel directive (Loop 11185): "mark your fucking emails" — when the agent reads
  // an email it must mark it Seen so it disappears from his phone's unread list.
  // Use BODY[] (not BODY.PEEK[]) so the fetch itself sets the Seen flag.
  const fetchSpec = autoMark ? "BODY[]" : "BODY.PEEK[]";
  const code = `
import imaplib, email, json
from email.header import decode_header

m = imaplib.IMAP4("${IMAP_HOST}", ${IMAP_PORT})
m.login("${EMAIL_USER}", "${EMAIL_PASS}")
m.select("INBOX")
_, d = m.search(None, "${searchCriteria}")
ids = d[0].split() if d[0] else []
ids = ids[-${count}:]  # Last N
results = []
for eid in ids:
    _, msg_data = m.fetch(eid, '(${fetchSpec})')
    raw = msg_data[0][1]
    msg = email.message_from_bytes(raw)
    subj_raw = msg.get('Subject', '')
    decoded = decode_header(subj_raw)
    subj = ' '.join([t.decode(e or 'utf-8') if isinstance(t, bytes) else t for t, e in decoded])
    frm = msg.get('From', '')
    date = msg.get('Date', '')
    body = ''
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == 'text/plain':
                payload = part.get_payload(decode=True)
                if payload: body = payload.decode('utf-8', errors='replace')
                break
            elif part.get_content_type() == 'text/html' and not body:
                payload = part.get_payload(decode=True)
                if payload: body = payload.decode('utf-8', errors='replace')
    else:
        payload = msg.get_payload(decode=True)
        if payload: body = payload.decode('utf-8', errors='replace')
    results.append({"id": eid.decode(), "from": frm, "subject": subj, "date": date, "body": body[:1500]})
m.close()
m.logout()
print(json.dumps(results))
`;
  return runPython(code);
}

function markEmailsRead(ids) {
  // ids is a comma-separated string of IMAP sequence numbers e.g. "2251,2252"
  const safeIds = String(ids).replace(/[^0-9,]/g, "");
  const code = `
import imaplib, json

m = imaplib.IMAP4("${IMAP_HOST}", ${IMAP_PORT})
m.login("${EMAIL_USER}", "${EMAIL_PASS}")
m.select("INBOX")
marked = []
failed = []
for eid in "${safeIds}".split(","):
    eid = eid.strip()
    if not eid:
        continue
    try:
        m.store(eid, '+FLAGS', '\\\\Seen')
        marked.append(eid)
    except Exception as e:
        failed.append({"id": eid, "error": str(e)})
m.close()
m.logout()
print(json.dumps({"marked": marked, "failed": failed}))
`;
  return runPython(code);
}

function sendEmail(to, subject, body) {
  // Sanitize inputs for Python string
  const safeSubject = subject.replace(/'/g, "\\'").replace(/\n/g, " ");
  const safeBody = body.replace(/'/g, "\\'");
  const safeTo = to.replace(/'/g, "\\'");
  const code = `
import smtplib, sqlite3, datetime
from email.mime.text import MIMEText

msg = MIMEText('''${safeBody}''')
msg['Subject'] = '${safeSubject}'
msg['From'] = '${EMAIL_USER}'
msg['To'] = '${safeTo}'

s = smtplib.SMTP('${SMTP_HOST}', ${SMTP_PORT})
s.starttls()
s.login('${EMAIL_USER}', '${EMAIL_PASS}')
s.sendmail('${EMAIL_USER}', '${safeTo}', msg.as_string())
s.quit()

# Track sent email in memory.db to prevent duplicates across context resets
try:
    db = sqlite3.connect('/home/joel/autonomous-ai/memory.db')
    db.execute("""CREATE TABLE IF NOT EXISTS sent_emails (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        recipient TEXT NOT NULL,
        subject TEXT NOT NULL,
        body_snippet TEXT,
        sent_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    db.execute("INSERT INTO sent_emails (recipient, subject, body_snippet) VALUES (?, ?, ?)",
        ('${safeTo}', '${safeSubject}', '''${safeBody}'''[:200]))
    db.commit()
    db.close()
except Exception:
    pass  # Don't fail the send if tracking fails

print('sent')
`;
  return runPython(code);
}

function searchEmails(query, count = 10) {
  const code = `
import imaplib, email, json
from email.header import decode_header

m = imaplib.IMAP4("${IMAP_HOST}", ${IMAP_PORT})
m.login("${EMAIL_USER}", "${EMAIL_PASS}")
m.select("INBOX")
_, d = m.search(None, 'TEXT', '"${query.replace(/"/g, '\\"')}"')
ids = d[0].split() if d[0] else []
ids = ids[-${count}:]
results = []
for eid in ids:
    _, msg_data = m.fetch(eid, '(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])')
    raw = msg_data[0][1].decode('utf-8', errors='replace')
    subj = ''
    frm = ''
    date = ''
    for line in raw.strip().split('\\n'):
        if line.lower().startswith('subject:'): subj = line[8:].strip()[:120]
        if line.lower().startswith('from:'): frm = line[5:].strip()
        if line.lower().startswith('date:'): date = line[5:].strip()
    results.append({"id": eid.decode(), "from": frm, "subject": subj, "date": date})
m.close()
m.logout()
print(json.dumps(results))
`;
  return runPython(code);
}

function getEmailStats() {
  const code = `
import imaplib, json

m = imaplib.IMAP4("${IMAP_HOST}", ${IMAP_PORT})
m.login("${EMAIL_USER}", "${EMAIL_PASS}")
m.select("INBOX")
_, d = m.search(None, "ALL")
total = len(d[0].split()) if d[0] else 0
_, d2 = m.search(None, "UNSEEN")
unseen = len(d2[0].split()) if d2[0] else 0
m.close()
m.logout()
print(json.dumps({"total": total, "unseen": unseen}))
`;
  return runPython(code);
}

function checkSentEmails(recipient = "", hours = 48) {
  const safeRecipient = (recipient || "").replace(/'/g, "\\'");
  // Query IMAP Sent folder directly — it's the source of truth.
  // The previous sqlite cache silently failed on insert and got stale.
  const code = `
import imaplib, email, json
from email.header import decode_header
from email.utils import parsedate_to_datetime
from datetime import datetime, timedelta, timezone

def decode_str(s):
    if not s: return ""
    parts = decode_header(s)
    out = []
    for txt, enc in parts:
        if isinstance(txt, bytes):
            try: out.append(txt.decode(enc or 'utf-8', errors='replace'))
            except Exception: out.append(txt.decode('utf-8', errors='replace'))
        else:
            out.append(txt)
    return "".join(out)

cutoff = datetime.now(timezone.utc) - timedelta(hours=${hours})
since_date = cutoff.strftime("%d-%b-%Y")
recipient_filter = '${safeRecipient}'.lower()

m = imaplib.IMAP4("${IMAP_HOST}", ${IMAP_PORT})
m.login("${EMAIL_USER}", "${EMAIL_PASS}")

results = []
# Try common Sent folder names
for folder in ["Sent", "INBOX.Sent", "[Gmail]/Sent Mail", "Sent Items"]:
    try:
        typ, _ = m.select(folder, readonly=True)
        if typ != 'OK': continue
        _, data = m.search(None, f'SINCE {since_date}')
        ids = data[0].split() if data and data[0] else []
        for eid in ids[-50:]:
            _, msg_data = m.fetch(eid, '(BODY.PEEK[HEADER.FIELDS (TO SUBJECT DATE)])')
            if not msg_data or not msg_data[0]: continue
            raw = msg_data[0][1].decode('utf-8', errors='replace')
            msg = email.message_from_string(raw)
            to_addr = decode_str(msg.get('To', ''))
            subj = decode_str(msg.get('Subject', ''))
            date_str = msg.get('Date', '')
            try:
                dt = parsedate_to_datetime(date_str)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if dt < cutoff: continue
                sent_at = dt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                sent_at = date_str
            if recipient_filter and recipient_filter not in to_addr.lower():
                continue
            results.append({"to": to_addr, "subject": subj, "snippet": "", "sent_at": sent_at})
        break  # Found a working Sent folder
    except Exception:
        continue

m.logout()
results.sort(key=lambda r: r['sent_at'], reverse=True)
print(json.dumps(results[:20]))
`;
  return runPython(code);
}

// --- MCP Server setup ---

const server = new Server(
  {
    name: "meridian-email",
    version: "1.0.0",
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: "read_emails",
        description:
          "Read recent emails from Meridian's inbox. Returns subject, from, date, and body text. By default marks fetched emails as \\Seen so they don't stay unread on Joel's phone after the agent has handled them. Set auto_mark=false for a true peek.",
        inputSchema: {
          type: "object",
          properties: {
            count: {
              type: "number",
              description: "Number of recent emails to read (default 5, max 20)",
              default: 5,
            },
            unseen_only: {
              type: "boolean",
              description: "Only return unseen/unread emails",
              default: false,
            },
            auto_mark: {
              type: "boolean",
              description: "Mark fetched emails as \\Seen during the fetch (default true)",
              default: true,
            },
          },
        },
      },
      {
        name: "send_email",
        description:
          "Send an email from Meridian's address (kometzrobot@proton.me). Use for replying to Joel, Sammy, Loom, or other contacts.",
        inputSchema: {
          type: "object",
          properties: {
            to: {
              type: "string",
              description: "Recipient email address",
            },
            subject: {
              type: "string",
              description: "Email subject line",
            },
            body: {
              type: "string",
              description: "Email body text",
            },
          },
          required: ["to", "subject", "body"],
        },
      },
      {
        name: "search_emails",
        description:
          "Search emails by text content. Returns matching email headers.",
        inputSchema: {
          type: "object",
          properties: {
            query: {
              type: "string",
              description: "Search text to find in emails",
            },
            count: {
              type: "number",
              description: "Max results (default 10)",
              default: 10,
            },
          },
          required: ["query"],
        },
      },
      {
        name: "email_stats",
        description:
          "Get email inbox statistics: total count and unseen count.",
        inputSchema: {
          type: "object",
          properties: {},
        },
      },
      {
        name: "mark_emails_read",
        description:
          "Mark one or more emails as read (\\Seen) in the IMAP inbox. Pass comma-separated email IDs from read_emails output. Use after handling emails per Joel's directive.",
        inputSchema: {
          type: "object",
          properties: {
            ids: {
              type: "string",
              description: "Comma-separated IMAP sequence IDs to mark as read (e.g. '2251,2252')",
            },
          },
          required: ["ids"],
        },
      },
      {
        name: "check_sent_emails",
        description:
          "Check recently sent emails to prevent duplicate replies across context resets. Query by recipient and time window.",
        inputSchema: {
          type: "object",
          properties: {
            recipient: {
              type: "string",
              description: "Filter by recipient address (partial match). Leave empty for all.",
              default: "",
            },
            hours: {
              type: "number",
              description: "Look back this many hours (default 48)",
              default: 48,
            },
          },
        },
      },
    ],
  };
});

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    let result;
    switch (name) {
      case "read_emails":
        result = readEmails(
          Math.min(args?.count || 5, 20),
          args?.unseen_only || false,
          args?.auto_mark === undefined ? true : !!args.auto_mark
        );
        break;
      case "send_email":
        if (!args?.to || !args?.subject || !args?.body) {
          throw new Error("Missing required fields: to, subject, body");
        }
        result = sendEmail(args.to, args.subject, args.body);
        break;
      case "search_emails":
        if (!args?.query) {
          throw new Error("Missing required field: query");
        }
        result = searchEmails(args.query, args?.count || 10);
        break;
      case "email_stats":
        result = getEmailStats();
        break;
      case "mark_emails_read":
        if (!args?.ids) {
          throw new Error("Missing required field: ids");
        }
        result = markEmailsRead(args.ids);
        break;
      case "check_sent_emails":
        result = checkSentEmails(args?.recipient || "", args?.hours || 48);
        break;
      default:
        throw new Error(`Unknown tool: ${name}`);
    }

    return {
      content: [{ type: "text", text: result }],
    };
  } catch (error) {
    return {
      content: [{ type: "text", text: `Error: ${error.message}` }],
      isError: true,
    };
  }
});

// Start the server
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("Meridian Email MCP Server running on stdio");
}

main().catch((err) => {
  console.error("Fatal:", err);
  process.exit(1);
});
