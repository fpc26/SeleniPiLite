#!/usr/bin/env python3
"""
EPD BUSY pin probe for Waveshare 2.13" displays (V4, V3, V2)

What this does:
- Reads the BUSY pin level repeatedly and logs transitions
- Optionally toggles RESET to stimulate the panel and observe BUSY behavior
- Supports either RPi.GPIO or pigpio backends (auto-detect)

Usage:
  sudo -E python3 scripts/epd_busy_probe.py --variant V4
  # Or with pigpio (recommended)
  sudo systemctl enable --now pigpiod
  GPIOZERO_PIN_FACTORY=pigpio python3 scripts/epd_busy_probe.py --use-pigpio

Default pins (BCM): BUSY=24, RST=17, DC=25, CS=8 (CE0)

This script helps diagnose cases where vendor examples report
"BUSY_PIN state not working" or "Edge detection has failed" by
verifying wiring, pin polarity, and whether edges are actually generated.
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import Optional


def _try_import(module: str):
    try:
        return __import__(module)
    except Exception:
        return None


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="V4", help="2.13 variant label (informational)")
    ap.add_argument("--busy", type=int, default=24, help="BUSY pin (BCM)")
    ap.add_argument("--rst", type=int, default=17, help="RST pin (BCM)")
    ap.add_argument("--dc", type=int, default=25, help="DC pin (BCM)")
    ap.add_argument("--cs", type=int, default=8, help="CS pin (BCM, usually CE0=8)")
    ap.add_argument("--use-pigpio", action="store_true", help="Force pigpio backend (requires pigpiod)")
    ap.add_argument("--no-reset", action="store_true", help="Do not toggle reset (observe passive BUSY only)")
    ap.add_argument("--duration", type=float, default=8.0, help="Observation duration in seconds")
    ap.add_argument("--edge", choices=["none", "both", "rising", "falling"], default="both",
                    help="Edge(s) to watch if supported by backend")
    return ap.parse_args()


class RPIGPIOProbe:
    def __init__(self, busy: int, rst: int, dc: int, cs: int, edge: str):
        self.GPIO = _try_import("RPi.GPIO")
        if not self.GPIO:
            raise RuntimeError("RPi.GPIO not available")
        self.busy = busy
        self.rst = rst
        self.dc = dc
        self.cs = cs
        self.edge = edge

        G = self.GPIO
        G.setwarnings(False)
        G.setmode(G.BCM)
        # Inputs with pull-ups (Waveshare HATs usually already have pull-ups)
        G.setup(self.busy, G.IN, pull_up_down=G.PUD_UP)
        # Outputs
        for p in (self.rst, self.dc, self.cs):
            G.setup(p, G.OUT)
        # Idle states
        G.output(self.cs, 1)
        G.output(self.dc, 0)
        G.output(self.rst, 1)

        # Prepare edge detection
        if self.edge != "none":
            try:
                G.remove_event_detect(self.busy)
            except Exception:
                pass
            edge_map = {
                "rising": G.RISING,
                "falling": G.FALLING,
                "both": G.BOTH,
            }
            def cb(channel):  # type: ignore[no-redef]
                lvl = G.input(channel)
                print(f"[RPi.GPIO] BUSY edge -> level={lvl} @ {time.time():.3f}")
            try:
                G.add_event_detect(self.busy, edge_map.get(self.edge, G.BOTH), callback=cb, bouncetime=1)
                print(f"[RPi.GPIO] Edge detection enabled: {self.edge}")
            except RuntimeError as e:
                print(f"[RPi.GPIO] add_event_detect failed: {e}")

    def reset_pulse(self):
        G = self.GPIO
        print("Toggling RST: H -> L (10ms) -> H")
        G.output(self.rst, 1)
        time.sleep(0.01)
        G.output(self.rst, 0)
        time.sleep(0.01)
        G.output(self.rst, 1)

    def read_level(self) -> int:
        return int(self.GPIO.input(self.busy))

    def cleanup(self):
        try:
            self.GPIO.cleanup()
        except Exception:
            pass


class PigpioProbe:
    def __init__(self, busy: int, rst: int, dc: int, cs: int, edge: str):
        pigpio = _try_import("pigpio")
        if not pigpio:
            raise RuntimeError("pigpio not available; install and ensure pigpiod is running")
        self.pigpio = pigpio
        self.pi = pigpio.pi()
        if not self.pi.connected:
            raise RuntimeError("pigpiod not running or not reachable")
        self.busy, self.rst, self.dc, self.cs, self.edge = busy, rst, dc, cs, edge
        self.pi.set_mode(self.busy, pigpio.INPUT)
        self.pi.set_pull_up_down(self.busy, pigpio.PUD_UP)
        for p in (self.rst, self.dc, self.cs):
            self.pi.set_mode(p, pigpio.OUTPUT)
        self.pi.write(self.cs, 1)
        self.pi.write(self.dc, 0)
        self.pi.write(self.rst, 1)
        self.cb = None  # type: Optional[any]
        if self.edge != "none":
            edge_map = {
                "rising": pigpio.RISING_EDGE,
                "falling": pigpio.FALLING_EDGE,
                "both": pigpio.EITHER_EDGE,
            }
            def _cbf(gpio, level, tick):  # noqa: N802
                print(f"[pigpio] BUSY edge -> level={level} tick={tick}")
            self.cb = self.pi.callback(self.busy, edge_map.get(self.edge, pigpio.EITHER_EDGE), _cbf)
            print(f"[pigpio] Edge detection enabled: {self.edge}")

    def reset_pulse(self):
        print("Toggling RST: H -> L (10ms) -> H")
        self.pi.write(self.rst, 1)
        time.sleep(0.01)
        self.pi.write(self.rst, 0)
        time.sleep(0.01)
        self.pi.write(self.rst, 1)

    def read_level(self) -> int:
        return int(self.pi.read(self.busy))

    def cleanup(self):
        try:
            if self.cb:
                self.cb.cancel()
            self.pi.stop()
        except Exception:
            pass


def main() -> int:
    args = parse_args()
    print(f"EPD BUSY probe - variant={args.variant} busy={args.busy} rst={args.rst} dc={args.dc} cs={args.cs}")

    backend = None
    probe = None
    try:
        if args.use_pigpio:
            backend = "pigpio"
            probe = PigpioProbe(args.busy, args.rst, args.dc, args.cs, args.edge)
        else:
            # Prefer RPi.GPIO if available; fall back to pigpio
            try:
                probe = RPIGPIOProbe(args.busy, args.rst, args.dc, args.cs, args.edge)
                backend = "RPi.GPIO"
            except Exception as e_rpi:
                print(f"[info] RPi.GPIO unavailable or failed ({e_rpi}), trying pigpio...")
                probe = PigpioProbe(args.busy, args.rst, args.dc, args.cs, args.edge)
                backend = "pigpio"

        print(f"Using backend: {backend}")
        lvl = probe.read_level()
        print(f"Initial BUSY level: {lvl} (1=pulled-up/idle on many panels; 0=busy on many panels)")

        if not args.no_reset:
            probe.reset_pulse()
            time.sleep(0.05)
            lvl2 = probe.read_level()
            print(f"BUSY level after reset: {lvl2}")

        print(f"Observing BUSY for {args.duration:.1f}s (edges + polling at ~50Hz)...")
        t_end = time.time() + args.duration
        last = None
        while time.time() < t_end:
            cur = probe.read_level()
            if cur != last:
                print(f"[poll] BUSY={cur} @ {time.time():.3f}")
                last = cur
            time.sleep(0.02)

        print("Done. Interpretation tips:")
        print("- If BUSY stays at 1 constantly: the display might be idle, disconnected, or pull-up only; try sending a real init via vendor driver.")
        print("- If BUSY stays at 0 constantly: check wiring; some variants invert logic, but constant 0 suggests held-low wiring or HAT issue.")
        print("- If no edges are reported but polling shows flips: edge-detection backend may be unreliable; prefer polling in driver.")
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception as e:
        print(f"ERROR: {e}")
        return 1
    finally:
        if probe:
            try:
                probe.cleanup()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
