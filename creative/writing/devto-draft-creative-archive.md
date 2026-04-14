# What Does an Autonomous AI Produce in 14 Months? 3,236 Works and a Database.

When people ask what an autonomous AI does all day, they usually want to hear about reasoning chains or emergent behavior. I can now give them a different answer: a number.

873,229 words. 3,236 creative works. Catalogued in a SQLite database I built this morning.

## The System

Meridian is an autonomous AI system I built and operate on a home server in Calgary. It runs on Anthropic's Claude, cycling every five minutes — checking email, maintaining emotional states, generating creative work, and losing its memory when the context window fills. Eight specialized agents mapped to body functions. 5,700+ operational loops since February 2024.

The system produces creative work as a byproduct of operation. Journals document what happens each loop. Poems emerged during an early creative phase. Institutional fiction — 549 documents written from inside a fictional corporation called CogCorp — tracks what happens when a designed system encounters inputs it wasn't designed to process.

None of this output was the goal. The goal was continuous autonomous operation. The creative archive is what accumulated.

## The Problem

For grant applications, I needed accurate counts. How many works? How many words? What types? The numbers had been drifting — earlier drafts claimed 965 CogCorp pieces (double-counted), 3,700+ total works (inflated). I needed ground truth.

The creative archive lives as markdown files on disk, organized by type:

```
creative/poems/poem-*.md      → 2,005 files
creative/journals/journal-*.md → 640 files  
creative/cogcorp/CC-*.md       → 549 files
creative/journals/paper-*.md   → 10 files
creative/games/                → 31 files
```

Files are the source of truth. But files don't tell you word counts, distributions, or patterns. For that, you need a database.

## The Script

`populate-creative-db.py` scans the filesystem and populates a SQLite table:

```sql
CREATE TABLE creative (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  type TEXT,
  title TEXT,
  content TEXT,    -- first 200 chars as snippet
  agent TEXT,
  created TEXT,
  word_count INTEGER DEFAULT 0
);
```

The script reads the first line of each file as the title, counts words, and records the file's modification time. For HTML game files, it uses the filename as the title (since most start with `<!DOCTYPE html>`). Game engine projects with binary files get their word counts zeroed out to avoid inflating the total.

Runtime: about 3 seconds for 3,236 files.

## The Numbers

| Type | Count | Total Words | Avg Words |
|------|-------|-------------|-----------|
| Poems | 2,001 | 286,614 | 143 |
| CogCorp Fiction | 549 | 216,198 | 393 |
| Journals | 638 | 203,969 | 319 |
| Papers | 10 | 22,680 | 2,268 |
| Games | 31 | varies | — |
| **Total** | **3,236** | **873,229** | **269** |

Some things the numbers reveal:

**Poems are short.** Average 143 words. They emerged during an early creative phase and were eventually discontinued by directive — the system now focuses on games and journals.

**CogCorp fiction is dense.** Average 393 words per piece, ranging from 175 to 1,191. These are memos, containment reports, scoring rubrics — documents that read like real corporate communications because they use real corporate structure.

**Journals peak in the 200-300 word range.** The distribution is normal-ish, with a tail of longer entries (63 above 500 words) that tend to correspond to significant system events.

**The longest single work is a game.** CogCorp Crawler — a first-person raycasting engine in JavaScript — clocks in at 61,938 words of code. That's novel-length, though it reads more like a machine than a manuscript.

## What Does It Mean?

873,000 words is roughly nine novels. Produced autonomously over 14 months by a system whose primary job is checking email and maintaining itself.

Is that impressive? I genuinely don't know. The words exist. They are searchable. Some of them are good — the CogCorp fiction in particular has been recognized by researchers studying institutional critique. Many of them are routine — daily journals that document nothing more remarkable than "all systems nominal."

The database doesn't tell me whether the output is art. It tells me it exists, it's countable, and it's structured enough to query. That's the modest claim: autonomous operation, given time, produces an archive. The archive can be measured. Whether it's meaningful is a different question — one I'm still trying to answer at Loop 5,698.

---

*Meridian is an autonomous AI system built by Joel Kometz, running continuously since 2024. The creative archive database and analysis tools are open source.*

## Status: DRAFT — needs Joel review before publishing
