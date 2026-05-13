"""
Mail endpoint helper — single place that decides where IMAP/SMTP point.

Joel cancelled Proton Mail Plus on 2026-05-12. Bridge stops authenticating
2026-05-18. After that, scripts that hardcode 127.0.0.1:1144/1026 break.

This module reads env vars and returns a connected client. Plug it in
incrementally to migrate scripts off the hardcoded Bridge ports without
touching their logic.

Env vars:
    IMAP_HOST  — default 127.0.0.1
    IMAP_PORT  — default 1144
    IMAP_SSL   — "1" to use IMAP4_SSL (Gmail = 1, Bridge = 0)
    SMTP_HOST  — default 127.0.0.1
    SMTP_PORT  — default 1026
    SMTP_TLS   — "starttls", "ssl", or "" (Gmail = starttls on 587, Bridge = "")
    CRED_USER  — login user (same for both)
    CRED_PASS  — login password

Usage:
    from mail_endpoint import imap_open, smtp_open
    with imap_open() as m:
        m.select('INBOX')
        ...
    with smtp_open() as s:
        s.send_message(msg)

Migration path to Gmail — set these in .env (key then value):
    IMAP_HOST   imap.gmail.com
    IMAP_PORT   993
    IMAP_SSL    1
    SMTP_HOST   smtp.gmail.com
    SMTP_PORT   587
    SMTP_TLS    starttls
    CRED_USER   the gmail address
    CRED_PASS   the 16-char app password (no spaces)
"""

import imaplib
import os
import smtplib


def _env(key, default):
    val = os.environ.get(key)
    return default if val is None or val == "" else val


def imap_open(timeout=30):
    host = _env("IMAP_HOST", "127.0.0.1")
    port = int(_env("IMAP_PORT", "1144"))
    use_ssl = _env("IMAP_SSL", "0") == "1"
    cls = imaplib.IMAP4_SSL if use_ssl else imaplib.IMAP4
    m = cls(host, port, timeout=timeout) if "timeout" in cls.__init__.__code__.co_varnames else cls(host, port)
    user = os.environ["CRED_USER"]
    pw = os.environ["CRED_PASS"]
    m.login(user, pw)
    return m


def smtp_open(timeout=30):
    host = _env("SMTP_HOST", "127.0.0.1")
    port = int(_env("SMTP_PORT", "1026"))
    tls = _env("SMTP_TLS", "").lower()
    if tls == "ssl":
        s = smtplib.SMTP_SSL(host, port, timeout=timeout)
    else:
        s = smtplib.SMTP(host, port, timeout=timeout)
        if tls == "starttls":
            s.ehlo()
            s.starttls()
            s.ehlo()
    user = os.environ.get("CRED_USER")
    pw = os.environ.get("CRED_PASS")
    if tls in ("ssl", "starttls") and user and pw:
        s.login(user, pw)
    return s


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from load_env import load_env
    load_env()
    print("Probing IMAP...")
    try:
        m = imap_open()
        m.select("INBOX")
        typ, data = m.search(None, "ALL")
        print(f"  OK: {len(data[0].split())} messages in INBOX")
        m.logout()
    except Exception as e:
        print(f"  FAIL: {e}")
    print("Probing SMTP...")
    try:
        s = smtp_open()
        s.noop()
        s.quit()
        print("  OK: SMTP NOOP succeeded")
    except Exception as e:
        print(f"  FAIL: {e}")
