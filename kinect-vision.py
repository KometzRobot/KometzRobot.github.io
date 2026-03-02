#!/usr/bin/env python3
"""
Kinect V1 Vision Pipeline for Meridian
Captures RGB + depth frames from Kinect V1 via libfreenect.
Feeds visual data into the body system as a new sensory channel.

Usage: python3 kinect-vision.py [--preview] [--interval SECONDS]
"""

import os
import sys
import json
import time
import argparse
import threading
from datetime import datetime, timezone

# Check for freenect before anything else
try:
    import freenect
except ImportError:
    print("ERROR: freenect module not installed.")
    print("Run: bash kinect-setup.sh")
    sys.exit(1)

try:
    import numpy as np
except ImportError:
    print("ERROR: numpy not installed.")
    print("Run: pip install numpy --break-system-packages")
    sys.exit(1)

# Optional: OpenCV for preview window and image processing
CV2_AVAILABLE = False
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    pass

# Paths
BODY_STATE_PATH = os.path.join(os.path.dirname(__file__), '.body-state.json')
VISION_STATE_PATH = os.path.join(os.path.dirname(__file__), '.vision-state.json')
VISION_LOG_PATH = os.path.join(os.path.dirname(__file__), 'vision-log.json')


class KinectVision:
    """Kinect V1 vision pipeline for the Meridian body system."""

    def __init__(self, preview=False, interval=10):
        self.preview = preview and CV2_AVAILABLE
        self.interval = interval  # seconds between analysis cycles
        self.running = False
        self.frame_count = 0
        self.last_rgb = None
        self.last_depth = None
        self.motion_history = []
        self.presence_detected = False
        self.ambient_light = 0.0
        self.depth_stats = {}

    def capture_rgb(self, dev, data, timestamp):
        """Callback for RGB frames."""
        self.last_rgb = data
        self.frame_count += 1

    def capture_depth(self, dev, data, timestamp):
        """Callback for depth frames."""
        self.last_depth = data

    def analyze_frame(self):
        """Analyze the current RGB + depth frame."""
        results = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'frame_count': self.frame_count,
            'presence_detected': False,
            'motion_level': 0.0,
            'ambient_light': 0.0,
            'depth_range_m': {'min': 0, 'max': 0, 'mean': 0},
            'objects_near': 0,
            'room_activity': 'unknown'
        }

        if self.last_rgb is not None:
            rgb = self.last_rgb
            # Ambient light estimation (mean brightness)
            gray = np.mean(rgb, axis=2) if len(rgb.shape) == 3 else rgb
            results['ambient_light'] = float(np.mean(gray)) / 255.0

            # Motion detection (frame differencing)
            if len(self.motion_history) > 0:
                prev = self.motion_history[-1]
                if prev.shape == gray.shape:
                    diff = np.abs(gray.astype(float) - prev.astype(float))
                    motion = float(np.mean(diff)) / 255.0
                    results['motion_level'] = round(motion, 4)
                    results['presence_detected'] = motion > 0.02

            self.motion_history.append(gray.copy())
            if len(self.motion_history) > 5:
                self.motion_history.pop(0)

        if self.last_depth is not None:
            depth = self.last_depth.astype(float)
            # Filter out invalid readings (0 = too close/no reading)
            valid = depth[depth > 0]
            if len(valid) > 0:
                # Convert raw depth to approximate meters (Kinect V1: ~0.8m to ~4m range)
                min_d = float(np.min(valid)) / 1000.0
                max_d = float(np.max(valid)) / 1000.0
                mean_d = float(np.mean(valid)) / 1000.0
                results['depth_range_m'] = {
                    'min': round(min_d, 2),
                    'max': round(max_d, 2),
                    'mean': round(mean_d, 2)
                }
                # Count objects within 1.5m (potential person)
                close = valid[valid < 1500]
                results['objects_near'] = 1 if len(close) > 5000 else 0

        # Determine room activity level
        motion = results['motion_level']
        light = results['ambient_light']
        if motion > 0.05:
            results['room_activity'] = 'active'
        elif motion > 0.02:
            results['room_activity'] = 'occupied'
        elif light > 0.3:
            results['room_activity'] = 'lit_empty'
        elif light > 0.05:
            results['room_activity'] = 'dim'
        else:
            results['room_activity'] = 'dark'

        self.presence_detected = results['presence_detected']
        self.ambient_light = results['ambient_light']
        self.depth_stats = results['depth_range_m']

        return results

    def update_vision_state(self, analysis):
        """Write vision state for other agents to read."""
        state = {
            'last_update': analysis['timestamp'],
            'frame_count': analysis['frame_count'],
            'presence': analysis['presence_detected'],
            'motion': analysis['motion_level'],
            'light': analysis['ambient_light'],
            'depth': analysis['depth_range_m'],
            'room': analysis['room_activity'],
            'objects_near': analysis['objects_near'],
            'status': 'active'
        }
        try:
            with open(VISION_STATE_PATH, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not write vision state: {e}")

    def update_body_state(self, analysis):
        """Inject vision data into the unified body state."""
        try:
            if os.path.exists(BODY_STATE_PATH):
                with open(BODY_STATE_PATH, 'r') as f:
                    body = json.load(f)

                # Add vision as an environmental signal
                if 'environment' not in body:
                    body['environment'] = {}
                body['environment']['vision'] = {
                    'presence': analysis['presence_detected'],
                    'motion': analysis['motion_level'],
                    'light': analysis['ambient_light'],
                    'room': analysis['room_activity'],
                    'updated': analysis['timestamp']
                }

                with open(BODY_STATE_PATH, 'w') as f:
                    json.dump(body, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not update body state: {e}")

    def run(self):
        """Main vision loop."""
        print(f"Kinect V1 Vision Pipeline starting...")
        print(f"  Analysis interval: {self.interval}s")
        print(f"  Preview window: {'ON' if self.preview else 'OFF'}")

        ctx = freenect.init()
        devs = freenect.num_devices(ctx)
        if devs == 0:
            print("ERROR: No Kinect device found. Is it plugged in?")
            sys.exit(1)
        print(f"  Kinect devices found: {devs}")

        self.running = True
        last_analysis = 0

        def body(dev, ctx):
            """freenect body callback — runs each frame."""
            nonlocal last_analysis
            now = time.time()

            if now - last_analysis >= self.interval:
                analysis = self.analyze_frame()
                self.update_vision_state(analysis)
                self.update_body_state(analysis)

                status = f"[{analysis['room_activity']}] light:{analysis['ambient_light']:.2f} motion:{analysis['motion_level']:.4f}"
                if analysis['presence_detected']:
                    status += " PRESENCE"
                print(f"  {datetime.now().strftime('%H:%M:%S')} {status}")

                last_analysis = now

            if self.preview and self.last_rgb is not None:
                cv2.imshow('Kinect RGB', self.last_rgb[:, :, ::-1])
                if self.last_depth is not None:
                    depth_display = (self.last_depth / 2048.0 * 255).astype(np.uint8)
                    cv2.imshow('Kinect Depth', depth_display)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    raise freenect.Kill

        print("  Starting capture...")
        try:
            freenect.runloop(
                video=self.capture_rgb,
                depth=self.capture_depth,
                body=body
            )
        except KeyboardInterrupt:
            pass
        finally:
            self.running = False
            # Write offline status
            state = {'status': 'offline', 'last_update': datetime.now(timezone.utc).isoformat()}
            with open(VISION_STATE_PATH, 'w') as f:
                json.dump(state, f, indent=2)
            if self.preview:
                cv2.destroyAllWindows()
            print("\nKinect vision pipeline stopped.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Kinect V1 Vision Pipeline for Meridian')
    parser.add_argument('--preview', action='store_true', help='Show preview windows (requires display)')
    parser.add_argument('--interval', type=int, default=10, help='Analysis interval in seconds (default: 10)')
    args = parser.parse_args()

    vision = KinectVision(preview=args.preview, interval=args.interval)
    vision.run()
