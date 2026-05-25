#!/usr/bin/env python3
"""
Generate an Instagram session file for instaloader from a browser session cookie.

Instagram blocks automated logins since 2024. The reliable approach is to:
  1. Log in via a browser (Firefox or Chrome)
  2. Copy the 'sessionid' cookie value from DevTools
  3. Run this script with that value

Usage:
    pip install instaloader
    python3 scripts/generate_instagram_session.py

How to get the sessionid cookie:
    Chrome : DevTools (F12) → Application → Cookies → instagram.com → sessionid
    Firefox: DevTools (F12) → Storage  → Cookies → instagram.com → sessionid
"""

import os
import sys

try:
    import instaloader
except ImportError:
    print("instaloader not installed. Run: pip install instaloader")
    sys.exit(1)

SESSION_FILE = os.environ.get("INSTAGRAM_SESSION_FILE", "/data/instagram_session")
USERNAME = os.environ.get("INSTAGRAM_USERNAME", "")

if not USERNAME:
    USERNAME = input("Instagram username (without @): ").strip()

print("\nOpen Instagram in your browser, log in, then:")
print("  Chrome : DevTools (F12) → Application → Cookies → instagram.com → sessionid")
print("  Firefox: DevTools (F12) → Storage → Cookies → instagram.com → sessionid")
session_id = input("\nPaste the sessionid cookie value: ").strip()

if not session_id:
    print("No session ID provided.")
    sys.exit(1)

loader = instaloader.Instaloader(
    download_pictures=False,
    download_videos=False,
    quiet=True,
)

loader.context._session.cookies.set("sessionid", session_id, domain=".instagram.com")
loader.context.username = USERNAME

print(f"\nVerifying session for @{USERNAME}...")
try:
    username_check = loader.test_login()
    if not username_check:
        print("Session invalid or expired. Get a fresh sessionid from your browser.")
        sys.exit(1)
    print(f"Session valid — logged in as: {username_check}")
except Exception as e:
    print(f"Session check failed: {e}")
    sys.exit(1)

os.makedirs(
    os.path.dirname(SESSION_FILE) if os.path.dirname(SESSION_FILE) else ".",
    exist_ok=True,
)
loader.save_session_to_file(SESSION_FILE)
print(f"\nSession saved to: {SESSION_FILE}")
print("The Docker containers will use this file — no more login needed.")
