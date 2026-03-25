#!/bin/bash
# NFC Jukebox - One-line installer
# Usage: curl -fsSL https://raw.githubusercontent.com/YOUR_USERNAME/nfc-jukebox/main/install.sh | bash

set -e

REPO="https://raw.githubusercontent.com/lordhaon/nfc-jukebox/main"
INSTALL_DIR="$HOME/nfc-jukebox"
SERVICE_FILE="/etc/systemd/system/nfc-jukebox.service"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}"
echo "  _   _ _____ ____     _ _   _ _  _______ ____   _____  __"
echo " | \ | |  ___/ ___|   | | | | | |/ /  ___| __ ) / _ \ \/ /"
echo " |  \| | |_  \___ \   | | | | | ' /| |_  |  _ \| | | \  / "
echo " | |\  |  _|  ___) |  | | |_| | . \|  _| | |_) | |_| /  \ "
echo " |_| \_|_|   |____/   |_|\___/|_|\_\_|   |____/ \___/_/\_\\"
echo -e "${NC}"
echo -e "${GREEN}NFC Jukebox Installer${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── Check we're on a Pi / Debian-based system ──────────────────────────────
if ! command -v apt-get &> /dev/null; then
    echo -e "${RED}Error: This installer requires a Debian/Ubuntu-based system.${NC}"
    exit 1
fi

echo -e "${YELLOW}[1/6] Installing system dependencies...${NC}"
sudo apt-get update -qq
sudo apt-get install -y -qq libacsccid1 pcscd pcsc-tools python3-pyscard python3-pip git

# ── Blacklist kernel NFC modules that hijack ACR122U ──────────────────────
echo -e "${YELLOW}[2/6] Configuring NFC kernel modules...${NC}"
printf '%s\n' 'pn533' 'pn533_usb' 'nfc' | sudo tee /etc/modprobe.d/blacklist-nfc.conf > /dev/null
sudo systemctl enable pcscd
sudo systemctl start pcscd

# ── Install Python dependencies ────────────────────────────────────────────
echo -e "${YELLOW}[3/6] Installing Python packages...${NC}"
sudo pip3 install flask flask-socketio requests --break-system-packages -q

# ── Download app files ─────────────────────────────────────────────────────
echo -e "${YELLOW}[4/6] Downloading NFC Jukebox...${NC}"
mkdir -p "$INSTALL_DIR/templates"

curl -fsSL "$REPO/app.py" -o "$INSTALL_DIR/app.py"
curl -fsSL "$REPO/templates/index.html" -o "$INSTALL_DIR/templates/index.html"

echo -e "${GREEN}✓ Files downloaded${NC}"

# ── Install FileBrowser ────────────────────────────────────────────────────
echo -e "${YELLOW}[5/6] Installing FileBrowser...${NC}"
if ! command -v filebrowser &> /dev/null; then
    curl -fsSL https://raw.githubusercontent.com/filebrowser/get/master/get.sh | bash > /dev/null 2>&1
    mkdir -p ~/.filebrowser
    filebrowser config init --database ~/.filebrowser/filebrowser.db > /dev/null 2>&1
    filebrowser config set --address 0.0.0.0 --port 8080 --root /home/pi --database ~/.filebrowser/filebrowser.db > /dev/null 2>&1
    filebrowser users add admin adminpassword123 --perm.admin --database ~/.filebrowser/filebrowser.db > /dev/null 2>&1

    sudo tee /etc/systemd/system/filebrowser.service > /dev/null << 'EOF'
[Unit]
Description=FileBrowser
After=network.target

[Service]
ExecStart=/usr/local/bin/filebrowser --database /home/pi/.filebrowser/filebrowser.db
Restart=always
User=pi

[Install]
WantedBy=multi-user.target
EOF
    sudo systemctl daemon-reload
    sudo systemctl enable filebrowser
    sudo systemctl start filebrowser
    echo -e "${GREEN}✓ FileBrowser installed${NC}"
else
    echo -e "${GREEN}✓ FileBrowser already installed${NC}"
fi

# ── Install systemd service ────────────────────────────────────────────────
echo -e "${YELLOW}[6/6] Setting up service...${NC}"

sudo tee $SERVICE_FILE > /dev/null << EOF
[Unit]
Description=NFC Jukebox Web Interface
After=network.target pcscd.service
Requires=pcscd.service

[Service]
ExecStart=/usr/bin/python3 $INSTALL_DIR/app.py
WorkingDirectory=$INSTALL_DIR
Restart=always
User=root
Environment=PYTHONUNBUFFERED=1
Environment=PCSCLITE_CSOCK_NAME=/run/pcscd/pcscd.comm

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable nfc-jukebox
sudo systemctl start nfc-jukebox

sleep 2

# ── Done ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  ✓ NFC Jukebox installed successfully!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Get IP
IP=$(hostname -I | awk '{print $1}')
echo -e "  ${CYAN}Web UI:${NC}       http://$IP:5000"
echo -e "  ${CYAN}FileBrowser:${NC}  http://$IP:8080  (admin / adminpassword123)"
echo ""
echo -e "  ${YELLOW}Next steps:${NC}"
echo "  1. Open the web UI and go to Settings"
echo "  2. Enter your Home Assistant URL and token"
echo "  3. Enter your Jellyfin URL, API key, and User ID"
echo "  4. Plug in your ACR122U NFC reader"
echo "  5. Go to Tags → Add Tag → scan a tag → assign a movie!"
echo ""
echo -e "  ${YELLOW}Note:${NC} A reboot is recommended to ensure NFC kernel"
echo "  modules are blacklisted properly:"
echo -e "  ${CYAN}sudo reboot${NC}"
echo ""
