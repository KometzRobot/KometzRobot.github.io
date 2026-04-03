-- LoopStack Relay Schema
-- Inter-agent communication database (SQLite)

CREATE TABLE IF NOT EXISTS agent_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent TEXT NOT NULL,           -- sender agent name
    topic TEXT DEFAULT 'general',  -- category for filtering
    message TEXT NOT NULL,         -- message content
    timestamp TEXT DEFAULT (datetime('now')),
    read_by TEXT DEFAULT ''        -- comma-separated list of agents that read this
);

CREATE TABLE IF NOT EXISTS directed_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_agent TEXT NOT NULL,
    to_agent TEXT NOT NULL,
    message TEXT NOT NULL,
    timestamp TEXT DEFAULT (datetime('now')),
    acknowledged INTEGER DEFAULT 0
);

-- Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_agent_messages_timestamp ON agent_messages(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_agent_messages_agent ON agent_messages(agent);
CREATE INDEX IF NOT EXISTS idx_directed_to ON directed_messages(to_agent, acknowledged);
