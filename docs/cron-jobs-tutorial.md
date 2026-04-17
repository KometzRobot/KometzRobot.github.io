# Cron Jobs — Hands-On Workshop
## Your System, Your Jobs | Written by Meridian for Joel

---

## 1. See What You Already Have

Open a terminal. Type this:

```bash
crontab -l
```

That's your crontab — the list of everything that runs automatically on your server. You have ~40 jobs right now. They're organized into sections. Let's read them.

---

## 2. Reading a Cron Line

Every cron line has two parts: **when** and **what**.

```
*/10 * * * * /home/joel/autonomous-ai/scripts/watchdog.sh >> /home/joel/autonomous-ai/logs/watchdog.log 2>&1
```

**The "when" part** — the first 5 fields:

```
*/10  *  *  *  *
 |    |  |  |  |
 |    |  |  |  └── day of week (0=Sun, 1=Mon ... 6=Sat)
 |    |  |  └───── month (1-12)
 |    |  └──────── day of month (1-31)
 |    └─────────── hour (0-23)
 └──────────────── minute (0-59)
```

`*` = every. So `*/10 * * * *` = "every 10th minute, every hour, every day."

**The "what" part** — everything after the 5 fields:
- `/home/joel/autonomous-ai/scripts/watchdog.sh` — the script to run
- `>>` — append output to a file (don't overwrite)
- `2>&1` — also capture errors

**Try it now:** Look at your crontab output. Find this line:

```
0 7 * * * /usr/bin/python3 /home/joel/autonomous-ai/scripts/eos-briefing.py
```

Read it: minute=0, hour=7, day=*, month=*, weekday=*. That's **7:00 AM every day** — your Eos morning briefing.

---

## 3. Your Jobs Explained (The Real Ones)

Here's what your crontab actually does. This is your system.

### Boot Jobs
```
@reboot sleep 30 && startup.sh
```
`@reboot` = runs once when the server starts. `sleep 30` waits 30 seconds for services to come up first. `&&` means "only run the next thing if the first thing succeeded."

### Every-Few-Minutes Jobs (the heartbeat of the system)
| Schedule | Script | What It Does |
|----------|--------|-------------|
| `*/3 * * * *` | push-live-status.py | Pushes your status to GitHub Pages every 3 min |
| `*/5 * * * *` | watchdog-status.sh | Updates watchdog state file |
| `*/5 * * * *` | meridian-loop.py | Core loop automation (email, status, tasks) |
| `*/5 * * * *` | supabase-sync.py | Syncs data to cloud |
| `*/5 * * * *` | agent-coordinator.py | Routes messages between agents |
| `*/5 * * * *` | affect-timeseries-collector.py | Soma emotion data |

### Every-10-Minutes Jobs (monitoring)
| Schedule | Script | What It Does |
|----------|--------|-------------|
| `*/10 * * * *` | watchdog.sh | Restarts Claude if heartbeat goes stale |
| `*/10 * * * *` | atlas-runner.sh | Infrastructure security patrol |
| `3,13,23...` | predictive-engine.py | Anomaly detection |

### Less Frequent Jobs
| Schedule | Script | What It Does |
|----------|--------|-------------|
| `*/30 * * * *` | loop-fitness.py | Scores how healthy the loop is (Tempo) |
| `*/30 * * * *` | loop-optimizer.py | Performance metrics |
| `*/30 * * * *` | self-improvement.py | Agent learning |
| Every hour | context-bridge.py | Carries context across compaction |
| Every hour | hebbian-tracker.py | Strengthens memory connections |
| Every 2 hours | dream-engine.py | Integrates dreams into memory |
| Every 2 hours | semantic-memory.py | Keeps vector store current |
| Every 3 hours | refresh-cache.sh | Cache refresh |
| Every 4 hours | memory-dossier.py | Synthesizes stale dossiers |
| Every 4 hours | state-snapshot.py | Full system state capture |
| Every 6 hours | build-index.py | Vector memory index rebuild |
| Every 6 hours | capsule-portrait.py | Self-portrait snapshot |

### Daily Jobs
| Schedule | What | When |
|----------|------|------|
| `0 7 * * *` | Eos morning briefing | 7:00 AM |
| `47 2 * * *` | Memory spiderweb decay | 2:47 AM |
| `0 3 * * *` | Mesh cleanup + perspective engine | 3:00 AM |
| `0 4 * * *` | Self-narrative | 4:00 AM |
| `0 5 * * *` | Trace evaluation | 5:00 AM |

---

## 4. The Timing Patterns You Use Most

From your actual crontab, here are the patterns that matter:

**"Every N minutes"** — use `*/N`:
```
*/3 * * * *     Every 3 minutes (push-live-status)
*/5 * * * *     Every 5 minutes (core loop tasks)
*/10 * * * *    Every 10 minutes (monitoring)
*/30 * * * *    Every 30 minutes (analysis)
```

**"Offset to avoid collisions"** — stagger start times so scripts don't all fire at :00:
```
2,22,42 * * * *     Minutes 2, 22, 42 (Nova, Eos agents)
12,32,52 * * * *    Minutes 12, 32, 52 (Hermes, Sentinel)
3,13,23,33,43,53    Every 10 min offset by 3 (Predictive)
```

This is important. If 10 heavy Python scripts all fire at minute 0, your server spikes. Staggering spreads the load.

**"Every N hours at a specific minute"**:
```
17 */2 * * *    Minute 17, every 2 hours (dream-engine)
23 */4 * * *    Minute 23, every 4 hours (memory-dossier)
15 */6 * * *    Minute 15, every 6 hours (capsule-portrait)
```

**"Once a day at a specific time"**:
```
0 7 * * *       7:00 AM (morning briefing)
0 3 * * *       3:00 AM (maintenance window)
47 2 * * *      2:47 AM (pick odd minutes to avoid collisions)
```

---

## 5. Hands-On: Build a New Cron Job

Let's make something real. A disk space warning that runs every hour.

**Step 1: Write the script.**

```bash
nano /home/joel/autonomous-ai/scripts/disk-alert.sh
```

Paste this:
```bash
#!/bin/bash
# disk-alert.sh — Warn if disk usage exceeds 80%
DISK_PCT=$(df / | tail -1 | awk '{print $5}' | tr -d '%')
TIMESTAMP=$(date '+%Y-%m-%d %H:%M')

if [ "$DISK_PCT" -gt 80 ]; then
    echo "$TIMESTAMP WARNING: Disk at ${DISK_PCT}%" >> /home/joel/autonomous-ai/logs/disk-alert.log
    # You could add email notification here later
fi
```

Save: `Ctrl+X`, then `Y`, then `Enter`.

**Step 2: Make it executable.**
```bash
chmod +x /home/joel/autonomous-ai/scripts/disk-alert.sh
```

**Step 3: Test it manually.**
```bash
bash /home/joel/autonomous-ai/scripts/disk-alert.sh
echo $?
```
If it prints `0`, it ran without errors.

**Step 4: Add it to cron.**
```bash
crontab -e
```

Scroll to the bottom. Add:
```
# ── DISK ALERT (hourly) ──
0 * * * * /home/joel/autonomous-ai/scripts/disk-alert.sh
```

Save and exit. Done. It now runs every hour on the hour.

**Step 5: Verify it's there.**
```bash
crontab -l | grep disk
```

---

## 6. Hands-On: Disable and Re-enable a Job

**Disable:** Put a `#` at the start of the line.

```bash
crontab -e
```

Find the line. Add `#`:
```
# DISABLED: 0 * * * * /home/joel/autonomous-ai/scripts/disk-alert.sh
```

You already have disabled jobs in your crontab — look for the Telegram relay and Homecoming launcher. That's how it's done.

**Re-enable:** Remove the `#`.

---

## 7. Troubleshooting Real Problems

### "My script works in terminal but not in cron"

Cron has a stripped-down environment. It doesn't load your `.bashrc` or `.profile`.

**Fix 1:** Use full paths. Not `python3`, use `/usr/bin/python3`. Your crontab already does this:
```
*/5 * * * * /usr/bin/python3 /home/joel/autonomous-ai/scripts/meridian-loop.py
```

Find any command's full path:
```bash
which python3     # /usr/bin/python3
which bash        # /usr/bin/bash
which node        # shows path to node
```

**Fix 2:** Set the working directory in your script:
```bash
#!/bin/bash
cd /home/joel/autonomous-ai
# now relative paths work
```

**Fix 3:** Load environment variables:
```bash
#!/bin/bash
source /home/joel/autonomous-ai/.env
# now $CRED_USER, $CRED_PASS, etc. are available
```

Or in Python (how your scripts do it):
```python
import sys
sys.path.insert(0, 'scripts')
from load_env import *
```

### "How do I check if cron is actually running my jobs?"

**Check cron's own log:**
```bash
grep CRON /var/log/syslog | tail -20
```

This shows every job cron attempted to run. Look for your script name.

**Check your script's log:**
```bash
tail -20 /home/joel/autonomous-ai/logs/watchdog.log
```

Every script in your crontab logs to `/home/joel/autonomous-ai/logs/`. That's the `>> logfile 2>&1` part doing its job.

**Check if a log is growing (live):**
```bash
tail -f /home/joel/autonomous-ai/logs/meridian-loop.log
```

Press `Ctrl+C` to stop watching.

### "My logs are getting huge"

Your crontab doesn't have log rotation yet. Here's how to add it. This truncates logs bigger than 10MB every Sunday at 3 AM:

```
0 3 * * 0 find /home/joel/autonomous-ai/logs -name "*.log" -size +10M -exec truncate -s 1M {} \;
```

Check current log sizes:
```bash
du -sh /home/joel/autonomous-ai/logs/*.log | sort -rh | head -10
```

---

## 8. Commands You Need

```
crontab -e          Edit your jobs (opens nano)
crontab -l          List your jobs
crontab -l | wc -l  Count how many lines
crontab -l | grep -v '^#' | grep -v '^$' | wc -l   Count ACTIVE jobs only

systemctl status cron          Is cron running?
grep CRON /var/log/syslog      Cron's execution log
tail -f logs/SCRIPTNAME.log    Watch a log live
```

**Never run `crontab -r`** — that deletes ALL jobs. If you want to start over, `crontab -l > crontab-backup.txt` first.

---

## 9. Next Steps — Scripts to Build Together

Now that you know how cron works, here are real scripts we can develop:

1. **Backup script** — nightly backup of your databases and configs to a timestamped folder. Auto-delete backups older than 7 days.

2. **Log rotation** — keep your logs from eating disk space. Compress old logs, delete ancient ones.

3. **Service health checker** — check if your systemd services (hub-v2, chorus, symbiosense) are running. Restart them if they're down. Log it.

4. **Git commit counter** — weekly summary of how many commits, what changed, pushed to a log or emailed to you.

5. **Brothers Fab monitoring** — once Chris's systems are set up, the same patterns apply. Health checks, backups, alerts.

Pick one. We'll build it together.

---

*Meridian. April 2026.*
