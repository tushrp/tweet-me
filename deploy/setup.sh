#!/usr/bin/env bash
# One-shot setup for tweet-me on an Ubuntu 22.04 VM (Oracle Always Free, etc.)
# Usage: bash setup.sh

set -euo pipefail

INSTALL_DIR="$HOME/tweet-me"

echo "=== tweet-me setup ==="
echo

echo "[1/5] Installing system dependencies..."
sudo apt-get update -q
if ! command -v python3.11 &>/dev/null; then
    sudo apt-get install -y software-properties-common
    sudo add-apt-repository -y ppa:deadsnakes/ppa
    sudo apt-get update -q
fi
sudo apt-get install -y python3.11 python3.11-venv git

echo
echo "[2/5] Cloning repository..."
if [ ! -d "$INSTALL_DIR" ]; then
    read -rp "GitHub repo URL (https://github.com/you/tweet-me): " REPO_URL
    git clone "$REPO_URL" "$INSTALL_DIR"
else
    echo "  $INSTALL_DIR already exists, pulling latest..."
    git -C "$INSTALL_DIR" pull --ff-only || true
fi
cd "$INSTALL_DIR"

echo
echo "[3/5] Setting up Python environment..."
if [ ! -d .venv ]; then
    python3.11 -m venv .venv
fi
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -e . -q

echo
echo "[4/5] Configuration..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "  Created .env from template. Fill in your credentials now."
    read -rp "  Press Enter to open .env in nano..."
    ${EDITOR:-nano} .env
else
    echo "  .env already exists, skipping."
fi

if [ ! -f src/persona.md ]; then
    cp src/persona.md.example src/persona.md
    echo "  Created persona.md. Describe your writing voice."
    read -rp "  Press Enter to open persona.md in nano..."
    ${EDITOR:-nano} src/persona.md
else
    echo "  src/persona.md already exists, skipping."
fi

echo
echo "[5/5] Installing systemd service..."
sudo tee /etc/systemd/system/tweet-me.service >/dev/null <<EOF
[Unit]
Description=tweet-me bot + nightly scheduler
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/.venv/bin/python scripts/worker.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable tweet-me
sudo systemctl restart tweet-me

echo
echo "=== Done ==="
echo
echo "Status:   sudo systemctl status tweet-me"
echo "Logs:     sudo journalctl -u tweet-me -f"
echo "Restart:  sudo systemctl restart tweet-me"
echo
echo "The worker runs the Telegram bot + internal scheduler"
echo "(nightly at 02:30, expire at 12:00 — your TIMEZONE from .env)."
