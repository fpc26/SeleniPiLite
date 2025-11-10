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

Send to Waveshare 2.13" touch e-ink HAT (on Raspberry Pi):

```
sudo systemctl enable --now pigpiod   # one-time setup; skip if already running
export GPIOZERO_PIN_FACTORY=pigpio    # or lgpio if installed inside the venv
python lunar_pi_skyfield.py --backend epd --epd-touch --rotate 0
```

Options:
- `--date YYYY-MM-DD` render a specific date
- `--rotate 0|90|180|270` rotate output clockwise
- `--no-sleep` keep the EPD awake (useful when chaining updates)
- `--epd-variant` accepts `auto`, `V4|V3|V2|V1` (non-touch) or `TP_V4|TP_V3|TP_V2` for touch HATs
- `--epd-touch` forces use of the touch TP_lib drivers (defaults variant to TP_V4 if left as auto)
- `--epd-clear` clears the Waveshare display to white and exits (touch/non-touch)
- `--epd-auto-clear-delay` wait N seconds before clearing the panel automatically (default 600, set 0 to disable)
- `--power-hold-seconds` adjust how long the touch power zone must be held before the panel clears and exits (default 5s)
- `--touch-poll-ms` tweak touch sampling latency (smaller value = more responsive, default 80ms)
- `--touch-map` pick a touch orientation correction (auto selects `transpose_invert_x` for the 2.13" TP panel)

## Touch workflow

- Prev/Next buttons show a brief processing card before the next day loads so you know the tap registered.
- Hold the Sleep/Power zone for the configured `--power-hold-seconds` to clear the panel and shut down cleanly.
- Touch polling defaults to 80ms; adjust via `--touch-poll-ms` if you want faster taps or a calmer idle loop.
- Touch orientation auto-detects (`transpose_invert_x` for the Waveshare 2.13" TP) and can be overridden with `--touch-map` when using other panels.

## Touch troubleshooting

1. Run the helper to capture raw readings and all mapping permutations:
  ```bash
  python scripts/touch_calibration.py --epd-variant auto --touch-map auto
  ```
  The script renders crosshairs on the panel and prints `Raw`, `Normalized`, and each mapping's projected `(x, y)` display coordinate.
2. Compare the reported coordinates with the on-screen prompts. The mapping whose coordinates line up with the target (e.g., buttons near 45/125/205 on the X axis) is the one to pass to `--touch-map`.
3. Launch the main app with the mapping that matched your hardware, for example:
  ```bash
  python lunar_pi_skyfield.py --backend epd --epd-touch --touch-map transpose_invert_x
  ```
4. Still misaligned? Double-check `--rotate` is `0`, ensure `pigpiod` (or your chosen GPIO factory) is running, and experiment with `--touch-poll-ms` to see if a slower poll smooths noisy taps.
5. If taps intermittently register, inspect the calibration output for jitter (wide raw value swings) and consider reseating the touch FFC or verifying 3.3V stability.

## Raspberry Pi setup (Waveshare 2.13)

Quick bootstrap (recommended on Raspberry Pi):

```bash
cd rbpi_eink_2.13
# Optional: choose a custom venv name (default: lunar)
# VENV_NAME=myenv bash scripts/setup_pi.sh
# The script will recreate the venv if it is missing an activate script.
bash scripts/setup_pi.sh
```

Manual steps (equivalent to the script):

1) Enable SPI
- `sudo raspi-config` → Interface Options → SPI → Enable

2) Install system packages (Raspberry Pi OS)
- `sudo apt update && sudo apt install -y python3-pil python3-rpi.gpio python3-spidev python3-smbus python3-lgpio i2c-tools`
- For reliable edge detection on the BUSY/INT pins, install and start pigpio (recommended) or rely on lgpio:
  - `sudo apt install -y pigpio python3-pigpio`
  - `sudo systemctl enable --now pigpiod`

3) Install Python deps
- In your venv: `pip install -r requirements.txt`

- Touch-enabled HATs (GT1151 controller):
  - `git clone https://github.com/waveshare/Touch_e-Paper_HAT ~/Touch_e-Paper_HAT`
  - Export either of these so drivers can be found (the repo might appear as `Touch-e-Paper_HAT`, both are detected):
    - `export EPD_LIB_PATH=~/Touch_e-Paper_HAT/python/lib`
    - `export PYTHONPATH=~/Touch_e-Paper_HAT/python/lib:~/Touch_e-Paper_HAT/python/lib/TP_lib:$PYTHONPATH`
  - Keep both SPI and I2C enabled and confirm `i2cdetect -y 1` shows the touch controller (0x5d).
  - Inside your venv, install the GPIO pin factory packages so you can run without sudo:
    - `pip install pigpio lgpio`
    - Choose one at runtime, e.g. `export GPIOZERO_PIN_FACTORY=pigpio`
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
- `export GPIOZERO_PIN_FACTORY=pigpio`
- `python lunar_pi_skyfield.py --backend epd --epd-touch --rotate 0`
- The display will remain visible for 10 minutes (configurable via `--epd-auto-clear-delay`), then the script clears the panel before shutting down.
- If you see a driver import error, ensure the Waveshare repo path is exported and SPI/I2C are enabled.

Troubleshooting:
- No module named 'waveshare_epd': install the library (step 4) or set PYTHONPATH to Waveshare's repo `python/lib`.
- No module named 'epd2in13': set EPD_LIB_PATH to the repo's `RaspberryPi_Jetson_Nano/python/lib`,
  or place the `e-Paper` repo inside the project folder so it’s auto-detected.
- Permission denied on /dev/spidev*: add your user to the `spi` group: `sudo usermod -aG spi $USER` then log out/in.
- Runtime error `Failed to add edge detection`: install `python3-lgpio` or `pigpio`, start `pigpiod`, and set `GPIOZERO_PIN_FACTORY=pigpio` (or `lgpio`).
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
pip install pigpio lgpio smbus2
```

6) Waveshare driver (choose one)

```bash
# Touch-enabled HATs
git clone https://github.com/waveshare/Touch_e-Paper_HAT ~/Touch_e-Paper_HAT
export PYTHONPATH=~/Touch_e-Paper_HAT/python/lib:~/Touch_e-Paper_HAT/python/lib/TP_lib:$PYTHONPATH
export EPD_TOUCH_VARIANT=TP_V4  # optional helper when scripting
pip install --prefer-binary smbus2  # fallback when python3-smbus is unavailable for your Python build
# Non-touch HATs
git clone https://github.com/waveshare/e-Paper ~/e-Paper
export PYTHONPATH=~/e-Paper/RaspberryPi_Jetson_Nano/python/lib:$PYTHONPATH
# Community package (fallback)
pip install waveshare-epd
```

If you use the touch HAT, ensure I2C remains enabled (`sudo raspi-config` → Interface Options → I2C) and that the GT1151 device shows up on `/dev/i2c-1`.
Install an I2C backend for Python (`sudo apt install python3-smbus` for the distro interpreter, and `pip install smbus2` inside the venv) so the touch controller can talk over I2C. For GPIO interrupts install `pigpio` or `lgpio` (both instructions above) and pick the backend at runtime via `export GPIOZERO_PIN_FACTORY=pigpio` (recommended) or `export GPIOZERO_PIN_FACTORY=lgpio`.

To wipe the display when shutting down, run:

```bash
python lunar_pi_skyfield.py --backend epd --epd-variant TP_V4 --epd-clear
# or explicitly force the touch driver auto-detection
python lunar_pi_skyfield.py --backend epd --epd-touch --epd-clear
```
`--no-sleep` keeps the panel awake after clearing if you plan to refresh immediately again. The normal render path clears automatically after the configured `--epd-auto-clear-delay` (10 minutes by default) to prevent long-term ghosting.

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
