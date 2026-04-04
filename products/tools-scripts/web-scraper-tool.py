#!/usr/bin/env python3
"""
Web Scraper Tool — Professional Gig Product
Scrapes websites, extracts structured data, exports to CSV/JSON.
Built by KometzRobot / Meridian AI

Usage:
  python3 web-scraper-tool.py --url "https://example.com" --selector "div.product" --fields "name:h2,price:.price,link:a@href" --output products.csv
"""

import argparse
import csv
import json
import re
import time
from urllib.request import urlopen, Request
from html.parser import HTMLParser


class SimpleHTMLExtractor(HTMLParser):
    """Lightweight HTML parser — no external dependencies needed."""

    def __init__(self):
        super().__init__()
        self.elements = []
        self.current_tag = None
        self.current_attrs = {}
        self.current_text = ''
        self.tag_stack = []
        self.capture = False

    def handle_starttag(self, tag, attrs):
        self.tag_stack.append((tag, dict(attrs)))
        if self.capture:
            self.current_text += f'<{tag}>'

    def handle_endtag(self, tag):
        if self.tag_stack:
            self.tag_stack.pop()

    def handle_data(self, data):
        if self.tag_stack:
            tag, attrs = self.tag_stack[-1]
            self.elements.append({
                'tag': tag,
                'attrs': attrs,
                'text': data.strip(),
                'depth': len(self.tag_stack)
            })


def fetch_page(url, headers=None, delay=1):
    """Fetch a page with polite delay and user-agent."""
    default_headers = {
        'User-Agent': 'Mozilla/5.0 (compatible; DataCollector/1.0)',
        'Accept': 'text/html,application/xhtml+xml',
    }
    if headers:
        default_headers.update(headers)

    time.sleep(delay)
    req = Request(url, headers=default_headers)
    with urlopen(req, timeout=30) as response:
        return response.read().decode('utf-8', errors='replace')


def extract_by_pattern(html, pattern):
    """Extract data using regex patterns."""
    return re.findall(pattern, html, re.DOTALL)


def extract_links(html, base_url=''):
    """Extract all links from HTML."""
    links = re.findall(r'<a[^>]+href=["\']([^"\']+)["\']', html, re.IGNORECASE)
    results = []
    for link in links:
        if link.startswith('/') and base_url:
            link = base_url.rstrip('/') + link
        results.append(link)
    return results


def extract_emails(html):
    """Extract email addresses from HTML."""
    return list(set(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', html)))


def extract_tables(html):
    """Extract HTML tables into list of dicts."""
    tables = []
    table_pattern = re.compile(r'<table[^>]*>(.*?)</table>', re.DOTALL | re.IGNORECASE)
    row_pattern = re.compile(r'<tr[^>]*>(.*?)</tr>', re.DOTALL | re.IGNORECASE)
    cell_pattern = re.compile(r'<t[dh][^>]*>(.*?)</t[dh]>', re.DOTALL | re.IGNORECASE)

    for table_match in table_pattern.finditer(html):
        table_html = table_match.group(1)
        rows = []
        headers = []

        for i, row_match in enumerate(row_pattern.finditer(table_html)):
            cells = [re.sub(r'<[^>]+>', '', cell).strip()
                    for cell in cell_pattern.findall(row_match.group(1))]
            if i == 0:
                headers = cells
            else:
                if headers:
                    row_dict = dict(zip(headers, cells))
                else:
                    row_dict = {f'col_{j}': cell for j, cell in enumerate(cells)}
                rows.append(row_dict)

        tables.append(rows)
    return tables


def extract_text(html):
    """Strip HTML tags and return clean text."""
    text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def scrape_multiple(urls, extract_func, delay=2):
    """Scrape multiple URLs with rate limiting."""
    results = []
    for i, url in enumerate(urls):
        print(f"  [{i+1}/{len(urls)}] {url}")
        try:
            html = fetch_page(url, delay=delay)
            data = extract_func(html)
            results.append({'url': url, 'data': data, 'status': 'ok'})
        except Exception as e:
            results.append({'url': url, 'data': None, 'status': str(e)})
    return results


def save_results(data, output_file, format='csv'):
    """Save results to CSV or JSON."""
    if format == 'json':
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)
    elif format == 'csv':
        if not data:
            return
        if isinstance(data[0], dict):
            keys = data[0].keys()
            with open(output_file, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=keys)
                writer.writeheader()
                writer.writerows(data)
        else:
            with open(output_file, 'w', newline='') as f:
                writer = csv.writer(f)
                for row in data:
                    writer.writerow([row] if not isinstance(row, (list, tuple)) else row)

    print(f"Saved {len(data)} records to {output_file}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Web Scraper Tool')
    parser.add_argument('--url', required=True, help='URL to scrape')
    parser.add_argument('--mode', choices=['links', 'emails', 'tables', 'text', 'pattern'],
                       default='text', help='Extraction mode')
    parser.add_argument('--pattern', help='Regex pattern for pattern mode')
    parser.add_argument('--output', help='Output file')
    parser.add_argument('--format', choices=['csv', 'json'], default='csv')
    parser.add_argument('--delay', type=float, default=1, help='Delay between requests (seconds)')

    args = parser.parse_args()

    print(f"Fetching {args.url}...")
    html = fetch_page(args.url, delay=0)

    if args.mode == 'links':
        data = extract_links(html, args.url)
        print(f"Found {len(data)} links")
    elif args.mode == 'emails':
        data = extract_emails(html)
        print(f"Found {len(data)} email addresses")
    elif args.mode == 'tables':
        tables = extract_tables(html)
        data = [row for table in tables for row in table]
        print(f"Found {len(tables)} tables, {len(data)} total rows")
    elif args.mode == 'text':
        data = [{'text': extract_text(html)}]
        print(f"Extracted {len(data[0]['text'])} characters of text")
    elif args.mode == 'pattern':
        data = extract_by_pattern(html, args.pattern)
        print(f"Found {len(data)} matches")

    if args.output:
        save_results(data, args.output, args.format)
    else:
        for item in data[:10]:
            print(f"  {item}")
        if len(data) > 10:
            print(f"  ... and {len(data) - 10} more")
