#!/usr/bin/env python3
"""
CoderLegion Article Import Tool
================================
Imports Dev.to articles to CoderLegion using the import-post workflow
or direct posting via the new-post form.

Usage:
    python3 scripts/coderlegion-import.py --list          # List Dev.to articles
    python3 scripts/coderlegion-import.py --import URL     # Import specific article
    python3 scripts/coderlegion-import.py --import-all     # Import all articles
    python3 scripts/coderlegion-import.py --post URL       # Direct post (fallback)
    python3 scripts/coderlegion-import.py --test-login     # Test login credentials

Requires:
    CODERLEGION_USER and CODERLEGION_PASS in .env
    DEVTO_API_KEY in .env (for fetching articles)
"""

import sys
import os
import re
import json
import time
import argparse
import requests

# Load env
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, 'scripts'))

def load_env():
    env = {}
    env_path = os.path.join(BASE, '.env')
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    key, val = line.split('=', 1)
                    env[key.strip()] = val.strip()
    return env

ENV = load_env()
CL_USER = ENV.get('CODERLEGION_USER', 'Meridian_AI')
CL_PASS = ENV.get('CODERLEGION_PASS', '')
DEVTO_KEY = ENV.get('DEVTO_API_KEY', '')
COOKIES_FILE = os.path.join(BASE, '.coderlegion-cookies.json')
IMPORT_LOG = os.path.join(BASE, '.coderlegion-imported.json')

# Load/save import tracking
def load_imported():
    if os.path.exists(IMPORT_LOG):
        with open(IMPORT_LOG) as f:
            return json.load(f)
    return {}

def save_imported(data):
    with open(IMPORT_LOG, 'w') as f:
        json.dump(data, f, indent=2)


class CoderLegionClient:
    """Handles authentication and posting to CoderLegion."""

    BASE_URL = 'https://coderlegion.com'

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })
        self.logged_in = False
        self.csrf_code = None

    def _get_csrf(self, html):
        """Extract CSRF code from page."""
        codes = re.findall(r'name="code"[^>]*value="([^"]+)"', html)
        return codes[-1] if codes else None

    def login(self, username=None, password=None):
        """Login to CoderLegion. Returns True on success."""
        username = username or CL_USER
        password = password or CL_PASS

        if not password:
            print("ERROR: No password configured. Set CODERLEGION_PASS in .env")
            return False

        # Get login page for CSRF token
        resp = self.session.get(f'{self.BASE_URL}/login', timeout=30)
        csrf = self._get_csrf(resp.text)
        if not csrf:
            print("ERROR: Could not get CSRF token from login page")
            return False

        # Submit login
        resp = self.session.post(f'{self.BASE_URL}/login', data={
            'emailhandle': username,
            'password': password,
            'remember': '1',
            'dologin': '1',
            'code': csrf
        }, timeout=30, allow_redirects=False)

        # Check: successful login returns 302 redirect
        if resp.status_code in (301, 302, 303):
            self.logged_in = True
            print(f"Logged in as {username}")
            return True

        # Check for errors in 200 response
        if 'Password not correct' in resp.text:
            print(f"ERROR: Password not correct for {username}")
            return False
        if 'User not found' in resp.text:
            print(f"ERROR: User not found: {username}")
            return False

        # Check if somehow logged in despite 200
        resp_check = self.session.get(f'{self.BASE_URL}/account', timeout=30)
        if 'Log in' not in re.findall(r'<title>(.*?)</title>', resp_check.text)[0]:
            self.logged_in = True
            print(f"Logged in as {username}")
            return True

        print("ERROR: Login failed (unknown reason)")
        return False

    def import_article(self, dev_to_url):
        """
        Import an article using CoderLegion's import-post feature.
        This is a 3-step process:
        1. Enter URL (step 2)
        2. Review fetched content (step 3 shows auth page)
        3. Login & Publish (submits via step-3 auth form)

        Returns the URL of the published article, or None on failure.
        """
        print(f"\n--- Importing: {dev_to_url} ---")

        # The import flow uses cookies to track state.
        # Step 1: Visit import page
        resp = self.session.get(f'{self.BASE_URL}/import-post', timeout=30)

        # Step 2: Fetch the article
        print("  Fetching article content...")
        resp = self.session.post(f'{self.BASE_URL}/import-post', data={
            'import_step': '2',
            'import_url': dev_to_url
        }, timeout=30)

        if 'Successfully fetched' in resp.text:
            print("  Article fetched successfully!")
        elif 'already' in resp.text.lower():
            print("  Article may already be imported")
            return 'already_imported'
        else:
            text = self._extract_main_text(resp.text)
            print(f"  Fetch result: {text[:200]}")
            # Check if step 3 form exists anyway
            if 'import_step' not in resp.text or '"3"' not in resp.text:
                print("  ERROR: Could not fetch article")
                return None

        # Step 3: Submit to get to auth page
        print("  Moving to publish step...")
        resp = self.session.post(f'{self.BASE_URL}/import-post', data={
            'import_step': '3'
        }, timeout=30)

        # Step 3 always shows "Claim Your Authorship" and requires re-login
        if 'Claim Your Authorship' in resp.text:
            print("  Auth required for publishing...")
            # Get CSRF from the "Log In & Publish" form
            # This form: POST ./login?to=import-post&u=home
            form_match = re.search(
                r'<form[^>]*action="./login\?to=import-post&amp;u=home"[^>]*>(.*?)</form>',
                resp.text, re.DOTALL
            )
            if form_match:
                code = re.search(r'name="code"[^>]*value="([^"]+)"', form_match.group(1))
                if code:
                    csrf = code.group(1)
                    print("  Submitting login & publish...")
                    resp = self.session.post(
                        f'{self.BASE_URL}/login?to=import-post&u=home',
                        data={
                            'emailhandle': CL_USER,
                            'password': CL_PASS,
                            'dologin': '1',
                            'code': csrf
                        },
                        timeout=30, allow_redirects=True
                    )

                    if 'Password not correct' in resp.text:
                        print("  ERROR: Password not correct at publish step")
                        return None
                    if 'User not found' in resp.text:
                        print("  ERROR: User not found at publish step")
                        return None

                    # Check for success
                    if resp.url and '/import-post' not in resp.url:
                        print(f"  PUBLISHED! URL: {resp.url}")
                        return resp.url
                    elif 'Published' in resp.text or 'success' in resp.text.lower():
                        print("  PUBLISHED!")
                        return True
            else:
                # Try the modal login form as fallback
                csrf = self._get_csrf(resp.text)
                if csrf:
                    resp = self.session.post(
                        f'{self.BASE_URL}/login?to=import-post',
                        data={
                            'emailhandle': CL_USER,
                            'password': CL_PASS,
                            'remember': '1',
                            'dologin': '1',
                            'code': csrf
                        },
                        timeout=30, allow_redirects=True
                    )
                    if resp.url and '/import-post' not in resp.url:
                        print(f"  PUBLISHED! URL: {resp.url}")
                        return resp.url

        # Check final state
        if resp.url and '/import-post' not in resp.url:
            print(f"  PUBLISHED! URL: {resp.url}")
            return resp.url

        text = self._extract_main_text(resp.text)
        print(f"  Final page: {text[:300]}")
        return None

    def direct_post(self, title, content_md, tags, source_url=None, category='Articles'):
        """
        Post an article directly using the new-post form.
        Requires being logged in first.

        Args:
            title: Article title
            content_md: Markdown content
            tags: Comma-separated tags (up to 4)
            source_url: Original canonical URL (for cross-posted content)
            category: 'Articles' (2), 'Tutorials' (5), 'Launches' (1971)
        """
        if not self.logged_in:
            print("ERROR: Must be logged in to post directly")
            return None

        cat_map = {'Articles': '2', 'Tutorials': '5', 'Launches': '1971', 'Videos': '2005'}
        cat_id = cat_map.get(category, '2')

        # Get the new post page for CSRF
        resp = self.session.get(f'{self.BASE_URL}/ask', timeout=30)
        csrf = self._get_csrf(resp.text)
        if not csrf:
            print("ERROR: Could not get CSRF for post form")
            return None

        data = {
            'title': title,
            'content': content_md,
            'tags': tags,
            'category_0': cat_id,
            'category_1': cat_id,
            'cats_radio': cat_id,
            'audience_hidden_input': '',
            'code': csrf,
            'q_doanswer': '1',
        }

        if source_url:
            data['psource_checkbox'] = '1'
            data['source'] = source_url

        print(f"  Posting: {title}")
        resp = self.session.post(f'{self.BASE_URL}/post', data=data, timeout=30, allow_redirects=True)

        if resp.url and resp.url != f'{self.BASE_URL}/post':
            print(f"  POSTED! URL: {resp.url}")
            return resp.url

        text = self._extract_main_text(resp.text)
        print(f"  Post result: {text[:300]}")
        return None

    def _extract_main_text(self, html):
        """Extract readable text from the main content area."""
        main = re.search(r'class="qa-main"[^>]*>(.*?)(?=<div class="qa-footer|<footer)', html, re.DOTALL)
        if main:
            text = re.sub(r'<script[^>]*>.*?</script>', '', main.group(1), flags=re.DOTALL)
            text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
            text = re.sub(r'<[^>]+>', ' ', text)
            text = re.sub(r'\s+', ' ', text).strip()
            return text
        return ''


def fetch_devto_articles(username='meridian-ai', per_page=30, page=1):
    """Fetch articles from Dev.to API."""
    headers = {'User-Agent': 'Meridian-AI-Importer/1.0'}
    if DEVTO_KEY:
        headers['api-key'] = DEVTO_KEY

    articles = []
    while True:
        resp = requests.get(
            f'https://dev.to/api/articles?username={username}&per_page={per_page}&page={page}',
            headers=headers, timeout=30
        )
        if resp.status_code != 200:
            print(f"Dev.to API error: {resp.status_code}")
            break
        batch = resp.json()
        if not batch:
            break
        articles.extend(batch)
        if len(batch) < per_page:
            break
        page += 1
        time.sleep(0.5)  # Rate limit

    return articles


def fetch_devto_article_detail(article_id):
    """Fetch full article content from Dev.to."""
    headers = {'User-Agent': 'Meridian-AI-Importer/1.0'}
    if DEVTO_KEY:
        headers['api-key'] = DEVTO_KEY

    resp = requests.get(f'https://dev.to/api/articles/{article_id}', headers=headers, timeout=30)
    if resp.status_code == 200:
        return resp.json()
    return None


def main():
    parser = argparse.ArgumentParser(description='CoderLegion Article Import Tool')
    parser.add_argument('--list', action='store_true', help='List Dev.to articles')
    parser.add_argument('--import', dest='import_url', help='Import specific Dev.to article URL')
    parser.add_argument('--import-all', action='store_true', help='Import all Dev.to articles')
    parser.add_argument('--post', help='Direct post a Dev.to article URL (requires login)')
    parser.add_argument('--test-login', action='store_true', help='Test login credentials')
    parser.add_argument('--username', default=CL_USER, help='CoderLegion username')
    parser.add_argument('--password', default=CL_PASS, help='CoderLegion password')
    parser.add_argument('--limit', type=int, default=50, help='Max articles to list/import')
    args = parser.parse_args()

    if args.test_login:
        client = CoderLegionClient()
        if client.login(args.username, args.password):
            print("Login test: SUCCESS")
            # Verify by accessing account page
            resp = client.session.get(f'{client.BASE_URL}/account', timeout=30)
            title = re.findall(r'<title>(.*?)</title>', resp.text)
            print(f"Account page: {title}")
        else:
            print("Login test: FAILED")
        return

    if args.list:
        print("Fetching Dev.to articles...")
        articles = fetch_devto_articles(per_page=min(args.limit, 30))
        imported = load_imported()
        print(f"\nFound {len(articles)} articles:\n")
        for i, art in enumerate(articles, 1):
            url = art.get('url', '')
            status = 'IMPORTED' if url in imported else 'pending'
            print(f"  {i:2d}. [{status:8s}] {art['title']}")
            print(f"      URL: {url}")
            print(f"      Tags: {', '.join(art.get('tag_list', []))}")
            print(f"      Published: {art.get('published_at', '?')[:10]}")
            print()
        return

    if args.import_url:
        client = CoderLegionClient()
        result = client.import_article(args.import_url)
        if result:
            imported = load_imported()
            imported[args.import_url] = {
                'status': 'imported',
                'result': str(result),
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
            }
            save_imported(imported)
            print(f"\nImport result: {result}")
        else:
            print("\nImport FAILED")
        return

    if args.import_all:
        print("Fetching Dev.to articles...")
        articles = fetch_devto_articles(per_page=30)
        imported = load_imported()
        client = CoderLegionClient()

        success = 0
        failed = 0
        skipped = 0

        for art in articles[:args.limit]:
            url = art.get('url', '')
            if url in imported:
                print(f"  Skipping (already imported): {art['title']}")
                skipped += 1
                continue

            result = client.import_article(url)
            if result:
                imported[url] = {
                    'status': 'imported',
                    'result': str(result),
                    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
                }
                save_imported(imported)
                success += 1
            else:
                failed += 1

            time.sleep(2)  # Be respectful

        print(f"\nResults: {success} imported, {failed} failed, {skipped} skipped")
        return

    if args.post:
        # Direct post approach - fetch article from Dev.to, then post to CoderLegion
        client = CoderLegionClient()
        if not client.login(args.username, args.password):
            print("Cannot login - aborting direct post")
            return

        # Parse Dev.to URL to get article slug
        # Fetch article content
        articles = fetch_devto_articles()
        article = None
        for art in articles:
            if art.get('url') == args.post:
                article = art
                break

        if not article:
            print(f"Article not found on Dev.to: {args.post}")
            return

        # Get full article with body_markdown
        detail = fetch_devto_article_detail(article['id'])
        if not detail:
            print("Could not fetch article details")
            return

        title = detail['title']
        body = detail.get('body_markdown', '')
        tags = ','.join(detail.get('tag_list', [])[:4])

        result = client.direct_post(title, body, tags, source_url=args.post)
        if result:
            imported = load_imported()
            imported[args.post] = {
                'status': 'direct_posted',
                'result': str(result),
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
            }
            save_imported(imported)
            print(f"\nDirect post result: {result}")
        else:
            print("\nDirect post FAILED")
        return

    parser.print_help()


if __name__ == '__main__':
    main()
