#!/usr/bin/env python3
"""
Ars Electronica Video Builder v2
Creates 3 composited videos from screenshots + title cards.
No screen recording or window automation — pure ffmpeg compositing.
Ken Burns zoom/pan effects + crossfade transitions.
"""

import subprocess
import os
import sys
import tempfile
import shutil

FFMPEG = '/home/joel/.local/bin/ffmpeg'
FRAMES_DIR = '/home/joel/autonomous-ai/video-frames'
OUT_DIR = '/home/joel/autonomous-ai/video-frames'
FPS = 24

# Image assets
TITLE = f'{FRAMES_DIR}/title.png'
ARCHITECTURE = f'{FRAMES_DIR}/architecture.png'
CREATIVE = f'{FRAMES_DIR}/creative.png'
INNERWORLD = f'{FRAMES_DIR}/innerworld.png'
CLOSING = f'{FRAMES_DIR}/closing.png'
HUB = f'{FRAMES_DIR}/hub-recolored.png'  # Hub screenshot (clean)
HUB_LIVE = '/tmp/ars-video-2-hub-tour-frame30.png'  # From video frame (shows more)
TERMINAL = '/tmp/ars-video-4-living-system-frame30.png'  # Terminal + hub
DESKTOP = f'{FRAMES_DIR}/desktop-now.png'
KINECT_DEPTH = f'{FRAMES_DIR}/kinect-depth-scaled.png'
KINECT_RGB = f'{FRAMES_DIR}/kinect-rgb-scaled.png'
WEBSITE = f'{FRAMES_DIR}/website-screenshot.png'
WEBSITE_GAMES = f'{FRAMES_DIR}/website-games.png'
CRAWLER = f'{FRAMES_DIR}/website-crawler.png'
DASHBOARD = f'{FRAMES_DIR}/website-dashboard.png'


def make_segment(image_path, output_path, duration_s, effect='zoom_in',
                 zoom_start=1.0, zoom_end=1.3, pan_x='center', pan_y='center'):
    """Create a video segment from a single image with Ken Burns effect.

    Effects:
      zoom_in  - slowly zoom into center
      zoom_out - slowly zoom out from center
      pan_right - pan from left to right
      pan_left  - pan from right to left
      pan_down  - pan from top to bottom
      static    - no movement, just hold
    """
    d_frames = int(duration_s * FPS)

    # All images get scaled to 1920x1080 first, then zoompan works on that
    # zoompan outputs at 1920x1080

    if effect == 'static':
        cmd = [
            FFMPEG, '-y', '-loop', '1', '-i', image_path,
            '-vf', f'scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black',
            '-c:v', 'libx264', '-t', str(duration_s),
            '-pix_fmt', 'yuv420p', '-r', str(FPS),
            output_path
        ]
    else:
        # For zoompan, input should be larger than output to allow panning
        # Scale input to 2880x1620 (1.5x) for headroom
        if effect == 'zoom_in':
            z_expr = f"min(zoom+{(zoom_end - zoom_start) / d_frames:.6f},{zoom_end})"
            x_expr = "iw/2-(iw/zoom/2)"
            y_expr = "ih/2-(ih/zoom/2)"
        elif effect == 'zoom_out':
            z_expr = f"if(eq(on,1),{zoom_end},max(zoom-{(zoom_end - zoom_start) / d_frames:.6f},{zoom_start}))"
            x_expr = "iw/2-(iw/zoom/2)"
            y_expr = "ih/2-(ih/zoom/2)"
        elif effect == 'pan_right':
            z_expr = f"{zoom_start}"
            x_expr = f"(iw-iw/zoom)*on/{d_frames}"
            y_expr = "ih/2-(ih/zoom/2)"
        elif effect == 'pan_left':
            z_expr = f"{zoom_start}"
            x_expr = f"(iw-iw/zoom)*(1-on/{d_frames})"
            y_expr = "ih/2-(ih/zoom/2)"
        elif effect == 'pan_down':
            z_expr = f"{zoom_start}"
            x_expr = "iw/2-(iw/zoom/2)"
            y_expr = f"(ih-ih/zoom)*on/{d_frames}"
        elif effect == 'pan_up':
            z_expr = f"{zoom_start}"
            x_expr = "iw/2-(iw/zoom/2)"
            y_expr = f"(ih-ih/zoom)*(1-on/{d_frames})"
        else:
            z_expr = "1"
            x_expr = "0"
            y_expr = "0"

        # zoompan: z=zoom, d=total frames, s=output size, x/y=pan position
        zp = f"zoompan=z='{z_expr}':d={d_frames}:s=1920x1080:x='{x_expr}':y='{y_expr}':fps={FPS}"

        cmd = [
            FFMPEG, '-y', '-i', image_path,
            '-vf', f'scale=2880:1620:force_original_aspect_ratio=decrease,pad=2880:1620:(ow-iw)/2:(oh-ih)/2:black,{zp}',
            '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
            output_path
        ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        print(f"  ERROR creating segment: {result.stderr[-200:]}")
        return False
    return True


def concat_with_xfade(segments, output_path, fade_duration=1.0):
    """Concatenate video segments with crossfade transitions."""
    if len(segments) == 0:
        return False

    if len(segments) == 1:
        shutil.copy(segments[0], output_path)
        return True

    # Build complex filter for xfade chain
    # First, get durations of each segment
    durations = []
    for seg in segments:
        result = subprocess.run([
            FFMPEG, '-i', seg, '-f', 'null', '-'
        ], capture_output=True, text=True, timeout=30)
        # Parse duration from stderr
        for line in result.stderr.split('\n'):
            if 'Duration:' in line:
                parts = line.split('Duration:')[1].split(',')[0].strip()
                h, m, s = parts.split(':')
                dur = float(h) * 3600 + float(m) * 60 + float(s)
                durations.append(dur)
                break

    if len(durations) != len(segments):
        print(f"  Could not determine durations for all segments")
        # Fallback: simple concat without transitions
        return concat_simple(segments, output_path)

    # Build xfade filter chain
    inputs = []
    for seg in segments:
        inputs.extend(['-i', seg])

    n = len(segments)
    filter_parts = []
    offsets = []

    # Calculate offsets: each transition starts at (cumulative_duration - fade_duration)
    cumulative = 0
    for i in range(n - 1):
        offset = cumulative + durations[i] - fade_duration
        offsets.append(offset)
        cumulative = offset  # After xfade, the output duration starts from the offset

    # Build filter chain
    if n == 2:
        filter_complex = f"[0:v][1:v]xfade=transition=fade:duration={fade_duration}:offset={offsets[0]}[v]"
    else:
        # Chain: [0][1]xfade[v01]; [v01][2]xfade[v02]; ...
        prev = "[0:v]"
        for i in range(1, n):
            next_input = f"[{i}:v]"
            out_label = f"[v{i:02d}]" if i < n - 1 else "[v]"
            filter_parts.append(
                f"{prev}{next_input}xfade=transition=fade:duration={fade_duration}:offset={offsets[i-1]}{out_label}"
            )
            prev = out_label if i < n - 1 else ""

        filter_complex = ";".join(filter_parts)

    cmd = [FFMPEG, '-y'] + inputs + [
        '-filter_complex', filter_complex,
        '-map', '[v]',
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
        '-preset', 'medium', '-crf', '20',
        output_path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        print(f"  xfade ERROR: {result.stderr[-300:]}")
        return concat_simple(segments, output_path)
    return True


def concat_simple(segments, output_path):
    """Simple concatenation without transitions (fallback)."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        for seg in segments:
            f.write(f"file '{seg}'\n")
        concat_file = f.name

    cmd = [
        FFMPEG, '-y', '-f', 'concat', '-safe', '0', '-i', concat_file,
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
        '-preset', 'medium', '-crf', '20',
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    os.unlink(concat_file)
    return result.returncode == 0


def make_video_2_hub_tour():
    """Video 2: Command Center Tour — Hub exploration."""
    print("\n=== VIDEO 2: COMMAND CENTER TOUR ===")
    tmpdir = tempfile.mkdtemp(prefix='ars_v2_')
    segments = []

    scenes = [
        # (image, duration, effect, zoom_start, zoom_end, name)
        (TITLE, 6, 'static', 1.0, 1.0, 'title'),
        (HUB_LIVE, 18, 'zoom_in', 1.0, 1.25, 'hub-overview'),
        (HUB_LIVE, 15, 'pan_right', 1.3, 1.3, 'hub-pan-right'),
        (HUB_LIVE, 15, 'pan_left', 1.3, 1.3, 'hub-pan-left'),
        (INNERWORLD, 8, 'static', 1.0, 1.0, 'innerworld'),
        (ARCHITECTURE, 8, 'static', 1.0, 1.0, 'architecture'),
        (HUB_LIVE, 12, 'zoom_out', 1.0, 1.2, 'hub-final'),
        (CLOSING, 6, 'static', 1.0, 1.0, 'closing'),
    ]

    for i, (img, dur, effect, zs, ze, name) in enumerate(scenes):
        if not os.path.exists(img):
            print(f"  SKIP: {name} — image not found: {img}")
            continue
        out = os.path.join(tmpdir, f'seg_{i:02d}_{name}.mp4')
        print(f"  Creating segment: {name} ({dur}s, {effect})")
        if make_segment(img, out, dur, effect, zs, ze):
            segments.append(out)
        else:
            print(f"  FAILED: {name}")

    output = f'{OUT_DIR}/ars-video-2-hub-tour.mp4'
    print(f"  Concatenating {len(segments)} segments...")
    if concat_with_xfade(segments, output):
        size_mb = os.path.getsize(output) / (1024 * 1024)
        print(f"  SUCCESS: {output} ({size_mb:.1f} MB)")
    else:
        print(f"  FAILED to create final video")

    shutil.rmtree(tmpdir, ignore_errors=True)
    return output


def make_video_3_website():
    """Video 3: Website & Creative Output."""
    print("\n=== VIDEO 3: WEBSITE & CREATIVE OUTPUT ===")
    tmpdir = tempfile.mkdtemp(prefix='ars_v3_')
    segments = []

    scenes = [
        (CREATIVE, 6, 'static', 1.0, 1.0, 'creative-title'),
        (WEBSITE_GAMES, 18, 'zoom_in', 1.0, 1.2, 'website-overview'),
        (WEBSITE_GAMES, 14, 'pan_down', 1.2, 1.2, 'website-scroll'),
        (CRAWLER, 15, 'zoom_in', 1.0, 1.15, 'crawler-game'),
        (DASHBOARD, 14, 'zoom_in', 1.0, 1.2, 'dashboard'),
        (CLOSING, 6, 'static', 1.0, 1.0, 'closing'),
    ]

    for i, (img, dur, effect, zs, ze, name) in enumerate(scenes):
        if not os.path.exists(img):
            print(f"  SKIP: {name} — image not found: {img}")
            continue
        out = os.path.join(tmpdir, f'seg_{i:02d}_{name}.mp4')
        print(f"  Creating segment: {name} ({dur}s, {effect})")
        if make_segment(img, out, dur, effect, zs, ze):
            segments.append(out)
        else:
            print(f"  FAILED: {name}")

    output = f'{OUT_DIR}/ars-video-3-website.mp4'
    print(f"  Concatenating {len(segments)} segments...")
    if concat_with_xfade(segments, output):
        size_mb = os.path.getsize(output) / (1024 * 1024)
        print(f"  SUCCESS: {output} ({size_mb:.1f} MB)")
    else:
        print(f"  FAILED to create final video")

    shutil.rmtree(tmpdir, ignore_errors=True)
    return output


def make_video_4_living_system():
    """Video 4: The Living System — everything together."""
    print("\n=== VIDEO 4: THE LIVING SYSTEM ===")
    tmpdir = tempfile.mkdtemp(prefix='ars_v4_')
    segments = []

    scenes = [
        (TITLE, 8, 'static', 1.0, 1.0, 'title'),
        (TERMINAL, 18, 'zoom_in', 1.0, 1.15, 'terminal-pulse'),
        (TERMINAL, 14, 'pan_right', 1.2, 1.2, 'terminal-pan'),
        (HUB_LIVE, 16, 'zoom_in', 1.0, 1.2, 'hub-brain'),
        (WEBSITE_GAMES, 14, 'zoom_in', 1.0, 1.15, 'website-face'),
        (KINECT_DEPTH, 12, 'zoom_in', 1.0, 1.2, 'kinect-body'),
        (CRAWLER, 12, 'zoom_in', 1.0, 1.15, 'crawler-creative'),
        (INNERWORLD, 8, 'static', 1.0, 1.0, 'innerworld'),
        (ARCHITECTURE, 8, 'static', 1.0, 1.0, 'architecture'),
        (CLOSING, 8, 'static', 1.0, 1.0, 'closing'),
    ]

    for i, (img, dur, effect, zs, ze, name) in enumerate(scenes):
        if not os.path.exists(img):
            print(f"  SKIP: {name} — image not found: {img}")
            continue
        out = os.path.join(tmpdir, f'seg_{i:02d}_{name}.mp4')
        print(f"  Creating segment: {name} ({dur}s, {effect})")
        if make_segment(img, out, dur, effect, zs, ze):
            segments.append(out)
        else:
            print(f"  FAILED: {name}")

    output = f'{OUT_DIR}/ars-video-4-living-system.mp4'
    print(f"  Concatenating {len(segments)} segments...")
    if concat_with_xfade(segments, output):
        size_mb = os.path.getsize(output) / (1024 * 1024)
        print(f"  SUCCESS: {output} ({size_mb:.1f} MB)")
    else:
        print(f"  FAILED to create final video")

    shutil.rmtree(tmpdir, ignore_errors=True)
    return output


if __name__ == '__main__':
    print("Ars Electronica Video Builder v2")
    print("================================")

    which = sys.argv[1] if len(sys.argv) > 1 else 'all'

    if which in ('2', 'hub', 'all'):
        make_video_2_hub_tour()
    if which in ('3', 'website', 'all'):
        make_video_3_website()
    if which in ('4', 'living', 'all'):
        make_video_4_living_system()

    print("\nDone!")
