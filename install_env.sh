#!/bin/bash
echo "[+] Setting up Python virtual environment..."
python3 -m venv venv
source venv/bin/activate
echo "[+] Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
echo "[+] Installing system dependencies (requires sudo)..."
sudo apt update
sudo apt install -y ffmpeg v4l-utils pulseaudio pavucontrol net-tools netcat dnsmasq python3-dev libffi-dev build-essential
echo "[✓] Setup complete."
