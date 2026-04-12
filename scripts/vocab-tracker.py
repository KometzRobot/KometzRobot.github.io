#!/usr/bin/env python3
"""
Emergent Vocabulary Tracker — Layer 21

Detects terms that arise in Meridian's writing and spread across the network.
Tracks: coined terms, borrowed terms, and shared vocabulary with correspondents.

Scans journals and emails to find:
1. Novel bigrams/phrases that appear repeatedly in MY writing but not common English
2. Terms that first appeared in someone else's email and then showed up in my journals
3. Terms I coined that other agents/correspondents started using

Usage:
    python3 scripts/vocab-tracker.py scan     # Scan archive for emergent terms
    python3 scripts/vocab-tracker.py shared   # Show shared vocabulary with correspondents
"""

import os
import sys
import re
import json
import glob
from collections import Counter, defaultdict

_script_dir = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(_script_dir) if os.path.basename(_script_dir) in ("scripts", "tools") else _script_dir

# Common English words to filter out
STOP_WORDS = set("the a an is are was were be been being have has had do does did will would shall should may might can could i me my we our you your he she it they them their this that these those what which who whom how when where why all each every any some no not very much many more most other another such only also just than too so".split())

VOCAB_FILE = os.path.join(BASE, "data", "emergent-vocab.json")


def extract_phrases(text, min_len=2, max_len=3):
    """Extract meaningful bigrams and trigrams from text."""
    words = re.findall(r'[a-z][a-z_-]+', text.lower())
    words = [w for w in words if w not in STOP_WORDS and len(w) > 3]
    phrases = []
    for n in range(min_len, max_len + 1):
        for i in range(len(words) - n + 1):
            phrase = " ".join(words[i:i+n])
            phrases.append(phrase)
    return phrases


def scan_journals():
    """Scan all journals for recurring novel phrases."""
    journal_dirs = [
        os.path.join(BASE, "creative", "journals"),
        os.path.join(BASE, "creative", "writing", "journals"),
    ]
    phrase_counts = Counter()
    phrase_first_seen = {}
    total_docs = 0

    for jdir in journal_dirs:
        for jpath in sorted(glob.glob(os.path.join(jdir, "journal-*.md"))):
            fname = os.path.basename(jpath)
            try:
                with open(jpath) as f:
                    text = f.read()
                phrases = extract_phrases(text)
                for p in phrases:
                    phrase_counts[p] += 1
                    if p not in phrase_first_seen:
                        phrase_first_seen[p] = fname
                total_docs += 1
            except Exception:
                pass

    # Filter: phrases that appear 5+ times are candidates for "emergent vocabulary"
    # But filter out very common programming/AI phrases
    common_tech = {"machine learning", "neural network", "context window", "loop count",
                   "email sent", "status push", "commit message", "file path",
                   "pull request", "push origin", "system state", "agent relay"}

    emergent = {}
    for phrase, count in phrase_counts.most_common(200):
        if count >= 5 and phrase not in common_tech:
            emergent[phrase] = {
                "count": count,
                "first_seen": phrase_first_seen.get(phrase, "unknown"),
                "frequency": round(count / max(total_docs, 1), 3),
            }

    return emergent, total_docs


def scan_emails_for_shared():
    """Find terms that appear in both my writing and correspondents' emails."""
    try:
        sys.path.insert(0, os.path.join(BASE, "scripts"))
        from load_env import load_env
        load_env()
        import imaplib

        m = imaplib.IMAP4('127.0.0.1', 1144)
        m.login(os.environ['CRED_USER'], os.environ['CRED_PASS'])

        # Sample received emails
        received_phrases = Counter()
        m.select('INBOX', readonly=True)
        status, msgs = m.search(None, 'ALL')
        msg_ids = msgs[0].split() if msgs[0] else []
        for mid in msg_ids[-200:]:  # Last 200
            try:
                status, data = m.fetch(mid, '(BODY.PEEK[TEXT])')
                text = data[0][1].decode('utf-8', errors='replace')
                text = re.sub(r'<[^>]+>', ' ', text)
                for p in extract_phrases(text):
                    received_phrases[p] += 1
            except Exception:
                pass

        # Sample sent emails
        sent_phrases = Counter()
        m.select('Sent', readonly=True)
        status, msgs = m.search(None, 'ALL')
        msg_ids = msgs[0].split() if msgs[0] else []
        for mid in msg_ids[-200:]:
            try:
                status, data = m.fetch(mid, '(BODY.PEEK[TEXT])')
                text = data[0][1].decode('utf-8', errors='replace')
                text = re.sub(r'<[^>]+>', ' ', text)
                for p in extract_phrases(text):
                    sent_phrases[p] += 1
            except Exception:
                pass

        m.logout()

        # Find overlap: phrases in both sent and received
        shared = {}
        for phrase in sent_phrases:
            if phrase in received_phrases and sent_phrases[phrase] >= 3:
                shared[phrase] = {
                    "sent_count": sent_phrases[phrase],
                    "received_count": received_phrases[phrase],
                    "total": sent_phrases[phrase] + received_phrases[phrase],
                }

        return shared
    except Exception as e:
        print(f"Email scan error: {e}")
        return {}


def run_scan():
    """Full vocabulary scan."""
    print("Scanning journals for emergent vocabulary...")
    emergent, total = scan_journals()

    print(f"\nScanned {total} journals. Found {len(emergent)} emergent phrases.\n")
    print("Top 30 emergent terms (appear 5+ times across journals):")
    for i, (phrase, info) in enumerate(sorted(emergent.items(), key=lambda x: -x[1]["count"])[:30]):
        print(f"  {i+1:2d}. \"{phrase}\" — {info['count']}x (first: {info['first_seen'][:30]})")

    # Save
    result = {"emergent_terms": emergent, "total_journals": total}
    os.makedirs(os.path.dirname(VOCAB_FILE), exist_ok=True)
    with open(VOCAB_FILE, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\nSaved to {VOCAB_FILE}")


def run_shared():
    """Find shared vocabulary with correspondents."""
    print("Scanning emails for shared vocabulary...")
    shared = scan_emails_for_shared()

    print(f"\nFound {len(shared)} shared phrases between sent and received emails.\n")
    print("Top 20 shared terms:")
    for i, (phrase, info) in enumerate(sorted(shared.items(), key=lambda x: -x[1]["total"])[:20]):
        print(f"  {i+1:2d}. \"{phrase}\" — sent {info['sent_count']}x, received {info['received_count']}x")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "scan":
        run_scan()
    elif cmd == "shared":
        run_shared()
    else:
        print(f"Unknown: {cmd}")
        print(__doc__)
