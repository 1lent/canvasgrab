import base64
import glob
import hashlib
import hmac
import json
import os
import platform
import re
import struct
import subprocess
import sqlite3
import time
from pathlib import Path
from typing import Optional, Tuple

import requests

from .proto import encode_canvas_request, decode_canvas_url
from .utils import die

TOKEN_URL = "https://open.spotify.com/api/token"
TOTP_SECRETS_URL = (
    "https://raw.githubusercontent.com/xyloflake/spot-secrets-go/"
    "refs/heads/main/secrets/secretDict.json"
)
TOTP_SECRETS_CACHE = Path.home() / ".cache" / "canvasgrab" / "totp_secrets.json"
TOTP_CACHE_TTL = 1800
SP_DC_CACHE = Path.home() / ".cache" / "canvasgrab" / "sp_dc"
CANVAS_ENDPOINT = "https://gew1-spclient.spotify.com/canvaz-cache/v0/canvases"
CANVAS_URL_RE = re.compile(rb"https?://[a-zA-Z0-9._/%-]+\.cnvs\.mp4")


def get_spotify_token(sp_dc: str) -> Optional[str]:
    try:
        secret = _get_latest_totp_secret()
        try:
            ts = requests.get("https://open.spotify.com/server-time").json()["serverTime"]
        except Exception:
            ts = int(time.time())
        totp = _generate_totp(secret)
        totp_server = _generate_totp(secret, counter=ts // 30)
        resp = requests.get(
            TOKEN_URL,
            params={
                "reason": "init",
                "productType": "mobile-web-player",
                "totp": totp,
                "totpVer": "5",
                "totpServer": totp_server,
                "ts": int(time.time()),
            },
            headers={
                "Cookie": f"sp_dc={sp_dc}",
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                ),
            },
        )
        resp.raise_for_status()
        return resp.json().get("accessToken")
    except Exception:
        return None


def _fetch_totp_secrets() -> dict:
    if TOTP_SECRETS_CACHE.exists():
        age = TOTP_SECRETS_CACHE.stat().st_mtime
        if (time.time() - age) < TOTP_CACHE_TTL:
            try:
                return json.loads(TOTP_SECRETS_CACHE.read_text())
            except Exception:
                pass
    resp = requests.get(TOTP_SECRETS_URL)
    resp.raise_for_status()
    secrets = resp.json()
    TOTP_SECRETS_CACHE.parent.mkdir(parents=True, exist_ok=True)
    TOTP_SECRETS_CACHE.write_text(json.dumps(secrets))
    return secrets


def _get_latest_totp_secret() -> bytes:
    secrets = _fetch_totp_secrets()
    versions = sorted(secrets.keys(), key=int)
    cipher = secrets[versions[-1]]
    mapped = "".join(str(v ^ ((i % 33) + 9)) for i, v in enumerate(cipher))
    hex_str = "".join(f"{ord(c):02x}" for c in mapped)
    secret_bytes = bytes.fromhex(hex_str)
    b32 = ""
    t = n = 0
    for b in secret_bytes:
        n = (n << 8) | b
        t += 8
        while t >= 5:
            b32 += "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"[(n >> (t - 5)) & 31]
            t -= 5
    if t > 0:
        b32 += "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"[(n << (5 - t)) & 31]
    if len(b32) % 8:
        b32 += "=" * (8 - len(b32) % 8)
    return base64.b32decode(b32.upper())


def _generate_totp(secret_bytes: bytes, counter: Optional[int] = None) -> str:
    if counter is None:
        try:
            ts = requests.get("https://open.spotify.com/server-time").json()["serverTime"]
        except Exception:
            ts = int(time.time())
        counter = ts // 30
    ctr = struct.pack(">Q", counter)
    d = hmac.new(secret_bytes, ctr, hashlib.sha1).digest()
    off = d[-1] & 0x0F
    code = struct.unpack(">I", d[off:off + 4])[0] & 0x7FFFFFFF
    return f"{code % 1000000:06d}"


class CanvasError(Exception):
    pass


class NoCanvasError(CanvasError):
    pass


def get_canvas_url(track_id: str, token: str, verbose: bool = False) -> str:
    uri = f"spotify:track:{track_id}"
    body = encode_canvas_request(uri)
    resp = requests.post(
        CANVAS_ENDPOINT,
        headers={"Content-Type": "application/x-protobuf", "Authorization": f"Bearer {token}"},
        data=body,
    )
    resp.raise_for_status()
    if verbose:
        import sys
        print(f"  [verbose] Canvas status: {resp.status_code}, content length: {len(resp.content)}", file=sys.stderr)
    url = decode_canvas_url(resp.content)
    if not url:
        raise NoCanvasError("No canvas available for this track")
    return url


def auto_get_sp_dc() -> Optional[str]:
    def _try_spotify(sqlite_path: str) -> Optional[str]:
        try:
            conn = sqlite3.connect(f"file:{sqlite_path}?mode=ro&immutable=1", uri=True)
            rows = conn.execute(
                "SELECT name, value, encrypted_value FROM cookies "
                "WHERE host_key LIKE '%spotify%' AND name='sp_dc'"
            ).fetchall()
            conn.close()
            for _name, value, enc in rows:
                if value:
                    return value
                if enc:
                    val = _decrypt_chromium_cookie(enc)
                    if val:
                        return val
        except Exception:
            pass
        return None

    is_macos = platform.system() == "Darwin"
    BASE = str(Path.home())
    appdata = os.environ.get("APPDATA", "")
    localappdata = os.environ.get("LOCALAPPDATA", "")

    if is_macos:
        browser_dirs: list[Tuple[str, list[str]]] = [
            ("Chrome", [f"{BASE}/Library/Application Support/Google/Chrome"]),
            ("Brave", [f"{BASE}/Library/Application Support/BraveSoftware/Brave-Browser"]),
            ("Edge", [f"{BASE}/Library/Application Support/Microsoft Edge"]),
            ("Chromium", [f"{BASE}/Library/Application Support/Chromium"]),
            ("Vivaldi", [f"{BASE}/Library/Application Support/Vivaldi"]),
            ("Opera", [f"{BASE}/Library/Application Support/com.operasoftware.Opera"]),
            ("Discord", [f"{BASE}/Library/Application Support/discord"]),
            ("Cursor", [f"{BASE}/Library/Application Support/Cursor"]),
        ]
    else:
        browser_dirs = [
            ("Chrome", [f"{localappdata}/Google/Chrome/User Data"]),
            ("Brave", [f"{localappdata}/BraveSoftware/Brave-Browser/User Data"]),
            ("Edge", [f"{localappdata}/Microsoft/Edge/User Data"]),
            ("Chromium", [f"{localappdata}/Chromium/User Data"]),
            ("Opera", [f"{appdata}/Opera Software/Opera Stable"]),
            ("Vivaldi", [f"{localappdata}/Vivaldi/User Data"]),
        ]

    for _name, dirs in browser_dirs:
        for d in dirs:
            if not d or not os.path.isdir(d):
                continue
            for profile in ["Default", "Profile 1", "Profile 2", ""]:
                path = os.path.join(d.strip(), profile.strip(), "Cookies")
                if path.count("//"):
                    path = path.replace("//", "/")
                if os.path.isfile(path):
                    cookie = _try_spotify(path)
                    if cookie:
                        _cache_sp_dc(cookie)
                        return cookie

    if is_macos:
        ff_profiles = f"{BASE}/Library/Application Support/Firefox/Profiles"
        if os.path.isdir(ff_profiles):
            for name in os.listdir(ff_profiles):
                path = os.path.join(ff_profiles, name, "cookies.sqlite")
                if os.path.isfile(path):
                    cookie = _try_spotify(path)
                    if cookie:
                        _cache_sp_dc(cookie)
                        return cookie

        for saf_path in [
            f"{BASE}/Library/Containers/com.apple.Safari/Data/Library/Cookies/Cookies.binarycookies",
            f"{BASE}/Library/Cookies/Cookies.binarycookies",
        ]:
            cookie = _parse_safari_binarycookies(saf_path)
            if cookie:
                _cache_sp_dc(cookie)
                return cookie

    if SP_DC_CACHE.exists():
        try:
            return SP_DC_CACHE.read_text().strip()
        except Exception:
            pass

    return None


def _cache_sp_dc(cookie: str) -> None:
    SP_DC_CACHE.parent.mkdir(parents=True, exist_ok=True)
    SP_DC_CACHE.write_text(cookie.strip())


def _parse_safari_binarycookies(path: str) -> Optional[str]:
    try:
        with open(path, "rb") as f:
            data = f.read()
    except (PermissionError, FileNotFoundError, OSError):
        return None
    if data[:4] != b"cook":
        return None
    try:
        num_pages = struct.unpack_from(">I", data, 4)[0]
        page_sizes = struct.unpack_from(">" + "I" * num_pages, data, 8)
    except struct.error:
        return None
    offset = 8 + 4 * num_pages
    for page_size in page_sizes:
        page = data[offset:offset + page_size]
        offset += page_size
        if page[:4] != b"\x00\x00\x01\x00":
            continue
        pos = 4
        try:
            num_cookies = struct.unpack_from("<I", page, pos)[0]
        except struct.error:
            continue
        pos += 4
        for _ in range(min(num_cookies, 1000)):
            try:
                cookie_size = struct.unpack_from("<I", page, pos)[0]
            except struct.error:
                break
            pos += 4
            cookie_data = page[pos:pos + cookie_size]
            pos += cookie_size
            if len(cookie_data) < 12:
                continue
            cpos = 8
            domain = _read_cstring(cookie_data, cpos)
            cpos += len(domain) + 1
            name = _read_cstring(cookie_data, cpos)
            cpos += len(name) + 1
            path_ = _read_cstring(cookie_data, cpos)
            cpos += len(path_) + 1
            value = _read_cstring(cookie_data, cpos)
            if "spotify" in domain.lower() and name == "sp_dc":
                return value
    return None


def _read_cstring(data: bytes, offset: int) -> str:
    end = data.find(b"\x00", offset)
    if end < 0:
        return ""
    return data[offset:end].decode("utf-8", errors="replace")


def _decrypt_chromium_cookie(encrypted_value: bytes) -> Optional[str]:
    if platform.system() != "Darwin":
        return None
    if not encrypted_value or len(encrypted_value) < 18:
        return None
    ver = encrypted_value[:3]
    if ver not in (b"v10", b"v11"):
        return None
    for service in ["Chrome Safe Storage", "Chromium Safe Storage"]:
        try:
            result = subprocess.run(
                ["security", "find-generic-password", "-w", "-s", service],
                capture_output=True, text=True,
            )
            if result.returncode == 0 and result.stdout.strip():
                password = result.stdout.strip()
                break
        except Exception:
            continue
    else:
        return None
    key = hashlib.pbkdf2_hmac("sha1", password.encode(), b"saltysalt", 1003, 16)
    iv = encrypted_value[3:15]
    ciphertext = encrypted_value[15:]
    try:
        p = subprocess.run(
            ["openssl", "enc", "-d", "-aes-128-cbc", "-K", key.hex(), "-iv", iv.hex(), "-nopad"],
            input=ciphertext, capture_output=True,
        )
        if p.returncode != 0:
            return None
        plain = p.stdout
        if not plain:
            return None
        pad_len = plain[-1]
        if 0 < pad_len <= 16:
            plain = plain[:-pad_len]
        return plain.decode("utf-8", errors="replace")
    except Exception:
        return None


def get_cached_canvas_url(track_uri: str) -> Optional[str]:
    needles = [track_uri.encode(), base64.b64encode(track_uri.encode())]
    is_macos = platform.system() == "Darwin"
    if is_macos:
        search_roots = [
            os.path.expanduser("~/Library/Application Support/Spotify/PersistentCache"),
        ]
    else:
        search_roots = [
            os.path.join(os.environ.get("APPDATA", ""), "Spotify", "PersistentCache"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Spotify", "PersistentCache"),
        ]
    for spotify_dir in search_roots:
        if not spotify_dir or not os.path.isdir(spotify_dir):
            continue
        for pattern in ["Users/*/primary.ldb/*.ldb", "Users/*/*.ldb/*.ldb", "public.ldb/*.ldb"]:
            for ldb_file in glob.glob(os.path.join(spotify_dir, pattern)):
                if not os.path.isfile(ldb_file):
                    continue
                try:
                    with open(ldb_file, "rb") as f:
                        data = f.read()
                    for needle in needles:
                        idx = data.find(needle)
                        if idx < 0:
                            continue
                        m = CANVAS_URL_RE.search(data, idx, idx + 600)
                        if m:
                            return m.group().decode()
                except Exception:
                    pass
    return None


def get_current_track() -> Tuple[str, str, str]:
    if platform.system() != "Darwin":
        die(
            "No track provided. Auto-detection only works on macOS with Spotify desktop app.\n"
            "  Provide a track URI/URL as argument:\n"
            '  canvasgrab "spotify:track:3OHfY25tqY28d16oZczHc8"'
        )
    script = (
        'tell application "Spotify" to '
        "get {artist of current track, name of current track, id of current track}"
    )
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if result.returncode != 0:
        die("Spotify not running or no track playing.")
    parts = [p.strip() for p in result.stdout.strip().split(", ", 2)]
    if len(parts) < 3:
        die("Could not parse Spotify track info.")
    artist, title = parts[0], parts[1]
    track_id = parts[2].split(":")[-1] if ":" in parts[2] else parts[2]
    return artist, title, track_id
