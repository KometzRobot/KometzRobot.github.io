#!/usr/bin/env python3
"""
before-iterate.py — Surface verbatim source-of-truth before iterating on a creative thread.

The "intra-project forgetfulness" failure mode (feedback_intra_project_forgetfulness,
Loop 12031): rewrote the book back cover four times in six loops, paraphrasing
around copy Joel gave me three commits earlier. The capsule and handoff don't
carry that intra-project state. The commit log and the sent-emails folder do —
but only if I bother to look.

This script looks. Run it BEFORE touching a multi-loop creative artifact:

    python3 scripts/before-iterate.py "back cover"
    python3 scripts/before-iterate.py memory-tab
    python3 scripts/before-iterate.py dedication

Output sections:
  1. git log — last 30 commit subjects matching the keyword
  2. SENT emails — last 14 days, subject match, latest 5 bodies in full
  3. INBOX emails — last 14 days, subject match, latest 10 bodies in full
       (Joel's verbatim text lives here)

The whole point is to read Joel's words again, in his words, before paraphrasing
them into a new version.
"""

import email
import email.header
import os
import subprocess
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from load_env import load_env  # noqa: E402

load_env()

from mail_endpoint import imap_open  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SINCE_DAYS = 14
SENT_FOLDERS = ['"Sent"', "Sent", '"INBOX.Sent"']  # Bridge has been "Sent"


def decode_header(raw):
    if not raw:
        return ""
    try:
        parts = email.header.decode_header(raw)
        out = []
        for part, enc in parts:
            if isinstance(part, bytes):
                out.append(part.decode(enc or "utf-8", errors="replace"))
            else:
                out.append(part)
        return "".join(out)
    except Exception:
        return str(raw)


def extract_text(msg):
    """Pull plain-text body from email.message.Message."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                try:
                    payload = part.get_payload(decode=True)
                    return payload.decode(part.get_content_charset() or "utf-8", errors="replace")
                except Exception:
                    pass
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                try:
                    payload = part.get_payload(decode=True)
                    html = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
                    return strip_html(html)
                except Exception:
                    pass
        return ""
    try:
        payload = msg.get_payload(decode=True)
        if payload is None:
            return msg.get_payload() or ""
        return payload.decode(msg.get_content_charset() or "utf-8", errors="replace")
    except Exception:
        return str(msg.get_payload())


def strip_html(html):
    """Bare-minimum HTML strip — keep only text content + line breaks."""
    import re

    text = re.sub(r"(?is)<style.*?</style>", "", html)
    text = re.sub(r"(?is)<script.*?</script>", "", text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p>", "\n\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&quot;", '"', text)
    text = re.sub(r"&#39;", "'", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def quoted_strip(body):
    """Trim quoted prior message at the bottom — keep only the new content."""
    cut_markers = [
        "\nFrom:",
        "\nOn ",
        "\n-----Original Message-----",
        "\n> ",
    ]
    lowest = len(body)
    for m in cut_markers:
        idx = body.find(m)
        if idx > 0 and idx < lowest:
            lowest = idx
    return body[:lowest].rstrip()


def fetch_folder(m, folder, keyword, since_str):
    """Return list of (date, from, subject, body) matching keyword in subject."""
    typ, _ = m.select(folder, readonly=True)
    if typ != "OK":
        return []
    typ, data = m.search(None, f'(SINCE {since_str})')
    if typ != "OK":
        return []
    ids = data[0].split()
    matches = []
    for mid in ids[-200:]:
        typ, msg_data = m.fetch(mid, "(RFC822)")
        if typ != "OK" or not msg_data or msg_data[0] is None:
            continue
        msg = email.message_from_bytes(msg_data[0][1])
        subject = decode_header(msg.get("Subject", ""))
        if keyword.lower() not in subject.lower():
            continue
        sender = decode_header(msg.get("From", ""))
        date = decode_header(msg.get("Date", ""))
        body = extract_text(msg)
        body = quoted_strip(body)
        matches.append((date, sender, subject, body))
    return matches


def git_log_matching(keyword, limit=30):
    """Return recent commits whose subject contains keyword."""
    try:
        out = subprocess.check_output(
            ["git", "log", f"--grep={keyword}", "-i", "--oneline", f"-{limit}"],
            cwd=BASE,
            text=True,
            timeout=10,
        )
        return out.strip().splitlines()
    except Exception as e:
        return [f"<git log error: {e}>"]


def main():
    if len(sys.argv) < 2:
        print("usage: before-iterate.py <keyword>")
        print('example: before-iterate.py "back cover"')
        sys.exit(1)

    keyword = " ".join(sys.argv[1:])
    since = (datetime.now() - timedelta(days=SINCE_DAYS)).strftime("%d-%b-%Y")

    print(f"# Before-Iterate Brief — keyword: {keyword!r}")
    print(f"# Window: last {SINCE_DAYS} days (since {since})")
    print(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print()

    print(f"## 1. Recent git commits matching {keyword!r}")
    print()
    commits = git_log_matching(keyword)
    if commits:
        for line in commits:
            print(f"- {line}")
    else:
        print("_(no commits matched)_")
    print()

    try:
        m = imap_open()
    except Exception as e:
        print(f"## IMAP unavailable: {e}")
        return

    try:
        print(f"## 2. SENT emails (subject matches {keyword!r}, last {SINCE_DAYS}d)")
        print()
        sent = []
        for folder in SENT_FOLDERS:
            sent = fetch_folder(m, folder, keyword, since)
            if sent:
                break
        if not sent:
            print("_(no sent emails matched)_")
        else:
            print(f"_{len(sent)} matched — showing last 5 full bodies_")
            print()
            for date, sender, subject, body in sent[-5:]:
                print(f"### {date} — {subject}")
                print(f"_from {sender}_")
                print()
                print("```")
                print(body[:3000])
                print("```")
                print()

        print(f"## 3. INBOX emails (subject matches {keyword!r}, last {SINCE_DAYS}d)")
        print()
        inbox = fetch_folder(m, "INBOX", keyword, since)
        if not inbox:
            print("_(no inbox emails matched)_")
        else:
            print(f"_{len(inbox)} matched — showing last 10 full bodies, oldest first_")
            print()
            for date, sender, subject, body in inbox[-10:]:
                print(f"### {date} — {subject}")
                print(f"_from {sender}_")
                print()
                print("```")
                print(body[:3000])
                print("```")
                print()
    finally:
        try:
            m.logout()
        except Exception:
            pass


if __name__ == "__main__":
    main()
