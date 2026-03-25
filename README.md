# NFC Jukebox 🎬

Tap an NFC tag → movie plays on your Roku TV.

A Raspberry Pi-based NFC tag controller that launches media on Roku TVs via Jellyfin or any streaming app (Netflix, Hulu, Disney+, YouTube, etc.).

![NFC Jukebox Dashboard](https://placeholder.com/dashboard.png)

## Features

- 📡 **NFC tag scanning** — ACR122U USB reader on Raspberry Pi
- 🎬 **Jellyfin integration** — search and assign movies/shows directly
- 📺 **External app support** — launch Netflix, Hulu, Disney+, YouTube, and any Roku app
- ▶️ **Resume playback** — picks up exactly where you left off
- 🌐 **Web UI** — manage tags, control your TV remotely from any browser
- 🎮 **Built-in Roku remote** — navigation, volume, playback, app launcher
- 🔊 **Audio language** — per-tag preferred audio track for multi-audio content
- 📋 **Scan log** — history of every tag scan

## Quick Install

On your Raspberry Pi, run:

```bash
curl -fsSL https://raw.githubusercontent.com/lordhaon/nfc-jukebox/main/install.sh | bash
```

Then open `http://<pi-ip>:5000` in your browser.

## Requirements

- Raspberry Pi (3B+ or 4 recommended)
- [ACR122U USB NFC Reader](https://www.amazon.com/s?k=ACR122U)
- NTAG213 or NTAG215 NFC stickers/cards
- [Home Assistant](https://www.home-assistant.io/) with Roku integration
- [Jellyfin](https://jellyfin.org/) media server (optional, for local media)
- Roku TV(s) on the same network

## Manual Setup

### 1. Install system dependencies

```bash
sudo apt update
sudo apt install -y libacsccid1 pcscd pcsc-tools python3-pyscard python3-pip

# Blacklist kernel NFC modules that interfere with ACR122U
printf '%s\n' 'pn533' 'pn533_usb' 'nfc' | sudo tee /etc/modprobe.d/blacklist-nfc.conf

sudo systemctl enable pcscd
sudo systemctl start pcscd
sudo reboot
```

### 2. Install Python packages

```bash
pip3 install flask flask-socketio requests --break-system-packages
```

### 3. Clone and run

```bash
git clone https://github.com/lordhaon/nfc-jukebox.git ~/nfc-jukebox
cd ~/nfc-jukebox
sudo python3 app.py
```

### 4. Run as a service

```bash
sudo cp nfc-jukebox.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable nfc-jukebox
sudo systemctl start nfc-jukebox
```

## Configuration

Open the web UI → **Settings** and enter:

| Field | Description |
|---|---|
| HA URL | e.g. `http://192.168.1.x:8123` |
| HA Token | Long-lived token from HA Profile page |
| Jellyfin URL | e.g. `http://192.168.1.x:8096` |
| Jellyfin API Key | From Jellyfin → Dashboard → API Keys |
| Jellyfin User ID | Use the "Look Up Users" button |

## Adding Tags

1. Go to **Tags** → **Add Tag**
2. Click **📡 Scan Tag** and tap your NFC tag
3. Choose source: **Jellyfin** or **External App**
4. Search for a movie/show or select an app
5. Pick your Roku TV and save

### Finding Content IDs for External Apps

| App | Where to find Content ID |
|---|---|
| Netflix | `netflix.com/title/XXXXXXX` — use the number |
| Hulu | `hulu.com/series/show-name-XXXX` — use the UUID at the end |
| YouTube | `youtube.com/watch?v=XXXXXXXXXXX` — use the video ID |
| Prime Video | `amazon.com/dp/XXXXXXXXXX` — use the ASIN |
| Disney+ | URL after `/movies/` or `/series/` |

Leave Content ID blank to just open the app.

## Finding Your Roku's Jellyfin Channel ID

```bash
curl http://<roku-ip>:8060/query/apps | grep -i jellyfin
```

## File Browser

The installer also sets up [FileBrowser](https://filebrowser.xyz/) at `http://<pi-ip>:8080` for easy file management.
Default login: `admin` / `adminpassword123` — **change this after setup!**

## Architecture

```
NFC Tag Scan
     │
     ▼
Raspberry Pi (ACR122U + pyscard)
     │
     ▼
Flask Web App (port 5000)
     │
     ├── Jellyfin API → get resume position + set audio language
     │
     └── Roku ECP (port 8060) → launch/592369?contentId=XXX
```

## License

MIT
