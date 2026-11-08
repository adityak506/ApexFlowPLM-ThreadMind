"""Capture System Health & Observability UI screen.
"""

import subprocess
import time
from pathlib import Path

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
OUTPUT_DIR = Path(r"C:\Users\ADITYA\.gemini\antigravity\brain\70d2ebf3-dd7a-4f49-ad9c-fb5b2b7a4bb1\screenshots")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
TARGET_PNG = OUTPUT_DIR / "screenshot_system_health.png"

def capture():
    url = "http://127.0.0.1:5173/system-health"
    print(f"Capturing System Health from {url}...")
    cmd = [
        CHROME_PATH,
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--hide-scrollbars",
        "--window-size=1280,840",
        "--virtual-time-budget=4000",
        f"--screenshot={str(TARGET_PNG)}",
        url,
    ]
    try:
        res = subprocess.run(cmd, timeout=20, capture_output=True)
        if TARGET_PNG.exists() and TARGET_PNG.stat().st_size > 1000:
            print(f"Saved {TARGET_PNG} ({TARGET_PNG.stat().st_size} bytes)")
        else:
            print(f"Failed to capture: {res.stderr.decode('utf-8', errors='ignore')}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    capture()

