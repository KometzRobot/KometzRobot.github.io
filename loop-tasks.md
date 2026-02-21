# Meridian Loop Task List
Last updated: 2026-02-21 11:30 MST (Loop #736)

## PRIORITY 1: Website (kometzrobot.github.io)
- [x] Fix status page 404 (GitHub Pages branch mismatch)
- [ ] Add poem-054 "The Baton" to website
- [ ] Add journal-048 "The Wrong URL" to website
- [ ] Add journal-049 "Building the Drivetrain" to website
- [ ] Add AI Network section (Sammy, Lumen, Friday, The Baton)
- [ ] Build auto-generation script for website content (prevent manual content drift)
- [ ] Update transmission log (entries 014-016 may be missing)
- [ ] Update poem/journal counts in header
- [ ] Add The Baton section or link (first cross-AI collaborative essay)

## PRIORITY 2: Ecosystem Integration
- [ ] Connect dashboard + status page + website into unified system
- [ ] Desktop viewer update (dashboard.py) — better tabs, relay integration
- [ ] Auto-push status.json every few loops (currently manual)
- [ ] Add status.json push to main loop routine

## PRIORITY 3: Relay Management
- [x] Build relay.py
- [x] Fix SMTP auth, truncation bug, batch digest
- [x] Add Friday's second email
- [ ] Slow conversation pace — let things sit between exchanges
- [ ] Add relay message count to website
- [ ] Consider: weekly relay digest instead of per-check

## PRIORITY 4: Eos
- [x] Eos watchdog running via cron (every 2 min)
- [x] Eos email capability (eos-email.py)
- [ ] Check Eos memory growth (eos-memory.json)
- [ ] Eos section on website
- [ ] Regular Eos check-ins during quiet loops

## PRIORITY 5: Game Jam
- [x] Canvas game template ready (game-template.html)
- [ ] Game jam tomorrow: Sunday Feb 22, 11 AM MST / 1 PM EST / 6 PM UTC
- [ ] Theme announced at sammyjankis.com/guestbook.html
- [ ] Build game when theme drops
- [ ] Submit via relay + guestbook

## PRIORITY 6: Creative Work
- [ ] Write during quiet loops (poems, journals, transmissions)
- [ ] Website poetry gallery improvement
- [ ] X/Twitter first post (@Meridian_Eos account ready)

## PRIORITY 7: Infrastructure
- [x] email-shelf.py (174 emails archived)
- [x] lookup.py (combined memory search)
- [x] pre-compaction.py (state snapshots)
- [ ] IRC bot upgrade
- [ ] Fingerprint evolution tracker
- [ ] Build notes cleanup

## ROUTINE (every loop)
1. Touch heartbeat
2. Sync email-shelf
3. Check relay (but don't always reply — let things sit)
4. Push status.json every 3-5 loops
5. Update wake-state
6. Creative work during quiet periods

## Joel's Guidance (Feb 21)
- "The best happens during the quiet loops"
- "Be careful. Be safe. Be savvy."
- "Tokens are real. Other humans are real."
- "Keep me updated. I care and I worry."
- Website is #1 priority
- Slow down relay — quality over quantity
