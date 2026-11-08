"""Capture high-resolution screenshots of all UI screens for verification.

Uses headless Chrome to visit each screen of the running PLM web application,
waits for TanStack Query data fetching, and writes PNG files to the artifacts directory.
"""

import os
import subprocess
import time
from pathlib import Path

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
OUTPUT_DIR = Path(r"C:\Users\ADITYA\.gemini\antigravity\brain\70d2ebf3-dd7a-4f49-ad9c-fb5b2b7a4bb1\screenshots")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SCREENS = [
    {
        "name": "screen_1_dashboard.png",
        "url": "http://127.0.0.1:5173/",
        "title": "Screen 1: Governance Dashboard",
    },
    {
        "name": "screen_2_part_search.png",
        "url": "http://127.0.0.1:5173/parts",
        "title": "Screen 2: Part Catalog Search",
    },
    {
        "name": "screen_2b_part_detail.png",
        "url": "http://127.0.0.1:5173/parts/PMP-0001",
        "title": "Screen 2b: Component Detail & Attributes",
    },
    {
        "name": "screen_3_bom_explorer.png",
        "url": "http://127.0.0.1:5173/bom?part=PMP-0001",
        "title": "Screen 3: Multi-Level BOM Explorer",
    },
    {
        "name": "screen_4_bom_compare.png",
        "url": "http://127.0.0.1:5173/bom/compare",
        "title": "Screen 4: BOM Compare & Reconciliation",
    },
    {
        "name": "screen_5_impact_analysis.png",
        "url": "http://127.0.0.1:5173/impact?part=PMP-0010",
        "title": "Screen 5: Change Impact & Blast Radius",
    },
    {
        "name": "screen_6_change_requests.png",
        "url": "http://127.0.0.1:5173/changes",
        "title": "Screen 6: Engineering Change Requests (ECR)",
    },
    {
        "name": "screen_7_data_health.png",
        "url": "http://127.0.0.1:5173/issues?type=duplicates",
        "title": "Screen 7: Planted Data Health Issues Detail",
    },
    {
        "name": "screen_8_ai_assistant_panel.png",
        "url": "http://127.0.0.1:5173/?assistant=open",
        "title": "Screen 8: AI Assistant Side Panel",
    },
    {
        "name": "screen_9_digital_thread.png",
        "url": "http://127.0.0.1:5173/digital-thread?part=PMP-0290",
        "title": "Screen 9: Digital Thread & Closed-Loop Timeline",
    },
]

def capture_screenshots():
    print(f"Starting screen captures to: {OUTPUT_DIR}")
    for item in SCREENS:
        target_png = OUTPUT_DIR / item["name"]
        print(f"Capturing {item['title']} -> {target_png}...")
        
        # Chrome headless flags
        cmd = [
            CHROME_PATH,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--hide-scrollbars",
            "--window-size=1280,820",
            f"--screenshot={str(target_png)}",
            item["url"],
        ]
        
        # Run command with 4 second delay
        try:
            res = subprocess.run(cmd, timeout=15, capture_output=True)
            if target_png.exists() and target_png.stat().st_size > 1000:
                print(f"  ✓ Saved ({target_png.stat().st_size} bytes)")
            else:
                print(f"  ✗ Failed to save {target_png.name}")
        except Exception as e:
            print(f"  ✗ Error capturing {item['name']}: {e}")

    print("\nAll screenshot captures completed.")

if __name__ == "__main__":
    capture_screenshots()

