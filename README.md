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
- `--epd-variant` accepts `auto`, `V4|V3|V2|V1` (non-touch) or `TP_V4|TP_V3|TP_V2` for touch HATs

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

- Touch-enabled HATs (GT1151 controller):
  - `git clone https://github.com/waveshare/Touch_e-Paper_HAT ~/Touch_e-Paper_HAT`
  - Export either of these so drivers can be found:
    - `export EPD_LIB_PATH=~/Touch_e-Paper_HAT/python/lib`
    - `export PYTHONPATH=~/Touch_e-Paper_HAT/python/lib:~/Touch_e-Paper_HAT/python/lib/TP_lib:$PYTHONPATH`
  - Keep both SPI and I2C enabled and confirm `i2cdetect -y 1` shows the touch controller (0x5d).
  - Use `--epd-variant TP_V4` (or TP_V3/TP_V2) when running this project.
- Non-touch HATs:
  - `git clone https://github.com/waveshare/e-Paper ~/e-Paper`
  - Export the driver path:
    - `export EPD_LIB_PATH=~/e-Paper/RaspberryPi_Jetson_Nano/python/lib`
  - Cloning into the project root as `./e-Paper` or `./Touch_e-Paper_HAT` also works; `_load_driver` scans both.
- Community package (fallback, support varies by platform): `pip install waveshare-epd`

5) Verify environment (recommended)
- `python check_env.py`

6) Run the script
- `python lunar_pi_skyfield.py --backend epd --epd-variant auto --rotate 0`
- Use `--epd-variant V4|V3|V2|V1|auto` to match your HAT version. Start with `auto`.
- If you see a driver import error, ensure step 4 succeeded and SPI is enabled.

Troubleshooting:
- No module named 'waveshare_epd': install the library (step 4) or set PYTHONPATH to Waveshare's repo `python/lib`.
- No module named 'epd2in13': set EPD_LIB_PATH to the repo's `RaspberryPi_Jetson_Nano/python/lib`,
  or place the `e-Paper` repo inside the project folder so it’s auto-detected.
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
# Touch-enabled HATs
git clone https://github.com/waveshare/Touch_e-Paper_HAT ~/Touch_e-Paper_HAT
export PYTHONPATH=~/Touch_e-Paper_HAT/python/lib:~/Touch_e-Paper_HAT/python/lib/TP_lib:$PYTHONPATH
export EPD_TOUCH_VARIANT=TP_V4  # optional helper when scripting
# Non-touch HATs
git clone https://github.com/waveshare/e-Paper ~/e-Paper
export PYTHONPATH=~/e-Paper/RaspberryPi_Jetson_Nano/python/lib:$PYTHONPATH
# Community package (fallback)
pip install waveshare-epd
```

If you use the touch HAT, ensure I2C remains enabled (`sudo raspi-config` → Interface Options → I2C) and that the GT1151 device shows up on `/dev/i2c-1`.

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
