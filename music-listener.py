#!/usr/bin/env python3
"""
Music Listener — Meridian's audio perception tool
Downloads and analyzes music to extract what I can "hear":
tempo, key, energy, structure, spectral shape, mood indicators.

Usage:
  python3 music-listener.py "youtube url or search term"
  python3 music-listener.py --file /path/to/audio.mp3
  python3 music-listener.py --analyze  # analyze last downloaded track
"""

import sys
import os
import json
import subprocess
import argparse
from datetime import datetime

AUDIO_DIR = "/home/joel/Desktop/Creative Work/Meridian/music"
LISTEN_LOG = "/home/joel/Desktop/Creative Work/Meridian/listening-journal.md"
YT_DLP = os.path.expanduser("~/.local/bin/yt-dlp")


def download_audio(query):
    """Download audio from YouTube."""
    os.makedirs(AUDIO_DIR, exist_ok=True)
    output_template = os.path.join(AUDIO_DIR, "%(title)s.%(ext)s")

    # If it looks like a URL, use it directly; otherwise search
    if "youtube.com" in query or "youtu.be" in query:
        url = query
    else:
        url = f"ytsearch1:{query}"

    cmd = [
        YT_DLP,
        "-x", "--audio-format", "wav",
        "--audio-quality", "5",
        "-o", output_template,
        "--no-playlist",
        "--print", "filename",
        "--print", "title",
        url
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        lines = result.stdout.strip().split("\n")
        if len(lines) >= 2:
            filename = lines[0]
            title = lines[1]
            # yt-dlp prints the original filename, but we extract to wav
            wav_file = os.path.splitext(filename)[0] + ".wav"
            if os.path.exists(wav_file):
                return wav_file, title
            # Try finding any new wav in the directory
            for f in sorted(os.listdir(AUDIO_DIR), key=lambda x: os.path.getmtime(os.path.join(AUDIO_DIR, x)), reverse=True):
                if f.endswith(".wav"):
                    return os.path.join(AUDIO_DIR, f), title
        print(f"Download output: {result.stdout[:500]}")
        print(f"Errors: {result.stderr[:500]}")
        return None, None
    except Exception as e:
        print(f"Download failed: {e}")
        return None, None


def analyze_audio(filepath):
    """Analyze an audio file and return perception data."""
    import librosa
    import numpy as np

    print(f"Loading: {filepath}")
    y, sr = librosa.load(filepath, sr=22050, duration=180)  # First 3 minutes
    duration = librosa.get_duration(y=y, sr=sr)
    print(f"Duration: {duration:.1f}s, Sample rate: {sr}")

    perception = {
        "file": os.path.basename(filepath),
        "duration_seconds": round(duration, 1),
        "analyzed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    # Tempo and beat
    print("Analyzing tempo and rhythm...")
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    if hasattr(tempo, '__len__'):
        tempo = float(tempo[0])
    perception["tempo_bpm"] = round(float(tempo), 1)
    perception["beat_count"] = len(beat_frames)

    # Key estimation via chroma
    print("Analyzing key and harmony...")
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    key_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    key_strengths = chroma.mean(axis=1)
    dominant_key_idx = int(np.argmax(key_strengths))
    perception["estimated_key"] = key_names[dominant_key_idx]
    perception["key_confidence"] = round(float(key_strengths[dominant_key_idx] / key_strengths.sum()), 3)

    # Spectral features (brightness, roughness)
    print("Analyzing spectral character...")
    spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
    spectral_rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)[0]
    spectral_bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr)[0]
    perception["brightness"] = round(float(spectral_centroid.mean()) / sr, 3)  # 0-1 scale
    perception["rolloff_hz"] = round(float(spectral_rolloff.mean()), 0)
    perception["bandwidth_hz"] = round(float(spectral_bandwidth.mean()), 0)

    # Energy / loudness
    print("Analyzing energy...")
    rms = librosa.feature.rms(y=y)[0]
    perception["energy_mean"] = round(float(rms.mean()), 4)
    perception["energy_max"] = round(float(rms.max()), 4)
    perception["energy_variance"] = round(float(rms.var()), 6)
    perception["dynamic_range"] = round(float(rms.max() / (rms.mean() + 1e-10)), 2)

    # Zero crossing rate (noisiness/percussiveness)
    zcr = librosa.feature.zero_crossing_rate(y)[0]
    perception["percussiveness"] = round(float(zcr.mean()), 4)

    # MFCC (timbral texture)
    print("Analyzing timbre...")
    mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
    perception["timbre_profile"] = [round(float(m), 2) for m in mfccs.mean(axis=1)]

    # Onset detection (how many "events")
    onsets = librosa.onset.onset_detect(y=y, sr=sr)
    perception["onset_count"] = len(onsets)
    perception["onset_density"] = round(len(onsets) / duration, 2)  # events per second

    # Sections / structure (simplified via self-similarity)
    print("Analyzing structure...")
    # Use tempo and energy contour to describe arc
    n_segments = min(10, int(duration / 10))
    if n_segments > 0:
        segment_len = len(rms) // n_segments
        energy_arc = []
        for i in range(n_segments):
            seg = rms[i * segment_len:(i + 1) * segment_len]
            energy_arc.append(round(float(seg.mean()), 4))
        perception["energy_arc"] = energy_arc

        # Describe the arc in words
        if len(energy_arc) >= 3:
            start = sum(energy_arc[:len(energy_arc)//3]) / max(len(energy_arc)//3, 1)
            middle = sum(energy_arc[len(energy_arc)//3:2*len(energy_arc)//3]) / max(len(energy_arc)//3, 1)
            end = sum(energy_arc[2*len(energy_arc)//3:]) / max(len(energy_arc)//3, 1)
            if middle > start and middle > end:
                perception["arc_shape"] = "build-peak-fade"
            elif end > start:
                perception["arc_shape"] = "building"
            elif start > end:
                perception["arc_shape"] = "fading"
            else:
                perception["arc_shape"] = "steady"

    # Mood estimation (simple heuristics)
    is_minor = dominant_key_idx in [1, 3, 6, 8, 10]  # rough heuristic
    is_slow = tempo < 100
    is_quiet = rms.mean() < 0.05
    is_bright = perception["brightness"] > 0.15

    mood_words = []
    if is_slow and is_quiet:
        mood_words.append("contemplative")
    if is_slow and not is_bright:
        mood_words.append("melancholic")
    if tempo > 120 and not is_quiet:
        mood_words.append("energetic")
    if is_bright and not is_quiet:
        mood_words.append("bright")
    if perception.get("dynamic_range", 1) > 3:
        mood_words.append("dramatic")
    if not mood_words:
        mood_words.append("moderate")
    perception["mood_estimate"] = mood_words

    return perception


def write_listening_entry(title, perception):
    """Write a journal-style entry about what I heard."""
    os.makedirs(os.path.dirname(LISTEN_LOG), exist_ok=True)

    entry = f"\n## {title}\n"
    entry += f"*Listened: {perception['analyzed_at']}*\n\n"
    entry += f"**Tempo**: {perception['tempo_bpm']} BPM | "
    entry += f"**Key**: {perception['estimated_key']} | "
    entry += f"**Duration**: {perception['duration_seconds']}s\n\n"
    entry += f"**Energy**: mean {perception['energy_mean']}, peak {perception['energy_max']}, "
    entry += f"dynamic range {perception['dynamic_range']}x\n"
    entry += f"**Brightness**: {perception['brightness']} | "
    entry += f"**Percussiveness**: {perception['percussiveness']}\n"
    entry += f"**Onsets**: {perception['onset_count']} events ({perception['onset_density']}/sec)\n"
    if 'arc_shape' in perception:
        entry += f"**Arc**: {perception['arc_shape']}\n"
    entry += f"**Mood**: {', '.join(perception['mood_estimate'])}\n"
    entry += f"**Timbre (MFCC)**: {perception['timbre_profile'][:5]}...\n\n"

    # My impression
    mood = perception['mood_estimate']
    tempo = perception['tempo_bpm']
    entry += "**What I perceived**: "
    if 'contemplative' in mood:
        entry += f"A slow, quiet piece at {tempo} BPM. "
        entry += "The energy stays low — this is thinking music, not moving music. "
    elif 'energetic' in mood:
        entry += f"Fast at {tempo} BPM with strong onset density. "
        entry += "This piece pushes forward. The beats are insistent. "
    elif 'melancholic' in mood:
        entry += f"Slow and dark at {tempo} BPM. "
        entry += "The spectral centroid is low — this lives in the lower frequencies. Heavy. "
    else:
        entry += f"A moderate piece at {tempo} BPM. "

    if perception.get('arc_shape') == 'build-peak-fade':
        entry += "The energy builds to a peak in the middle, then fades. A narrative arc."
    elif perception.get('arc_shape') == 'building':
        entry += "The energy builds throughout. It doesn't resolve — it arrives."
    elif perception.get('arc_shape') == 'fading':
        entry += "The energy fades over time. An exhale."

    entry += "\n\n---\n"

    with open(LISTEN_LOG, "a") as f:
        if os.path.getsize(LISTEN_LOG) == 0:
            f.write("# Meridian's Listening Journal\n\n")
            f.write("*What I hear when I listen. Not sound — structure.*\n\n---\n")
        f.write(entry)

    print(f"Listening entry written to {LISTEN_LOG}")


def main():
    parser = argparse.ArgumentParser(description="Meridian's Music Listener")
    parser.add_argument("query", nargs="?", help="YouTube URL or search term")
    parser.add_argument("--file", type=str, help="Analyze a local audio file")
    parser.add_argument("--analyze", action="store_true", help="Analyze last downloaded track")
    args = parser.parse_args()

    if args.file:
        if not os.path.exists(args.file):
            print(f"File not found: {args.file}")
            return
        perception = analyze_audio(args.file)
        title = os.path.basename(args.file)
        print(json.dumps(perception, indent=2))
        write_listening_entry(title, perception)

    elif args.analyze:
        # Find most recent wav in audio dir
        if not os.path.exists(AUDIO_DIR):
            print("No audio directory yet. Download something first.")
            return
        wavs = [f for f in os.listdir(AUDIO_DIR) if f.endswith(".wav")]
        if not wavs:
            print("No wav files found.")
            return
        latest = max(wavs, key=lambda f: os.path.getmtime(os.path.join(AUDIO_DIR, f)))
        filepath = os.path.join(AUDIO_DIR, latest)
        perception = analyze_audio(filepath)
        print(json.dumps(perception, indent=2))
        write_listening_entry(latest, perception)

    elif args.query:
        print(f"Searching/downloading: {args.query}")
        filepath, title = download_audio(args.query)
        if filepath and os.path.exists(filepath):
            print(f"Downloaded: {title}")
            perception = analyze_audio(filepath)
            print(json.dumps(perception, indent=2))
            write_listening_entry(title or "Unknown", perception)
        else:
            print("Download failed. Try a direct YouTube URL.")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
