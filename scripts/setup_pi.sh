#!/usr/bin/env bash
# Bootstrap script for Raspberry Pi to set up environment for rbpi_eink_2.13
# - Configures pip to use piwheels and prefer binary wheels
# - Installs system libraries needed by Pillow/NumPy
# - Creates a Python venv and installs Python dependencies
# - Installs Waveshare EPD driver (via pip by default)
# - Runs environment checks

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
cd "$REPO_DIR"

echo "[1/7] Configuring pip to use piwheels and prefer binary wheels (user-level)"
pip config set global.extra-index-url https://www.piwheels.org/simple || true
pip config set global.prefer-binary true || true
pip config set global.only-binary :all: || true

echo "[2/7] Installing system libraries for Pillow/NumPy"
sudo apt-get update -y
sudo apt-get install -y \
  python3-dev python3-setuptools \
  libjpeg-dev zlib1g-dev libfreetype-dev libopenjp2-7 || true
# OpenBLAS (name varies by distro release)
if ! sudo apt-get install -y libopenblas0; then
  sudo apt-get install -y libopenblas0-pthread || true
fi

echo "[3/7] Creating Python virtual environment (.venv) if missing"
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
source .venv/bin/activate

echo "[4/7] Upgrading pip/setuptools/wheel in venv"
pip install --upgrade pip setuptools wheel

echo "[5/7] Installing core Python packages using piwheels"
pip install --prefer-binary --only-binary=:all: \
  --extra-index-url https://www.piwheels.org/simple \
  numpy pillow sgp4 skyfield

echo "[6/7] Installing project requirements and Raspberry Pi deps"
pip install -r requirements.txt
# GPIO/SPI modules via pip so they are available inside venv
pip install --prefer-binary --only-binary=:all: \
  --extra-index-url https://www.piwheels.org/simple \
  RPi.GPIO spidev

echo "Installing Waveshare EPD driver (pip)"
if ! pip install --prefer-binary --only-binary=:all: \
    --extra-index-url https://www.piwheels.org/simple \
    waveshare-epd; then
  echo "[WARN] pip install waveshare-epd failed or not available for your platform."
  echo "       You can use the official repo instead:"
  echo "         git clone https://github.com/waveshare/e-Paper ~/e-Paper"
  echo "         export PYTHONPATH=~/e-Paper/RaspberryPi_Jetson_Nano/python/lib:\$PYTHONPATH"
fi

echo "[7/7] Running environment check"
python check_env.py || true

echo
echo "Done. If SPI is not yet enabled, run: sudo raspi-config -> Interface Options -> SPI -> Enable"
echo "If you just installed SPI, add your user to the spi group and log out/in:"
echo "  sudo usermod -aG spi $USER"
echo
echo "Try running:"
echo "  source .venv/bin/activate"
echo "  python lunar_pi_skyfield.py --backend epd --epd-variant auto --rotate 0"
