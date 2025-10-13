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

1. Enable SPI: `sudo raspi-config` → Interface Options → SPI → Enable
2. Install system deps (if needed): `sudo apt install python3-pip python3-pil`
3. Install Python deps: `pip install -r requirements.txt`
4. Install Waveshare Python library. Options:
	- Clone https://github.com/waveshare/e-Paper and add its `python/lib` folder to `PYTHONPATH`
	- Or install a packaged module (community): `pip install waveshare-epd` (names may vary)
5. Run with `--backend epd`. Use `--epd-variant V4|V3|V2|auto` to match your board.

Tip: Skyfield will download `de421.bsp` on first run and cache it. To preseed on a headless Pi, copy the file next to `lunar_pi_skyfield.py`, or set `SKYFIELD_EPH=/path/to/de421.bsp`.

# rbpi_eink_2.13
RBPi Lunar Tracker - RBPi Z &amp; E-ink display
