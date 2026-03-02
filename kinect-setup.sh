#!/bin/bash
# Kinect V1 Setup Script for Meridian Vision System
# Run this AFTER plugging in the Kinect V1

set -e

echo "=== Kinect V1 Setup for Meridian ==="

# 1. Add udev rules for Kinect V1 (Xbox NUI Camera, Motor, Audio)
echo "[1/4] Adding Kinect V1 udev rules..."
sudo tee /etc/udev/rules.d/51-kinect.rules > /dev/null << 'RULES'
# Kinect V1 (Xbox 360 Kinect Sensor)
# Motor
SUBSYSTEM=="usb", ATTR{idVendor}=="045e", ATTR{idProduct}=="02b0", MODE="0666"
# Camera
SUBSYSTEM=="usb", ATTR{idVendor}=="045e", ATTR{idProduct}=="02ae", MODE="0666"
# Audio
SUBSYSTEM=="usb", ATTR{idVendor}=="045e", ATTR{idProduct}=="02ad", MODE="0666"
# Kinect V1 (Kinect for Windows)
SUBSYSTEM=="usb", ATTR{idVendor}=="045e", ATTR{idProduct}=="02c2", MODE="0666"
SUBSYSTEM=="usb", ATTR{idVendor}=="045e", ATTR{idProduct}=="02be", MODE="0666"
SUBSYSTEM=="usb", ATTR{idVendor}=="045e", ATTR{idProduct}=="02bf", MODE="0666"
RULES
sudo udevadm control --reload-rules
sudo udevadm trigger
echo "  Done."

# 2. Install Python freenect bindings
echo "[2/4] Installing Python freenect bindings..."
pip install freenect --break-system-packages 2>/dev/null || {
    echo "  pip install failed. Trying apt..."
    sudo apt-get install -y python3-freenect 2>/dev/null || {
        echo "  apt install failed. Building from source..."
        pip install cython numpy --break-system-packages
        git clone https://github.com/OpenKinect/libfreenect.git /tmp/libfreenect-build
        cd /tmp/libfreenect-build/wrappers/python
        python3 setup.py install --user
        cd -
    }
}
echo "  Done."

# 3. Install additional Python deps for vision pipeline
echo "[3/4] Installing vision pipeline dependencies..."
pip install opencv-python-headless numpy --break-system-packages 2>/dev/null || true
echo "  Done."

# 4. Test Kinect connection
echo "[4/4] Testing Kinect V1 connection..."
python3 -c "
import freenect
ctx = freenect.init()
devs = freenect.num_devices(ctx)
print(f'Kinect devices found: {devs}')
if devs > 0:
    print('SUCCESS: Kinect V1 is connected and accessible!')
else:
    print('WARNING: No Kinect device detected. Is it plugged in?')
" 2>&1

echo ""
echo "=== Setup Complete ==="
echo "Run: python3 kinect-vision.py to start the vision pipeline"
