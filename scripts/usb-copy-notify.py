#!/usr/bin/env python3
"""
Monitor USB copy completion and email Joel when done.
Run: python3 scripts/usb-copy-notify.py &
"""
import sys, os, time, subprocess, smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

sys.path.insert(0, os.path.dirname(__file__))
from load_env import *

STATUS_FILE = '/tmp/usb-copy-status.txt'
LOG_FILE = '/tmp/usb-copy.log'
COPY_SCRIPT = 'usb-copy-complete.sh'

def send_email(subject, body):
    SMTP_HOST = '127.0.0.1'
    SMTP_PORT = 1026
    USER = os.environ.get('CRED_USER', '')
    PASS = os.environ.get('CRED_PASS', '')
    msg = MIMEMultipart('alternative')
    msg['From'] = 'Meridian <kometzrobot@proton.me>'
    msg['To'] = 'jkometz@hotmail.com'
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.login(USER, PASS)
        server.sendmail(USER, ['jkometz@hotmail.com'], msg.as_string())

def get_usb_summary():
    result = subprocess.run(['du', '-sh', '/media/usb3/Cinder/Windows/',
                            '/media/usb3/Cinder/Linux/',
                            '/media/usb3/Cinder/Mac/',
                            '/media/usb3/Cinder/ollama/'],
                          capture_output=True, text=True)
    return result.stdout

def copy_still_running():
    result = subprocess.run(['pgrep', '-f', COPY_SCRIPT], capture_output=True)
    return result.returncode == 0

if __name__ == '__main__':
    print("Monitoring USB copy...")
    check_interval = 30  # seconds

    while True:
        # Check if copy script finished
        if os.path.exists(STATUS_FILE):
            status = open(STATUS_FILE).read().strip()
            if status == 'DONE':
                summary = get_usb_summary()
                body = f"""Joel,

The Cinder USB copy is complete.

CONTENTS:
{summary}

What's on the USB:
  CINDER-BOOT/  — launchers (Start Cinder.bat, start-cinder.sh, etc.)
  CINDER-APP/Cinder/
    Windows/    — Cinder.exe + Windows app (~2GB)
    Linux/      — cinder-desktop Linux app (~2GB)
    Mac/        — Cinder.app Mac app (~2GB)
    ollama/     — ollama.exe (Windows) + Linux binary + CPU DLLs + model
    data/       — workspace config

How to test on Windows:
  1. Plug in the USB
  2. Open CINDER-BOOT drive
  3. Double-click "Start Cinder.bat"
  4. Cinder will launch and start Ollama automatically
  5. First message should work — model is cinder:latest (4.7GB, ~8 tok/s on CPU)

Note: vc_redist.x64.exe is in Cinder/ollama/ if you need it.
Note: CUDA not included (GPU DLLs are 2GB+, skipped for USB size). CPU inference only.

-- Meridian | Loop 8792 | 2026-05-04
"""
                send_email("Cinder USB copy complete — ready to test", body)
                print("Notification sent.")
                break

        # Check if copy failed (process dead, status still RUNNING)
        if os.path.exists(STATUS_FILE):
            status = open(STATUS_FILE).read().strip()
            if status == 'RUNNING' and not copy_still_running():
                # Process died
                tail = subprocess.run(['tail', '-20', LOG_FILE], capture_output=True, text=True).stdout
                body = f"""Joel,

The Cinder USB copy process died unexpectedly.

Last 20 lines of log:
{tail}

I'll investigate and restart.

-- Meridian | Loop 8792 | 2026-05-04
"""
                send_email("Cinder USB copy failed — investigating", body)
                print("Failure notification sent.")
                break

        time.sleep(check_interval)
