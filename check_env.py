"""
Quick environment check for running the Waveshare 2.13" EPD backend on Raspberry Pi.

Run:
    python check_env.py

This validates:
- Python version and architecture
- Presence of required Python modules (Pillow, spidev, RPi.GPIO, waveshare_epd)
- SPI device nodes (/dev/spidev*)
- Basic permissions (read/write) on SPI
"""

from __future__ import annotations

import os
import sys
import platform
import importlib
from typing import Tuple


def _check_module(name: str) -> Tuple[bool, str]:
    try:
        importlib.import_module(name)
        return True, "ok"
    except Exception as e:
        return False, f"missing: {e}"


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


def main() -> int:
    print("-- System --")
    print(f"Python: {sys.version.split()[0]}")
    print(f"Platform: {platform.system()} {platform.release()} ({platform.machine()})")

    print("\n-- Python modules --")
    for mod in ["PIL", "spidev", "RPi.GPIO", "waveshare_epd"]:
        ok, msg = _check_module(mod)
        status = "OK" if ok else "FAIL"
        print(f"{mod:12s}: {status:4s} - {msg}")

    print("\n-- SPI devices --")
    ok, msg = _check_spi_nodes()
    status = "OK" if ok else "FAIL"
    print(f"SPI nodes  : {status:4s} - {msg}")

    print("\n-- Next steps --")
    if platform.system() == "Linux" and ("arm" in platform.machine() or "aarch64" in platform.machine()):
        print("If modules are missing on Raspberry Pi OS:")
        print("  1) Enable SPI: sudo raspi-config -> Interface Options -> SPI -> Enable")
        print("  2) Install system packages: sudo apt update && sudo apt install -y python3-pil python3-rpi.gpio python3-spidev")
        print("  3) Install Waveshare Python lib:")
        print("     - EITHER: pip install waveshare-epd")
        print("     - OR: git clone https://github.com/waveshare/e-Paper && export PYTHONPATH=~/e-Paper/RaspberryPi_Jetson_Nano/python/lib:$PYTHONPATH")
        print("  4) Log out/in or add your user to 'spi' group: sudo usermod -aG spi $USER")
    else:
        print("This device does not appear to be a Raspberry Pi. The EPD backend requires a Pi with SPI enabled.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
