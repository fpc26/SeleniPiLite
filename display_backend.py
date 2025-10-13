"""
Display backends for outputting a PIL image either to a file (PNG) or to a
Waveshare 2.13" e-ink display. Designed so you can develop on a desktop and
switch to hardware later without changing the rendering code.

Usage:
    from display_backend import FileBackend, WaveshareEPD2in13Backend

    backend = FileBackend("out.png")
    backend.render(image)

    # or on Raspberry Pi with Waveshare HAT installed:
    backend = WaveshareEPD2in13Backend(variant="auto", rotate=0, sleep_after=True)
    backend.render(image)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import os
from PIL import Image


class DisplayBackend:
    """Abstract display backend."""

    def render(self, image: Image.Image) -> None:  # pragma: no cover - simple wrapper
        raise NotImplementedError


@dataclass
class FileBackend(DisplayBackend):
    """Save the image to a PNG file (default: 1-bit palette)."""

    path: str = "lunar_output.png"
    mode: str = "1"  # 1-bit for e-ink preview; use "L" or "RGB" if you prefer

    def render(self, image: Image.Image) -> None:
        img = image
        if self.mode and image.mode != self.mode:
            img = image.convert(self.mode)
        # Ensure dir exists
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        img.save(self.path)


class WaveshareEPD2in13Backend(DisplayBackend):
    """Render to a Waveshare 2.13" e-ink display.

    Attempts to import supported variants and detect width/height. Converts the
    provided image to 1-bit and rotates if requested.

    Parameters
    - variant: "auto", "V4", "V3", "V2", or "V1" (best effort)
    - rotate: 0, 90, 180, 270 (clockwise degrees)
    - sleep_after: put the display to sleep after rendering
    """

    def __init__(self, variant: str = "auto", rotate: int = 0, sleep_after: bool = True):
        self.variant = (variant or "auto").upper()
        self.rotate = rotate % 360
        self.sleep_after = sleep_after

        self._epd = None
        self._module = None
        self._load_driver()

    def _load_driver(self) -> None:
        # Try commonly used module/class names
        candidates = []
        if self.variant == "AUTO":
            candidates = [
                ("waveshare_epd.epd2in13_V4", "EPD"),
                ("waveshare_epd.epd2in13_V3", "EPD"),
                ("waveshare_epd.epd2in13_V2", "EPD"),
                ("waveshare_epd.epd2in13", "EPD"),
            ]
        else:
            mod = f"waveshare_epd.epd2in13_{self.variant}"
            candidates = [(mod, "EPD")]

        last_err: Optional[Exception] = None
        for mod_name, class_name in candidates:
            try:
                module = __import__(mod_name, fromlist=[class_name])
                epd_cls = getattr(module, class_name)
                self._module = module
                self._epd = epd_cls()
                break
            except Exception as e:  # ImportError or attribute errors
                last_err = e
                continue

        if self._epd is None:
            hint = (
                "Ensure the Waveshare Python library is installed and SPI is enabled.\n"
                "- pip install RPi.GPIO spidev Pillow\n"
                "- Clone https://github.com/waveshare/e-Paper and add its python lib to PYTHONPATH,\n"
                "  or pip install waveshare-epd (community packages may vary).\n"
                "- On Raspberry Pi: sudo raspi-config -> Interface Options -> SPI: Enable\n"
            )
            raise RuntimeError(f"Failed to load 2.13\" EPD driver (last error: {last_err}).\n{hint}")

        # Initialize once
        self._epd.init()
        # Clear to white to avoid ghosting on first use
        try:
            self._epd.Clear(0xFF)
        except Exception:
            # Some drivers use 'clear' (lowercase) or no-op if not supported
            try:
                self._epd.clear()
            except Exception:
                pass

    def render(self, image: Image.Image) -> None:
        # Determine target dimensions (driver convention: attributes width/height may be swapped orientation-wise)
        width = getattr(self._epd, "width", None)
        height = getattr(self._epd, "height", None)
        if width is None or height is None:
            # Fallback to common 2.13" V4 resolution
            width, height = 122, 250

        # The script renders a 250x122 landscape image. Map to EPD orientation.
        img = image.convert("1")

        # Apply optional rotation first (clockwise). PIL rotates CCW, so use negative degrees
        if self.rotate:
            img = img.rotate(-self.rotate, expand=True)

        # If size mismatches, try to rotate to match expected (height x width)
        if img.size != (height, width):
            # Try simple 90-degree rotation to match portrait EPD buffers
            if img.size == (width, height):
                pass  # already matching swapped orientation
            else:
                # Resize with nearest-neighbor to preserve 1-bit edges
                img = img.resize((height, width), resample=Image.NEAREST)

        # Some drivers expect the buffer in a specific orientation; try both mappings
        try:
            self._epd.display(self._epd.getbuffer(img))
        except Exception:
            # Try rotate 180 deg if orientation is flipped
            try:
                self._epd.display(self._epd.getbuffer(img.rotate(180)))
            except Exception as e:
                raise
        finally:
            if self.sleep_after:
                try:
                    self._epd.sleep()
                except Exception:
                    try:
                        self._epd.Sleep()
                    except Exception:
                        pass
