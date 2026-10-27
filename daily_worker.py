#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
daily_worker.py — Automated Daily Video Publisher for YouTube Channel.

Picks the next un-used video from the competitor library (1 to 63),
renders the video with Pexels HD B-roll and speaker branding,
uploads to YouTube, and records state.
"""

import os
import sys
import json
import time
import argparse
import subprocess
from datetime import datetime

# UTF-8 stream handling
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

POSTED_FILE = os.path.join(os.path.dirname(__file__), "data", "posted_videos.json")
COMPETITORS_FILE = os.path.join(os.path.dirname(__file__), "extracted_competitor_videos.json")
DOCS_INDEX = os.path.join(os.path.dirname(__file__), "docs", "index.html")


def load_posted():
    if os.path.exists(POSTED_FILE):
        try:
            with open(POSTED_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_posted(posted_list):
    os.makedirs(os.path.dirname(POSTED_FILE), exist_ok=True)
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(posted_list, f, indent=2, ensure_ascii=False)


def get_next_video():
    posted = load_posted()
    posted_ids = {p.get("id") for p in posted}

    if not os.path.exists(COMPETITORS_FILE):
        raise FileNotFoundError(f"Missing {COMPETITORS_FILE}")

    with open(COMPETITORS_FILE, "r", encoding="utf-8") as f:
        all_videos = json.load(f)

    for idx, v in enumerate(all_videos, 1):
        if v.get("id") not in posted_ids:
            return idx, v
    return None, None


def update_docs_index(video_id, published_date_str):
    """Updates docs/index.html so the web dashboard marks the video as Used."""
    if not os.path.exists(DOCS_INDEX):
        return
    try:
        with open(DOCS_INDEX, "r", encoding="utf-8") as f:
            html = f.read()

        # Find {"num": ..., "id": "video_id", ... "used": false, "used_at": null}
        target_pattern = f'"id": "{video_id}"'
        if target_pattern in html:
            # Simple replacement for this specific video in the JS array
            import re
            def replace_used(match):
                block = match.group(0)
                block = block.replace('"used": false', '"used": true')
                block = block.replace('"used_at": null', f'"used_at": "{published_date_str}"')
                return block

            regex = re.compile(r'\{[^{}]*?"id":\s*"' + re.escape(video_id) + r'"[^{}]*?\}')
            new_html = regex.sub(replace_used, html, count=1)

            with open(DOCS_INDEX, "w", encoding="utf-8", newline="\n") as f:
                f.write(new_html)
            print(f"✅ Updated docs/index.html: marked {video_id} as Used.")
    except Exception as e:
        print(f"⚠️ Warning updating docs/index.html: {e}")


def main():
    parser = argparse.ArgumentParser(description="Daily YouTube Automation Worker")
    parser.add_argument("--privacy", type=str, default="public", choices=["public", "private", "unlisted"])
    parser.add_argument("--duration", type=str, default="180", help="Clip duration in seconds (0 for full)")
    parser.add_argument("--dry-run", action="store_true", help="Dry run test mode")
    args = parser.parse_args()

    print("=" * 70)
    print("  Daily YouTube Video Auto-Publisher")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Target Privacy: {args.privacy} | Duration: {args.duration}s")
    print("=" * 70)

    num, video = get_next_video()
    if not video:
        print("🎉 All 63 videos in the library have been posted!")
        return

    vid_id = video["id"]
    title = video["title"]
    url = video["url"]

    print(f"\n🎬 Next Video to Publish: #{num}")
    print(f"   Title: {title}")
    print(f"   URL:   {url}")
    print(f"   ID:    {vid_id}\n")

    # Build command to execute pipeline.py
    cmd = [
        sys.executable,
        "pipeline.py",
        "--url", url,
        "--privacy", args.privacy,
        "--upload",
        "--upload-shorts",
    ]

    dur_val = str(args.duration).strip()
    if dur_val and dur_val not in ("0", "full"):
        cmd.extend(["--duration", dur_val])

    if args.dry_run:
        cmd.append("--dry-run")

    print(f"🚀 Executing Pipeline: {' '.join(cmd)}\n")
    start_t = time.time()
    res = subprocess.run(cmd)
    elapsed = time.time() - start_t

    if res.returncode == 0:
        if not args.dry_run:
            pub_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"\n🎉 Video #{num} ({vid_id}) successfully processed and published in {elapsed:.1f}s!")

            # Update posted state
            posted = load_posted()
            posted.append({
                "num": num,
                "id": vid_id,
                "title": title,
                "url": url,
                "published_at": pub_time,
                "privacy": args.privacy,
                "duration": dur_val,
            })
            save_posted(posted)
            print(f"📝 Recorded in {POSTED_FILE} (Total posted: {len(posted)}/63)")

            # Update dashboard
            update_docs_index(vid_id, pub_time)
        else:
            print(f"\n✅ Dry run completed successfully in {elapsed:.1f}s (no state updated).")

    else:
        print(f"\n❌ Pipeline failed with return code {res.returncode}")
        sys.exit(res.returncode)


if __name__ == "__main__":
    main()
