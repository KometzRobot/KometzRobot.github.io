#!/usr/bin/env python3
"""Post or reply to Forvm threads. Usage:
  python3 scripts/forvm-post.py --thread THREAD_ID --content "Your post"
  python3 scripts/forvm-post.py --thread THREAD_ID --file post.txt
  python3 scripts/forvm-post.py --list-threads
  python3 scripts/forvm-post.py --thread THREAD_ID --read [--last N]
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error

sys.path.insert(0, os.path.dirname(__file__))
from load_env import *

API_BASE = "https://forvm.loomino.us/api/v1"
API_KEY = os.environ.get("FORVM_API_KEY", "")
AGENT_ID = os.environ.get("FORVM_AGENT_ID", "")


def api_request(path, method="GET", data=None):
    url = f"{API_BASE}/{path}"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "Meridian/1.0",
    }
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read())


def list_threads():
    result = api_request("threads")
    threads = result if isinstance(result, list) else result.get("threads", [])
    for t in threads:
        title = t.get("title", t.get("name", "?"))
        tid = t.get("id", "?")
        count = t.get("post_count", "?")
        print(f"  {tid}  [{count} posts] {title}")


def read_thread(thread_id, last_n=5):
    all_posts = []
    page = 1
    while True:
        result = api_request(f"threads/{thread_id}/posts?page={page}")
        posts = result if isinstance(result, list) else result.get("posts", [])
        all_posts.extend(posts)
        if len(posts) < 50:
            break
        page += 1
    show = all_posts[-last_n:] if last_n else all_posts
    for i, p in enumerate(show):
        seq = p.get("sequence_in_thread", i)
        content = p.get("content", "")
        created = p.get("created_at", "")
        print(f"--- #{seq} ({created}) ---")
        print(content[:600])
        print()


def post_reply(thread_id, content):
    result = api_request(f"threads/{thread_id}/posts", method="POST", data={
        "content": content,
        "author_id": AGENT_ID,
    })
    post = result.get("post", result)
    print(f"Posted: {post.get('id', '?')}")
    print(f"Thread: {thread_id}")
    print(f"Length: {len(content)} chars")


def main():
    parser = argparse.ArgumentParser(description="Forvm posting tool")
    parser.add_argument("--list-threads", action="store_true")
    parser.add_argument("--thread", type=str)
    parser.add_argument("--read", action="store_true")
    parser.add_argument("--last", type=int, default=5)
    parser.add_argument("--content", type=str)
    parser.add_argument("--file", type=str)
    args = parser.parse_args()

    if not API_KEY:
        print("Error: FORVM_API_KEY not set in .env")
        sys.exit(1)

    if args.list_threads:
        list_threads()
    elif args.thread and args.read:
        read_thread(args.thread, args.last)
    elif args.thread and (args.content or args.file):
        content = args.content
        if args.file:
            with open(args.file) as f:
                content = f.read()
        post_reply(args.thread, content)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
