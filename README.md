# canvasgrab

Download Spotify Canvas videos (the looping clips behind songs) as MP4 or GIF.

## Install

```bash
git clone https://github.com/1lent/canvasgrab.git
cd canvasgrab
pip3 install -r requirements.txt
brew install ffmpeg                   # for GIF conversion (optional)   (choco install ffmpeg (FOR WINDOWS))
python3 canvasgrab.py --install       # symlinks to /usr/local/bin
sudo python3 canvasgrab.py --install  # if /usr/local/bin needs permission
```

After `--install`, run `canvasgrab` from anywhere.

## Usage

```bash
canvasgrab                           # current Spotify track (macOS)
canvasgrab "spotify:track:3OHfY..."  # any track by URI
canvasgrab "https://open.spotify.com/track/3OHfY..."  # by share URL
canvasgrab --gif                     # also create a GIF
canvasgrab --open                    # open file after download
canvasgrab --gif --open              # both
```

Files land in `~/Downloads/Canvas/`.

## How it works

canvasgrab auto-detects your Spotify `sp_dc` cookie from Chrome, Brave, Edge, Firefox, Safari, Discord, or Cursor. On macOS it decrypts Chromium cookies via the Keychain. If no browser cookies exist, it falls back to the Spotify desktop app's LevelDB cache.
> if errors on windows you do not use 'export' to export the cookie you use setx..


No manual setup required — just install and run.




## Acknowledgements

- [Paxsenix0/Spotify-Canvas-API](https://github.com/Paxsenix0/Spotify-Canvas-API) — protobuf schema, TOTP auth flow, and endpoint discovery
- [Delitefully/spotify-canvas-downloader](https://github.com/Delitefully/spotify-canvas-downloader) — original Python implementation and auth approach
- [bartleyg/my-spotify-canvas](https://github.com/bartleyg/my-spotify-canvas) — anonymous canvas token discovery
- [xyloflake/spot-secrets-go](https://github.com/xyloflake/spot-secrets-go) — Spotify TOTP signing secret rotation

## License

MIT
