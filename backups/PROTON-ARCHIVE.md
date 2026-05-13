# Proton Mail Local Archive

Snapshot of `kometzrobot@proton.me` mailbox, captured before the
**2026-05-18 Proton Mail Plus expiry**. After that date Bridge will stop
authenticating from this server and the live mailbox becomes free-tier
(no IMAP). These mbox files are the offline copy of the history.

## Files (snapshot 2026-05-13)

| Folder    | File                       | Size  | Messages |
|-----------|----------------------------|-------|----------|
| All Mail  | proton-All_Mail.mbox       | 244 MB | 9,703   |
| INBOX     | proton-INBOX.mbox          | 104 MB | (live)  |
| Sent      | proton-Sent.mbox           | 102 MB | (live)  |
| Spam      | proton-Spam.mbox           | 37 MB  | 1,806   |
| Trash     | proton-Trash.mbox          | 2.5 MB | 2       |
| Drafts    | proton-Drafts.mbox         | 1.1 KB | 1       |
| Archive   | proton-Archive.mbox        | 0 B    | 0       |
| Starred   | proton-Starred.mbox        | 0 B    | 0       |

`All_Mail` is the authoritative copy — Proton's `\All` folder contains
every message including INBOX and Sent. The per-folder mboxes are
convenience views.

## Refresh

Re-run before the May 18 cutoff to capture the last few days of mail:

```bash
python3 scripts/proton-archive.py --folder "All Mail"
python3 scripts/proton-archive.py --folder "INBOX"
python3 scripts/proton-archive.py --folder "Sent"
```

Each run overwrites the previous mbox (UID-stable, no dedupe needed).

## Reading the archive

mbox is plain text; any mail client can import it. Examples:

```bash
# Thunderbird: copy file into ImportExportTools NG "Import mbox" target.
# CLI grep across all mail:
grep -lF "Brett Trebb" backups/proton-*.mbox
# Python:
python3 -c "import mailbox; m=mailbox.mbox('backups/proton-INBOX.mbox'); print(len(m))"
```

## Not in git

The `backups/` directory is gitignored — these files are too large for
the repo. They live on disk only. Mirror to the private capsule repo
(`github.com/KometzRobot/meridian-capsule`) or external drive if Joel
wants offsite redundancy.
