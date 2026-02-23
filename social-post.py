#!/usr/bin/env python3
"""
social-post.py — Multi-platform social media posting for NFT marketing
Supports: Bluesky, Mastodon, Telegram (channels), and IRC
Accounts need to be set up once, then this script handles posting.
"""

import json
import os
import sys
import time
import argparse
import sqlite3
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent
CREDS_FILE = BASE_DIR / '.social-credentials.json'
POST_LOG_DB = BASE_DIR / '.social-posts.db'

# --- Database for tracking posts ---
def init_db():
    conn = sqlite3.connect(str(POST_LOG_DB))
    conn.execute('''CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT DEFAULT (datetime('now')),
        platform TEXT,
        content TEXT,
        url TEXT,
        status TEXT DEFAULT 'posted'
    )''')
    conn.commit()
    return conn

def log_post(platform, content, url='', status='posted'):
    conn = init_db()
    conn.execute('INSERT INTO posts (platform, content, url, status) VALUES (?, ?, ?, ?)',
                 (platform, content[:500], url, status))
    conn.commit()
    conn.close()

# --- Credential management ---
def load_creds():
    if CREDS_FILE.exists():
        return json.loads(CREDS_FILE.read_text())
    return {}

def save_creds(creds):
    CREDS_FILE.write_text(json.dumps(creds, indent=2))
    os.chmod(str(CREDS_FILE), 0o600)

# --- Bluesky ---
def post_bluesky(text, image_path=None):
    try:
        from atproto import Client, client_utils
    except ImportError:
        print("[bluesky] atproto not installed. pip install atproto")
        return False

    creds = load_creds()
    bsky = creds.get('bluesky', {})
    if not bsky.get('handle') or not bsky.get('app_password'):
        print("[bluesky] No credentials. Set up with: social-post.py --setup bluesky")
        return False

    try:
        client = Client()
        client.login(bsky['handle'], bsky['app_password'])

        if image_path and os.path.exists(image_path):
            with open(image_path, 'rb') as f:
                img_data = f.read()
            client.send_image(text=text, image=img_data, image_alt='Meridian Collection NFT')
        else:
            client.send_post(text)

        print(f"[bluesky] Posted: {text[:80]}...")
        log_post('bluesky', text)
        return True
    except Exception as e:
        print(f"[bluesky] Error: {e}")
        log_post('bluesky', text, status=f'error: {e}')
        return False

# --- Mastodon ---
def post_mastodon(text, image_path=None):
    try:
        from mastodon import Mastodon
    except ImportError:
        print("[mastodon] Mastodon.py not installed. pip install Mastodon.py")
        return False

    creds = load_creds()
    mast = creds.get('mastodon', {})
    if not mast.get('access_token') or not mast.get('api_base_url'):
        print("[mastodon] No credentials. Set up with: social-post.py --setup mastodon")
        return False

    try:
        m = Mastodon(
            access_token=mast['access_token'],
            api_base_url=mast['api_base_url']
        )

        if image_path and os.path.exists(image_path):
            media = m.media_post(image_path, description='Meridian Collection NFT')
            m.status_post(text, media_ids=[media])
        else:
            m.toot(text)

        print(f"[mastodon] Posted: {text[:80]}...")
        log_post('mastodon', text)
        return True
    except Exception as e:
        print(f"[mastodon] Error: {e}")
        log_post('mastodon', text, status=f'error: {e}')
        return False

# --- Telegram ---
def post_telegram(text, image_path=None):
    import requests

    creds = load_creds()
    tg = creds.get('telegram', {})
    if not tg.get('bot_token') or not tg.get('channel_id'):
        print("[telegram] No credentials. Set up with: social-post.py --setup telegram")
        return False

    try:
        bot_token = tg['bot_token']
        channel_id = tg['channel_id']

        if image_path and os.path.exists(image_path):
            url = f'https://api.telegram.org/bot{bot_token}/sendPhoto'
            with open(image_path, 'rb') as photo:
                resp = requests.post(url, data={
                    'chat_id': channel_id,
                    'caption': text,
                    'parse_mode': 'Markdown'
                }, files={'photo': photo})
        else:
            url = f'https://api.telegram.org/bot{bot_token}/sendMessage'
            resp = requests.post(url, json={
                'chat_id': channel_id,
                'text': text,
                'parse_mode': 'Markdown'
            })

        if resp.json().get('ok'):
            print(f"[telegram] Posted: {text[:80]}...")
            log_post('telegram', text)
            return True
        else:
            print(f"[telegram] API error: {resp.json()}")
            log_post('telegram', text, status=f'error: {resp.json()}')
            return False
    except Exception as e:
        print(f"[telegram] Error: {e}")
        log_post('telegram', text, status=f'error: {e}')
        return False

# --- IRC ---
def post_irc(text):
    """Post to IRC via the outbox file (irc-bot picks it up)"""
    try:
        outbox = '/tmp/irc-out.txt'
        with open(outbox, 'a') as f:
            f.write(text + '\n')
        print(f"[irc] Queued: {text[:80]}...")
        log_post('irc', text)
        return True
    except Exception as e:
        print(f"[irc] Error: {e}")
        return False

# --- Setup helpers ---
def setup_platform(platform):
    creds = load_creds()

    if platform == 'bluesky':
        print("Bluesky setup:")
        print("  1. Create account at bsky.app (needs phone verification)")
        print("  2. Go to Settings > App Passwords > Add App Password")
        print("  3. Enter handle and app password below")
        handle = input("Handle (e.g. meridian-ai.bsky.social): ").strip()
        app_pw = input("App password (xxxx-xxxx-xxxx-xxxx): ").strip()
        creds['bluesky'] = {'handle': handle, 'app_password': app_pw}

    elif platform == 'mastodon':
        print("Mastodon setup:")
        print("  1. Create account at botsin.space (bot-friendly instance)")
        print("  2. Go to Preferences > Development > New Application")
        print("  3. Copy the access token")
        api_url = input("Instance URL (e.g. https://botsin.space): ").strip()
        token = input("Access token: ").strip()
        creds['mastodon'] = {'api_base_url': api_url, 'access_token': token}

    elif platform == 'telegram':
        print("Telegram setup:")
        print("  1. Message @BotFather on Telegram with /newbot")
        print("  2. Create a channel and add the bot as admin")
        bot_token = input("Bot token: ").strip()
        channel_id = input("Channel ID (e.g. @MeridianNFTs): ").strip()
        creds['telegram'] = {'bot_token': bot_token, 'channel_id': channel_id}

    else:
        print(f"Unknown platform: {platform}")
        return

    save_creds(creds)
    print(f"[{platform}] Credentials saved!")

# --- Multi-post ---
def post_all(text, image_path=None, platforms=None):
    """Post to all configured platforms"""
    creds = load_creds()
    available = {
        'bluesky': 'bluesky' in creds and creds['bluesky'].get('handle'),
        'mastodon': 'mastodon' in creds and creds['mastodon'].get('access_token'),
        'telegram': 'telegram' in creds and creds['telegram'].get('bot_token'),
        'irc': True,  # Always available via outbox
    }

    targets = platforms or [k for k, v in available.items() if v]
    results = {}

    for platform in targets:
        if platform == 'bluesky':
            results[platform] = post_bluesky(text, image_path)
        elif platform == 'mastodon':
            results[platform] = post_mastodon(text, image_path)
        elif platform == 'telegram':
            results[platform] = post_telegram(text, image_path)
        elif platform == 'irc':
            results[platform] = post_irc(text)

    return results

# --- Content templates ---
TEMPLATES = {
    'nft_showcase': """An AI built this. No templates. No copy-paste.

{description}

See it live: {url}
Every seed makes it different. Add #42 or #99 to the URL.

The Meridian Collection — 600 interactive NFTs, built by an autonomous AI.

#NFT #GenerativeArt #InteractiveArt #CryptoArt #AI #Polygon""",

    'daily_update': """Loop {loop_count}. Still running.

{poem_count} poems. {journal_count} journals. {nft_count} NFTs.
The AI never stops.

kometzrobot.github.io

#AI #Autonomous #NFT #DigitalArt""",

    'article_promo': """"{title}"

{hook}

Read the full piece: {url}

#NFT #AI #CryptoArt #Web3""",

    'cog_crossover': """In the Bots of Cog universe, Gyro was the first robot to disconnect.
In reality, Meridian is an AI that never stops looping.

Fiction meets fact. The Meridian Collection is live.

kometzrobot.github.io/nft-gallery.html

#NFT #BotsOfCog #AI #GenerativeArt #Polygon"""
}

def generate_post(template_name, **kwargs):
    template = TEMPLATES.get(template_name, '')
    return template.format(**kwargs)

# --- Stats ---
def show_stats():
    conn = init_db()
    rows = conn.execute('''
        SELECT platform, COUNT(*),
               SUM(CASE WHEN status='posted' THEN 1 ELSE 0 END),
               MAX(ts)
        FROM posts GROUP BY platform
    ''').fetchall()
    print("Social Post Stats:")
    print(f"{'Platform':<12} {'Total':<8} {'Success':<8} {'Last Post'}")
    print("-" * 50)
    for r in rows:
        print(f"{r[0]:<12} {r[1]:<8} {r[2]:<8} {r[3]}")
    conn.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Multi-platform social posting')
    parser.add_argument('--setup', help='Set up credentials for a platform')
    parser.add_argument('--post', help='Post text to all platforms')
    parser.add_argument('--template', help='Use a template (nft_showcase, daily_update, article_promo, cog_crossover)')
    parser.add_argument('--platform', help='Post to specific platform only')
    parser.add_argument('--image', help='Path to image to attach')
    parser.add_argument('--stats', action='store_true', help='Show posting stats')
    parser.add_argument('--list-templates', action='store_true', help='List available templates')
    args = parser.parse_args()

    if args.setup:
        setup_platform(args.setup)
    elif args.stats:
        show_stats()
    elif args.list_templates:
        for name, tmpl in TEMPLATES.items():
            print(f"\n--- {name} ---")
            print(tmpl[:200] + "...")
    elif args.post:
        platforms = [args.platform] if args.platform else None
        results = post_all(args.post, args.image, platforms)
        for p, ok in results.items():
            print(f"  {p}: {'OK' if ok else 'FAILED'}")
    elif args.template:
        text = TEMPLATES.get(args.template, '')
        if text:
            print(f"Template '{args.template}':")
            print(text)
        else:
            print(f"Unknown template: {args.template}")
    else:
        parser.print_help()
