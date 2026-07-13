import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Optional

import requests


OUTPUT_DIR = Path.home() / "canvasgrab"


def die(msg: str, code: int = 1) -> None:
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(code)


def _which(cmd: str) -> Optional[str]:
    try:
        prog = "where" if platform.system() == "Windows" else "which"
        result = subprocess.run([prog, cmd], capture_output=True, text=True)
        return result.stdout.strip().split("\n")[0] if result.stdout.strip() else None
    except FileNotFoundError:
        return None


def open_file(path: Path) -> None:
    system = platform.system()
    if system == "Darwin":
        subprocess.run(["open", str(path)])
    elif system == "Windows":
        os.startfile(str(path))
    else:
        subprocess.run(["xdg-open", str(path)])


def download_file(url: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    resp = requests.get(url, stream=True)
    resp.raise_for_status()
    total = int(resp.headers.get("content-length", 0))
    downloaded = 0
    with open(path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
            downloaded += len(chunk)
            if total:
                pct = downloaded * 100 // total
                bar_len = 40
                filled = pct * bar_len // 100
                bar = "\u2588" * filled + "\u2591" * (bar_len - filled)
                print(f"\r  [{bar}] {pct}%", end="", flush=True)
    if total:
        print()


def convert_to_gif(mp4_path: Path, gif_path: Path) -> None:
    if not _which("ffmpeg"):
        die("FFmpeg not found. Install it: brew install ffmpeg")
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", str(mp4_path),
         "-vf", "fps=10,scale=400:-1:flags=lanczos",
         str(gif_path)],
        capture_output=True,
    )
    if result.returncode != 0:
        die(f"FFmpeg failed:\n{result.stderr.decode()}")
