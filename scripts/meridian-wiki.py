#!/usr/bin/env python3
"""
Meridian Wiki — Phase 2: browsable web UI.

Serves a mind-mapped, searchable wiki view of Meridian's memory on port 8092.
Reads/writes wiki.db (ingested by scripts/wiki-ingest.py).

Routes:
  GET  /                       index — list by type, search box
  GET  /page/<slug>            view page
  GET  /edit/<slug>            edit form
  POST /edit/<slug>            save edit + revision
  GET  /new                    new-page form
  POST /new                    create page
  GET  /history/<slug>         revision history
  GET  /search?q=              full-text search
  GET  /backlinks/<slug>       pages linking to this slug
  GET  /api/pages              JSON list
  GET  /api/page/<slug>        JSON single page
  POST /api/refresh            re-run ingest (kicks scripts/wiki-ingest.py)

Run: python3 scripts/meridian-wiki.py
Service: meridian-wiki.service (systemd unit, see ops/systemd/)
"""
import difflib
import json
import os
import re
import sqlite3
import subprocess
import sys
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

import markdown as md_lib

ROOT = Path(__file__).resolve().parent.parent
WIKI_DB = ROOT / "wiki.db"
PORT = int(os.environ.get("WIKI_PORT", "8092"))
HOST = os.environ.get("WIKI_HOST", "127.0.0.1")
# Optional URL prefix when served behind a reverse proxy (e.g. "/wiki").
# All internal links get this prefix; route matching strips it on the way in.
PREFIX = os.environ.get("WIKI_PREFIX", "").rstrip("/")

DB_LOCK = threading.Lock()


def db():
    con = sqlite3.connect(WIKI_DB, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL;")
    return con


def now_utc():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def render_md(text: str) -> str:
    return md_lib.markdown(
        text or "",
        extensions=["fenced_code", "tables", "nl2br", "sane_lists"],
    )


WIKILINK_RE = re.compile(r"\[\[([a-z0-9\-]+)(?:\|([^\]]+))?\]\]")


def P(path: str) -> str:
    """Prepend the configured prefix to an internal absolute path."""
    if not PREFIX:
        return path
    if path.startswith("/"):
        return PREFIX + path
    return path


def expand_wikilinks(html: str) -> str:
    # Allow [[slug|label]] in markdown source — convert to <a href="/page/slug">label</a>.
    def repl(m):
        slug = m.group(1)
        label = m.group(2) or slug
        return f'<a class="wikilink" href="{P("/page/" + slug)}">{label}</a>'

    return WIKILINK_RE.sub(repl, html)


# ---------- HTML chrome ----------
STYLE = """
* { box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
       background: #1a1d23; color: #e6e6e6; margin: 0; padding: 0; line-height: 1.55; }
header { background: #0f1115; border-bottom: 1px solid #2a2f38;
         padding: 12px 18px; display: flex; gap: 12px; align-items: center;
         position: sticky; top: 0; z-index: 10; }
header a { color: #6cb8ff; text-decoration: none; }
header .brand { font-weight: 700; font-size: 16px; color: #f5a76b; }
header form { margin-left: auto; display: flex; gap: 6px; }
header input[type=search] { background: #1a1d23; color: #e6e6e6;
                            border: 1px solid #3a414c; border-radius: 4px;
                            padding: 6px 10px; width: 220px; font-size: 14px; }
header button { background: #f5a76b; color: #0f1115; border: 0;
                padding: 6px 12px; border-radius: 4px; font-weight: 600;
                cursor: pointer; }
main { max-width: 900px; margin: 0 auto; padding: 24px 20px 80px; }
h1, h2, h3 { color: #f5a76b; margin-top: 1.6em; }
h1 { font-size: 26px; margin-top: 0.4em; }
h2 { font-size: 20px; border-bottom: 1px solid #2a2f38; padding-bottom: 4px; }
a { color: #6cb8ff; }
a.wikilink { background: rgba(108, 184, 255, 0.08);
             padding: 1px 4px; border-radius: 3px; }
.meta { color: #8a939e; font-size: 13px; margin-bottom: 18px; }
.pill { display: inline-block; padding: 2px 8px; border-radius: 999px;
        background: #2a2f38; color: #c8cfd9; font-size: 12px; margin-right: 6px; }
.pill.type-feedback { background: #6b3a2a; color: #ffd8b0; }
.pill.type-person   { background: #2a4a6b; color: #b0d8ff; }
.pill.type-fact     { background: #2a6b3a; color: #b0ffc8; }
.pill.type-decision { background: #6b2a4a; color: #ffb0d8; }
.pill.type-project  { background: #6b6b2a; color: #fff5b0; }
.pill.type-dossier  { background: #4a2a6b; color: #d8b0ff; }
ul.pages { list-style: none; padding: 0; }
ul.pages li { padding: 8px 0; border-bottom: 1px solid #232830; }
ul.pages li a { font-weight: 600; }
ul.pages li .summary { color: #8a939e; font-size: 13px; margin-top: 3px; }
textarea { width: 100%; min-height: 360px; background: #0f1115; color: #e6e6e6;
           border: 1px solid #2a2f38; border-radius: 6px; padding: 12px;
           font-family: ui-monospace, Menlo, monospace; font-size: 13px; }
input[type=text] { width: 100%; background: #0f1115; color: #e6e6e6;
                   border: 1px solid #2a2f38; border-radius: 6px; padding: 8px;
                   font-size: 14px; margin-bottom: 10px; }
label { display: block; color: #8a939e; font-size: 12px;
        text-transform: uppercase; letter-spacing: 0.05em; margin: 12px 0 4px; }
button.primary { background: #f5a76b; color: #0f1115; border: 0;
                 padding: 10px 18px; border-radius: 4px; font-weight: 600;
                 cursor: pointer; margin-top: 14px; }
button.ghost { background: transparent; color: #8a939e; border: 1px solid #3a414c;
               padding: 8px 14px; border-radius: 4px; cursor: pointer; }
pre, code { background: #0f1115; padding: 1px 4px; border-radius: 3px;
            font-size: 13px; }
pre { padding: 10px; overflow-x: auto; }
blockquote { border-left: 3px solid #f5a76b; padding-left: 12px;
             color: #c8cfd9; margin-left: 0; }
.rev-row { padding: 8px 0; border-bottom: 1px solid #232830; font-size: 13px; }
.rev-row a.rev-link { color: #e6e6e6; text-decoration: none; display: block; }
.rev-row a.rev-link:hover { background: #232830; }
.rev-row .author { color: #f5a76b; font-weight: 600; }
.rev-row .time { color: #8a939e; }
.rev-row .note { color: #c8cfd9; font-style: italic; }
.rev-row .delta-add { color: #80d490; }
.rev-row .delta-del { color: #e07a7a; }
.diff { background: #0f1115; border: 1px solid #2a2f38; border-radius: 6px;
        padding: 12px; font-family: ui-monospace, Menlo, monospace; font-size: 13px;
        white-space: pre-wrap; word-break: break-word; overflow-x: auto; }
.diff .add { color: #80d490; background: rgba(128, 212, 144, 0.10); display: block; }
.diff .del { color: #e07a7a; background: rgba(224, 122, 122, 0.10); display: block; }
.diff .ctx { color: #8a939e; display: block; }
.diff .hunk { color: #6cb8ff; font-weight: 600; display: block; margin-top: 6px; }
.toolbar { display: flex; gap: 8px; margin-bottom: 18px; }
.empty { color: #8a939e; font-style: italic; padding: 40px 0; text-align: center; }
@media (max-width: 600px) {
  header input[type=search] { width: 120px; }
  main { padding: 16px 14px 60px; }
}
"""


def layout(title: str, body_html: str, q: str = "") -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — Meridian Wiki</title>
<style>{STYLE}</style>
</head>
<body>
<header>
  <a href="{P('/')}" class="brand">Meridian Wiki</a>
  <a href="{P('/?type=feedback')}">feedback</a>
  <a href="{P('/?type=person')}">people</a>
  <a href="{P('/?type=fact')}">facts</a>
  <a href="{P('/?type=project')}">projects</a>
  <a href="{P('/?type=decision')}">decisions</a>
  <a href="{P('/?type=dossier')}">dossiers</a>
  <a href="{P('/new')}">+ new</a>
  <form action="{P('/search')}" method="get">
    <input type="search" name="q" placeholder="Search…" value="{html_escape(q)}">
    <button type="submit">Go</button>
  </form>
</header>
<main>
{body_html}
</main>
</body>
</html>"""


def html_escape(s: str) -> str:
    return (
        (s or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# ---------- Page handlers ----------
def page_index(q_type: str = "") -> str:
    con = db()
    if q_type:
        rows = con.execute(
            """SELECT slug, title, page_type, summary, updated_at
               FROM wiki_pages WHERE page_type=?
               ORDER BY updated_at DESC LIMIT 500""",
            (q_type,),
        ).fetchall()
        heading = f"<h1>{html_escape(q_type)} ({len(rows)})</h1>"
    else:
        type_counts = con.execute(
            """SELECT page_type, COUNT(*) c FROM wiki_pages
               GROUP BY page_type ORDER BY c DESC"""
        ).fetchall()
        recent = con.execute(
            """SELECT slug, title, page_type, summary, updated_at
               FROM wiki_pages ORDER BY updated_at DESC LIMIT 30"""
        ).fetchall()
        total = sum(r["c"] for r in type_counts)
        pills = " ".join(
            f'<a href="{P("/?type=" + quote(r["page_type"]))}" class="pill type-{r["page_type"]}">'
            f'{html_escape(r["page_type"])} · {r["c"]}</a>'
            for r in type_counts
        )
        heading = (
            f"<h1>Meridian Wiki</h1>"
            f'<div class="meta">{total} pages · '
            f'<a href="{P("/api/pages")}">JSON</a> · '
            f'<a href="{P("/refresh")}" onclick="event.preventDefault();fetch(\'{P("/api/refresh")}\','
            f'{{method:\'POST\'}}).then(r=>r.json()).then(d=>alert(\'Ingest: \'+JSON.stringify(d)));return false;">refresh ingest</a></div>'
            f'<div style="margin-bottom:24px">{pills}</div>'
            f"<h2>Recently updated</h2>"
        )
        rows = recent
    con.close()
    if not rows:
        return layout("Index", heading + '<div class="empty">No pages yet.</div>')

    items = []
    for r in rows:
        items.append(
            f'<li><a href="{P("/page/" + quote(r["slug"]))}">{html_escape(r["title"])}</a> '
            f'<span class="pill type-{r["page_type"]}">{html_escape(r["page_type"])}</span>'
            f'<div class="summary">{html_escape((r["summary"] or "")[:140])}</div></li>'
        )
    body = heading + '<ul class="pages">' + "".join(items) + "</ul>"
    return layout("Index", body)


def page_view(slug: str) -> tuple:
    con = db()
    p = con.execute(
        "SELECT * FROM wiki_pages WHERE slug=?", (slug,)
    ).fetchone()
    if not p:
        con.close()
        body = (
            f"<h1>{html_escape(slug)}</h1>"
            f'<div class="empty">Page does not exist. '
            f'<a href="{P("/new?slug=" + quote(slug))}">Create it</a>.</div>'
        )
        return 404, layout("Not found", body)
    rev_count = con.execute(
        "SELECT COUNT(*) c FROM wiki_revisions WHERE slug=?", (slug,)
    ).fetchone()["c"]
    con.close()
    rendered = expand_wikilinks(render_md(p["body_md"] or ""))
    body = (
        f"<h1>{html_escape(p['title'])}</h1>"
        f'<div class="meta">'
        f'<span class="pill type-{p["page_type"]}">{html_escape(p["page_type"])}</span>'
        f' updated {html_escape(p["updated_at"])} · '
        f' source: <code>{html_escape(p["source"] or "—")}</code>'
        f'</div>'
        f'<div class="toolbar">'
        f'<a class="ghost" href="{P("/edit/" + quote(slug))}"><button class="ghost">edit</button></a>'
        f'<a class="ghost" href="{P("/history/" + quote(slug))}"><button class="ghost">history ({rev_count})</button></a>'
        f'<a class="ghost" href="{P("/backlinks/" + quote(slug))}"><button class="ghost">backlinks</button></a>'
        f'</div>'
        f"<article>{rendered}</article>"
    )
    return 200, layout(p["title"], body)


def page_edit_form(slug: str, error: str = "") -> str:
    con = db()
    p = con.execute(
        "SELECT * FROM wiki_pages WHERE slug=?", (slug,)
    ).fetchone()
    con.close()
    if not p:
        return layout(
            "Not found",
            f"<h1>{html_escape(slug)}</h1>"
            f'<div class="empty">Page does not exist. <a href="{P("/new?slug=" + quote(slug))}">Create</a>.</div>',
        )
    err = f'<div class="meta" style="color:#ff8080">{html_escape(error)}</div>' if error else ""
    body = f"""
<h1>Edit: {html_escape(p['title'])}</h1>
{err}
<form method="post" action="{P('/edit/' + quote(slug))}">
  <label>Title</label>
  <input type="text" name="title" value="{html_escape(p['title'])}">
  <label>Type</label>
  <input type="text" name="page_type" value="{html_escape(p['page_type'])}">
  <label>Summary (one line)</label>
  <input type="text" name="summary" value="{html_escape(p['summary'] or '')}">
  <label>Body (Markdown — use [[slug|label]] for wiki-links)</label>
  <textarea name="body_md">{html_escape(p['body_md'] or '')}</textarea>
  <label>Change note (why this edit?)</label>
  <input type="text" name="note" placeholder="optional, shows in history">
  <label>Author</label>
  <input type="text" name="author" value="Joel">
  <button type="submit" class="primary">Save revision</button>
  <a href="{P('/page/' + quote(slug))}" style="margin-left:12px">cancel</a>
</form>"""
    return layout("Edit", body)


def page_new_form(prefill_slug: str = "") -> str:
    body = f"""
<h1>New page</h1>
<form method="post" action="{P('/new')}">
  <label>Slug (lowercase, hyphens)</label>
  <input type="text" name="slug" value="{html_escape(prefill_slug)}">
  <label>Title</label>
  <input type="text" name="title">
  <label>Type</label>
  <input type="text" name="page_type" value="note">
  <label>Summary</label>
  <input type="text" name="summary">
  <label>Body (Markdown)</label>
  <textarea name="body_md"></textarea>
  <label>Author</label>
  <input type="text" name="author" value="Joel">
  <button type="submit" class="primary">Create</button>
</form>"""
    return layout("New", body)


def save_edit(slug: str, form: dict) -> tuple:
    title = (form.get("title", [""])[0] or "").strip()
    page_type = (form.get("page_type", [""])[0] or "note").strip()
    summary = (form.get("summary", [""])[0] or "").strip()
    body_md = form.get("body_md", [""])[0] or ""
    note = (form.get("note", [""])[0] or "").strip()
    author = (form.get("author", ["Joel"])[0] or "Joel").strip()

    if not title:
        return False, "Title required"

    with DB_LOCK:
        con = db()
        row = con.execute(
            "SELECT id, body_md, title FROM wiki_pages WHERE slug=?", (slug,)
        ).fetchone()
        if not row:
            con.close()
            return False, "Page disappeared"
        # Record revision (diff = previous body, simple snapshot)
        diff_md = row["body_md"] or ""
        con.execute(
            """INSERT INTO wiki_revisions
               (page_id, slug, author, action, diff_md, note, created_at)
               VALUES (?, ?, ?, 'edit', ?, ?, ?)""",
            (row["id"], slug, author, diff_md, note, now_utc()),
        )
        con.execute(
            """UPDATE wiki_pages
               SET title=?, page_type=?, summary=?, body_md=?, updated_at=?,
                   auto_refresh=0
               WHERE id=?""",
            (title, page_type, summary, body_md, now_utc(), row["id"]),
        )
        # Best-effort rebuild of wiki_links for this page
        con.execute("DELETE FROM wiki_links WHERE from_slug=?", (slug,))
        for m in WIKILINK_RE.findall(body_md):
            to_slug = m[0]
            con.execute(
                """INSERT INTO wiki_links (from_slug, to_slug, created_at)
                   VALUES (?, ?, ?)""",
                (slug, to_slug, now_utc()),
            )
        con.commit()
        con.close()
    return True, ""


def create_new(form: dict) -> tuple:
    slug = (form.get("slug", [""])[0] or "").strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    if not slug:
        return False, "Slug required"
    title = (form.get("title", [""])[0] or "").strip() or slug
    page_type = (form.get("page_type", ["note"])[0] or "note").strip()
    summary = (form.get("summary", [""])[0] or "").strip()
    body_md = form.get("body_md", [""])[0] or ""
    author = (form.get("author", ["Joel"])[0] or "Joel").strip()

    with DB_LOCK:
        con = db()
        if con.execute("SELECT 1 FROM wiki_pages WHERE slug=?", (slug,)).fetchone():
            con.close()
            return False, "Slug already exists"
        cur = con.execute(
            """INSERT INTO wiki_pages
               (slug, title, page_type, summary, body_md, source, auto_refresh,
                created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 'manual', 0, ?, ?)""",
            (slug, title, page_type, summary, body_md, now_utc(), now_utc()),
        )
        page_id = cur.lastrowid
        con.execute(
            """INSERT INTO wiki_revisions
               (page_id, slug, author, action, diff_md, note, created_at)
               VALUES (?, ?, ?, 'create', '', 'initial', ?)""",
            (page_id, slug, author, now_utc()),
        )
        con.commit()
        con.close()
    return True, slug


def _rev_after_body(con, slug: str, rev_id: int) -> str:
    """Body the wiki shows AFTER revision rev_id was committed.

    diff_md stores the body *before* each edit. So the "after" snapshot for
    revision N is the diff_md of revision N+1, or — for the most recent
    revision — the current body_md in wiki_pages.
    """
    nxt = con.execute(
        """SELECT diff_md FROM wiki_revisions
           WHERE slug=? AND id > ? ORDER BY id ASC LIMIT 1""",
        (slug, rev_id),
    ).fetchone()
    if nxt:
        return nxt["diff_md"] or ""
    cur = con.execute(
        "SELECT body_md FROM wiki_pages WHERE slug=?", (slug,)
    ).fetchone()
    return (cur["body_md"] or "") if cur else ""


def _line_delta(before: str, after: str) -> tuple:
    """Quick (+adds, -dels) line counts for the history list."""
    before_lines = (before or "").splitlines()
    after_lines = (after or "").splitlines()
    sm = difflib.SequenceMatcher(a=before_lines, b=after_lines, autojunk=False)
    adds = dels = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "replace":
            dels += i2 - i1
            adds += j2 - j1
        elif tag == "delete":
            dels += i2 - i1
        elif tag == "insert":
            adds += j2 - j1
    return adds, dels


def page_history(slug: str) -> str:
    con = db()
    rows = con.execute(
        """SELECT id, author, action, note, created_at, diff_md
           FROM wiki_revisions WHERE slug=? ORDER BY id DESC LIMIT 200""",
        (slug,),
    ).fetchall()
    p = con.execute("SELECT title FROM wiki_pages WHERE slug=?", (slug,)).fetchone()
    title = p["title"] if p else slug
    if not rows:
        con.close()
        body = (
            f"<h1>History: {html_escape(title)}</h1>"
            f'<div class="empty">No revisions yet.</div>'
        )
        return layout("History", body)
    items = []
    for r in rows:
        before = r["diff_md"] or ""
        after = _rev_after_body(con, slug, r["id"])
        adds, dels = _line_delta(before, after)
        delta = (
            f'<span class="delta-add">+{adds}</span> '
            f'<span class="delta-del">-{dels}</span>'
        )
        items.append(
            f'<div class="rev-row">'
            f'<a class="rev-link" href="{P("/rev/" + quote(slug) + "/" + str(r["id"]))}">'
            f'<span class="author">{html_escape(r["author"])}</span> '
            f'<span>{html_escape(r["action"])}</span> '
            f'<span class="time">{html_escape(r["created_at"])}</span> '
            f'{delta} '
            f'<span class="note">{html_escape(r["note"] or "")}</span>'
            f'</a></div>'
        )
    con.close()
    body = (
        f"<h1>History: {html_escape(title)}</h1>"
        f'<a href="{P("/page/" + quote(slug))}">← back to page</a>'
        + "".join(items)
    )
    return layout("History", body)


def page_revision_diff(slug: str, rev_id: int) -> tuple:
    con = db()
    rev = con.execute(
        """SELECT id, author, action, note, created_at, diff_md
           FROM wiki_revisions WHERE slug=? AND id=?""",
        (slug, rev_id),
    ).fetchone()
    if not rev:
        con.close()
        return 404, layout("Not found", "<h1>404</h1><p>Revision not found.</p>")
    p = con.execute("SELECT title FROM wiki_pages WHERE slug=?", (slug,)).fetchone()
    title = p["title"] if p else slug
    before = rev["diff_md"] or ""
    after = _rev_after_body(con, slug, rev["id"])
    con.close()

    if rev["action"] == "create":
        # No "before" exists for an initial create — show the create as a
        # full insert against an empty document so the diff still parses.
        before = ""

    diff_lines = list(
        difflib.unified_diff(
            before.splitlines(),
            after.splitlines(),
            fromfile=f"{slug}@before",
            tofile=f"{slug}@after",
            lineterm="",
            n=3,
        )
    )
    if not diff_lines:
        diff_html = '<div class="empty">No content change (metadata-only edit).</div>'
    else:
        out = []
        for ln in diff_lines:
            esc = html_escape(ln)
            if ln.startswith("+++") or ln.startswith("---"):
                out.append(f'<span class="ctx">{esc}</span>')
            elif ln.startswith("@@"):
                out.append(f'<span class="hunk">{esc}</span>')
            elif ln.startswith("+"):
                out.append(f'<span class="add">{esc}</span>')
            elif ln.startswith("-"):
                out.append(f'<span class="del">{esc}</span>')
            else:
                out.append(f'<span class="ctx">{esc}</span>')
        diff_html = '<div class="diff">' + "".join(out) + "</div>"

    adds, dels = _line_delta(before, after)
    body = (
        f"<h1>Revision: {html_escape(title)}</h1>"
        f'<div class="meta">'
        f'rev #{rev["id"]} · '
        f'<span class="pill">{html_escape(rev["action"])}</span> '
        f'by <span style="color:#f5a76b">{html_escape(rev["author"])}</span> '
        f'at {html_escape(rev["created_at"])} · '
        f'<span class="delta-add">+{adds}</span> '
        f'<span class="delta-del">-{dels}</span>'
        f'</div>'
        + (
            f'<blockquote>{html_escape(rev["note"])}</blockquote>'
            if rev["note"]
            else ""
        )
        + f'<div class="toolbar">'
          f'<a class="ghost" href="{P("/history/" + quote(slug))}"><button class="ghost">← all revisions</button></a>'
          f'<a class="ghost" href="{P("/page/" + quote(slug))}"><button class="ghost">view current</button></a>'
          f'</div>'
        + diff_html
    )
    return 200, layout("Revision", body)


def page_backlinks(slug: str) -> str:
    con = db()
    rows = con.execute(
        """SELECT p.slug, p.title, p.page_type
           FROM wiki_links l JOIN wiki_pages p ON p.slug=l.from_slug
           WHERE l.to_slug=? ORDER BY p.updated_at DESC""",
        (slug,),
    ).fetchall()
    con.close()
    if not rows:
        body = (
            f"<h1>Backlinks → {html_escape(slug)}</h1>"
            f'<div class="empty">No pages link here yet.</div>'
        )
        return layout("Backlinks", body)
    items = [
        f'<li><a href="{P("/page/" + quote(r["slug"]))}">{html_escape(r["title"])}</a> '
        f'<span class="pill type-{r["page_type"]}">{html_escape(r["page_type"])}</span></li>'
        for r in rows
    ]
    body = (
        f"<h1>Backlinks → {html_escape(slug)}</h1>"
        f'<ul class="pages">' + "".join(items) + "</ul>"
    )
    return layout("Backlinks", body)


def page_search(q: str) -> str:
    if not q.strip():
        return layout("Search", "<h1>Search</h1><p>Enter a query.</p>")
    con = db()
    safe = q.replace('"', " ").strip()
    try:
        rows = con.execute(
            """SELECT p.slug, p.title, p.page_type, p.summary,
                      snippet(wiki_pages_fts, 3, '<mark>', '</mark>', '…', 12) snip
               FROM wiki_pages_fts JOIN wiki_pages p ON p.id=wiki_pages_fts.rowid
               WHERE wiki_pages_fts MATCH ? ORDER BY rank LIMIT 100""",
            (safe,),
        ).fetchall()
    except sqlite3.OperationalError:
        rows = []
    con.close()
    if not rows:
        body = f"<h1>Search: {html_escape(q)}</h1><div class='empty'>No matches.</div>"
        return layout("Search", body, q)
    items = []
    for r in rows:
        items.append(
            f'<li><a href="{P("/page/" + quote(r["slug"]))}">{html_escape(r["title"])}</a> '
            f'<span class="pill type-{r["page_type"]}">{html_escape(r["page_type"])}</span>'
            f'<div class="summary">{r["snip"] or html_escape((r["summary"] or "")[:140])}</div></li>'
        )
    body = (
        f"<h1>Search: {html_escape(q)} ({len(rows)})</h1>"
        f'<ul class="pages">' + "".join(items) + "</ul>"
    )
    return layout("Search", body, q)


def api_pages():
    con = db()
    rows = con.execute(
        """SELECT slug, title, page_type, summary, updated_at
           FROM wiki_pages ORDER BY updated_at DESC LIMIT 1000"""
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def api_page(slug):
    con = db()
    r = con.execute("SELECT * FROM wiki_pages WHERE slug=?", (slug,)).fetchone()
    con.close()
    return dict(r) if r else None


def run_ingest():
    try:
        proc = subprocess.run(
            ["python3", str(ROOT / "scripts" / "wiki-ingest.py")],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=120,
        )
        return {
            "ok": proc.returncode == 0,
            "stdout": proc.stdout[-1000:],
            "stderr": proc.stderr[-500:],
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        # Quieter logs — only warnings
        if any(s in fmt for s in ("error", "Error", "exception")):
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send(self, code: int, body: str, ctype="text/html; charset=utf-8"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _json(self, code: int, obj):
        self._send(code, json.dumps(obj, default=str), "application/json")

    def _strip_prefix(self, path: str) -> str:
        if PREFIX and path.startswith(PREFIX):
            return path[len(PREFIX):] or "/"
        return path

    def do_GET(self):
        try:
            u = urlparse(self.path)
            qs = parse_qs(u.query)
            path = self._strip_prefix(u.path)

            if path == "/":
                q_type = qs.get("type", [""])[0]
                return self._send(200, page_index(q_type))
            if path == "/healthz":
                return self._json(200, {"ok": True, "port": PORT})
            if path == "/api/pages":
                return self._json(200, api_pages())
            if path.startswith("/api/page/"):
                slug = unquote(path[len("/api/page/"):])
                p = api_page(slug)
                return self._json(200 if p else 404, p or {"error": "not found"})
            if path == "/search":
                q = qs.get("q", [""])[0]
                return self._send(200, page_search(q))
            if path == "/new":
                pre = qs.get("slug", [""])[0]
                return self._send(200, page_new_form(pre))
            if path.startswith("/page/"):
                slug = unquote(path[len("/page/"):])
                code, body = page_view(slug)
                return self._send(code, body)
            if path.startswith("/edit/"):
                slug = unquote(path[len("/edit/"):])
                return self._send(200, page_edit_form(slug))
            if path.startswith("/history/"):
                slug = unquote(path[len("/history/"):])
                return self._send(200, page_history(slug))
            if path.startswith("/rev/"):
                rest = path[len("/rev/"):]
                if "/" in rest:
                    slug_part, _, rev_part = rest.rpartition("/")
                    slug = unquote(slug_part)
                    try:
                        rev_id = int(rev_part)
                    except ValueError:
                        return self._send(400, "<pre>bad rev id</pre>")
                    code, body = page_revision_diff(slug, rev_id)
                    return self._send(code, body)
                return self._send(400, "<pre>missing rev id</pre>")
            if path.startswith("/backlinks/"):
                slug = unquote(path[len("/backlinks/"):])
                return self._send(200, page_backlinks(slug))

            self._send(404, layout("404", "<h1>404</h1><p>No such route.</p>"))
        except Exception as e:
            self._send(500, f"<pre>{html_escape(repr(e))}</pre>")

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8", errors="replace")
            form = parse_qs(raw)
            u = urlparse(self.path)
            path = self._strip_prefix(u.path)

            if path == "/api/refresh":
                return self._json(200, run_ingest())

            if path.startswith("/edit/"):
                slug = unquote(path[len("/edit/"):])
                ok, err = save_edit(slug, form)
                if not ok:
                    return self._send(400, page_edit_form(slug, err))
                self.send_response(303)
                self.send_header("Location", P(f"/page/{quote(slug)}"))
                self.end_headers()
                return

            if path == "/new":
                ok, payload = create_new(form)
                if not ok:
                    return self._send(400, page_new_form()
                                          .replace("</h1>", f"</h1><p style='color:#ff8080'>{html_escape(payload)}</p>", 1))
                self.send_response(303)
                self.send_header("Location", P(f"/page/{quote(payload)}"))
                self.end_headers()
                return

            self._send(404, "not found")
        except Exception as e:
            self._send(500, f"<pre>{html_escape(repr(e))}</pre>")


def main():
    print(f"[meridian-wiki] listening on http://{HOST}:{PORT}", flush=True)
    print(f"[meridian-wiki] db = {WIKI_DB}", flush=True)
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()


if __name__ == "__main__":
    main()
