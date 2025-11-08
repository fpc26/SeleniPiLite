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
  python3-dev python3-setuptools python3-venv \
  libjpeg-dev zlib1g-dev libfreetype-dev libopenjp2-7 \
  python3-smbus i2c-tools || true
# GPIO helpers and pigpio daemon (more reliable edge detection than RPi.GPIO on some setups)
sudo apt-get install -y pigpio python3-pigpio || true
sudo systemctl enable --now pigpiod || true
# OpenBLAS (name varies by distro release)
if ! sudo apt-get install -y libopenblas0; then
  sudo apt-get install -y libopenblas0-pthread || true
fi

VENV_NAME="${VENV_NAME:-lunar}"
VENV_DIR="$REPO_DIR/.venv/$VENV_NAME"

echo "[3/7] Creating Python virtual environment ($VENV_DIR) if missing"
# Pick a Python interpreter (prefer newer if available)
PY_CANDIDATES=(python3.13 python3.12 python3.11 python3)
PY_CMD=""
for c in "${PY_CANDIDATES[@]}"; do
  if command -v "$c" >/dev/null 2>&1; then
    PY_CMD="$c"
    break
  fi
done
if [[ -z "$PY_CMD" ]]; then
  echo "[ERROR] No suitable python3 interpreter found in PATH"
  exit 1
fi

if [[ ! -d "$VENV_DIR" || ! -f "$VENV_DIR/bin/activate" ]]; then
  if [[ -e "$VENV_DIR" && ! -f "$VENV_DIR/bin/activate" ]]; then
    echo "[3/7] Existing venv folder missing activate script; recreating"
    rm -rf "$VENV_DIR"
  fi
  "$PY_CMD" -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"

# Ensure common interpreter aliases point inside the venv (helps when shell aliases use python3.13)
if [[ "$PY_CMD" == "python3.13" && -x "$VENV_DIR/bin/python" && ! -e "$VENV_DIR/bin/python3.13" ]]; then
  ln -sf python "$VENV_DIR/bin/python3.13"
fi

# Use venv-local executables explicitly to avoid system pip with PEP 668
VENV_PY="$VENV_DIR/bin/python"
VENV_PIP="$VENV_DIR/bin/pip"
# Some distros may not create the 'python' symlink; fall back to python3
if [[ ! -x "$VENV_PY" && -x "$VENV_DIR/bin/python3" ]]; then
  VENV_PY="$VENV_DIR/bin/python3"
fi
if [[ ! -x "$VENV_PIP" && -x "$VENV_DIR/bin/pip3" ]]; then
  VENV_PIP="$VENV_DIR/bin/pip3"
fi

# If pip is missing inside venv (ensurepip not present initially), bootstrap it
if [[ ! -x "$VENV_PIP" ]]; then
  echo "Bootstrapping pip inside venv (ensurepip)"
  "$VENV_PY" -m ensurepip --upgrade || true
fi

echo "[4/7] Upgrading pip/setuptools/wheel in venv"
"$VENV_PY" -m pip install --upgrade pip setuptools wheel

echo "[5/7] Installing core Python packages using piwheels"
"$VENV_PIP" install --prefer-binary --only-binary=:all: \
  --extra-index-url https://www.piwheels.org/simple \
  numpy pillow sgp4 skyfield

echo "[6/7] Installing project requirements and Raspberry Pi deps"
"$VENV_PIP" install -r requirements.txt
# GPIO/SPI modules via pip so they are available inside venv
"$VENV_PIP" install --prefer-binary --only-binary=:all: \
  --extra-index-url https://www.piwheels.org/simple \
  RPi.GPIO spidev gpiozero pigpio smbus2

echo "Skipping Waveshare EPD pip install (no official package). Clone the matching vendor repo:"
echo "  # Touch-enabled HATs"
echo "  git clone https://github.com/waveshare/Touch_e-Paper_HAT ~/Touch_e-Paper_HAT"
echo "  export PYTHONPATH=~/Touch_e-Paper_HAT/python/lib:~/Touch_e-Paper_HAT/python/lib/TP_lib:\$PYTHONPATH"
echo "  # (Some distributions name the folder Touch-e-Paper_HAT; both are supported.)"
echo ""
echo "  # Non-touch HATs"
echo "  git clone https://github.com/waveshare/e-Paper ~/e-Paper"
echo "  export EPD_LIB_PATH=~/e-Paper/RaspberryPi_Jetson_Nano/python/lib  # or RaspberryPi_JetsonNano"

echo "[7/7] Running environment check"
"$VENV_PY" "$REPO_DIR/check_env.py" || true

echo
echo "Done. If SPI is not yet enabled, run: sudo raspi-config -> Interface Options -> SPI -> Enable"
echo "If you have a touch-enabled HAT, enable I2C as well: sudo raspi-config -> Interface Options -> I2C -> Enable"
echo "If you just enabled SPI/GPIO/I2C, add your user to the spi,gpio,i2c groups and log out/in:"
echo "  sudo usermod -aG spi,gpio,i2c $USER"
echo "If you see gpiozero pin factory errors, try using pigpio backend:"
echo "  sudo systemctl enable --now pigpiod"
echo "  export GPIOZERO_PIN_FACTORY=pigpio"
echo
echo "Try running:"
echo "  source $VENV_DIR/bin/activate"
echo "  python lunar_pi_skyfield.py --backend epd --epd-variant auto --rotate 0"
echo "  # Touch panels: add --epd-touch (defaults to TP_V4)"
