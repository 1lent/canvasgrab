#!/usr/bin/env python3
"""Spotify Canvas Grabber — grab the looping video for any song.

Usage:
    canvasgrab                        Auto-detect current track (macOS)
    canvasgrab "spotify:track:xxx"    Grab specific track
    canvasgrab --gif                  Also convert to GIF
    canvasgrab --open                 Open file after download
"""

import argparse
import os
import sys
from pathlib import Path

_script_dir = Path(__file__).resolve().parent
if str(_script_dir) not in sys.path:
    sys.path.insert(0, str(_script_dir))

import platform
import re
from typing import Optional

from canvasgrab.auth import (
    auto_get_sp_dc,
    get_cached_canvas_url,
    get_canvas_url,
    get_current_track,
    get_spotify_token,
)
from canvasgrab.utils import OUTPUT_DIR, convert_to_gif, die, download_file, open_file

SPOTIFY_URI_RE = re.compile(r"spotify:track:([A-Za-z0-9]{22})")
SPOTIFY_URL_RE = re.compile(r"open\.spotify\.com/track/([A-Za-z0-9]{22})")
BARE_ID_RE = re.compile(r"^[A-Za-z0-9]{22}$")


def parse_track_id(raw: str) -> str:
    m = SPOTIFY_URI_RE.search(raw) or SPOTIFY_URL_RE.search(raw)
    if m:
        return m.group(1)
    if BARE_ID_RE.match(raw):
        return raw
    die(f"Not a valid Spotify track URI/URL/ID: {raw}")


def _install(argv0: str) -> None:
    target = Path("/usr/local/bin/canvasgrab")
    source = Path(argv0).resolve()
    source.chmod(source.stat().st_mode | 0o111)
    if not target.parent.exists():
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            die(f"Need permission to create {target.parent}.\n  sudo python3 {source} --install")
    if target.is_symlink() or target.exists():
        target.unlink()
    try:
        target.symlink_to(source)
    except PermissionError:
        die(f"Need permission to write to {target}.\n  sudo python3 {source} --install")
    print("Installed. Run `canvasgrab` from anywhere.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Spotify Canvas Grabber — download the looping video for any song"
    )
    parser.add_argument("track", nargs="?", help="Spotify track URI, share URL, or bare ID")
    parser.add_argument("--gif", action="store_true", help="Also convert to GIF (requires FFmpeg)")
    parser.add_argument("--open", action="store_true", help="Open the file after download")
    parser.add_argument("--sp-dc", metavar="COOKIE", help="Spotify sp_dc cookie (or set SP_DC env var)")
    parser.add_argument("--install", action="store_true", help="Install canvasgrab to /usr/local/bin")
    args = parser.parse_args()

    if args.install:
        _install(argv0=__file__)
        return

    if args.track:
        track_id = parse_track_id(args.track)
        artist, title = "Unknown", "Unknown"
    else:
        artist, title, track_id = get_current_track()

    track_uri = f"spotify:track:{track_id}"
    print(f"\n  {artist} — {title}")

    sp_dc: Optional[str] = None
    from_manual = False

    if args.sp_dc:
        sp_dc = args.sp_dc
        from_manual = True
        print("  Using manual cookie")
    elif os.environ.get("SP_DC"):
        sp_dc = os.environ["SP_DC"]
    else:
        sp_dc = auto_get_sp_dc()

    canvas_url: Optional[str] = None

    if sp_dc:
        print("  Authenticating ...")
        token = get_spotify_token(sp_dc)
        if token:
            print("  Looking up Canvas ...")
            try:
                canvas_url = get_canvas_url(track_id, token)
            except Exception as e:
                err = str(e)
                if from_manual and "401" in err:
                    die(
                        "Canvas API rejected the token.\n"
                        "Your --sp-dc cookie is likely invalid or expired.\n"
                        "Re-copy it from open.spotify.com → DevTools → Cookies."
                    )
                print(f"  Canvas API error: {err}", file=sys.stderr)
                canvas_url = None
        else:
            if from_manual:
                die(
                    "Authentication failed with provided --sp-dc cookie.\n"
                    "The cookie may be expired or invalid."
                )
            print("  Auth failed, trying cache ...")

    if not canvas_url:
        print("  Searching local cache ...")
        canvas_url = get_cached_canvas_url(track_uri)

    if not canvas_url:
        if not sp_dc:
            die(
                "No sp_dc cookie found and no cached canvas available.\n\n"
                "To fix:\n"
                "  1. Go to https://open.spotify.com and log in\n"
                "  2. Open DevTools → Application → Cookies → open.spotify.com\n"
                "  3. Copy the 'sp_dc' cookie value\n"
                "  4. Run: canvasgrab --sp-dc \"<cookie>\""
            )
        elif from_manual:
            die(
                "No canvas found. Either:\n"
                "  - This track has no looping video, or\n"
                "  - The --sp-dc cookie is invalid/expired.\n\n"
                "Check that your cookie is correct by visiting open.spotify.com\n"
                "and re-copying it from DevTools → Application → Cookies."
            )
        else:
            die(
                "No canvas available for this track."
            )

    safe_name = f"{artist} - {title}".replace("/", ":")
    mp4_path = OUTPUT_DIR / f"{safe_name}.mp4"
    print("  Downloading ...")
    try:
        download_file(canvas_url, mp4_path)
    except Exception as e:
        die(f"Download failed: {e}")
    print(f"  Saved: {mp4_path}")

    if args.gif:
        gif_path = OUTPUT_DIR / f"{safe_name}.gif"
        print("  Converting to GIF ...")
        convert_to_gif(mp4_path, gif_path)
        print(f"  Saved: {gif_path}")

    if args.open:
        open_file(mp4_path)


if __name__ == "__main__":
    main()
