#!/usr/bin/env python3
"""Interactive touch calibration helper for Waveshare touch EPDs."""

import argparse
import os
import sys
import time
from statistics import mean
from typing import Iterable, List, Optional, Tuple

# Allow running the script directly without needing PYTHONPATH tweaks.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
	sys.path.insert(0, REPO_ROOT)

from PIL import Image, ImageDraw, ImageFont

from display_backend import WaveshareEPDBackend
from lunar_pi_skyfield import (
	TOUCH_MAP_CHOICES,
	TouchController,
	load_fonts,
	transform_touch_point,
)

IMAGE_SIZE = (250, 122)
CROSS_SIZE = 8

# Positions cover the button row and key quadrants for diagnosis.
TARGETS: List[Tuple[str, Tuple[int, int]]] = [
	("Top Left", (22, 18)),
	("Top Right", (228, 18)),
	("Bottom Left", (22, 100)),
	("Bottom Right", (228, 100)),
	("Prev Button", (45, 96)),
	("Next Button", (125, 96)),
	("Sleep Button", (205, 96)),
	("Center", (125, 61)),
]


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Touch calibration tool for Waveshare touch panels")
	parser.add_argument("--epd-model", default="2in13", help="Waveshare model (default: 2in13)")
	parser.add_argument(
		"--epd-variant",
		default="auto",
		help="Waveshare variant such as TP_V4/TP_V3; auto will probe (default)",
	)
	parser.add_argument("--rotate", type=int, default=0, help="Rotate output clockwise; touch requires 0")
	parser.add_argument(
		"--epd-lib-path",
		default=None,
		help="Path to the Waveshare python/lib directory (optional)",
	)
	parser.add_argument(
		"--samples",
		type=int,
		default=20,
		help="Maximum touch samples to average for each target (default: 20)",
	)
	parser.add_argument(
		"--poll-ms",
		type=int,
		default=60,
		help="Touch polling interval in milliseconds (default: 60)",
	)
	parser.add_argument(
		"--touch-map",
		choices=sorted(TOUCH_MAP_CHOICES),
		default="auto",
		help="Mapping to highlight; auto reports every permutation",
	)
	parser.add_argument(
		"--no-epd",
		action="store_true",
		help="Skip drawing to the EPD, only print touch samples",
	)
	return parser.parse_args()


def ensure_epd_path(epd_lib_path: Optional[str]) -> None:
	if not epd_lib_path:
		return
	os.environ["EPD_LIB_PATH"] = epd_lib_path
	if os.path.isdir(epd_lib_path) and epd_lib_path not in sys.path:
		sys.path.insert(0, epd_lib_path)


def draw_target(
	draw: ImageDraw.ImageDraw,
	fonts: Tuple[ImageFont.ImageFont, ImageFont.ImageFont],
	label: str,
	coord: Tuple[int, int],
) -> None:
	font_large, font_small = fonts
	draw.rectangle((0, 0, IMAGE_SIZE[0] - 1, IMAGE_SIZE[1] - 1), outline=0, width=1)
	draw.text((6, 4), "Touch Calibration", font=font_large, fill=0)
	draw.text((6, 24), f"Target: {label}", font=font_small, fill=0)
	draw.text((6, 40), "Tap the cross and release", font=font_small, fill=0)
	draw.text((6, 52), "Press Ctrl+C to exit", font=font_small, fill=0)
	x, y = coord
	draw.line((x - CROSS_SIZE, y, x + CROSS_SIZE, y), fill=0)
	draw.line((x, y - CROSS_SIZE, x, y + CROSS_SIZE), fill=0)


def render_summary(
	draw: ImageDraw.ImageDraw,
	fonts: Tuple[ImageFont.ImageFont, ImageFont.ImageFont],
	message_lines: Iterable[str],
) -> None:
	font_large, font_small = fonts
	draw.rectangle((0, 0, IMAGE_SIZE[0] - 1, IMAGE_SIZE[1] - 1), outline=0, width=1)
	draw.text((6, 4), "Touch Calibration", font=font_large, fill=0)
	y = 28
	for line in message_lines:
		draw.text((6, y), line, font=font_small, fill=0)
		y += font_small.getbbox("Ag")[3] + 2


def collect_touch(
	touch: TouchController,
	poll_interval: float,
	max_samples: int,
) -> Optional[Tuple[int, int, int]]:
	samples: List[Tuple[int, int]] = []
	touched = False
	while True:
		sample = touch.sample()
		if sample.pressed:
			touched = True
			if sample.x is not None and sample.y is not None:
				samples.append((sample.x, sample.y))
			if len(samples) >= max_samples:
				break
		elif touched:
			break
		time.sleep(poll_interval)
	if not samples:
		return None
	avg_x = int(round(mean(val[0] for val in samples)))
	avg_y = int(round(mean(val[1] for val in samples)))
	return avg_x, avg_y, len(samples)


def describe_mappings(
	raw_x: int,
	raw_y: int,
	backend: WaveshareEPDBackend,
	rotate: int,
) -> List[str]:
	epd = getattr(backend, "_epd", None)
	hw_width = max(1, getattr(epd, "width", IMAGE_SIZE[1]) if epd else IMAGE_SIZE[1])
	hw_height = max(1, getattr(epd, "height", IMAGE_SIZE[0]) if epd else IMAGE_SIZE[0])
	norm_x = raw_x / max(hw_width - 1, 1)
	norm_y = raw_y / max(hw_height - 1, 1)

	lines = [
		f"Raw: ({raw_x}, {raw_y}) from {hw_width}x{hw_height} panel",
		f"Normalized: x={norm_x:.3f}, y={norm_y:.3f}",
		"Mappings (x, y):",
	]
	for mapping in sorted(TOUCH_MAP_CHOICES):
		if mapping == "auto":
			continue
		pt = transform_touch_point(raw_x, raw_y, IMAGE_SIZE, backend, mapping, rotate)
		lines.append(f"  {mapping:<15} -> {pt}")
	return lines


def main() -> None:
	args = parse_args()
	if args.rotate % 360 != 0:
		print("[WARN] Touch calibration expects --rotate 0. Results may not be valid.")
	ensure_epd_path(args.epd_lib_path)

	backend = WaveshareEPDBackend(
		model=args.epd_model,
		variant=args.epd_variant,
		rotate=args.rotate,
		sleep_after=False,
		touch=True,
	)
	fonts = load_fonts()

	try:
		touch = TouchController()
	except Exception as err:  # pragma: no cover - hardware dependent
		backend.shutdown(sleep=False)
		raise SystemExit(f"Failed to init touch controller: {err}") from err

	poll_interval = args.poll_ms / 1000.0

	try:
		for label, coord in TARGETS:
			if not args.no_epd:
				img = Image.new("1", IMAGE_SIZE, 255)
				draw = ImageDraw.Draw(img)
				draw_target(draw, fonts, label, coord)
				backend.render(img)
			print(f"\nTouch target: {label} at display coords {coord}")
			print("Touch and hold the cross, then release...")
			result = collect_touch(touch, poll_interval, args.samples)
			if result is None:
				print("  No touch detected; retrying target")
				continue
			raw_x, raw_y, count = result
			print(f"  Captured {count} samples -> raw ({raw_x}, {raw_y})")
			mapping_info = describe_mappings(raw_x, raw_y, backend, args.rotate)
			for line in mapping_info:
				print("  " + line)
			if not args.no_epd:
				img = Image.new("1", IMAGE_SIZE, 255)
				draw = ImageDraw.Draw(img)
				summary_lines = [f"Target: {label}"] + mapping_info[:4]
				render_summary(draw, fonts, summary_lines)
				backend.render(img)
			time.sleep(0.8)
	except KeyboardInterrupt:
		print("Calibration aborted by user.")
	finally:
		try:
			touch.close()
		except Exception:
			pass
		backend.shutdown(sleep=False)


if __name__ == "__main__":
	main()