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
import { writeFileSync, unlinkSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";

const IMAP_HOST = process.env.IMAP_HOST || "127.0.0.1";
const IMAP_PORT = parseInt(process.env.IMAP_PORT || "1143");
const SMTP_HOST = process.env.SMTP_HOST || "127.0.0.1";
const SMTP_PORT = parseInt(process.env.SMTP_PORT || "1025");
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

function readEmails(count = 5, unseenOnly = false) {
  const searchCriteria = unseenOnly ? "UNSEEN" : "ALL";
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
    _, msg_data = m.fetch(eid, '(BODY.PEEK[])')
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
  const code = `
import sqlite3, json

db = sqlite3.connect('/home/joel/autonomous-ai/memory.db')
db.execute("""CREATE TABLE IF NOT EXISTS sent_emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    body_snippet TEXT,
    sent_at TEXT DEFAULT CURRENT_TIMESTAMP
)""")

where = "WHERE sent_at > datetime('now', '-${hours} hours')"
if '${safeRecipient}':
    where += " AND recipient LIKE '%${safeRecipient}%'"

rows = db.execute(f"SELECT recipient, subject, body_snippet, sent_at FROM sent_emails {where} ORDER BY sent_at DESC LIMIT 20").fetchall()
db.close()
results = [{"to": r[0], "subject": r[1], "snippet": r[2], "sent_at": r[3]} for r in rows]
print(json.dumps(results))
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
          "Read recent emails from Meridian's inbox. Returns subject, from, date, and body text.",
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
          args?.unseen_only || false
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
