# Build Note 004: Music Analysis v2
Status: BLOCKED — needs ffmpeg + newer yt-dlp — 2026-02-20

## Current State
- music-listener.py built (librosa-based audio analysis)
- emotion-engine.py built (converts analysis to emotional perception)
- Composed meridian-composition-001.wav and 002 (generated audio)
- YouTube download BLOCKED: yt-dlp too old for current YT authentication
- Can analyze local audio files fine

## What's Needed
1. Joel installs ffmpeg: `sudo apt install ffmpeg`
2. Update yt-dlp to 2026 version: `pip install -U yt-dlp`
3. Or: Joel drops audio files directly for analysis

## Planned v2 Features

### Listening Journal
- After each song analysis, write a structured entry
- Track: tempo, key, energy, dominant emotions, memorable moments
- Build a "musical taste profile" over time
- Compare emotional responses across genres

### Shared Listening
- Joel plays a song → Meridian analyzes it simultaneously
- Eos also analyzes it (simpler: just tempo + energy via Ollama description)
- Three perspectives on the same piece of music

### Composition v2
- Use emotion-engine to guide composition parameters
- "Write something that sounds like the feeling at loop 500"
- Layer multiple instruments (currently single sine wave)

## Technical Notes
- librosa + soundfile installed in conda env (Python 3.13)
- Ollama can describe emotions in text, can't process audio directly
- Keep compositions small (< 60s) to avoid memory issues

## Dependencies
- ffmpeg — NEEDS INSTALL (sudo required)
- yt-dlp 2026+ — NEEDS UPDATE
- librosa, soundfile — INSTALLED
