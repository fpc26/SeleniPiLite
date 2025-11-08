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


class WaveshareEPDBackend(DisplayBackend):
    """Generic backend for Waveshare e-Paper HATs (multiple sizes/models).

    Attempts to import the appropriate driver from the official repos and detect
    width/height. Converts the provided image to 1-bit and rotates if requested.

    Parameters
    - model: e.g., "2in13" (default), "7in5", "7in5b" (tri-color), etc.
    - variant: "auto", "V4", "V3", "V2", "V1" (best effort; depends on model)
    - rotate: 0, 90, 180, 270 (clockwise degrees)
    - sleep_after: put the display to sleep after rendering
    """

    def __init__(self, model: str = "2in13", variant: str = "auto", rotate: int = 0, sleep_after: bool = True):
        self.model = (model or "2in13").lower()
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

        # Consider both folder name variants used by the repos (e-Paper and Touch_e-Paper_HAT)
        repo_variants = ["RaspberryPi_Jetson_Nano", "RaspberryPi_JetsonNano"]
        for base in [proj_root, os.path.expanduser("~")]:
            for variant in repo_variants:
                # Official e-Paper repo
                candidate_paths.append(os.path.join(base, "e-Paper", variant, "python", "lib"))
                # Touch e-Paper HAT repo
                candidate_paths.append(os.path.join(base, "Touch_e-Paper_HAT", variant, "python", "lib"))

        added_paths: list[str] = []
        for p in candidate_paths:
            if p and os.path.isdir(p) and p not in sys.path:
                sys.path.insert(0, p)
                added_paths.append(p)

        # Try commonly used module/class names
        candidates = []
        def _model_module_candidates(model: str) -> list[tuple[str, str]]:
            m = model.lower()
            names: list[tuple[str, str]] = []
            # Support Waveshare touch-panel drivers shipped under TP_lib
            touch_variant_aliases = {
                "TP_V4": "TP_V4",
                "TP2IN13_V4": "TP_V4",
                "TOUCH_V4": "TP_V4",
                "TPV4": "TP_V4",
                "TP_V3": "TP_V3",
                "TP2IN13_V3": "TP_V3",
                "TOUCH_V3": "TP_V3",
                "TPV3": "TP_V3",
                "TP_V2": "TP_V2",
                "TP2IN13_V2": "TP_V2",
                "TOUCH_V2": "TP_V2",
                "TPV2": "TP_V2",
            }
            touch_variant_modules = {
                "TP_V4": ["TP_lib.epd2in13_V4"],
                "TP_V3": ["TP_lib.epd2in13_V3"],
                "TP_V2": ["TP_lib.epd2in13_V2"],
            }
            normalized_variant = self.variant.replace("-", "_")
            variant_key = touch_variant_aliases.get(normalized_variant)

            if self.variant == "AUTO":
                # Try common variants first
                base_names = [f"epd{m}_V4", f"epd{m}_V3", f"epd{m}_V2", f"epd{m}"]
                # Include some typical tri-color suffixes for both 2.13 and 7.5 families
                tri = [f"epd{m}b_V4", f"epd{m}b_V3", f"epd{m}b_V2", f"epd{m}b"]
                # Extra alternates seen for 2.13
                extra = []
                if m == "2in13":
                    extra = ["epd2in13d", "epd2in13g"]
                    for mod in ["TP_lib.epd2in13_V4", "TP_lib.epd2in13_V3", "TP_lib.epd2in13_V2"]:
                        names.append((mod, "EPD"))
                        names.append((mod.split(".", 1)[-1], "EPD"))
                all_mods = base_names + tri + extra
                for mod in all_mods:
                    names.append((f"waveshare_epd.{mod}", "EPD"))
                for mod in all_mods:
                    names.append((mod, "EPD"))
            else:
                if variant_key and m == "2in13":
                    for mod in touch_variant_modules.get(variant_key, []):
                        names.append((mod, "EPD"))
                        names.append((mod.split(".", 1)[-1], "EPD"))
                    return names
                mod_suffix = f"epd{m}_{self.variant}"
                names.append((f"waveshare_epd.{mod_suffix}", "EPD"))
                names.append((mod_suffix, "EPD"))
                # Also try non-suffixed for convenience (some repos don't use variant suffix)
                names.append((f"waveshare_epd.epd{m}", "EPD"))
                names.append((f"epd{m}", "EPD"))
            return names

        # Build candidates for the requested model, but if AUTO variant fails entirely
        # and the model looks like 2in13 touch panel, suggest Touch repo in error.
        candidates = _model_module_candidates(self.model)

        last_err: Optional[Exception] = None
        for mod_name, class_name in candidates:
            try:
                module = __import__(mod_name, fromlist=[class_name])
                epd_cls = getattr(module, class_name)
                try:
                    # Attempt to instantiate the driver; if this fails due to GPIO/SPI permissions,
                    # surface that error immediately (it's the correct module).
                    epd = epd_cls()
                except Exception as e:
                    # If instantiation fails (e.g., RuntimeError: Failed to add edge detection),
                    # stop trying other variants and raise with helpful hints.
                    last_err = e
                    break
                self._module = module
                self._epd = epd
                break
            except Exception as e:  # ImportError or attribute errors
                last_err = e
                continue

        if self._epd is None:
            hint = (
                "Ensure the Waveshare Python library is installed and SPI is enabled.\n"
                "- pip install RPi.GPIO spidev Pillow\n"
                "- Clone official repos (pick the one matching your HAT):\n"
                "    https://github.com/waveshare/e-Paper\n"
                "    https://github.com/waveshare/Touch_e-Paper_HAT  (for touch versions like 2.13 Touch)\n"
                "  Place at: ./e-Paper or ~/e-Paper (and/or ./Touch_e-Paper_HAT or ~/Touch_e-Paper_HAT),\n"
                "  or set EPD_LIB_PATH to the python lib folder, e.g.:\n"
                "    export EPD_LIB_PATH=~/e-Paper/RaspberryPi_Jetson_Nano/python/lib\n"
                "    export EPD_LIB_PATH=~/Touch_e-Paper_HAT/RaspberryPi_Jetson_Nano/python/lib\n"
                "  Then rerun this script.\n"
                "  Community packages like 'waveshare-epd' may also work on some platforms.\n"
                "- On Raspberry Pi: sudo raspi-config -> Interface Options -> SPI: Enable\n"
                "- GPIO permissions: add your user to 'spi' and 'gpio' groups and log out/in:\n"
                "    sudo usermod -aG spi,gpio $USER\n"
                "  To quickly test permissions, try running as root (not recommended long-term):\n"
                "    sudo -E python your_script.py --backend epd ...\n"
            )
            paths_info = ("\nSearched paths added to sys.path:\n  - " + "\n  - ".join(added_paths)) if added_paths else ""
            raise RuntimeError(
                f"Failed to load EPD driver for model '{self.model}' (last error: {last_err}).\n{hint}{paths_info}"
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
            # Fallbacks by model
            if self.model == "7in5" or self.model == "7in5b":
                width, height = 480, 800  # typical 7.5" resolution (WxH)
            else:
                width, height = 122, 250  # 2.13" default

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


class WaveshareEPD2in13Backend(WaveshareEPDBackend):
    """Backward-compatible alias for 2.13" displays.

    Kept for existing callers; equivalent to WaveshareEPDBackend(model="2in13", ...).
    """

    def __init__(self, variant: str = "auto", rotate: int = 0, sleep_after: bool = True):
        super().__init__(model="2in13", variant=variant, rotate=rotate, sleep_after=sleep_after)
