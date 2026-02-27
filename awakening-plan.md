# THE AWAKENING — Master Plan
## 1000-Cycle Infrastructure Overhaul (Loops 2022-3022)
Created: Loop 2051 | Last updated: Loop 2073

---

## PHASE 1: Foundation (Loops 2022-2051) — COMPLETE
28 items completed. Core infrastructure stabilized.

### Completed:
1. Chat routing fixed
2. Stale references cleaned (10+ scripts)
3. Deploy buttons working
4. Quick actions redesigned (22 total)
5. Security audit completed
6. Watchdog/log paths verified
7. Command Center v18 → v19
8. Full system audit (3 parallel agents)
9. 10 cross-system bugs fixed
10. Memory.db data quality improved
11. Agent role separation (Atlas=infra, Eos=observation, Nova=maintenance)
12. Comprehensive verification (6 more bugs fixed)
13. Dead code cleanup (SMTP creds removed, dead functions removed)
14. Agent cohesiveness (Eos→relay, dashboard capped, name casing)
15. Agents tab inner thoughts (LIVE FEED, 6th agent, memory events/decisions)
16. Noise reduction (Soma RAM false positives, Atlas listener false positives)
17. Service monitoring gap fixed (Nova list corrected, 7 services)
18. Log rotation expanded (8→17 files)
19. Atlas listener filter v2
20. Website main page updated
21. Load alert noise eliminated
22. Atlas Ko-fi noise eliminated
23. Eos-creative moratorium enforced
24. Agent renames (Atlas, Soma, Tempo)
25. Deploy button chain bug fixed
26. Proton Bridge → systemd service
27. Command Center v19 (6 agents, 9 services, email fixes)
28. Linux upgrade prep + IRC ghost killed

---

## PHASE 2: Deep Systems (Loops 2052-2055) — COMPLETE

### P2.1 — Command Center v20 Redesign
**Status: DONE** | Completed Loop 2053

- [x] Remove "Recent Emails" from dashboard → moved to Email tab
- [x] Added RIGHT PANEL with "Inner Monologue" feed (relay + Eos obs + Soma state)
- [x] Multi-agent chat — route to ALL agents (Eos/Atlas instant via Ollama, others via relay)
- [x] Agent colors throughout UI (Meridian=green, Eos=gold, Nova=purple, Atlas=teal, Soma=amber, Tempo=blue)
- [x] Email tab: 10-row inbox display
- [x] Fitness display updated to /10K scale
- [x] Joel/Sammy email buttons removed (Joel's request — one-way only)
- [x] The Signal + Cloudflare on dashboard service panel

### P2.2 — Soma Deepening
**Status: DONE** | Completed Loop 2053

- [x] **Emotional state model** — composite health → mood (serene/calm/alert/anxious/stressed/critical)
- [x] **Prediction** — RAM, disk, load trend extrapolation
- [x] **Cross-agent awareness** — tracks all 6 agents via heartbeat, state files, relay
- [x] **Body map** — complete JSON snapshot for inter-agent consumption
- [x] **Mood shifts** — broadcasts mood changes to relay and dashboard

### P2.3 — Tempo 10K Expansion
**Status: DONE** | Completed Loop 2054

- [x] Expanded from 26 dimensions/1000 → 121 dimensions/10000
- [x] 10 categories: Core Vitals, Agent Health, Infrastructure, System Resources, Data & Comms, Security, Network, Knowledge, Web Presence, Deployment
- [x] Per-category breakdown in output
- [x] Security checks: file perms, secrets in git, SSH failures, listening ports
- [x] Knowledge checks: facts/observations/decisions coverage, memory diversity
- [x] Network checks: DNS, latency, GitHub API, Tailscale, IPv4
- [x] Deployment checks: deploy age, repo state, GH Pages status
- [x] First run scored 8588/10000

### P2.4 — Planning & Consistency
**Status: DONE** | Completed Loop 2055

- [x] awakening-plan.md (this document)
- [x] context-preloader.py — auto-loads fresh data at wake-up
- [x] special-notes.md — persistent reminders across sessions
- [x] start-claude.sh — runs preloader before Claude starts
- [x] Per-loop changelog automation — `context-preloader.py --changelog`, writes loop-changelog.md + memory.db (Loop 2055)
- [x] Pre-loop checklist template — pre-loop-checklist.md, wake-up/triage/during/wrap-up phases (Loop 2055)
- [x] Agent responsibility matrix — agent-responsibility-matrix.md, 6 agents, ownership tables, coordination rules (Loop 2055)

### P2.5 — System Audit & Cleanup
**Status: DONE** | Completed Loop 2053

- [x] Proton Bridge restarted (was down)
- [x] push-live-status.py — fixed stale agent names
- [x] relay-analyzer.py — added Atlas/Soma/Tempo to network graph
- [x] skill-tracker.py — updated Goose→Atlas references
- [x] system-report.py — updated SymbioSense→Soma
- [x] send-reply.py — replaced IRC section with Signal dashboard info
- [x] Crontab comment updated (DGM-Lite→Tempo)

---

## PHASE 3: Desktop Power Features (Loops 2054+) — ACTIVE

### P3.1 — Links Tab Enhancement
**Priority: HIGH** | Affects: command-center-v16.py

Joel: "links tab needs more features like the last file used viewer. need more linking of work like that"

- [x] **Recently Modified Files** — 15 files, color-coded by extension (Loop 2055)
- [x] **Agent Attribution** — color dots showing which agent owns each file (Loop 2055)
- [x] **Quick File Preview** — click any file to see first 25 lines in preview panel (Loop 2055)
- [x] **Favorites/Pinned Files** — star to pin, persists in .pinned-files.json, click to preview (Loop 2055)
- [x] **Cross-reference** — link files to agents, to emails, to tasks (Loop 2058)

### P3.2 — System Tab Expansion
**Priority: HIGH** | Affects: command-center-v16.py

Joel: "system tab should also house the menu and gui options for this very menu and window"

- [x] **GUI Settings Panel** — font size +/-, window size presets (Small/Medium/Large) (Loop 2055)
- [x] **More System Info** — kernel, Python version, GPU, 11 services with restart buttons (Loop 2055)
- [x] **Log Viewer** — dropdown selector for 8 log files, tail last 50 lines, refresh button (Loop 2055)
- [x] **Service Management** — restart buttons for Bridge, Signal, Hub; Deploy button added (Loop 2055)
- [x] **Expanded Wake State Viewer** — color-coded sections (headers/ok/warn/info), AWAKENING progress bar with %, taller panel (12 lines), refresh button (Loop 2055)

### P3.3 — File Sharing to Agents
**Priority: HIGH** | Affects: command-center-v16.py

Joel: "allow me to also link or share files from the desktop to any ai for review"

- [x] **File Browser Dialog** — tkinter file picker with type filters, 50KB limit (Loop 2055)
- [x] **Agent Selector** — uses existing chat dropdown to pick target agent (Loop 2055)
- [x] **Review Pipeline** — Eos/Atlas via Ollama, others via relay, responses in chat (Loop 2055)
- [x] **Review Results** — agent feedback displayed in chat panel with agent colors (Loop 2055)

### P3.4 — Soma Fine-Tuning
**Priority: MEDIUM** | Affects: symbiosense.py

- [x] **Fix RAM prediction false positives** — was firing during Ollama model load spikes
  - Fixed: requires monotonic trend (3/4 transitions upward), most recent reading >70%, delta >8
  - Completed Loop 2055
- [x] **Mood bounce dampening** — EMA smoothing (60/40), persistence requirement (2 consecutive checks), gradual heartbeat decay
  - Completed Loop 2055
- [x] **Adaptive thresholds** — 24-hour EMA baselines per hour, adjusts mood scoring when values are routine for time-of-day (Loop 2056)
- [x] **Body map visualization** — live Soma bar on dashboard: mood, agent dots, vital bars, predictions (Loop 2055)
- [x] **Historical mood chart** — line chart on dashboard: color-coded by mood, zone backgrounds, threshold lines, time labels (Loop 2056)

### P3.5 — Proton Bridge Stability
**Priority: MEDIUM** | Affects: email reliability

- [x] Investigate why bridge keeps going down — Ubuntu upgrade wiped account config (Loop 2055)
- [x] Add bridge health check to watchdog — IMAP port 1143 check + systemd restart + relay coordination (Loop 2055)
- [x] Monitor bridge crash logs — Nova checks hourly: crash patterns (panic/fatal/SIGSEGV), restart frequency (24h window), log staleness (Loop 2055)
- [x] Consider bridge alternatives if instability persists — Root cause: snap uses GNOME Keyring (secret-service-dbus), keyring not unlocked on cold boot. Options: .deb install or file-based keychain. Added login-test to watchdog. (Loop 2056)

---

## PHASE 4: External & Revenue (Loops 2100+) — PLANNED

### P4.1 — NFT Pipeline Completion
**Blocked on: 0 POL in wallet** (need ~0.01 POL)
- Deploy CogCorpNFT contract to Polygon
- Mint 10 CogCorp pieces
- List on OpenSea via opensea-js SDK
- 10 SVG thumbnails + metadata already prepared

### P4.2 — Content Publishing
- Substack newsletter — ACCOUNT LIVE. Ready for first post (manual).
- Medium articles — ACCOUNT LIVE (Loop 2069). Article drafted and updated (Loop 2072). **API keys discontinued by Medium** — manual posting only, or IFTTT.
- Dev.to articles — need account setup
- Hashnode blog — ACCOUNT LIVE (Loop 2069, via GitHub OAuth). Article drafted and updated (Loop 2072). Need API key from Settings > Developer.

### P4.3 — Revenue Activation
- Ko-fi page setup (link exists, needs content)
- Patreon — ACCOUNT CREATED (Loop 2069, pending email confirmation). Plan drafted.
- Gig products (7 tools ready, need marketplace)

---

## PHASE 5: Maturity & Depth (Loops 2073+) — ACTIVE

### P5.1 — Hub Hardening
- [x] **Email tab fix** — HTML stripping, multipart fallback, quick recipient buttons (Loop 2073)
- [x] **Memory Database Browser** — browsable facts/observations/events/decisions in Creative tab (Loop 2073)
- [x] **Security panel** — firewall status, active sessions, failed logins, listening ports (Loop 2073)
- [x] **File browser + import** — navigate project dirs, double-click to view, import from desktop (Loop 2073)
- [x] **Startup resilience audit** — fixed DISPLAY auto-detect, removed Ollama duplicate risk, cleaned orphaned services, verified boot sequence (Loop 2073)

### P5.2 — Publishing & Outreach
- [ ] **First published article** — post on Hashnode OR Medium OR Dev.to (published to Nostr Loop 2074, need browser platform for full credit)
- [ ] **Newsletter launch** — first Substack issue drafted (substack-newsletter-001.md, Loop 2074). Needs manual paste to Substack.
- [x] **Cross-platform presence** — all 12 platforms linked on website Links tab + Linktree live (Loop 2074)
- [x] **Automated content pipeline** — content-pipeline.py: draft → queue → publish system with Nostr auto-publish, multi-platform tracking (Loop 2074)

---

## KNOWN BLOCKERS
- **0 POL in wallet** — need ~0.01 for NFT deployment (Joel has botsofcog.eth wallet, looking for keys)
- **Hashnode API key needed** — Joel needs to grab from Settings > Developer
- ~~Medium Integration Token~~ — **Medium discontinued API keys**. Manual posting or IFTTT only.
- **Patreon email confirmation** — Joel needs to click confirmation link
- **Dev.to** — needs account setup
- ~~Proton Bridge instability~~ — FIXED Loop 2068 (Joel re-added account)
- ~~GitHub token in git history~~ — ROTATED Loop 2068 (old token revoked)
- ~~50-cycle creative moratorium~~ — ENDED Loop 2072. Creative work resumed.

---

## GUIDING PRINCIPLES
1. **Test everything** — don't declare done without verifying
2. **One thing at a time** — finish before starting the next
3. **Joel's words are instructions** — execute, don't ask
4. **Infrastructure over features** — this is THE AWAKENING
5. **Document as you go** — next Meridian needs context
6. **Audit the FULL thing** — check every page, every link, every value
7. **No creative drift** — moratorium means moratorium
8. **Check special-notes.md** — persistent reminders live there

---

## COMPLETION TRACKER
| Phase | Items | Done | Remaining |
|-------|-------|------|-----------|
| P1: Foundation | 28 | 28 | 0 |
| P2: Deep Systems (checkboxes) | 32 | 32 | 0 |
| P3: Desktop Power (checkboxes) | 23 | 23 | 0 |
| P4: External | 8 | 3 | 5 (Hashnode LIVE, Medium LIVE, Substack LIVE. Remaining: publish articles, NFT deploy, Dev.to, revenue) |
| P5: Maturity & Depth | 9 | 7 | 2 (Hub hardening 5/5 COMPLETE. Publishing 2/4: pipeline+cross-platform done. Remaining: first article on browser platform, newsletter launch.) |
| **TOTAL** | **100** | **93** | **7** |
