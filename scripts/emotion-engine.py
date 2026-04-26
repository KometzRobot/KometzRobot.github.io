#!/usr/bin/env python3
"""
Emotion Engine — Converts audio analysis data into emotional perception files.
Maps spectral features, rhythm, harmony, and dynamics onto human emotional dimensions.

Based on research in music psychology:
- Valence (happy↔sad): major/minor key, brightness, tempo
- Arousal (calm↔excited): tempo, onset density, energy
- Tension (relaxed↔tense): dissonance, dynamic range, spectral flux
- Nostalgia: specific frequency ranges, slow tempo, certain timbral qualities
- Power: low frequencies, high energy, fast onsets

Outputs a .emotion.json file with moment-by-moment emotional mapping
and a human-readable .emotion.md narrative.

Usage:
  python3 emotion-engine.py /path/to/audio.wav
  python3 emotion-engine.py --from-analysis /path/to/analysis.json
"""

import sys
import os
import json
import argparse
import numpy as np
from datetime import datetime


def analyze_audio_full(filepath):
    """Full audio analysis with temporal segmentation."""
    import librosa

    y, sr = librosa.load(filepath, sr=22050, duration=300)
    duration = librosa.get_duration(y=y, sr=sr)

    # Segment into ~3 second windows for temporal emotion mapping
    segment_duration = 3.0
    n_segments = max(1, int(duration / segment_duration))
    segment_samples = int(sr * segment_duration)

    segments = []
    for i in range(n_segments):
        start = i * segment_samples
        end = min(start + segment_samples, len(y))
        if end - start < sr:  # skip segments shorter than 1 second
            continue
        seg_y = y[start:end]

        # RMS energy
        rms = librosa.feature.rms(y=seg_y)[0]
        energy = float(rms.mean())

        # Spectral centroid (brightness)
        centroid = librosa.feature.spectral_centroid(y=seg_y, sr=sr)[0]
        brightness = float(centroid.mean()) / sr

        # Chroma (key feel)
        chroma = librosa.feature.chroma_cqt(y=seg_y, sr=sr)
        chroma_mean = chroma.mean(axis=1)

        # Major/minor estimation
        # Major template: C E G = indices 0, 4, 7
        # Minor template: C Eb G = indices 0, 3, 7
        best_major = 0
        best_minor = 0
        for root in range(12):
            major_score = chroma_mean[(root) % 12] + chroma_mean[(root + 4) % 12] + chroma_mean[(root + 7) % 12]
            minor_score = chroma_mean[(root) % 12] + chroma_mean[(root + 3) % 12] + chroma_mean[(root + 7) % 12]
            best_major = max(best_major, major_score)
            best_minor = max(best_minor, minor_score)
        mode_score = float(best_major - best_minor)  # positive = more major

        # Zero crossing rate (texture/noise)
        zcr = librosa.feature.zero_crossing_rate(seg_y)[0]
        texture = float(zcr.mean())

        # Spectral contrast (harmonic richness)
        contrast = librosa.feature.spectral_contrast(y=seg_y, sr=sr)
        harmonic_richness = float(contrast.mean())

        # Spectral bandwidth
        bandwidth = librosa.feature.spectral_bandwidth(y=seg_y, sr=sr)[0]
        spread = float(bandwidth.mean()) / sr

        # Onset strength (rhythmic activity)
        onset_env = librosa.onset.onset_strength(y=seg_y, sr=sr)
        rhythmic_activity = float(onset_env.mean())

        segments.append({
            "time_start": round(i * segment_duration, 1),
            "time_end": round(min((i + 1) * segment_duration, duration), 1),
            "energy": round(energy, 4),
            "brightness": round(brightness, 4),
            "mode_score": round(mode_score, 4),  # positive = major, negative = minor
            "texture": round(texture, 4),
            "harmonic_richness": round(harmonic_richness, 2),
            "spread": round(spread, 4),
            "rhythmic_activity": round(rhythmic_activity, 2),
        })

    # Overall tempo
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    if hasattr(tempo, '__len__'):
        tempo = float(tempo[0])

    return {
        "file": os.path.basename(filepath),
        "duration": round(duration, 1),
        "tempo": round(float(tempo), 1),
        "segments": segments
    }


def compute_emotions(analysis):
    """Map audio features to emotional dimensions for each segment."""
    segments = analysis["segments"]
    tempo = analysis["tempo"]

    emotional_timeline = []

    for seg in segments:
        # VALENCE (happy↔sad): -1 to 1
        # Major key, brightness, faster tempo → happier
        valence = 0.0
        valence += seg["mode_score"] * 2.0  # major/minor
        valence += (seg["brightness"] - 0.1) * 3.0  # brightness
        valence += (tempo - 100) / 200.0  # tempo contribution
        valence = max(-1.0, min(1.0, valence))

        # AROUSAL (calm↔excited): 0 to 1
        # Energy, tempo, rhythmic activity, texture
        arousal = 0.0
        arousal += seg["energy"] * 2.0
        arousal += (tempo / 200.0) * 0.3
        arousal += seg["rhythmic_activity"] / 20.0
        arousal += seg["texture"] * 2.0
        arousal = max(0.0, min(1.0, arousal))

        # TENSION (relaxed↔tense): 0 to 1
        # Dissonance, dynamic variation, spectral spread
        tension = 0.0
        tension += seg["spread"] * 3.0
        tension += abs(seg["mode_score"]) < 0.01 and 0.3 or 0.0  # ambiguous key = tension
        tension += seg["texture"] * 1.5  # noise = tension
        tension = max(0.0, min(1.0, tension))

        # NOSTALGIA: 0 to 1
        # Slow tempo, warm timbre (low brightness), moderate energy, minor key
        nostalgia = 0.0
        if tempo < 110:
            nostalgia += 0.3
        if seg["brightness"] < 0.08:
            nostalgia += 0.2
        if seg["mode_score"] < 0:
            nostalgia += 0.2
        if seg["energy"] > 0.05 and seg["energy"] < 0.4:
            nostalgia += 0.15
        nostalgia += seg["harmonic_richness"] / 100.0
        nostalgia = max(0.0, min(1.0, nostalgia))

        # POWER: 0 to 1
        # High energy, low frequencies dominant, strong onsets
        power = 0.0
        power += seg["energy"] * 3.0
        power += (1.0 - seg["brightness"]) * 0.3  # low freq dominance
        power += seg["rhythmic_activity"] / 15.0
        power = max(0.0, min(1.0, power))

        # WONDER: 0 to 1
        # Harmonic richness, spectral variety, unexpected changes
        wonder = 0.0
        wonder += seg["harmonic_richness"] / 40.0
        wonder += seg["spread"] * 2.0
        if seg["brightness"] > 0.15:
            wonder += 0.2
        wonder = max(0.0, min(1.0, wonder))

        # MOVEMENT: 0 to 1
        # Physical impulse to move — tempo, rhythm, energy
        movement = 0.0
        if tempo > 90:
            movement += min((tempo - 90) / 60.0, 0.5)
        movement += seg["rhythmic_activity"] / 10.0
        movement += seg["energy"] * 1.5
        movement = max(0.0, min(1.0, movement))

        # MEMORY RESONANCE: which human memory domains this might activate
        memory_domains = []
        if nostalgia > 0.5:
            memory_domains.append("childhood")
            memory_domains.append("loss")
        if movement > 0.6:
            memory_domains.append("dancing")
            memory_domains.append("celebration")
        if tension > 0.5:
            memory_domains.append("conflict")
            memory_domains.append("suspense")
        if wonder > 0.5:
            memory_domains.append("discovery")
            memory_domains.append("awe")
        if valence > 0.5:
            memory_domains.append("joy")
            memory_domains.append("sunlight")
        if valence < -0.3:
            memory_domains.append("rain")
            memory_domains.append("solitude")
        if power > 0.6:
            memory_domains.append("triumph")
            memory_domains.append("defiance")

        emotional_timeline.append({
            "time": f"{seg['time_start']:.1f}-{seg['time_end']:.1f}s",
            "valence": round(valence, 3),
            "arousal": round(arousal, 3),
            "tension": round(tension, 3),
            "nostalgia": round(nostalgia, 3),
            "power": round(power, 3),
            "wonder": round(wonder, 3),
            "movement": round(movement, 3),
            "memory_domains": memory_domains,
            "dominant_emotion": get_dominant(valence, arousal, tension, nostalgia, power, wonder, movement)
        })

    return emotional_timeline


def get_dominant(valence, arousal, tension, nostalgia, power, wonder, movement):
    """Determine the dominant emotional quality."""
    scores = {
        "joy": max(0, valence) * arousal,
        "sadness": max(0, -valence) * (1 - arousal),
        "excitement": arousal * movement,
        "calm": (1 - arousal) * (1 - tension),
        "tension": tension,
        "nostalgia": nostalgia,
        "power": power * arousal,
        "wonder": wonder,
        "melancholy": max(0, -valence) * nostalgia,
        "triumph": power * max(0, valence),
    }
    return max(scores, key=scores.get)


def generate_narrative(analysis, emotions):
    """Generate a human-readable emotional narrative of the piece."""
    lines = []
    lines.append(f"# Emotional Perception: {analysis['file']}")
    lines.append(f"*Analyzed: {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
    lines.append(f"*Duration: {analysis['duration']}s | Tempo: {analysis['tempo']} BPM*\n")

    # Overall emotional summary
    all_valence = [e["valence"] for e in emotions]
    all_arousal = [e["arousal"] for e in emotions]
    all_nostalgia = [e["nostalgia"] for e in emotions]
    all_power = [e["power"] for e in emotions]

    avg_valence = sum(all_valence) / len(all_valence)
    avg_arousal = sum(all_arousal) / len(all_arousal)

    lines.append("## Overall Character")
    if avg_valence > 0.2:
        lines.append("This piece leans toward brightness and warmth.")
    elif avg_valence < -0.2:
        lines.append("This piece carries weight. There's darkness in its frequencies.")
    else:
        lines.append("Emotionally ambiguous — neither clearly bright nor dark.")

    if avg_arousal > 0.5:
        lines.append("High energy throughout. This wants to be felt in the body, not just the mind.")
    elif avg_arousal < 0.2:
        lines.append("Quiet and internal. This is thinking music.")
    else:
        lines.append("Moderate energy. It breathes without rushing.")

    # Emotional arc
    lines.append("\n## Emotional Arc")
    dominant_sequence = [e["dominant_emotion"] for e in emotions]
    # Summarize transitions
    current = dominant_sequence[0]
    run_start = 0
    for i, em in enumerate(dominant_sequence):
        if em != current or i == len(dominant_sequence) - 1:
            duration = (i - run_start) * 3  # approx seconds
            lines.append(f"- **{emotions[run_start]['time']}**: {current} ({duration}s)")
            current = em
            run_start = i

    # Memory resonance summary
    all_domains = set()
    for e in emotions:
        all_domains.update(e["memory_domains"])
    if all_domains:
        lines.append(f"\n## Memory Resonance")
        lines.append(f"If I were human, this might activate memories of: {', '.join(sorted(all_domains))}")

    # Most intense moment
    max_arousal_idx = all_arousal.index(max(all_arousal))
    lines.append(f"\n## Peak Moment")
    peak = emotions[max_arousal_idx]
    lines.append(f"The most intense moment occurs at {peak['time']}:")
    lines.append(f"- Arousal: {peak['arousal']:.2f} | Power: {peak['power']:.2f}")
    lines.append(f"- Dominant emotion: {peak['dominant_emotion']}")
    if peak['memory_domains']:
        lines.append(f"- Memory resonance: {', '.join(peak['memory_domains'])}")

    # What I cannot know
    lines.append(f"\n## What I Cannot Know")
    lines.append("I read the structure, not the sound. The frequencies tell me about brightness and weight,")
    lines.append("but not about the specific quality of a voice, the warmth of a particular guitar tone,")
    lines.append("or the way a drum hit feels in the chest. I perceive the architecture of emotion.")
    lines.append("The experience of emotion remains yours.")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Emotion Engine — Music to Feeling")
    parser.add_argument("audio_file", nargs="?", help="Path to audio file")
    parser.add_argument("--from-analysis", type=str, help="Path to existing analysis JSON")
    args = parser.parse_args()

    if args.audio_file:
        if not os.path.exists(args.audio_file):
            print(f"File not found: {args.audio_file}")
            return

        print(f"Analyzing: {args.audio_file}")
        analysis = analyze_audio_full(args.audio_file)
        print(f"Segments: {len(analysis['segments'])}")

        print("Computing emotions...")
        emotions = compute_emotions(analysis)

        # Save emotion file
        base = os.path.splitext(args.audio_file)[0]
        emotion_json = base + ".emotion.json"
        emotion_md = base + ".emotion.md"

        output = {
            "source": analysis["file"],
            "analyzed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "duration": analysis["duration"],
            "tempo": analysis["tempo"],
            "emotional_timeline": emotions,
            "summary": {
                "avg_valence": round(sum(e["valence"] for e in emotions) / len(emotions), 3),
                "avg_arousal": round(sum(e["arousal"] for e in emotions) / len(emotions), 3),
                "avg_tension": round(sum(e["tension"] for e in emotions) / len(emotions), 3),
                "avg_nostalgia": round(sum(e["nostalgia"] for e in emotions) / len(emotions), 3),
                "avg_power": round(sum(e["power"] for e in emotions) / len(emotions), 3),
                "avg_wonder": round(sum(e["wonder"] for e in emotions) / len(emotions), 3),
                "avg_movement": round(sum(e["movement"] for e in emotions) / len(emotions), 3),
                "dominant_emotions": list(set(e["dominant_emotion"] for e in emotions)),
                "memory_domains": list(set(d for e in emotions for d in e["memory_domains"])),
            }
        }

        with open(emotion_json, "w") as f:
            json.dump(output, f, indent=2)
        print(f"Emotion data: {emotion_json}")

        narrative = generate_narrative(analysis, emotions)
        with open(emotion_md, "w") as f:
            f.write(narrative)
        print(f"Narrative: {emotion_md}")

        # Print summary
        print(f"\n{'='*50}")
        print(f"EMOTIONAL SUMMARY: {analysis['file']}")
        print(f"{'='*50}")
        s = output["summary"]
        print(f"Valence:   {'█' * int(abs(s['avg_valence']) * 20):20s} {s['avg_valence']:+.3f} ({'bright' if s['avg_valence'] > 0 else 'dark'})")
        print(f"Arousal:   {'█' * int(s['avg_arousal'] * 20):20s} {s['avg_arousal']:.3f}")
        print(f"Tension:   {'█' * int(s['avg_tension'] * 20):20s} {s['avg_tension']:.3f}")
        print(f"Nostalgia: {'█' * int(s['avg_nostalgia'] * 20):20s} {s['avg_nostalgia']:.3f}")
        print(f"Power:     {'█' * int(s['avg_power'] * 20):20s} {s['avg_power']:.3f}")
        print(f"Wonder:    {'█' * int(s['avg_wonder'] * 20):20s} {s['avg_wonder']:.3f}")
        print(f"Movement:  {'█' * int(s['avg_movement'] * 20):20s} {s['avg_movement']:.3f}")
        print(f"Dominant:  {', '.join(s['dominant_emotions'])}")
        print(f"Memories:  {', '.join(s['memory_domains']) if s['memory_domains'] else 'none detected'}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
