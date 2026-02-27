#!/usr/bin/env python3
"""Quick email stats for The Signal terminal."""
import imaplib, json, os

try:
    import sys; sys.path.insert(0, "/home/joel/autonomous-ai"); import load_env
except:
    pass

CRED_FILE = os.path.join(os.path.dirname(__file__), "credentials.txt")

def get_creds():
    try:
        with open(CRED_FILE) as f:
            for line in f:
                if line.startswith("EMAIL_PASSWORD="):
                    return line.strip().split("=", 1)[1]
    except Exception:
        pass
    return os.environ.get("CRED_PASS", "")

try:
    m = imaplib.IMAP4("127.0.0.1", 1143)
    m.login(os.environ.get("CRED_USER", "kometzrobot@proton.me"), get_creds())
    m.select("INBOX")
    _, d = m.search(None, "ALL")
    total = len(d[0].split()) if d[0] else 0
    _, d2 = m.search(None, "UNSEEN")
    unseen = len(d2[0].split()) if d2[0] else 0
    m.close()
    m.logout()
    print(f"Total: {total} emails, Unread: {unseen}")
except Exception as e:
    print(f"Email check failed: {e}")
