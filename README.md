# NFC Jukebox 🎬

Tap an NFC tag → movie plays on your Roku TV.

A Raspberry Pi-based NFC tag controller that launches media on Roku TVs via Jellyfin or any streaming app (Netflix, Hulu, Disney+, YouTube, etc.).

## Features

- 📡 **NFC tag scanning** — ACR122U USB reader on Raspberry Pi
- 🎬 **Jellyfin integration** — search and assign movies/shows directly
- 📺 **External app support** — launch Netflix, Hulu, Disney+, YouTube, and any Roku app
- 📺 **Multiple Roku TVs** — manage and switch between TVs from Settings
- ▶️ **Resume playback** — picks up exactly where you left off
- 🌐 **Web UI** — manage tags, control your TV remotely from any browser
- 🎮 **Built-in Roku remote** — navigation, volume, playback, app launcher
- 🔊 **Audio language** — per-tag preferred audio track for multi-audio content
- 📋 **Scan log** — history of every tag scan
- 🛰️ **Satellite support** — add extra Pi units for additional TVs around the house
- 🖨️ **3D Card Maker** — design and export multicolor cartridge labels for 3D printing

---

## Main Unit Setup

### 1. Install system dependencies

```bash
sudo apt update
sudo apt install -y libacsccid1 pcscd pcsc-tools python3-pip

# Blacklist kernel NFC modules that interfere with ACR122U
printf '%s\n' 'pn533' 'pn533_usb' 'nfc' | sudo tee /etc/modprobe.d/blacklist-nfc.conf

sudo systemctl enable pcscd
sudo systemctl start pcscd
sudo reboot
```

### 2. Install Python packages

```bash
cd ~/nfc-jukebox
pip3 install -r requirements.txt --break-system-packages
```

### 3. Test your NFC reader

```bash
pcsc_scan
# Tap a tag — you should see a UID printed
```

### 4. Run the app

```bash
python3 app.py
```

Open `http://<pi-ip>:5000` in your browser.

### 5. Configure (Settings page)

| Field | Description |
|---|---|
| Jellyfin URL | e.g. `http://192.168.1.x:8096` |
| Jellyfin API Key | Jellyfin → Dashboard → API Keys |
| Jellyfin User ID | Use the "Look Up Users" button |
| HA URL | e.g. `http://192.168.1.x:8123` (optional) |
| HA Token | Long-lived token from HA Profile page (optional) |

### 6. Add Roku TVs

Go to **Settings → Roku TVs** and add each TV by name and IP address.
To find a Roku's IP: Roku Settings → Network → About.

### 7. Run at boot

```bash
sudo cp nfc-jukebox.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable nfc-jukebox
sudo systemctl start nfc-jukebox
```

---

## Adding Tags

1. Go to **Tags** → **Add Tag**
2. Click **Scan Tag** and tap your NFC tag on the reader
3. Choose source: **Jellyfin** or **External App**
4. Search for a movie/show or select a streaming app
5. Pick your Roku TV and save

Next time you tap that tag, the movie launches automatically.

### Finding Content IDs for External Apps

| App | Where to find Content ID |
|---|---|
| Netflix | `netflix.com/title/XXXXXXX` — use the number |
| Hulu | `hulu.com/series/show-name-XXXX` — use the UUID at the end |
| YouTube | `youtube.com/watch?v=XXXXXXXXXXX` — use the video ID |
| Prime Video | `amazon.com/dp/XXXXXXXXXX` — use the ASIN |
| Disney+ | URL after `/movies/` or `/series/` |

Leave Content ID blank to just open the app.

---

## Satellite Setup

A satellite is a second Raspberry Pi connected to its own TV. It reads NFC tags locally but pulls the tag library from the main unit — no need to re-configure tags on each Pi.

### On the satellite Pi

#### 1. Install dependencies (same as main)

```bash
sudo apt update
sudo apt install -y libacsccid1 pcscd pcsc-tools python3-pip
printf '%s\n' 'pn533' 'pn533_usb' 'nfc' | sudo tee /etc/modprobe.d/blacklist-nfc.conf
sudo systemctl enable pcscd && sudo systemctl start pcscd
sudo reboot
```

#### 2. Install Python packages

```bash
pip3 install flask flask-socketio requests --break-system-packages
```

#### 3. Copy files to the satellite Pi

From the release, copy these files to `~/nfc-jukebox/` on the satellite:
- `satellite.py`
- `satellite_config.json`
- `nfc-jukebox-satellite.service`

#### 4. Edit satellite_config.json

```json
{
  "main_url":         "http://<main-pi-ip>:5000",
  "satellite_name":   "Living Room",
  "local_roku_ip":    "<roku-ip-for-this-tv>",
  "local_channel_id": "592369",
  "port":             5001
}
```

- `main_url` — IP of your main NFC Jukebox Pi
- `satellite_name` — display name shown in the main UI
- `local_roku_ip` — the Roku TV this satellite controls
- `port` — port the satellite web UI runs on (default 5001)

#### 5. Run the satellite

```bash
python3 satellite.py
```

Open `http://<satellite-pi-ip>:5001` for its own web UI.

#### 6. Run at boot

```bash
sudo cp nfc-jukebox-satellite.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable nfc-jukebox-satellite
sudo systemctl start nfc-jukebox-satellite
```

The satellite will auto-register with the main unit and appear under **Settings → Satellites** in the main web UI.

---

## 3D Card Maker

The built-in card maker generates multicolor `.3mf` files for printing cartridge labels on a multi-filament 3D printer.

1. Go to **Tools → 3D Print** in the web UI
2. Design your label using Text Art or upload an image
3. Set filament colors to match your printer
4. Click **Export** to download the `.3mf` file or **Save to Pi** to store it

STL files for the cartridge enclosure are included in the release.

---

## Finding Your Jellyfin Channel ID

```bash
curl http://<roku-ip>:8060/query/apps | grep -i jellyfin
```

Default is usually `592369`.

---

## Architecture

```
NFC Tag Scan
     │
     ▼
Main Pi (ACR122U + pyscard)
     │
     ├── Flask Web UI (port 5000)
     │     ├── Tag management
     │     ├── Roku remote
     │     ├── Jellyfin search
     │     └── Settings (TVs, satellites, API keys)
     │
     ├── Jellyfin API → resume position + audio language
     │
     └── Roku ECP (port 8060) → launch media


Satellite Pi ──── pulls tags from Main Pi
     │
     ├── Local NFC reader
     ├── Satellite Web UI (port 5001)
     └── Controls its own local Roku TV
```

---

## License

MIT
