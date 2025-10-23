#!/usr/bin/env python3
"""
Minimal sanity test for Waveshare 2.13" displays.
Draws a full black frame, waits, then a full white frame.

Usage:
  EPD_LIB_PATH=/path/to/e-Paper/.../python/lib \
  GPIOZERO_PIN_FACTORY=pigpio \
  python scripts/epd_sanity.py --variant V4

Variants: V4, V3, V2, auto
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from PIL import Image


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="V4", help="2.13 variant: V4|V3|V2|auto")
    args = ap.parse_args()

    variant = args.variant.upper()

    # Ensure EPD_LIB_PATH is present
    lib = os.environ.get("EPD_LIB_PATH")
    if not lib or not os.path.isdir(lib):
        print("ERROR: EPD_LIB_PATH not set to e-Paper python/lib")
        return 2
    if lib not in sys.path:
        sys.path.insert(0, lib)

    # Import driver
    mod_names = []
    if variant == "AUTO":
        mod_names = [
            "waveshare_epd.epd2in13_V4",
            "waveshare_epd.epd2in13_V3",
            "waveshare_epd.epd2in13_V2",
            "waveshare_epd.epd2in13",
        ]
    else:
        mod_names = [f"waveshare_epd.epd2in13_{variant}"]

    epd = None
    last_err = None
    for name in mod_names:
        try:
            mod = __import__(name, fromlist=["EPD"])
            EPD = getattr(mod, "EPD")
            epd = EPD()
            break
        except Exception as e:
            last_err = e
            continue

    if epd is None:
        print(f"ERROR: Failed to import/construct driver: {last_err}")
        return 3

    # Init and draw
    init = getattr(epd, "init", None) or getattr(epd, "Init", None)
    if callable(init):
        init()

    w = getattr(epd, "width", 122)
    h = getattr(epd, "height", 250)
    # Many drivers expect buffer in (height, width)
    img_black = Image.new("1", (h, w), 0)
    img_white = Image.new("1", (h, w), 255)

    display = getattr(epd, "display", None) or getattr(epd, "Display", None)
    getbuffer = getattr(epd, "getbuffer", None) or getattr(epd, "getBuffer", None)
    if not callable(display) or not callable(getbuffer):
        print("ERROR: display/getbuffer missing on driver")
        return 4

    print(f"Drawing black frame {h}x{w}...")
    display(getbuffer(img_black))
    time.sleep(3)
    print("Drawing white frame...")
    display(getbuffer(img_white))
    time.sleep(2)

    sleep = getattr(epd, "sleep", None) or getattr(epd, "Sleep", None)
    if callable(sleep):
        sleep()
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
