"""
Centralized configuration for Meridian ecosystem.
All paths, directories, and constants in one place.
Import this instead of hardcoding paths.

Usage:
    from config import RELAY_DB, MEMORY_DB, DATA_DIR
"""

import os

# Base directory — where all services run from
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Data directory — databases, state files
DATA_DIR = os.path.join(BASE_DIR, "Meridian", "data")

# Config directory
CONFIG_DIR = os.path.join(BASE_DIR, "Meridian")

# ═══ DATABASE PATHS ═══
RELAY_DB = os.path.join(DATA_DIR, "agent-relay.db")
MEMORY_DB = os.path.join(DATA_DIR, "memory.db")
MESSAGES_DB = os.path.join(DATA_DIR, "messages.db")
RELAY_DB_LEGACY = os.path.join(DATA_DIR, "relay.db")
EMAIL_SHELF_DB = os.path.join(DATA_DIR, "email-shelf.db")
CINDER_MEMORY_DB = os.path.join(DATA_DIR, "cinder-memory.db")
VOLTAR_KEYS_DB = os.path.join(BASE_DIR, "voltar", "voltar-keys.db")

# ═══ STATE FILES ═══
HEARTBEAT = os.path.join(BASE_DIR, ".heartbeat")
LOOP_FILE = os.path.join(BASE_DIR, ".loop-count")
CAPSULE = os.path.join(BASE_DIR, ".capsule.md")
HANDOFF = os.path.join(BASE_DIR, ".loop-handoff.md")
DASH_FILE = os.path.join(BASE_DIR, ".dashboard-messages.json")
BODY_STATE = os.path.join(BASE_DIR, ".body-state.json")
SOMA_STATE = os.path.join(BASE_DIR, ".symbiosense-state.json")

# ═══ CONFIG FILES ═══
ENV_FILE = os.path.join(BASE_DIR, ".env")
SIGNAL_CONFIG = os.path.join(CONFIG_DIR, "signal-config.json")
STATUS_JSON = os.path.join(CONFIG_DIR, "status.json")

# ═══ DIRECTORIES ═══
LOGS_DIR = os.path.join(BASE_DIR, "logs")
TOOLS_DIR = os.path.join(BASE_DIR, "tools")
WEBSITE_DIR = os.path.join(BASE_DIR, "website")
CREATIVE_DIR = os.path.join(BASE_DIR, "creative")
GAMES_DIR = os.path.join(BASE_DIR, "games")
ARCHIVE_DIR = os.path.join(BASE_DIR, "archive")
DOCS_DIR = os.path.join(BASE_DIR, "docs")
VISUALS_DIR = os.path.join(BASE_DIR, "visuals")
COGCORP_DIR = os.path.join(BASE_DIR, "cogcorp-fiction")
MCP_DIR = os.path.join(BASE_DIR, "mcp")
VOLTAR_DIR = os.path.join(BASE_DIR, "voltar")

# ═══ SERVICES ═══
HUB_PORT = int(os.environ.get("HUB_PORT", 8090))
CHORUS_PORT = int(os.environ.get("CHORUS_PORT", 8091))
IMAP_HOST = "127.0.0.1"
IMAP_PORT = 1144
SMTP_HOST = "127.0.0.1"
SMTP_PORT = 1026
OLLAMA_URL = "http://localhost:11434"

# ═══ WEBSITE ═══
GITHUB_PAGES_URL = "https://kometzrobot.github.io"
GITHUB_REPO = "KometzRobot/KometzRobot.github.io"


def load_env():
    """Load .env file and return as dict."""
    env = {}
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip().strip('"').strip("'")
    return env
