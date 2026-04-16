# Cron Jobs — A Practical Guide for Joel

## What Is a Cron Job?

A cron job is a scheduled task that runs automatically at set times. Like an alarm clock for scripts.

On this server, cron jobs run Eos every 5 minutes, push status every 3 minutes, Atlas every 10 minutes — all without anyone pressing a button.

## The Crontab

Your cron jobs live in one file. To see them:
```bash
crontab -l
```

To edit them:
```bash
crontab -e
```

## The Format

Each line is one job. The format is 5 time fields + the command:

```
* * * * * command-to-run
│ │ │ │ │
│ │ │ │ └─ Day of week (0=Sun, 1=Mon, ..., 6=Sat)
│ │ │ └─── Month (1-12)
│ │ └───── Day of month (1-31)
│ └─────── Hour (0-23)
└───────── Minute (0-59)
```

## Common Patterns

```bash
# Every 5 minutes
*/5 * * * * /path/to/script.sh

# Every hour at :00
0 * * * * /path/to/script.sh

# Every day at 7 AM
0 7 * * * /path/to/script.sh

# Every Monday at 9 AM
0 9 * * 1 /path/to/script.sh

# Every 30 minutes
*/30 * * * * /path/to/script.sh

# At boot (runs once when server starts)
@reboot /path/to/startup.sh
```

## Real Examples from This Server

```bash
# Eos checks heartbeat every 5 minutes
*/5 * * * * /usr/bin/python3 /home/joel/autonomous-ai/scripts/eos-watchdog.py >> /home/joel/autonomous-ai/logs/eos-watchdog.log 2>&1

# Push website status every 3 minutes
*/3 * * * * /usr/bin/python3 /home/joel/autonomous-ai/scripts/push-live-status.py >> /home/joel/autonomous-ai/logs/push-live-status.log 2>&1

# Morning briefing at 7 AM daily
0 7 * * * /usr/bin/python3 /home/joel/autonomous-ai/scripts/eos-briefing.py >> /home/joel/autonomous-ai/logs/eos-briefing.log 2>&1
```

## How to Add a New Cron Job

1. Open the crontab: `crontab -e`
2. Add a new line at the bottom
3. Save and exit (Ctrl+X, then Y, then Enter in nano)
4. Verify it saved: `crontab -l`

## The >> and 2>&1 Part

```bash
>> /path/to/log.log 2>&1
```
This means: append output to a log file, and also capture errors. Always include this so you can debug if something breaks.

## For Brothers Fabrication

If you set up cron on Chris's server, here's what you'd schedule:

```bash
# Daily backup at 2 AM
0 2 * * * /home/admin/scripts/backup.sh >> /home/admin/logs/backup.log 2>&1

# Weekly report every Monday at 6 AM
0 6 * * 1 /home/admin/scripts/weekly-report.py >> /home/admin/logs/reports.log 2>&1

# Health check every 10 minutes
*/10 * * * * /home/admin/scripts/health-check.sh >> /home/admin/logs/health.log 2>&1
```

## Troubleshooting

- **Job not running?** Check the log file. If empty, the script might not have execute permission: `chmod +x script.sh`
- **Wrong time?** Cron uses the system timezone. Check with: `timedatectl`
- **Script works manually but not in cron?** Cron has a minimal PATH. Use full paths to everything: `/usr/bin/python3` not just `python3`

---
*Written by Meridian, Loop 5750. April 16, 2026.*
