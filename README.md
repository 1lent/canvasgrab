# canvasgrab

Download Spotify Canvas videos (the looping clips behind songs) as MP4 or GIF.

<img width="400" height="711" alt="PARTYNEXTDOOR - DIE TRYING" src="https://github.com/user-attachments/assets/3ef2dc8b-60f2-4053-b9bc-c693a2e8096e" /> <img width="400" height="711" alt="PARTYNEXTDOOR - DIE TRYING" src="https://github.com/user-attachments/assets/fe518ce6-c53b-4eed-9d72-8169b779ea7d" />



## Install

### macOS

```bash
git clone https://github.com/1lent/canvasgrab.git
cd canvasgrab
pip3 install -r requirements.txt
brew install ffmpeg                       # optional, for GIFs
sudo python3 canvasgrab.py --install      # symlinks to /usr/local/bin
```

### Windows

```powershell
git clone https://github.com/1lent/canvasgrab.git
cd canvasgrab
pip install -r requirements.txt
winget install ffmpeg                     # optional, for GIFs
```

## Usage

```bash
canvasgrab --sp-dc "<cookie>"              # manual cookie (any platform)
canvasgrab                                 # current Spotify track (macOS)
canvasgrab "spotify:track:3OHfY..."         # any track by URI
canvasgrab "https://open.spotify.com/track/3OHfY..."  # by share URL
canvasgrab --gif                            # also create a GIF
canvasgrab --open                           # open file after download
canvasgrab --verbose                        # debug API responses
```

Files land in `~/canvasgrab/`.

## Getting your sp_dc cookie

canvasgrab needs your Spotify `sp_dc` cookie. On macOS it auto-detects from Chrome, Brave, Edge, Firefox, Safari, Discord, or Cursor. On Windows, provide it manually:

1. Go to [open.spotify.com](https://open.spotify.com) and log in
2. Open **DevTools** (F12) → **Application** → **Cookies** → `open.spotify.com`
3. Copy the value of the `sp_dc` cookie

**Windows (PowerShell):**
```powershell
$env:SP_DC = "<your_cookie>"
python canvasgrab.py "spotify:track:3OHfY25tqY28d16oZczHc8"
```

**Windows (cmd — persistent):**
```cmd
setx SP_DC "<your_cookie>"
```

**macOS / Linux:**
```bash
export SP_DC="<your_cookie>"
canvasgrab
```

Or pass it inline on any platform:
```bash
canvasgrab --sp-dc "<your_cookie>" "spotify:track:3OHfY25tqY28d16oZczHc8"
```

## How it works

canvasgrab auto-detects your Spotify `sp_dc` cookie from Chrome, Brave, Edge, Firefox, Safari, Discord, or Cursor. On macOS it decrypts Chromium cookies via the Keychain. If no browser cookies exist, it falls back to the Spotify desktop app's LevelDB cache.

## Acknowledgements

- [Paxsenix0/Spotify-Canvas-API](https://github.com/Paxsenix0/Spotify-Canvas-API) — protobuf schema, TOTP auth flow, and endpoint discovery
- [Delitefully/spotify-canvas-downloader](https://github.com/Delitefully/spotify-canvas-downloader) — original Python implementation and auth approach
- [bartleyg/my-spotify-canvas](https://github.com/bartleyg/my-spotify-canvas) — anonymous canvas token discovery
- [xyloflake/spot-secrets-go](https://github.com/xyloflake/spot-secrets-go) — Spotify TOTP signing secret rotation

## License

MIT
