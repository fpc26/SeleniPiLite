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
import sys
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
        # Attempt to discover and add Waveshare e-Paper python lib to sys.path
        proj_root = os.path.dirname(os.path.abspath(__file__))
        candidate_paths: list[str] = []
        env_path = os.environ.get("EPD_LIB_PATH")
        if env_path:
            # Normalize: if EPD_LIB_PATH points to .../waveshare_epd, use its parent lib folder
            base_path = env_path.rstrip(os.sep)
            if os.path.basename(base_path) == "waveshare_epd":
                base_path = os.path.dirname(base_path)
            candidate_paths.append(base_path)

        # Consider both folder name variants used by the repo
        repo_variants = ["RaspberryPi_Jetson_Nano", "RaspberryPi_JetsonNano"]
        for base in [proj_root, os.path.expanduser("~")]:
            for variant in repo_variants:
                lib_path = os.path.join(base, "e-Paper", variant, "python", "lib")
                candidate_paths.append(lib_path)

        added_paths: list[str] = []
        for p in candidate_paths:
            if p and os.path.isdir(p) and p not in sys.path:
                sys.path.insert(0, p)
                added_paths.append(p)

        # Try commonly used module/class names
        candidates = []
        if self.variant == "AUTO":
            candidates = [
                # Prefer namespaced imports (package context for relative imports)
                ("waveshare_epd.epd2in13_V4", "EPD"),
                ("waveshare_epd.epd2in13_V3", "EPD"),
                ("waveshare_epd.epd2in13_V2", "EPD"),
                ("waveshare_epd.epd2in13", "EPD"),
                # Alternate 2.13 variants seen in repos
                ("waveshare_epd.epd2in13b_V4", "EPD"),
                ("waveshare_epd.epd2in13b_V3", "EPD"),
                ("waveshare_epd.epd2in13d", "EPD"),
                ("waveshare_epd.epd2in13g", "EPD"),
                # Flat modules (fallback)
                ("epd2in13_V4", "EPD"),
                ("epd2in13_V3", "EPD"),
                ("epd2in13_V2", "EPD"),
                ("epd2in13", "EPD"),
                ("epd2in13b_V4", "EPD"),
                ("epd2in13b_V3", "EPD"),
                ("epd2in13d", "EPD"),
                ("epd2in13g", "EPD"),
            ]
        else:
            # Try both namespaced and flat module paths
            mod_suffix = f"epd2in13_{self.variant}"
            candidates = [
                (f"waveshare_epd.{mod_suffix}", "EPD"),
                (mod_suffix, "EPD"),
            ]

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
                "- Clone https://github.com/waveshare/e-Paper\n"
                "  Place it at either: ./e-Paper (next to this project) or ~/e-Paper,\n"
                "  or set EPD_LIB_PATH to its python lib, e.g.:\n"
                "    export EPD_LIB_PATH=~/e-Paper/RaspberryPi_Jetson_Nano/python/lib\n"
                "    or EPD_LIB_PATH=~/e-Paper/RaspberryPi_JetsonNano/python/lib\n"
                "  Then rerun this script.\n"
                "  Community packages like 'waveshare-epd' may also work on some platforms.\n"
                "- On Raspberry Pi: sudo raspi-config -> Interface Options -> SPI: Enable\n"
            )
            paths_info = ("\nSearched paths added to sys.path:\n  - " + "\n  - ".join(added_paths)) if added_paths else ""
            raise RuntimeError(
                f"Failed to load 2.13\" EPD driver (last error: {last_err}).\n{hint}{paths_info}"
            )

        # Initialize once (support both init and Init)
        init = getattr(self._epd, "init", None) or getattr(self._epd, "Init", None)
        if callable(init):
            init()
        else:
            # Some older drivers auto-init on construction
            pass
        # Clear to white to avoid ghosting on first use
        try:
            self._epd.Clear(0xFF)
        except Exception:
            # Some drivers use 'clear' (lowercase) or 'Clear' without args
            for name in ("clear", "Clear"):
                fn = getattr(self._epd, name, None)
                if callable(fn):
                    try:
                        # Try both with and without argument
                        try:
                            fn(0xFF)
                        except TypeError:
                            fn()
                        break
                    except Exception:
                        continue

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
        # Resolve display/getbuffer names across versions
        display = getattr(self._epd, "display", None) or getattr(self._epd, "Display", None)
        getbuffer = getattr(self._epd, "getbuffer", None) or getattr(self._epd, "getBuffer", None)
        if not callable(display) or not callable(getbuffer):
            raise RuntimeError("EPD driver missing display/getbuffer methods; incompatible driver version")

        try:
            display(getbuffer(img))
        except Exception:
            # Try rotate 180 deg if orientation is flipped
            try:
                display(getbuffer(img.rotate(180)))
            except Exception:
                raise
        finally:
            if self.sleep_after:
                for name in ("sleep", "Sleep"):
                    fn = getattr(self._epd, name, None)
                    if callable(fn):
                        try:
                            fn()
                            break
                        except Exception:
                            continue
