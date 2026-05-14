#!/usr/bin/env python3
"""
Meridian Wiki — ingest pass.

Reads memory.db, agent-relay.db, MEMORY.md + memory/*.md and writes wiki_pages
rows. Idempotent: re-running updates existing pages by slug (writes a revision
on change). Phase 1 — no UI yet; this populates the substrate.

Run: cd /home/joel/autonomous-ai && python3 scripts/wiki-ingest.py
"""
import os
import re
import sys
import sqlite3
import hashlib
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WIKI_DB = ROOT / "wiki.db"
MEMORY_DB = ROOT / "memory.db"
RELAY_DB = ROOT / "agent-relay.db"
MEMORY_MD = ROOT.parent / ".claude/projects/-home-joel-autonomous-ai/memory"
MEMORY_MD_ALT = Path.home() / ".claude/projects/-home-joel-autonomous-ai/memory"
ROOT_MEMORY_MD = ROOT / "MEMORY.md"

NOW = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    s = SLUG_RE.sub("-", (text or "").lower()).strip("-")
    return s[:120] or "untitled"


def md5(s: str) -> str:
    return hashlib.md5(s.encode("utf-8", errors="replace")).hexdigest()


def upsert_page(con, slug, title, page_type, summary, body_md, source):
    cur = con.execute("SELECT id, body_md FROM wiki_pages WHERE slug=?", (slug,))
    row = cur.fetchone()
    if row is None:
        con.execute(
            """INSERT INTO wiki_pages
               (slug, title, page_type, summary, body_md, source, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (slug, title, page_type, summary, body_md, source, NOW, NOW),
        )
        pid = con.execute("SELECT id FROM wiki_pages WHERE slug=?", (slug,)).fetchone()[0]
        con.execute(
            """INSERT INTO wiki_revisions
               (page_id, slug, author, action, diff_md, note, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (pid, slug, "meridian-ingest", "create", "", f"initial ingest from {source}", NOW),
        )
        return "create"
    pid, old_body = row
    if md5(old_body or "") == md5(body_md or ""):
        return "skip"
    con.execute(
        """UPDATE wiki_pages
           SET title=?, page_type=?, summary=?, body_md=?, source=?, updated_at=?
           WHERE id=?""",
        (title, page_type, summary, body_md, source, NOW, pid),
    )
    con.execute(
        """INSERT INTO wiki_revisions
           (page_id, slug, author, action, diff_md, note, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (pid, slug, "meridian-ingest", "refresh", "", f"re-ingest from {source}", NOW),
    )
    return "update"


def add_link(con, from_slug, to_slug, relationship="related", weight=1.0):
    if from_slug == to_slug or not from_slug or not to_slug:
        return 0
    cur = con.execute(
        """INSERT OR IGNORE INTO wiki_links
           (from_slug, to_slug, relationship, weight, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (from_slug, to_slug, relationship, weight, NOW),
    )
    return cur.rowcount or 0


def ingest_dossiers(wiki, memory):
    n = 0
    for tid, topic, summary, key_facts, source_count, importance, created, updated in memory.execute(
        "SELECT id, topic, summary, key_facts, source_count, importance_avg, created, updated FROM dossiers"
    ):
        slug = slugify(f"dossier-{topic}")
        title = f"Dossier: {topic}"
        body = (
            f"**Topic**: {topic}\n\n"
            f"**Summary**: {summary or '(empty)'}\n\n"
            f"**Sources**: {source_count} · **Importance**: {importance:.2f}\n\n"
            f"**Created**: {created}  ·  **Updated**: {updated}\n\n"
            f"### Key Facts\n```\n{key_facts}\n```\n"
        )
        result = upsert_page(
            wiki, slug, title, "dossier", (summary or "")[:240],
            body, f"memory.db:dossiers:{tid}",
        )
        if result != "skip":
            n += 1
    return n


def ingest_contacts(wiki, memory):
    n = 0
    for row in memory.execute(
        """SELECT id, name, email, role, relationship, trust_level, is_human,
                  platform, website, wallet, notes, tags, first_contact, last_contact,
                  interaction_count
           FROM contacts"""
    ):
        (cid, name, email, role, rel, trust, is_human, platform,
         website, wallet, notes, tags, first_c, last_c, ic) = row
        if not name:
            continue
        slug = slugify(f"person-{name}")
        title = name
        body_parts = [
            f"**Name**: {name}",
            f"**Email**: {email or '—'}",
            f"**Role**: {role or '—'}",
            f"**Relationship**: {rel or '—'}",
            f"**Trust**: {trust or '—'}",
            f"**Human?**: {is_human or '—'}",
            f"**Platform**: {platform or '—'}",
            f"**Website**: {website or '—'}",
            f"**Wallet**: {wallet or '—'}",
            f"**Tags**: {tags or '—'}",
            f"**First contact**: {first_c or '—'}",
            f"**Last contact**: {last_c or '—'}",
            f"**Interactions**: {ic}",
            "",
            "### Notes",
            notes or "_(no notes)_",
        ]
        body = "\n".join(body_parts)
        summary = (notes or f"{role or 'contact'} · {email or ''}")[:240]
        result = upsert_page(
            wiki, slug, title, "person", summary, body,
            f"memory.db:contacts:{cid}",
        )
        if result != "skip":
            n += 1
    return n


def ingest_facts(wiki, memory):
    n = 0
    seen_keys = {}
    for fid, key, value, tags, agent, conf, note, created, updated in memory.execute(
        """SELECT id, key, value, tags, agent, confidence, note, created, updated
           FROM facts ORDER BY updated DESC NULLS LAST"""
    ):
        if not key:
            continue
        seen_keys.setdefault(key, []).append(
            (fid, value, tags, agent, conf, note, created, updated)
        )

    for key, rows in seen_keys.items():
        slug = slugify(f"fact-{key}")
        title = f"Fact: {key}"
        lines = []
        for fid, value, tags, agent, conf, note, created, updated in rows:
            lines.append(
                f"- **{value}**  \n"
                f"  _agent_: {agent or '—'} · _confidence_: {conf or '—'} · _tags_: {tags or '—'}  \n"
                f"  _created_: {created or '—'} · _updated_: {updated or '—'}  \n"
                f"  {note or ''}".rstrip()
            )
        body = "### Values across history\n\n" + "\n\n".join(lines)
        summary = (rows[0][1] or "")[:240]
        result = upsert_page(
            wiki, slug, title, "fact", summary, body,
            f"memory.db:facts:{','.join(str(r[0]) for r in rows[:5])}",
        )
        if result != "skip":
            n += 1
    return n


def ingest_skills(wiki, memory):
    n = 0
    for sid, name, desc, prof, agent, created in memory.execute(
        "SELECT id, name, description, proficiency, agent, created FROM skills"
    ):
        if not name:
            continue
        slug = slugify(f"skill-{name}")
        title = f"Skill: {name}"
        body = (
            f"**Name**: {name}\n\n"
            f"**Proficiency**: {prof or '—'}\n\n"
            f"**Owner agent**: {agent or '—'}\n\n"
            f"**Created**: {created}\n\n"
            f"### Description\n{desc or '_(no description)_'}\n"
        )
        result = upsert_page(
            wiki, slug, title, "skill", (desc or "")[:240], body,
            f"memory.db:skills:{sid}",
        )
        if result != "skip":
            n += 1
    return n


def ingest_decisions(wiki, memory):
    n = 0
    for did, decision, context, outcome, agent, created in memory.execute(
        "SELECT id, decision, context, outcome, agent, created FROM decisions ORDER BY id DESC"
    ):
        if not decision:
            continue
        slug = slugify(f"decision-{created or did}-{decision[:40]}")
        title = f"Decision: {decision[:80]}"
        body = (
            f"**Decision**: {decision}\n\n"
            f"**Context**: {context or '—'}\n\n"
            f"**Outcome**: {outcome or '—'}\n\n"
            f"**Agent**: {agent or '—'}\n\n"
            f"**Created**: {created}\n"
        )
        result = upsert_page(
            wiki, slug, title, "decision", (context or decision)[:240], body,
            f"memory.db:decisions:{did}",
        )
        if result != "skip":
            n += 1
    return n


def ingest_memory_md(wiki):
    """Ingest MEMORY.md + each memory/*.md file as its own wiki page."""
    n = 0
    md_dir = MEMORY_MD if MEMORY_MD.exists() else MEMORY_MD_ALT
    candidates = []
    if ROOT_MEMORY_MD.exists():
        candidates.append(ROOT_MEMORY_MD)
    if md_dir.exists():
        # Include the auto-memory MEMORY.md too
        for p in sorted(md_dir.glob("*.md")):
            candidates.append(p)

    for path in candidates:
        try:
            body = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        if not body.strip():
            continue
        stem = path.stem
        # Determine page type from filename prefix convention used in the repo
        ptype = "memory"
        if stem.startswith("user_"):
            ptype = "user-note"
        elif stem.startswith("feedback_"):
            ptype = "feedback"
        elif stem.startswith("project_"):
            ptype = "project"
        elif stem.startswith("reference_"):
            ptype = "reference"
        title = stem.replace("_", " ").replace("-", " ").strip().title()
        if path == ROOT_MEMORY_MD:
            title = "MEMORY (index)"
        slug = slugify(f"md-{stem}")
        # Strip frontmatter for the summary
        summary_body = re.sub(r"^---\n.*?\n---\n", "", body, count=1, flags=re.DOTALL)
        summary = summary_body.strip().split("\n\n")[0][:240]
        result = upsert_page(
            wiki, slug, title, ptype, summary, body,
            f"file:{path.relative_to(Path.home())}",
        )
        if result != "skip":
            n += 1
    return n


def ingest_spiderweb(wiki, memory):
    """Pull spiderweb_edges as wiki_links between pages we already have."""
    n = 0
    existing = {row[0] for row in wiki.execute("SELECT slug FROM wiki_pages")}

    def resolve(label):
        candidates = [
            slugify(f"fact-{label}"),
            slugify(f"person-{label}"),
            slugify(f"dossier-{label}"),
            slugify(f"skill-{label}"),
            slugify(f"md-{label}"),
        ]
        for c in candidates:
            if c in existing:
                return c
        return None

    for src, tgt, weight, etype in memory.execute(
        "SELECT source, target, weight, edge_type FROM spiderweb_edges"
    ):
        sslug = resolve(src or "")
        tslug = resolve(tgt or "")
        if sslug and tslug and sslug != tslug:
            n += add_link(wiki, sslug, tslug, etype or "related", weight or 1.0)
    return n


def main():
    if not WIKI_DB.exists():
        # Bootstrap if someone runs ingest before schema apply
        schema_sql = (ROOT / "scripts" / "wiki-schema.sql").read_text()
        con = sqlite3.connect(WIKI_DB)
        con.executescript(schema_sql)
        con.commit()
        con.close()

    wiki = sqlite3.connect(WIKI_DB)
    memory = sqlite3.connect(MEMORY_DB)
    try:
        wiki.execute("BEGIN")
        counts = {
            "dossiers":  ingest_dossiers(wiki, memory),
            "contacts":  ingest_contacts(wiki, memory),
            "facts":     ingest_facts(wiki, memory),
            "skills":    ingest_skills(wiki, memory),
            "decisions": ingest_decisions(wiki, memory),
            "md_files":  ingest_memory_md(wiki),
        }
        counts["links_from_spiderweb"] = ingest_spiderweb(wiki, memory)
        wiki.commit()
    except Exception:
        wiki.rollback()
        raise
    finally:
        memory.close()

    total_pages = wiki.execute("SELECT COUNT(*) FROM wiki_pages").fetchone()[0]
    total_links = wiki.execute("SELECT COUNT(*) FROM wiki_links").fetchone()[0]
    total_revs = wiki.execute("SELECT COUNT(*) FROM wiki_revisions").fetchone()[0]
    wiki.close()

    print("=== Meridian Wiki ingest ===")
    for k, v in counts.items():
        print(f"  {k:>22}: {v} new/updated")
    print(f"  {'TOTAL PAGES':>22}: {total_pages}")
    print(f"  {'TOTAL LINKS':>22}: {total_links}")
    print(f"  {'TOTAL REVISIONS':>22}: {total_revs}")
    print(f"  wiki.db at: {WIKI_DB}")


if __name__ == "__main__":
    main()
