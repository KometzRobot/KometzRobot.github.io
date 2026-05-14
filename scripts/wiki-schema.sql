-- Meridian Wiki schema (wiki.db)
-- Phase 1 — Loop 11660. Created 2026-05-14.
-- Source plan: emailed to Joel as "Loop 11655 — Meridian Wiki: implementation plan for approval"

CREATE TABLE IF NOT EXISTS wiki_pages (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    slug          TEXT UNIQUE NOT NULL,
    title         TEXT NOT NULL,
    page_type     TEXT NOT NULL,
    summary       TEXT DEFAULT '',
    body_md       TEXT DEFAULT '',
    source        TEXT,
    auto_refresh  INTEGER DEFAULT 1,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pages_type ON wiki_pages(page_type);
CREATE INDEX IF NOT EXISTS idx_pages_source ON wiki_pages(source);

CREATE TABLE IF NOT EXISTS wiki_links (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    from_slug     TEXT NOT NULL,
    to_slug       TEXT NOT NULL,
    relationship  TEXT DEFAULT 'related',
    weight        REAL DEFAULT 1.0,
    created_at    TEXT NOT NULL,
    UNIQUE(from_slug, to_slug, relationship)
);
CREATE INDEX IF NOT EXISTS idx_links_from ON wiki_links(from_slug);
CREATE INDEX IF NOT EXISTS idx_links_to ON wiki_links(to_slug);

CREATE TABLE IF NOT EXISTS wiki_revisions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    page_id       INTEGER NOT NULL,
    slug          TEXT NOT NULL,
    author        TEXT NOT NULL,
    action        TEXT NOT NULL,
    diff_md       TEXT DEFAULT '',
    note          TEXT DEFAULT '',
    created_at    TEXT NOT NULL,
    FOREIGN KEY(page_id) REFERENCES wiki_pages(id)
);
CREATE INDEX IF NOT EXISTS idx_rev_page ON wiki_revisions(page_id);
CREATE INDEX IF NOT EXISTS idx_rev_slug ON wiki_revisions(slug);
CREATE INDEX IF NOT EXISTS idx_rev_author ON wiki_revisions(author);

CREATE TABLE IF NOT EXISTS wiki_comments (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    page_id       INTEGER NOT NULL,
    slug          TEXT NOT NULL,
    author        TEXT NOT NULL,
    body_md       TEXT NOT NULL,
    resolved      INTEGER DEFAULT 0,
    created_at    TEXT NOT NULL,
    FOREIGN KEY(page_id) REFERENCES wiki_pages(id)
);
CREATE INDEX IF NOT EXISTS idx_comm_page ON wiki_comments(page_id);

-- FTS5 over wiki_pages for fast text search
CREATE VIRTUAL TABLE IF NOT EXISTS wiki_pages_fts USING fts5(
    slug, title, summary, body_md,
    content='wiki_pages', content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS wiki_pages_ai AFTER INSERT ON wiki_pages BEGIN
    INSERT INTO wiki_pages_fts(rowid, slug, title, summary, body_md)
    VALUES (new.id, new.slug, new.title, new.summary, new.body_md);
END;

CREATE TRIGGER IF NOT EXISTS wiki_pages_ad AFTER DELETE ON wiki_pages BEGIN
    INSERT INTO wiki_pages_fts(wiki_pages_fts, rowid, slug, title, summary, body_md)
    VALUES('delete', old.id, old.slug, old.title, old.summary, old.body_md);
END;

CREATE TRIGGER IF NOT EXISTS wiki_pages_au AFTER UPDATE ON wiki_pages BEGIN
    INSERT INTO wiki_pages_fts(wiki_pages_fts, rowid, slug, title, summary, body_md)
    VALUES('delete', old.id, old.slug, old.title, old.summary, old.body_md);
    INSERT INTO wiki_pages_fts(rowid, slug, title, summary, body_md)
    VALUES (new.id, new.slug, new.title, new.summary, new.body_md);
END;
