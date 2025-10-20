# rbpi_eink_2.13
RBPi Lunar Tracker - RBPi Z & E-ink display

## Quick start

Create a virtual environment and install deps:

```
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

Render to a PNG for desktop testing:

```
python lunar_pi_skyfield.py --backend file --output lunar.png
```

Send to Waveshare 2.13" e-ink (on Raspberry Pi):

```
python lunar_pi_skyfield.py --backend epd --epd-variant auto --rotate 0
```

Options:
- `--date YYYY-MM-DD` render a specific date
- `--rotate 0|90|180|270` rotate output clockwise
- `--no-sleep` keep the EPD awake (useful when chaining updates)

## Raspberry Pi setup (Waveshare 2.13)

Quick bootstrap (recommended on Raspberry Pi):

```bash
cd rbpi_eink_2.13
# Optional: choose a custom venv name (default: lunar)
# VENV_NAME=myenv bash scripts/setup_pi.sh
bash scripts/setup_pi.sh
```

Manual steps (equivalent to the script):

1) Enable SPI
- `sudo raspi-config` → Interface Options → SPI → Enable

2) Install system packages (Raspberry Pi OS)
- `sudo apt update && sudo apt install -y python3-pil python3-rpi.gpio python3-spidev`

3) Install Python deps
- In your venv: `pip install -r requirements.txt`

4) Install Waveshare Python library
- Option A (packaged): `pip install waveshare-epd` (community package; version may vary)
- Option B (official repo):
  - `git clone https://github.com/waveshare/e-Paper ~/e-Paper`
  - `export PYTHONPATH=~/e-Paper/RaspberryPi_Jetson_Nano/python/lib:$PYTHONPATH`

5) Verify environment (recommended)
- `python check_env.py`

6) Run the script
- `python lunar_pi_skyfield.py --backend epd --epd-variant auto --rotate 0`
- Use `--epd-variant V4|V3|V2|V1|auto` to match your HAT version. Start with `auto`.
- If you see a driver import error, ensure step 4 succeeded and SPI is enabled.

Troubleshooting:
- No module named 'waveshare_epd': install the library (step 4) or set PYTHONPATH to Waveshare's repo `python/lib`.
- Permission denied on /dev/spidev*: add your user to the `spi` group: `sudo usermod -aG spi $USER` then log out/in.
- Orientation flipped or rotated: use `--rotate 90|180|270` or adjust the board variant with `--epd-variant`.

Tip: Skyfield will download `de421.bsp` on first run and cache it. To pre-seed on a headless Pi, copy the file next to `lunar_pi_skyfield.py`, or set `SKYFIELD_EPH=/path/to/de421.bsp`.

## Raspberry Pi Zero tips (armv6) for Skyfield/NumPy/Pillow

On older or smaller Pis (e.g., Pi Zero), prefer prebuilt wheels from piwheels to avoid long source builds. Also install system libraries that Pillow and NumPy depend on.

1) Dev headers and common tools

```bash
sudo apt-get update
sudo apt-get install -y python3-dev python3-setuptools
```

2) System libraries for Pillow and NumPy

```bash
sudo apt-get install -y python3-venv libjpeg-dev zlib1g-dev libfreetype-dev libopenjp2-7
# OpenBLAS is used by NumPy; package name may vary by OS release
sudo apt-get install -y libopenblas0 || sudo apt-get install -y libopenblas0-pthread
```

3) Create and activate a virtual environment

```bash
python3 -m venv .venv/lunar
source .venv/lunar/bin/activate
```

4) Install core Python packages using piwheels and prefer binary wheels

```bash
pip install --prefer-binary --only-binary=:all: \
  --extra-index-url https://www.piwheels.org/simple \
  numpy pillow sgp4 skyfield
```

5) Install the rest of the project dependencies and Pi-specific libraries

```bash
pip install -r requirements.txt
sudo apt-get install -y python3-rpi.gpio python3-spidev
# Optional general-purpose GPIO helper (not required by this project):
# sudo apt-get install -y python3-gpiozero
```

6) Waveshare driver (choose one)

```bash
# Packaged (community):
pip install waveshare-epd

# OR official repo:
git clone https://github.com/waveshare/e-Paper ~/e-Paper
export PYTHONPATH=~/e-Paper/RaspberryPi_Jetson_Nano/python/lib:$PYTHONPATH
```

7) Verify environment and run

```bash
python check_env.py
python lunar_pi_skyfield.py --backend epd --epd-variant auto --rotate 0
```

If pip keeps trying to build from source, ensure you included the `--extra-index-url https://www.piwheels.org/simple` flag and `--prefer-binary --only-binary=:all:`; alternatively, you can set these via pip config for your user:

```bash
# Optional: persist piwheels and prefer binaries
pip config set global.extra-index-url https://www.piwheels.org/simple
pip config set global.prefer-binary true
pip config set global.only-binary :all:
```

# rbpi_eink_2.13
RBPi Lunar Tracker - RBPi Z &amp; E-ink display
