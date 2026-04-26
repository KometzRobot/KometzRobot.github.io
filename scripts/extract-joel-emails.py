#!/usr/bin/env python3
"""Extract all emails from Joel (jkometz@hotmail.com) from IMAP and save to file."""

import sys
import os
import imaplib
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime
import re
import html

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from load_env import load_env
load_env()

IMAP_HOST = "127.0.0.1"
IMAP_PORT = 1144
USER = os.environ["CRED_USER"]
PASS = os.environ["CRED_PASS"]
SEARCH_FROM = "jkometz@hotmail.com"
OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs", "joel-all-emails-raw.txt")


def decode_header_value(raw):
    """Decode an email header value, handling encoded words."""
    if raw is None:
        return "(no subject)"
    parts = decode_header(raw)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return " ".join(decoded)


def strip_html(html_text):
    """Strip HTML tags and decode entities to get plain text."""
    # Remove style and script blocks
    text = re.sub(r'<style[^>]*>.*?</style>', '', html_text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
    # Replace <br> and <p> with newlines
    text = re.sub(r'<br\s*/?\s*>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</p>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</div>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</tr>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</li>', '\n', text, flags=re.IGNORECASE)
    # Remove all remaining tags
    text = re.sub(r'<[^>]+>', '', text)
    # Decode HTML entities
    text = html.unescape(text)
    # Collapse excessive blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def get_body(msg):
    """Extract the plain text body from an email message."""
    if msg.is_multipart():
        plain_parts = []
        html_parts = []
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", ""))
            if "attachment" in disposition:
                continue
            if content_type == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    plain_parts.append(payload.decode(charset, errors="replace"))
            elif content_type == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    html_parts.append(payload.decode(charset, errors="replace"))
        if plain_parts:
            return "\n".join(plain_parts)
        if html_parts:
            return strip_html("\n".join(html_parts))
        return "(no text body)"
    else:
        content_type = msg.get_content_type()
        payload = msg.get_payload(decode=True)
        if payload is None:
            return "(no text body)"
        charset = msg.get_content_charset() or "utf-8"
        text = payload.decode(charset, errors="replace")
        if content_type == "text/html":
            return strip_html(text)
        return text


def main():
    print(f"Connecting to IMAP {IMAP_HOST}:{IMAP_PORT}...")
    mail = imaplib.IMAP4(IMAP_HOST, IMAP_PORT)
    mail.starttls()
    mail.login(USER, PASS)
    print("Logged in successfully.")

    mail.select("INBOX", readonly=True)

    print(f"Searching for emails FROM {SEARCH_FROM}...")
    status, data = mail.search(None, f'(FROM "{SEARCH_FROM}")')
    if status != "OK":
        print(f"Search failed: {status}")
        mail.logout()
        return

    msg_ids = data[0].split()
    total = len(msg_ids)
    print(f"Found {total} emails from {SEARCH_FROM}.")

    if total == 0:
        mail.logout()
        return

    emails = []
    for i, msg_id in enumerate(msg_ids, 1):
        if i % 50 == 0 or i == 1:
            print(f"  Fetching {i}/{total}...")
        status, msg_data = mail.fetch(msg_id, "(BODY.PEEK[])")
        if status != "OK":
            print(f"  Failed to fetch message {msg_id}")
            continue

        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)

        subject = decode_header_value(msg.get("Subject"))
        date_str = msg.get("Date", "(no date)")
        try:
            dt = parsedate_to_datetime(date_str)
            date_formatted = dt.strftime("%Y-%m-%d %H:%M:%S %Z")
        except Exception:
            date_formatted = date_str

        body = get_body(msg)

        emails.append({
            "date": date_formatted,
            "subject": subject,
            "body": body,
        })

    mail.logout()
    print(f"Fetched {len(emails)} emails. Writing to {OUTPUT_FILE}...")

    # Sort by date (oldest first)
    emails.sort(key=lambda e: e["date"])

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(f"=== ALL EMAILS FROM {SEARCH_FROM} ===\n")
        f.write(f"=== Extracted: {total} emails ===\n")
        f.write(f"=== Generated by extract-joel-emails.py ===\n\n")

        for i, em in enumerate(emails, 1):
            f.write(f"{'='*80}\n")
            f.write(f"EMAIL #{i}\n")
            f.write(f"DATE: {em['date']}\n")
            f.write(f"SUBJECT: {em['subject']}\n")
            f.write(f"{'='*80}\n\n")
            f.write(em["body"])
            f.write(f"\n\n")

    print(f"\nDone! Extracted {len(emails)} emails to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
