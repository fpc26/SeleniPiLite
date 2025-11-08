"""
Quick environment check for running the Waveshare 2.13" EPD backend on Raspberry Pi.

Run:
    python check_env.py

This validates:
- Python version and architecture
- Presence of required Python modules (Pillow, spidev, RPi.GPIO)
- SPI device nodes (/dev/spidev*)
- Basic permissions (read/write) on SPI
"""

from __future__ import annotations

import os
import sys
import platform
import importlib
import importlib.util
from typing import Tuple


def _check_module(name: str) -> Tuple[bool, str]:
    try:
        importlib.import_module(name)
        return True, "ok"
    except ModuleNotFoundError as e:
        if name == "smbus":
            try:
                smbus2 = importlib.import_module("smbus2")
                sys.modules.setdefault("smbus", smbus2)
                return True, "using smbus2"
            except Exception:
                pass
        return False, f"missing: {e}"
    except Exception as e:
        return False, f"error: {e}"


def _check_spi_nodes() -> Tuple[bool, str]:
    candidates = [
        "/dev/spidev0.0",
        "/dev/spidev0.1",
        "/dev/spidev1.0",
    ]
    found = [p for p in candidates if os.path.exists(p)]
    if not found:
        return False, "no /dev/spidev* nodes found (is SPI enabled?)"
    # Check rw perms on the first found
    p = found[0]
    can_read = os.access(p, os.R_OK)
    can_write = os.access(p, os.W_OK)
    if can_read and can_write:
        return True, f"found {', '.join(found)}"
    else:
        return False, f"found {', '.join(found)} but insufficient permissions (try adding user to 'spi' group or run with sudo)"


def _discover_epd_paths() -> list[str]:
    proj_root = os.path.dirname(os.path.abspath(__file__))
    variants = ["RaspberryPi_Jetson_Nano", "RaspberryPi_JetsonNano"]
    candidates: list[str] = []
    env_path = os.environ.get("EPD_LIB_PATH", "")
    if env_path:
        env_path = env_path.rstrip(os.sep)
        candidates.append(env_path)
        candidates.append(os.path.join(env_path, "waveshare_epd"))
        candidates.append(os.path.join(env_path, "TP_lib"))
        if env_path.endswith("waveshare_epd") or env_path.endswith("TP_lib"):
            candidates.append(os.path.dirname(env_path))
    touch_repo_names = ["Touch_e-Paper_HAT", "Touch-e-Paper_HAT"]
    for base in [proj_root, os.path.expanduser(os.path.join("~"))]:
        for v in variants:
            # Official e-Paper repo
            lib = os.path.join(base, "e-Paper", v, "python", "lib")
            candidates.append(lib)
            candidates.append(os.path.join(lib, "waveshare_epd"))
            candidates.append(os.path.join(lib, "TP_lib"))
            # Touch e-Paper HAT repo
            for touch_repo in touch_repo_names:
                lib_t = os.path.join(base, touch_repo, v, "python", "lib")
                candidates.append(lib_t)
                candidates.append(os.path.join(lib_t, "waveshare_epd"))
                candidates.append(os.path.join(lib_t, "TP_lib"))
    return [p for p in candidates if p and os.path.isdir(p)]


def main() -> int:
    print("-- System --")
    print(f"Python: {sys.version.split()[0]}")
    print(f"Platform: {platform.system()} {platform.release()} ({platform.machine()})")

    print("\n-- Python modules --")
    for mod in ["PIL", "spidev", "RPi.GPIO", "smbus"]:
        ok, msg = _check_module(mod)
        status = "OK" if ok else "FAIL"
        print(f"{mod:12s}: {status:4s} - {msg}")

    # Try flat modules from the official e-Paper repo after adding likely paths
    added = []
    for p in _discover_epd_paths():
        if p not in sys.path:
            sys.path.insert(0, p)
            added.append(p)

    # Prefer checking availability without importing (to avoid GPIO side effects)
    print("\n-- Waveshare e-Paper module discovery --")
    # 1) Can we import the package without side effects?
    spec_pkg = importlib.util.find_spec("waveshare_epd")
    print(f"waveshare_epd pkg: {'FOUND' if spec_pkg else 'MISSING'}")
    # 2) Which common modules are present (namespaced)?
    for mod in [
        # 2.13 family
        "waveshare_epd.epd2in13_V4", "waveshare_epd.epd2in13_V3",
        "waveshare_epd.epd2in13_V2", "waveshare_epd.epd2in13",
        "waveshare_epd.epd2in13b_V3", "waveshare_epd.epd2in13b_V4",
        "waveshare_epd.epd2in13d", "waveshare_epd.epd2in13g",
        # 2.13 touch family (Touch_e-Paper_HAT)
        "TP_lib.epd2in13_V4", "TP_lib.epd2in13_V3", "TP_lib.epd2in13_V2",
        # 7.5 family
        "waveshare_epd.epd7in5_V3", "waveshare_epd.epd7in5_V2", "waveshare_epd.epd7in5",
        "waveshare_epd.epd7in5b_V2", "waveshare_epd.epd7in5b",
    ]:
        try:
            spec = importlib.util.find_spec(mod)
        except ModuleNotFoundError:
            spec = None
        status = "FOUND" if spec else "MISSING"
        print(f"{mod:24s}: {status}")

    print("\n-- SPI devices --")
    ok, msg = _check_spi_nodes()
    status = "OK" if ok else "FAIL"
    print(f"SPI nodes  : {status:4s} - {msg}")

    print("\n-- Next steps --")
    if platform.system() == "Linux" and ("arm" in platform.machine() or "aarch64" in platform.machine()):
        print("If modules are missing on Raspberry Pi OS:")
        print("  1) Enable SPI: sudo raspi-config -> Interface Options -> SPI -> Enable")
        print("  2) Install system packages: sudo apt update && sudo apt install -y python3-pil python3-rpi.gpio python3-spidev")
        print("  3) Install Waveshare e-Paper Python lib (official repo):")
        print("     git clone https://github.com/waveshare/e-Paper ~/e-Paper")
        print("     export EPD_LIB_PATH=~/e-Paper/RaspberryPi_Jetson_Nano/python/lib")
        print("     # Or place the repo inside this project as ./e-Paper and it will be auto-detected.")
        print("  4) Log out/in or add your user to 'spi' group: sudo usermod -aG spi $USER")
        if added:
            print("\nDetected e-Paper lib path(s):")
            for p in added:
                print(f"  - {p}")
        elif os.environ.get("EPD_LIB_PATH"):
            print(f"\nEPD_LIB_PATH set to: {os.environ.get('EPD_LIB_PATH')}")
    else:
        print("This device does not appear to be a Raspberry Pi. The EPD backend requires a Pi with SPI enabled.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
