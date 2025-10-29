#!/usr/bin/env python3
"""
Minimal sanity test for Waveshare e-Paper displays (2.13", 7.5", etc.).
Draws a full black frame, waits, then a full white frame.

Usage:
    EPD_LIB_PATH=/path/to/e-Paper/.../python/lib \
    GPIOZERO_PIN_FACTORY=pigpio \
    python scripts/epd_sanity.py --model 2in13 --variant V4

Models: 2in13 (default), 7in5, 7in5b
Variants: V4, V3, V2, auto (model-specific)
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from PIL import Image


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="2in13", help="Model family, e.g., 2in13, 7in5, 7in5b")
    ap.add_argument("--variant", default="V4", help="Variant: V4|V3|V2|auto (depends on model)")
    args = ap.parse_args()

    model = args.model.lower()
    variant = args.variant.upper()

    # Ensure EPD_LIB_PATH is present
    lib = os.environ.get("EPD_LIB_PATH")
    if not lib or not os.path.isdir(lib):
        print("ERROR: EPD_LIB_PATH not set to e-Paper python/lib")
        return 2
    if lib not in sys.path:
        sys.path.insert(0, lib)

    # Import driver for requested model
    mod_names = []
    def add_names(base: str):
        # namespaced then flat
        mod_names.append((f"waveshare_epd.{base}", "EPD"))
        mod_names.append((base, "EPD"))

    if variant == "AUTO":
        for base in [f"epd{model}_V4", f"epd{model}_V3", f"epd{model}_V2", f"epd{model}"]:
            add_names(base)
        # Include tri-color bases as well
        for base in [f"epd{model}b_V4", f"epd{model}b_V3", f"epd{model}b_V2", f"epd{model}b"]:
            add_names(base)
        if model == "2in13":
            for base in ["epd2in13d", "epd2in13g"]:
                add_names(base)
    else:
        add_names(f"epd{model}_{variant}")
        add_names(f"epd{model}")  # some repos omit variant suffix

    epd = None
    last_err = None
    for name, cls in mod_names:
        try:
            mod = __import__(name, fromlist=[cls])
            EPD = getattr(mod, cls)
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

    w = getattr(epd, "width", None)
    h = getattr(epd, "height", None)
    if w is None or h is None:
        # Fallbacks by model
        if model in ("7in5", "7in5b"):
            w, h = 480, 800
        else:
            w, h = 122, 250
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
