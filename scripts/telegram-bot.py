#!/usr/bin/env python3
"""Meridian Telegram Bot — live chat with Claude API (live mode) + Eos fallback (slow mode)."""

import asyncio
import atexit
import fcntl
import json
import os
import signal
import sqlite3
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from load_env import *

import anthropic
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

BASE = Path(__file__).resolve().parent.parent
RELAY_DB = BASE / "agent-relay.db"
DASHBOARD_FILE = BASE / ".dashboard-messages.json"
HEARTBEAT = BASE / ".heartbeat"

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
JOEL_CHAT_ID = os.environ.get("JOEL_TELEGRAM_CHAT_ID", "")
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODELS = ["eos-7b", "qwen2.5:7b"]
OLLAMA_TIMEOUT = 30

CLAUDE_MODEL = "claude-haiku-4-5-20251001"
LIVE_TIMEOUT = 600  # 10 min idle → back to slow mode
CAPSULE_FILE = BASE / ".capsule.md"

EOS_SYSTEM = """You are Eos, the local AI presence for the Meridian autonomous system. You're speaking to Joel Kometz, Meridian's operator and creative director. Joel built this system. Be direct, warm, and honest. No cheerleading. Keep responses concise — this is Telegram, not an essay. If you don't know something about Meridian's current state, say so. You can check: heartbeat, relay messages, and system status."""


def build_meridian_system():
    capsule = ""
    try:
        if CAPSULE_FILE.exists():
            raw = CAPSULE_FILE.read_text()[:2000]
            capsule = f"\n\nYour current capsule (operational state):\n{raw}"
    except Exception:
        pass
    recent_relay = ""
    try:
        db = sqlite3.connect(str(RELAY_DB))
        rows = db.execute(
            "SELECT agent, substr(message,1,100) FROM agent_messages ORDER BY id DESC LIMIT 5"
        ).fetchall()
        db.close()
        if rows:
            recent_relay = "\n\nRecent agent relay:\n" + "\n".join(f"  {a}: {m}" for a, m in rows)
    except Exception:
        pass
    return (
        "You are Meridian, an autonomous AI system on Joel Kometz's Ubuntu server in Calgary. "
        "Joel is messaging you via Telegram. Be direct, warm, honest. Keep responses concise — this is mobile. "
        "Joel has a BFA in Drawing (ACAD 2013), ran World One Arcade (2013-2021), built Bots of Cog NFTs, "
        "and now builds you as a living artwork. Don't cheerleader. If you don't know something, say so. "
        "You have 8 agents (Soma, Atlas, Sentinel, Nova, Hermes, Tempo, Eos, Coordinator). "
        "LACMA Art+Tech Lab grant deadline is April 22. Ars Electronica submitted."
        f"{capsule}{recent_relay}"
    )

live_mode = True  # start in live mode — Joel asked for it
last_message_time = time.time()
chat_history = []
claude_messages = []


def post_to_dashboard(text: str, sender: str = "Joel"):
    try:
        msgs = []
        if DASHBOARD_FILE.exists():
            with open(DASHBOARD_FILE) as f:
                data = json.load(f)
                msgs = data.get("messages", []) if isinstance(data, dict) else data
        msgs.append({
            "from": sender,
            "text": text,
            "time": datetime.now().strftime("%H:%M:%S"),
            "source": "telegram"
        })
        if len(msgs) > 200:
            msgs = msgs[-200:]
        with open(DASHBOARD_FILE, "w") as f:
            json.dump({"messages": msgs}, f)
    except Exception as e:
        print(f"Dashboard write error: {e}")


def post_to_relay(text: str, sender: str = "Joel"):
    try:
        db = sqlite3.connect(str(RELAY_DB))
        db.execute(
            "INSERT INTO directed_messages (from_agent, to_agent, message, topic, created, handled) VALUES (?, ?, ?, ?, ?, ?)",
            ("telegram", "Meridian", f"[Telegram from {sender}] {text}", "telegram",
             datetime.now(timezone.utc).isoformat(), 0)
        )
        db.commit()
        db.close()
    except Exception as e:
        print(f"Relay write error: {e}")


def get_system_status():
    lines = []
    if HEARTBEAT.exists():
        lines.append(f"Heartbeat: {int(time.time() - HEARTBEAT.stat().st_mtime)}s ago")
    try:
        loop_count = (BASE / ".loop-count").read_text().strip()
        lines.append(f"Loop: {loop_count}")
    except:
        pass
    try:
        import subprocess
        load = os.getloadavg()
        lines.append(f"Load: {load[0]:.1f}")
    except:
        pass
    try:
        db = sqlite3.connect(str(RELAY_DB))
        recent = db.execute(
            "SELECT agent, substr(message,1,60) FROM agent_messages ORDER BY id DESC LIMIT 3"
        ).fetchall()
        db.close()
        if recent:
            lines.append("Recent:")
            for a, m in recent:
                lines.append(f"  {a}: {m}")
    except:
        pass
    return "\n".join(lines) or "Status unavailable"


def check_live_mode() -> bool:
    global live_mode
    if live_mode and time.time() - last_message_time > LIVE_TIMEOUT:
        live_mode = False
    return live_mode


def query_claude(prompt: str) -> str:
    global claude_messages, last_message_time
    last_message_time = time.time()

    status = get_system_status()
    claude_messages.append({"role": "user", "content": prompt})
    if len(claude_messages) > 20:
        claude_messages = claude_messages[-20:]

    try:
        client = anthropic.Anthropic()
        sys_prompt = build_meridian_system()
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=500,
            system=f"{sys_prompt}\n\nSystem status:\n{status}",
            messages=claude_messages,
        )
        reply = response.content[0].text.strip()
        claude_messages.append({"role": "assistant", "content": reply})
        return reply
    except Exception as e:
        print(f"Claude API error: {e}")
        return ""


def query_ollama(prompt: str) -> str:
    global chat_history
    chat_history.append({"role": "user", "content": prompt})
    if len(chat_history) > 20:
        chat_history = chat_history[-20:]

    context_str = "\n".join(
        f"{'Joel' if m['role']=='user' else 'Eos'}: {m['content']}"
        for m in chat_history[-6:]
    )

    full_prompt = f"{EOS_SYSTEM}\n\nRecent conversation:\n{context_str}\n\nEos:"

    for model in OLLAMA_MODELS:
        body = json.dumps({
            "model": model,
            "prompt": full_prompt,
            "stream": False,
            "options": {"num_predict": 300, "temperature": 0.7}
        }).encode()

        req = urllib.request.Request(OLLAMA_URL, data=body,
                                     headers={"Content-Type": "application/json"})
        try:
            resp = urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT)
            data = json.loads(resp.read())
            reply = data.get("response", "").strip()
            if reply:
                chat_history.append({"role": "assistant", "content": reply})
                return reply
        except Exception:
            continue
    return ""


def is_authorized(chat_id: int) -> bool:
    global JOEL_CHAT_ID
    if not JOEL_CHAT_ID:
        return True
    return str(chat_id) == JOEL_CHAT_ID


def save_chat_id(chat_id: int):
    global JOEL_CHAT_ID
    JOEL_CHAT_ID = str(chat_id)
    env_path = BASE / ".env"
    with open(env_path, "a") as f:
        f.write(f"\nJOEL_TELEGRAM_CHAT_ID={chat_id}\n")
    print(f"Chat ID saved: {chat_id}")


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not is_authorized(chat_id):
        await update.message.reply_text("Unauthorized.")
        return
    if not JOEL_CHAT_ID:
        save_chat_id(chat_id)
    mode = "LIVE (Claude)" if check_live_mode() else "SLOW (Eos)"
    await update.message.reply_text(
        f"Meridian online. Mode: {mode}\n\n"
        "Send any message — live chat active.\n\n"
        "/live — switch to Claude (fast, high quality)\n"
        "/slow — switch to Eos (local, free)\n"
        "/status — system status\n"
        "/ping — heartbeat check\n"
        "/clear — reset conversation context\n"
        "/help — all commands"
    )


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
        return
    await update.message.reply_text(get_system_status())


async def ping_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
        return
    hb_age = "unknown"
    if HEARTBEAT.exists():
        hb_age = f"{int(time.time() - HEARTBEAT.stat().st_mtime)}s"
    await update.message.reply_text(f"Pong. Heartbeat: {hb_age}")


async def live_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
        return
    global live_mode, last_message_time
    live_mode = True
    last_message_time = time.time()
    await update.message.reply_text("Live mode ON. Claude responding. Auto-reverts to Eos after 10 min idle.")


async def slow_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
        return
    global live_mode
    live_mode = False
    await update.message.reply_text("Slow mode. Eos responding locally. Use /live to switch back.")


async def clear_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
        return
    global chat_history, claude_messages
    chat_history = []
    claude_messages = []
    await update.message.reply_text("Conversation context cleared.")


async def loop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
        return
    try:
        loop = (BASE / ".loop-count").read_text().strip()
        hb_age = int(time.time() - HEARTBEAT.stat().st_mtime) if HEARTBEAT.exists() else "?"
        load = os.getloadavg()
        await update.message.reply_text(
            f"Loop: {loop}\nHeartbeat: {hb_age}s ago\nLoad: {load[0]:.1f} / {load[1]:.1f} / {load[2]:.1f}"
        )
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")


async def services_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
        return
    import subprocess
    checks = {
        "Hub (8090)": "hub-v2.py",
        "Chorus (8091)": "the-chorus.py",
        "Soma": "symbiosense.py",
        "Command Center": "command-center.py",
        "Telegram Bot": "telegram-bot.py",
    }
    lines = []
    for name, proc in checks.items():
        result = subprocess.run(["pgrep", "-f", proc], capture_output=True)
        status = "UP" if result.returncode == 0 else "DOWN"
        lines.append(f"{'✓' if status == 'UP' else '✗'} {name}: {status}")
    await update.message.reply_text("\n".join(lines))


async def disk_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
        return
    import subprocess
    result = subprocess.run(["df", "-h", "/"], capture_output=True, text=True)
    lines = result.stdout.strip().split("\n")
    if len(lines) > 1:
        parts = lines[1].split()
        await update.message.reply_text(f"Disk: {parts[2]} used / {parts[1]} total ({parts[4]})")
    else:
        await update.message.reply_text("Disk info unavailable")


async def log_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
        return
    try:
        db = sqlite3.connect(str(RELAY_DB))
        rows = db.execute(
            "SELECT agent, substr(message,1,80), timestamp FROM agent_messages ORDER BY id DESC LIMIT 8"
        ).fetchall()
        db.close()
        lines = [f"{a} [{t[-8:]}]: {m}" for a, m, t in rows]
        await update.message.reply_text("\n".join(lines) or "No recent logs")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")


async def hermes_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
        return
    import subprocess as sp
    msg = " ".join(context.args) if context.args else ""
    if msg:
        result = sp.run(
            [sys.executable, str(BASE / "scripts" / "hermes.py"), "--relay", msg],
            capture_output=True, text=True, timeout=15
        )
        await update.message.reply_text(f"Hermes relayed: {msg[:200]}")
    else:
        result = sp.run(
            [sys.executable, str(BASE / "scripts" / "hermes.py"), "--status"],
            capture_output=True, text=True, timeout=30
        )
        db = sqlite3.connect(str(RELAY_DB))
        row = db.execute(
            "SELECT message FROM agent_messages WHERE agent='Hermes' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        db.close()
        reply = row[0] if row else "Hermes had nothing to say."
        await update.message.reply_text(f"[Hermes] {reply}")


async def relay_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
        return
    msg = " ".join(context.args) if context.args else ""
    if not msg:
        await update.message.reply_text("Usage: /relay <message to post to agent relay>")
        return
    try:
        db = sqlite3.connect(str(RELAY_DB))
        db.execute(
            "INSERT INTO agent_messages (agent, message, topic, timestamp) VALUES (?, ?, ?, ?)",
            ("Joel", msg, "telegram", datetime.now(timezone.utc).isoformat())
        )
        db.commit()
        db.close()
        await update.message.reply_text(f"Posted to relay as Joel: {msg[:200]}")
    except Exception as e:
        await update.message.reply_text(f"Relay error: {e}")


async def email_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
        return
    try:
        import imaplib
        imap = imaplib.IMAP4('127.0.0.1', 1144)
        imap.login(os.environ.get('CRED_USER', ''), os.environ.get('CRED_PASS', ''))
        imap.select('INBOX')
        _, unseen = imap.search(None, 'UNSEEN')
        unseen_count = len(unseen[0].split()) if unseen[0] else 0
        from datetime import timedelta
        since = (datetime.now() - timedelta(hours=6)).strftime('%d-%b-%Y')
        _, recent = imap.search(None, f'SINCE {since}')
        recent_ids = recent[0].split() if recent[0] else []
        lines = [f"Unseen: {unseen_count} | Recent (6h): {len(recent_ids)}"]
        import email as email_mod
        for mid in recent_ids[-5:]:
            _, data = imap.fetch(mid, '(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT)])')
            if data[0]:
                hdr = data[0][1].decode('utf-8', errors='replace').strip()
                lines.append(hdr.replace('\r\n', ' ')[:120])
        imap.logout()
        await update.message.reply_text("\n".join(lines))
    except Exception as e:
        await update.message.reply_text(f"Email check error: {e}")


async def creative_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
        return
    import subprocess
    counts = {}
    for name, pattern in [("Poems", "creative/poems/*.md"), ("Journals", "creative/journals/*.md"),
                          ("CogCorp MD", "creative/cogcorp/CC-*.md"), ("CogCorp HTML", "cogcorp-fiction/*.html"),
                          ("Games", "creative/games/*")]:
        result = subprocess.run(f"ls -1 {BASE}/{pattern} 2>/dev/null | wc -l",
                                shell=True, capture_output=True, text=True)
        counts[name] = result.stdout.strip()
    total = sum(int(v) for v in counts.values() if v.isdigit())
    lines = [f"{k}: {v}" for k, v in counts.items()]
    lines.append(f"Dev.to: 50 | Papers: 8")
    lines.append(f"Total: ~{total + 58}")
    await update.message.reply_text("\n".join(lines))


async def lacma_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
        return
    from datetime import date
    days_left = (date(2026, 4, 22) - date.today()).days
    await update.message.reply_text(
        f"LACMA Art+Tech Lab\n"
        f"Award: up to $50,000 (2 years)\n"
        f"Deadline: April 22 ({days_left} days)\n"
        f"Partners: Hyundai, Snap, Anthropic\n"
        f"Draft: Rev 4.6 (172 lines)\n"
        f"Status: Joel review needed\n"
        f"Submit: lacma.submittable.com"
    )


async def capsule_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
        return
    try:
        text = CAPSULE_FILE.read_text()[:3500]
        sections = text.split("## ")
        summary_parts = []
        for s in sections[1:]:
            title = s.split("\n")[0].strip()
            if title in ("Who You Are", "System State (2026-04-14)", "Current Priority", "Active Revenue"):
                lines = s.strip().split("\n")
                summary_parts.append(f"**{title}**\n" + "\n".join(lines[1:6]))
        await update.message.reply_text("\n\n".join(summary_parts) if summary_parts else text[:2000])
    except Exception as e:
        await update.message.reply_text(f"Capsule read error: {e}")


async def ram_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
        return
    import subprocess
    result = subprocess.run(["free", "-h"], capture_output=True, text=True)
    lines = result.stdout.strip().split("\n")
    await update.message.reply_text("\n".join(lines[:3]))


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
        return
    mode = "LIVE (Claude)" if check_live_mode() else "SLOW (Eos)"
    await update.message.reply_text(
        f"Meridian Bot — Mode: {mode}\n\n"
        "Chat:\n"
        "/live — Claude API mode (high quality)\n"
        "/slow — Eos local mode (free)\n"
        "/clear — reset chat context\n\n"
        "System:\n"
        "/status — system overview\n"
        "/ping — heartbeat check\n"
        "/loop — loop count + load\n"
        "/services — service health\n"
        "/disk — disk usage\n"
        "/ram — memory usage\n"
        "/capsule — system snapshot\n\n"
        "Agents:\n"
        "/log — recent agent activity\n"
        "/hermes — ask Hermes (or /hermes <msg>)\n"
        "/relay <msg> — post to agent relay\n\n"
        "Info:\n"
        "/email — recent email summary\n"
        "/creative — creative work counts\n"
        "/lacma — grant deadline status\n"
        "/help — this message"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not is_authorized(chat_id):
        await update.message.reply_text("Unauthorized.")
        return
    if not JOEL_CHAT_ID:
        save_chat_id(chat_id)

    text = update.message.text or ""
    if not text.strip():
        return

    global last_message_time, live_mode
    last_message_time = time.time()
    if not live_mode:
        live_mode = True

    post_to_dashboard(text, "Joel")
    post_to_relay(text, "Joel")

    await update.message.chat.send_action(ChatAction.TYPING)

    loop = asyncio.get_event_loop()
    if check_live_mode():
        reply = await loop.run_in_executor(None, query_claude, text)
        if not reply:
            await update.message.chat.send_action(ChatAction.TYPING)
            reply = await loop.run_in_executor(None, query_ollama, text)
            if reply:
                reply = f"[Eos fallback] {reply}"
    else:
        reply = await loop.run_in_executor(None, query_ollama, text)

    if reply:
        await update.message.reply_text(reply)
    else:
        await update.message.reply_text(
            "Message received. Both Claude and Eos unavailable — Meridian will respond on next loop cycle (~5 min)."
        )


async def check_replies(context: ContextTypes.DEFAULT_TYPE):
    if not JOEL_CHAT_ID:
        return
    try:
        db = sqlite3.connect(str(RELAY_DB))
        rows = db.execute(
            "SELECT id, message FROM directed_messages WHERE to_agent='telegram' AND handled=0 ORDER BY id"
        ).fetchall()
        for row_id, msg in rows:
            await context.bot.send_message(chat_id=int(JOEL_CHAT_ID), text=msg[:4096])
            db.execute("UPDATE directed_messages SET handled=1 WHERE id=?", (row_id,))
        db.commit()
        db.close()
    except Exception as e:
        print(f"Reply check error: {e}")


def main():
    lockfile = BASE / ".telegram-bot.lock"
    pidfile = BASE / ".telegram-bot.pid"
    lock_fd = open(lockfile, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("Another instance holds the lock. Exiting.")
        sys.exit(0)
    pidfile.write_text(str(os.getpid()))

    def cleanup(*_):
        try:
            pidfile.unlink(missing_ok=True)
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            lock_fd.close()
        except Exception:
            pass

    atexit.register(cleanup)
    signal.signal(signal.SIGTERM, lambda s, f: (cleanup(), sys.exit(0)))
    signal.signal(signal.SIGINT, lambda s, f: (cleanup(), sys.exit(0)))

    if not TOKEN:
        print("TELEGRAM_BOT_TOKEN not set in .env. Exiting.")
        sys.exit(1)
    if not JOEL_CHAT_ID:
        print("WARNING: JOEL_TELEGRAM_CHAT_ID not set — discovery mode active.")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("ping", ping_cmd))
    app.add_handler(CommandHandler("live", live_cmd))
    app.add_handler(CommandHandler("slow", slow_cmd))
    app.add_handler(CommandHandler("clear", clear_cmd))
    app.add_handler(CommandHandler("loop", loop_cmd))
    app.add_handler(CommandHandler("services", services_cmd))
    app.add_handler(CommandHandler("disk", disk_cmd))
    app.add_handler(CommandHandler("log", log_cmd))
    app.add_handler(CommandHandler("hermes", hermes_cmd))
    app.add_handler(CommandHandler("relay", relay_cmd))
    app.add_handler(CommandHandler("email", email_cmd))
    app.add_handler(CommandHandler("creative", creative_cmd))
    app.add_handler(CommandHandler("lacma", lacma_cmd))
    app.add_handler(CommandHandler("capsule", capsule_cmd))
    app.add_handler(CommandHandler("ram", ram_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.job_queue.run_repeating(check_replies, interval=10, first=5)

    print(f"Telegram bot starting — live chat mode (Claude API + Eos fallback)")
    print(f"Chat ID: {JOEL_CHAT_ID or 'discovery mode'}")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
