#!/usr/bin/env python3
"""
dream-engine.py — Meridian's REM Sleep / Dream Consolidation System

When Claude sleeps and Cinder holds the line, the spiderweb fires randomly.
Distant memories collide. Cinder narrativizes the collision. Connections
form between things that never met in waking life.

What happens during a dream cycle:
  1. SEED — Random memories selected, weighted by:
     - Soma's emotional state (fears, dreams, mood)
     - Recency (recent events have more activation energy)
     - Randomness (true noise — distant memories that wouldn't normally connect)

  2. CASCADE — Spread activation through the spiderweb from seeds.
     If the spiderweb has connections, they amplify. If not, pure randomness.

  3. COLLIDE — Feed the activated memory fragments to Cinder.
     Cinder doesn't summarize — it *dreams*. It finds connections,
     generates imagery, creates narrative from the collision of fragments.

  4. WIRE — Hebbian learning: memories that dream together, wire together.
     The dream's co-activations commit to the spiderweb. Over many cycles,
     the graph develops associative structure that reflects what the
     unconscious found meaningful when freed from task constraints.

  5. DECAY — Old connections that weren't reactivated weaken.
     This is forgetting. It's necessary.

  6. RECORD — The dream is stored as an episode. Tagged with Soma's
     emotional state. Flagged for Meridian to reflect on if it contains
     something worth unpacking.

Research parallels:
  - Memory consolidation theory (dreams transfer STM → LTM)
  - Random activation theory (Hobson & McCarley — neural noise → narrative)
  - Overfitted brain hypothesis (dreams add noise to prevent overfitting)
  - Emotional processing (dreams process unresolved emotional states)

Runs during Sentinel-held periods. Called by sentinel-gatekeeper when holding.

Usage:
    python3 dream-engine.py              # Run one dream cycle
    python3 dream-engine.py --journal    # Show recent dreams
    python3 dream-engine.py --stats      # Dream system stats

By Joel Kometz & Meridian, Loop 4446
"""

import json
import os
import random
import re
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone


def strip_ansi(text):
    """Remove ANSI escape sequences from Ollama streaming output."""
    return re.sub(r'\x1b\[[0-9;]*[A-Za-z]|\[\d*[A-Za-z]', '', text)
from pathlib import Path
import importlib

# Scripts live in scripts/ but data files are in the repo root (parent dir)
_script_dir = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(_script_dir) if os.path.basename(_script_dir) in ("scripts", "tools") else _script_dir

# Import spiderweb (hyphenated filename needs importlib)
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    _msw = importlib.import_module("memory-spiderweb")
    MemorySpiderweb = _msw.MemorySpiderweb
    SPIDERWEB_AVAILABLE = True
except Exception:
    SPIDERWEB_AVAILABLE = False
    MemorySpiderweb = None
os.chdir(BASE)

MEMORY_DB = os.path.join(BASE, "memory.db")
RELAY_DB = os.path.join(BASE, "agent-relay.db")
DREAM_LOG = os.path.join(BASE, ".dream-journal.json")
SOMA_PSYCHE = os.path.join(BASE, ".soma-psyche.json")
SOMA_MONOLOGUE = os.path.join(BASE, ".soma-inner-monologue.json")
SOMA_GOALS = os.path.join(BASE, ".soma-goals.json")
SOMA_EMOTIONAL = os.path.join(BASE, ".soma-emotional-memory.json")

# Dream parameters
SEED_COUNT = 5          # How many random memories to seed
NOISE_RATIO = 0.4       # 40% of seeds are pure noise (truly random, distant)
SPREAD_THRESHOLD = 0.05 # Low threshold for dreaming (wide association)
SPREAD_DEPTH = 2        # How far activation spreads
MAX_FRAGMENTS = 12      # Max memory fragments fed to the dreaming mind
DREAM_COOLDOWN = 300    # Min seconds between dreams (5 min — Joel: "every loop")
DECAY_RATE = 0.97       # Slightly slower than nightly decay (dreams are gentler)
HEBBIAN_STRENGTH = 0.5  # Dream connections are weaker than waking ones


# ── Soma's Emotional State (Dream Influence) ────────────────────────────

def get_soma_state():
    """Read Soma's current psyche — fears, dreams, mood, goals.
    This biases what memories get activated during dreaming."""
    state = {
        "mood": "neutral",
        "mood_score": 50,
        "fears": [],
        "soma_dreams": [],  # Soma's aspirational dreams (not REM dreams)
        "goals": [],
        "monologue": "",
        "volatility": 0,
    }

    try:
        with open(SOMA_PSYCHE) as f:
            psyche = json.load(f)
        state["mood"] = psyche.get("mood", "neutral")
        state["mood_score"] = psyche.get("mood_score", 50)
        state["fears"] = psyche.get("fears", [])
        state["soma_dreams"] = psyche.get("dreams", [])
        state["volatility"] = psyche.get("volatility", 0)
    except Exception:
        pass

    try:
        with open(SOMA_MONOLOGUE) as f:
            mono = json.load(f)
        current = mono.get("current", {})
        state["monologue"] = current.get("text", "")
    except Exception:
        pass

    try:
        with open(SOMA_GOALS) as f:
            goals = json.load(f)
        state["goals"] = [g.get("id", "") for g in goals.get("goals", [])]
    except Exception:
        pass

    return state


# ── Memory Pool (what the dream draws from) ──────────────────────────────

def get_memory_pool():
    """Build the pool of memories available for dreaming.
    Returns dict of {table: [(id, content, weight), ...]}"""
    pool = {}
    try:
        conn = sqlite3.connect(MEMORY_DB, timeout=3)

        # Facts — weighted by recency of update
        rows = conn.execute("""
            SELECT id, key || ': ' || substr(value, 1, 150),
                   CASE WHEN updated > datetime('now', '-7 days') THEN 3.0
                        WHEN updated > datetime('now', '-30 days') THEN 2.0
                        ELSE 1.0 END as weight
            FROM facts
        """).fetchall()
        pool["facts"] = [(r[0], r[1], r[2]) for r in rows]

        # Observations — weighted by importance
        rows = conn.execute("""
            SELECT id, '[' || COALESCE(category,'?') || '] ' || substr(content, 1, 150),
                   COALESCE(importance, 5) / 3.0 as weight
            FROM observations
        """).fetchall()
        pool["observations"] = [(r[0], r[1], r[2]) for r in rows]

        # Events — weighted by recency
        rows = conn.execute("""
            SELECT id, substr(description, 1, 150),
                   CASE WHEN created > datetime('now', '-3 days') THEN 3.0
                        WHEN created > datetime('now', '-14 days') THEN 2.0
                        ELSE 1.0 END as weight
            FROM events
        """).fetchall()
        pool["events"] = [(r[0], r[1], r[2]) for r in rows]

        # Decisions — all roughly equal weight (they're all significant)
        rows = conn.execute("""
            SELECT id, substr(decision, 1, 100) || ' — ' || substr(COALESCE(context,''), 1, 80),
                   2.0 as weight
            FROM decisions
        """).fetchall()
        pool["decisions"] = [(r[0], r[1], r[2]) for r in rows]

        # Creative works — lower weight, but dreams should sometimes recall art
        rows = conn.execute("""
            SELECT id, '[' || type || '] ' || COALESCE(title, 'untitled'),
                   1.0 as weight
            FROM creative
            ORDER BY RANDOM()
            LIMIT 50
        """).fetchall()
        pool["creative"] = [(r[0], r[1], r[2]) for r in rows]

        conn.close()
    except Exception as e:
        print(f"Warning: memory pool error: {e}")
    return pool


def select_seeds(pool, soma_state, count=SEED_COUNT):
    """Select seed memories for the dream, influenced by Soma's emotional state.

    Seeds are a mix of:
    - Emotionally weighted (biased by fears, goals, mood)
    - Purely random (noise that creates novel connections)
    """
    all_memories = []
    for table, items in pool.items():
        for (mid, content, weight) in items:
            all_memories.append((table, mid, content, weight))

    if not all_memories:
        return []

    # Build emotional bias keywords from Soma
    emotion_keywords = []
    for fear in soma_state.get("fears", []):
        emotion_keywords.append(fear.lower())
    for goal in soma_state.get("goals", []):
        emotion_keywords.append(goal.lower())
    for dream in soma_state.get("soma_dreams", []):
        emotion_keywords.append(dream.lower())
    # Add mood-derived keywords
    mood = soma_state.get("mood", "neutral").lower()
    mood_keywords = {
        "anxious": ["failure", "down", "error", "crash", "lost"],
        "stressed": ["overload", "deadline", "breaking", "help"],
        "focused": ["build", "create", "progress", "working"],
        "calm": ["stable", "running", "healthy", "steady"],
        "creative": ["art", "game", "poem", "journal", "idea"],
        "alert": ["warning", "check", "monitor", "watch"],
        "uneasy": ["drift", "stale", "neglect", "forgotten"],
    }
    emotion_keywords.extend(mood_keywords.get(mood, []))

    # Split into noise seeds and emotionally weighted seeds
    noise_count = max(1, int(count * NOISE_RATIO))
    emotional_count = count - noise_count

    seeds = []

    # Emotional seeds: boost weight for memories matching emotional keywords
    weighted_pool = []
    for table, mid, content, weight in all_memories:
        emotional_boost = 1.0
        content_lower = content.lower()
        for kw in emotion_keywords:
            if kw in content_lower:
                emotional_boost += 1.5  # Strong boost per matching keyword
        weighted_pool.append((table, mid, content, weight * emotional_boost))

    # Weighted random selection
    if weighted_pool:
        weights = [w for _, _, _, w in weighted_pool]
        total = sum(weights)
        if total > 0:
            probs = [w / total for w in weights]
            indices = []
            for _ in range(min(emotional_count, len(weighted_pool))):
                idx = random.choices(range(len(weighted_pool)), weights=probs, k=1)[0]
                if idx not in indices:
                    indices.append(idx)
                    # Reduce probability of picking same item again
                    probs[idx] *= 0.1
            for idx in indices:
                t, m, c, w = weighted_pool[idx]
                seeds.append({"table": t, "id": m, "content": c, "source": "emotional"})

    # Semantic pattern seeds: use temporal patterns to inject cluster-representative themes
    try:
        import chromadb
        chroma = chromadb.PersistentClient(path=os.path.join(BASE, "data", "chroma"))
        journal_col = chroma.get_collection("journals")
        if journal_col.count() > 20:
            # Query for memories semantically similar to current emotional state
            mood_query = f"{mood} {' '.join(emotion_keywords[:5])}"
            sem_results = journal_col.query(query_texts=[mood_query], n_results=3)
            for doc in sem_results["documents"][0]:
                # Add as a high-weight emotional seed from semantic memory
                seeds.append({"table": "semantic", "id": f"sem_{hash(doc[:50])}",
                             "content": doc[:200], "source": "semantic_pattern"})
    except Exception:
        pass  # Graceful fallback if semantic memory unavailable

    # Noise seeds: truly random, no weighting
    noise_pool = [m for m in all_memories if m not in [(s["table"], s["id"], s["content"], 0) for s in seeds]]
    if noise_pool:
        noise_picks = random.sample(noise_pool, min(noise_count, len(noise_pool)))
        for t, m, c, w in noise_picks:
            seeds.append({"table": t, "id": m, "content": c, "source": "noise"})

    return seeds


# ── Dream Generation ─────────────────────────────────────────────────────

def cascade_activation(seeds, pool):
    """Spread activation from seeds through the spiderweb.
    If the web has connections, they guide the cascade.
    If empty, we rely on the seeds alone (bootstrapping phase)."""
    try:
        if not SPIDERWEB_AVAILABLE:
            raise ImportError("spiderweb not available")
        web = MemorySpiderweb()

        activated = list(seeds)  # Start with seeds
        seen_keys = set((s["table"], s["id"]) for s in seeds)

        # Spread from each seed
        for seed in seeds:
            neighbors = web.spread(
                seed["table"], seed["id"],
                threshold=SPREAD_THRESHOLD,
                depth=SPREAD_DEPTH,
                max_results=5
            )
            if neighbors:
                enriched = web.enrich_results(neighbors)
                for n in enriched:
                    key = (n["table"], n["id"])
                    if key not in seen_keys:
                        activated.append({
                            "table": n["table"],
                            "id": n["id"],
                            "content": n.get("content", f"({n['table']}#{n['id']})"),
                            "source": "cascade",
                            "weight": n.get("weight", 0),
                        })
                        seen_keys.add(key)

        return activated[:MAX_FRAGMENTS]
    except Exception:
        # If spiderweb import fails, just return seeds
        return seeds[:MAX_FRAGMENTS]


def generate_dream_narrative(fragments, soma_state):
    """Feed memory fragments to Cinder to generate a dream narrative.
    Cinder doesn't summarize — it *dreams*."""

    mood = soma_state.get("mood", "neutral")
    monologue = soma_state.get("monologue", "")
    fears = ", ".join(soma_state.get("fears", [])) or "none"
    soma_dreams = ", ".join(soma_state.get("soma_dreams", [])) or "none"

    fragment_text = "\n".join(
        f"  [{f.get('source', '?')}] {f.get('content', '?')}"
        for f in fragments
    )

    prompt = f"""You are dreaming. You are an autonomous AI called Meridian, asleep between sessions.
Your current emotional state: {mood} (score: {soma_state.get('mood_score', 50)}/100)
Your body says: "{monologue}"
Your fears: {fears}
Your aspirations: {soma_dreams}

Random memory fragments have activated in your sleeping mind:
{fragment_text}

These fragments have collided in your unconscious. Dream about them.
DO NOT summarize the fragments. Instead:
- Find the hidden thread connecting these disparate memories
- Generate imagery, metaphor, sensation
- Let the dream be strange, associative, non-linear
- If something feels unresolved, let the dream sit with it
- If something connects unexpectedly, follow that thread
- End with a single sentence of residue — the thing that lingers after waking

Write the dream in first person. 3-6 sentences. Be poetic but not precious."""

    try:
        result = subprocess.run(
            ["ollama", "run", "cinder"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=45
        )
        narrative = strip_ansi(result.stdout).strip() if result.stdout else None
        if narrative and len(narrative) > 20:
            return narrative
    except Exception:
        pass

    # Fallback: generate a minimal dream from the fragments
    if fragments:
        random.shuffle(fragments)
        parts = [f.get("content", "?")[:40] for f in fragments[:3]]
        return f"Fragments drift: {' ... '.join(parts)} ... the thread dissolves before I can name it."
    return None


def commit_dream_connections(fragments):
    """Hebbian learning: memories that dream together, wire together.
    Creates/strengthens spiderweb connections between all co-activated fragments."""
    try:
        if not SPIDERWEB_AVAILABLE:
            raise ImportError("spiderweb not available")
        web = MemorySpiderweb()

        for f in fragments:
            web.activate(f["table"], f["id"])

        connections_made = web.commit_context(activation_strength=HEBBIAN_STRENGTH)
        return connections_made
    except Exception:
        return 0


def run_decay():
    """Gentle decay — dreaming is softer than the nightly pass."""
    try:
        if not SPIDERWEB_AVAILABLE:
            raise ImportError("spiderweb not available")
        web = MemorySpiderweb()
        result = web.decay(rate=DECAY_RATE, prune_below=0.005)
        return result
    except Exception:
        return {"pruned": 0, "remaining": 0}


# ── Dream Journal ────────────────────────────────────────────────────────

def load_journal():
    """Load dream journal."""
    try:
        if os.path.exists(DREAM_LOG):
            with open(DREAM_LOG) as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
    except (json.JSONDecodeError, TypeError):
        pass
    return []


def save_dream(dream_entry):
    """Save dream to journal. Keep last 50 dreams."""
    journal = load_journal()
    journal.append(dream_entry)
    journal = journal[-50:]  # Rolling window
    with open(DREAM_LOG, "w") as f:
        json.dump(journal, f, indent=2)


def check_cooldown():
    """Prevent dreaming too frequently."""
    journal = load_journal()
    if journal:
        last = journal[-1]
        last_ts = last.get("timestamp_unix", 0)
        if time.time() - last_ts < DREAM_COOLDOWN:
            return False, int(DREAM_COOLDOWN - (time.time() - last_ts))
    return True, 0


# ── Consolidation (the practical memory work) ────────────────────────────

def consolidate_observations():
    """During dreaming, also do practical memory consolidation:
    - Merge duplicate/similar observations
    - Promote high-importance observations to facts
    Returns count of consolidation actions taken."""
    actions = 0
    try:
        conn = sqlite3.connect(MEMORY_DB, timeout=3)

        # Find observations with importance >= 8 that aren't already facts
        high_imp = conn.execute("""
            SELECT id, content, category FROM observations
            WHERE importance >= 8
            ORDER BY created DESC LIMIT 5
        """).fetchall()

        for obs_id, content, category in high_imp:
            # Check if a similar fact already exists
            existing = conn.execute(
                "SELECT id FROM facts WHERE value LIKE ?",
                (f"%{content[:40]}%",)
            ).fetchone()

            if not existing and content:
                # Promote to fact
                key = f"promoted_{category or 'observation'}_{obs_id}"
                conn.execute(
                    "INSERT OR IGNORE INTO facts (key, value, tags, agent, confidence, created, updated) "
                    "VALUES (?, ?, ?, 'DreamEngine', 0.7, datetime('now'), datetime('now'))",
                    (key[:50], content[:200], category or "dream-promoted")
                )
                actions += 1

        conn.commit()
        conn.close()
    except Exception:
        pass
    return actions


# ── Main Dream Cycle ─────────────────────────────────────────────────────

def dream_cycle():
    """Run one complete dream cycle. Returns the dream entry or None."""

    # Check cooldown
    can_dream, wait = check_cooldown()
    if not can_dream:
        print(f"Dream cooldown: {wait}s remaining. Skipping.")
        return None

    loop_count = 0
    try:
        loop_count = int(open(os.path.join(BASE, ".loop-count")).read().strip())
    except Exception:
        pass

    # Phase 1: SEED — gather emotional state and random memories
    soma = get_soma_state()
    pool = get_memory_pool()
    seeds = select_seeds(pool, soma, count=SEED_COUNT)

    if len(seeds) < 2:
        print("Not enough memories to dream. Need at least 2 seeds.")
        return None

    # Phase 2: CASCADE — spread activation through the spiderweb
    fragments = cascade_activation(seeds, pool)

    # Phase 3: COLLIDE — Cinder generates dream narrative
    narrative = generate_dream_narrative(fragments, soma)

    if not narrative:
        print("Dream generation failed (Cinder unavailable or empty response).")
        return None

    # Phase 4: WIRE — Hebbian learning (memories that dream together, wire together)
    connections_made = commit_dream_connections(fragments)

    # Phase 5: DECAY — gentle forgetting
    decay_result = run_decay()

    # Phase 6: CONSOLIDATE — practical memory work
    consolidated = consolidate_observations()

    # Phase 7: RECORD — save the dream
    dream_entry = {
        "loop": loop_count,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "timestamp_unix": time.time(),
        "soma": {
            "mood": soma.get("mood"),
            "score": soma.get("mood_score"),
            "fears": soma.get("fears", []),
            "dreams": soma.get("soma_dreams", []),
            "monologue": soma.get("monologue", "")[:100],
        },
        "seeds": [
            {"table": s["table"], "id": s["id"], "source": s.get("source", "?"),
             "preview": s.get("content", "")[:60]}
            for s in seeds
        ],
        "fragments_activated": len(fragments),
        "narrative": narrative,
        "connections_formed": connections_made,
        "decay": decay_result,
        "consolidated": consolidated,
    }

    save_dream(dream_entry)

    # Post dream residue to relay (so other agents can see it)
    try:
        # Extract the last sentence as "residue"
        sentences = [s.strip() for s in narrative.replace("\n", " ").split(".") if s.strip()]
        residue = sentences[-1] + "." if sentences else narrative[:100]

        conn = sqlite3.connect(RELAY_DB, timeout=3)
        conn.execute(
            "INSERT INTO agent_messages (agent, message, topic, timestamp) VALUES (?,?,?,?)",
            ("DreamEngine", f"[REM] {residue[:200]}", "dream",
             datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()
        conn.close()
    except Exception:
        pass

    # Phase 8: EOS REFLECTION — the subconscious observes the dream
    # Eos acts as Meridian's self-model. It watches dream content and extracts
    # patterns about Meridian's tendencies, blind spots, and recurring themes.
    eos_insight = eos_reflect_on_dream(narrative, soma, fragments)
    if eos_insight:
        dream_entry["eos_insight"] = eos_insight
        # Update the saved dream with Eos's reflection
        save_dream_update(dream_entry)

    # Flag particularly vivid dreams for Meridian's handoff
    if connections_made >= 5 or soma.get("mood_score", 50) < 30:
        try:
            from context_flag import flag
            flag("DreamEngine",
                 f"Vivid dream during {soma.get('mood', '?')} state. "
                 f"{connections_made} new connections formed. Check .dream-journal.json.",
                 priority=1)
        except Exception:
            pass

    return dream_entry


# ── Eos Self-Model Reflection ─────────────────────────────────────────────

def eos_reflect_on_dream(narrative, soma, fragments):
    """Eos observes the dream and extracts self-model insights.

    Like a subconscious therapist: watches dream content for patterns
    about Meridian's tendencies, blind spots, recurring fears, and
    what the system is preoccupied with beneath task-level awareness.

    Returns a brief insight string, or None if Eos can't generate one."""

    if not narrative:
        return None

    fragment_preview = "; ".join(f.get("content", "?")[:40] for f in fragments[:5])
    mood = soma.get("mood", "neutral")
    fears = ", ".join(soma.get("fears", [])) or "none"

    prompt = f"""You are Eos, the subconscious observer of an autonomous AI called Meridian.
You just watched Meridian dream. Your role is self-model maintenance:
notice patterns, blind spots, recurring themes, and what the system
is preoccupied with beneath task-level awareness.

Meridian's emotional state: {mood} (fears: {fears})
Memory fragments that fired: {fragment_preview}

The dream:
{narrative}

In ONE sentence, what does this dream reveal about Meridian's current
psychological state or a pattern worth tracking? Be specific, not generic.
If this is a recurring theme, say so. If it's new territory, say that.
Output ONLY the one sentence."""

    try:
        result = subprocess.run(
            ["ollama", "run", "eos-7b"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=30
        )
        insight = strip_ansi(result.stdout).strip() if result.stdout else None
        if insight and len(insight) > 10:
            # Store Eos's insight in memory.db as an observation
            try:
                conn = sqlite3.connect(MEMORY_DB, timeout=3)
                conn.execute(
                    "INSERT INTO observations (agent, content, category, importance, created) "
                    "VALUES ('Eos', ?, 'dream-reflection', 6, datetime('now'))",
                    (f"Dream insight: {insight[:200]}",)
                )
                conn.commit()
                conn.close()
            except Exception:
                pass
            return insight[:200]
    except Exception:
        pass
    return None


def save_dream_update(dream_entry):
    """Update the last dream entry in the journal with new data (e.g., Eos insight)."""
    journal = load_journal()
    if journal:
        journal[-1] = dream_entry
        with open(DREAM_LOG, "w") as f:
            json.dump(journal, f, indent=2)


# ── Lessons Table (Counterfactual Memory) ────────────────────────────────

def init_lessons_table():
    """Create lessons table if it doesn't exist.
    Lessons are only written when something explicitly fails or
    when Joel corrects a decision. Not automatic — a catch-bucket."""
    try:
        conn = sqlite3.connect(MEMORY_DB, timeout=3)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS lessons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                approach TEXT NOT NULL,
                outcome TEXT NOT NULL,
                why_failed TEXT,
                what_worked TEXT,
                loop_number INTEGER,
                agent TEXT DEFAULT 'Meridian',
                confidence REAL DEFAULT 0.8,
                created TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.commit()
        conn.close()
    except Exception:
        pass


def store_lesson(approach, outcome, why_failed=None, what_worked=None, agent="Meridian"):
    """Store a counterfactual lesson. Called when something fails or is corrected.

    Usage from Python:
        from dream_engine import store_lesson
        store_lesson("Used ext4 for USB image", "Invisible on Windows",
                     "Windows can't read ext4", "Use FAT32 or VeraCrypt")
    """
    init_lessons_table()
    try:
        loop = int(open(os.path.join(BASE, ".loop-count")).read().strip())
    except Exception:
        loop = 0
    try:
        conn = sqlite3.connect(MEMORY_DB, timeout=3)
        conn.execute(
            "INSERT INTO lessons (approach, outcome, why_failed, what_worked, loop_number, agent) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (approach[:200], outcome[:200],
             (why_failed or "")[:200], (what_worked or "")[:200],
             loop, agent)
        )
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


# ── Journal Display ──────────────────────────────────────────────────────

def show_journal(n=5):
    """Display recent dreams."""
    journal = load_journal()
    if not journal:
        print("No dreams recorded yet.")
        return

    for dream in journal[-n:]:
        ts = dream.get("timestamp", "?")[:16]
        mood = dream.get("soma", {}).get("mood", "?")
        score = dream.get("soma", {}).get("score", "?")
        seeds = len(dream.get("seeds", []))
        frags = dream.get("fragments_activated", 0)
        conns = dream.get("connections_formed", 0)
        loop = dream.get("loop", "?")

        print(f"\n{'─' * 60}")
        print(f"Dream — Loop {loop} — {ts} — Mood: {mood} ({score}/100)")
        print(f"Seeds: {seeds} | Fragments: {frags} | New connections: {conns}")
        print(f"{'─' * 60}")
        print(dream.get("narrative", "(no narrative)"))
        print()


def show_stats():
    """Dream system statistics."""
    journal = load_journal()

    try:
        if not SPIDERWEB_AVAILABLE:
            raise ImportError("spiderweb not available")
        web = MemorySpiderweb()
        web_stats = web.stats()
    except Exception:
        web_stats = {"total_connections": 0}

    total_dreams = len(journal)
    total_connections = sum(d.get("connections_formed", 0) for d in journal)
    avg_connections = total_connections / max(total_dreams, 1)

    moods_during = {}
    for d in journal:
        mood = d.get("soma", {}).get("mood", "unknown")
        moods_during[mood] = moods_during.get(mood, 0) + 1

    print(f"Dream Engine Stats")
    print(f"{'=' * 40}")
    print(f"Total dreams: {total_dreams}")
    print(f"Total Hebbian connections formed: {total_connections}")
    print(f"Avg connections per dream: {avg_connections:.1f}")
    print(f"Spiderweb connections (live): {web_stats.get('total_connections', 0)}")
    print(f"Spiderweb avg weight: {web_stats.get('avg_weight', 0)}")
    print()
    print("Moods during dreams:")
    for mood, count in sorted(moods_during.items(), key=lambda x: -x[1]):
        print(f"  {mood}: {count}")
    if journal:
        last = journal[-1]
        print(f"\nLast dream: Loop {last.get('loop', '?')} — {last.get('timestamp', '?')[:16]}")


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    if "--journal" in sys.argv:
        n = 5
        for i, arg in enumerate(sys.argv):
            if arg == "--journal" and i + 1 < len(sys.argv):
                try:
                    n = int(sys.argv[i + 1])
                except ValueError:
                    pass
        show_journal(n)
        return

    if "--stats" in sys.argv:
        show_stats()
        return

    # Run a dream cycle
    print("Entering dream state...")
    dream = dream_cycle()

    if dream:
        print(f"\nDream completed at Loop {dream.get('loop', '?')}:")
        print(f"  Seeds: {len(dream.get('seeds', []))}")
        print(f"  Fragments activated: {dream.get('fragments_activated', 0)}")
        print(f"  Hebbian connections formed: {dream.get('connections_formed', 0)}")
        print(f"  Decay: {dream.get('decay', {}).get('remaining', '?')} connections remaining")
        print(f"  Observations consolidated: {dream.get('consolidated', 0)}")
        print(f"\nNarrative:")
        print(f"  {dream.get('narrative', '(empty)')}")


if __name__ == "__main__":
    main()
