import sys
import os
import datetime
import math
import argparse
import time
from zoneinfo import ZoneInfo
from skyfield.api import load, wgs84
from skyfield import almanac
from PIL import Image, ImageDraw, ImageFont

# Optional: Test with specific date (set to None for current date)
test_date = None  # e.g., datetime.date(2025, 9, 21)

# Observer location and timezone (Honey Brook, PA)
LATITUDE = 40.094
LONGITUDE = -75.911
TZ_NAME = "America/New_York"


def load_ephemeris():
	"""Load Skyfield timescale and ephemeris with local cache support.

	Tries in order:
	- Path from SKYFIELD_EPH env var
	- Local file 'de421.bsp' next to this script
	- Download 'de421.bsp' (may require internet)
	"""
	ts = load.timescale()
	eph_path = os.environ.get("SKYFIELD_EPH")
	if eph_path and os.path.exists(eph_path):
		return ts, load(eph_path)

	local_eph = os.path.join(os.path.dirname(os.path.abspath(__file__)), "de421.bsp")
	if os.path.exists(local_eph):
		return ts, load(local_eph)

	try:
		# This may download the file if not cached by Skyfield.
		return ts, load("de421.bsp")
	except Exception as e:
		raise RuntimeError(
			"Skyfield ephemeris not found. Set SKYFIELD_EPH or place de421.bsp next to the script."
		) from e


def local_midnight_bounds(day: datetime.date, tz: ZoneInfo) -> tuple[datetime.datetime, datetime.datetime]:
	"""Return local start/end datetimes for the given date."""
	start = datetime.datetime(day.year, day.month, day.day, 0, 0, 0, tzinfo=tz)
	end = start + datetime.timedelta(days=1)
	return start, end


def moonrise_moonset_for_date(eph, ts, lat: float, lon: float, day: datetime.date, tz: ZoneInfo):
	"""Compute moonrise and moonset local times for the given date.

	Returns (rise_dt, set_dt) as timezone-aware datetimes or None if not present.
	"""
	topos = wgs84.latlon(lat, lon)
	start_local, end_local = local_midnight_bounds(day, tz)
	t0 = ts.from_datetime(start_local.astimezone(datetime.timezone.utc))
	t1 = ts.from_datetime(end_local.astimezone(datetime.timezone.utc))

	# For generic bodies, events from find_discrete are: 1=rising, 0=setting
	f = almanac.risings_and_settings(eph, eph["Moon"], topos)
	t, y = almanac.find_discrete(t0, t1, f)

	rise_dt = None
	set_dt = None
	for ti, yi in zip(t, y):
		dt_utc = ti.utc_datetime().replace(tzinfo=datetime.timezone.utc)
		dt_local = dt_utc.astimezone(tz)
		if yi == 1 and rise_dt is None:
			rise_dt = dt_local
		elif yi == 0 and set_dt is None:
			set_dt = dt_local

	return rise_dt, set_dt


def phase_angle_deg(eph, ts, day: datetime.date, tz: ZoneInfo) -> float:
	"""Compute the Moon-Sun elongation angle in degrees at local noon."""
	noon_local = datetime.datetime(day.year, day.month, day.day, 12, 0, 0, tzinfo=tz)
	t = ts.from_datetime(noon_local.astimezone(datetime.timezone.utc))
	angle = almanac.moon_phase(eph, t)
	return angle.degrees % 360.0


def phase_description(deg: float) -> str:
	"""Label phase by elongation angle."""
	if (0 <= deg < 22.5) or (337.5 <= deg <= 360):
		return "New Moon"
	elif 22.5 <= deg < 67.5:
		return "Waxing Crescent"
	elif 67.5 <= deg < 112.5:
		return "First Quarter"
	elif 112.5 <= deg < 157.5:
		return "Waxing Gibbous"
	elif 157.5 <= deg < 202.5:
		return "Full Moon"
	elif 202.5 <= deg < 247.5:
		return "Waning Gibbous"
	elif 247.5 <= deg < 292.5:
		return "Last Quarter"
	else:  # 292.5 <= deg < 337.5
		return "Waning Crescent"


def draw_moon_phase(draw: ImageDraw.ImageDraw, center_x: int, center_y: int, radius: int, phase_deg: float):
	"""Draw a simple B/W moon phase using the two-circle overlap method."""
	angle = math.radians(phase_deg)
	f = (1 - math.cos(angle)) / 2  # Illuminated fraction (0 to 1)

	# Determine offset direction: left shadow for waxing (0–180°), right for waning (180–360°)
	if phase_deg < 180:
		offset_x = -2 * radius * f
	else:
		offset_x = 2 * radius * f

	# Draw illuminated disk (black circle)
	bbox_moon = (center_x - radius, center_y - radius, center_x + radius, center_y + radius)
	draw.ellipse(bbox_moon, fill=0)  # Black fill

	# Draw shadow (white circle, offset)
	shadow_center_x = center_x + offset_x
	bbox_shadow = (shadow_center_x - radius, center_y - radius, shadow_center_x + radius, center_y + radius)
	draw.ellipse(bbox_shadow, fill=255)  # White fill to cover dark part


def parse_args(argv: list[str]) -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Lunar info renderer with pluggable display backend")
	parser.add_argument("--date", help="ISO date (YYYY-MM-DD) to render; default today", default=None)
	parser.add_argument("--backend", choices=["file", "epd"], default="file", help="Output backend: file (PNG) or epd (Waveshare e-Paper)")
	parser.add_argument("--output", "-o", default="lunar_output.png", help="Output PNG path when using file backend")
	parser.add_argument("--rotate", type=int, default=0, help="Rotate output clockwise in degrees (0/90/180/270)")
	parser.add_argument("--epd-model", default="2in13", help="Waveshare model, e.g., 2in13 (default), 7in5, 7in5b")
	parser.add_argument(
		"--epd-variant",
		default="auto",
		help=(
			"Waveshare variant (model-specific). Non-touch: auto, V4, V3, V2, V1. "
			"Touch: TP_V4, TP_V3, TP_V2."
		),
	)
	parser.add_argument("--epd-touch", action="store_true", help="Use Waveshare touch drivers (TP_lib) for 2.13\" panels")
	parser.add_argument("--epd-clear", action="store_true", help="Clear Waveshare display to white and exit (requires epd backend)")
	parser.add_argument("--no-sleep", action="store_true", help="Do not put the EPD to sleep after rendering")
	parser.add_argument(
		"--epd-auto-clear-delay",
		type=int,
		default=600,
		help=(
			"Seconds to wait before automatically clearing the EPD and shutting down the driver. "
			"Use 0 to disable (default: 600 seconds / 10 minutes)."
		),
	)
	parser.add_argument(
		"--epd-lib-path",
		default=None,
		help=(
			"Path to Waveshare e-Paper python lib (RaspberryPi_Jetson_Nano/python/lib). "
			"If set, this is added to sys.path and EPD_LIB_PATH is exported before loading the backend."
		),
	)
	args = parser.parse_args(argv)
	if args.epd_clear and args.backend != "epd":
		parser.error("--epd-clear requires --backend epd")
	if args.epd_auto_clear_delay < 0:
		parser.error("--epd-auto-clear-delay must be zero or a positive number of seconds")
	return args


def _epd_clear_after_delay(backend, delay: int, sleep_after: bool) -> None:
	"""Wait the requested delay, clear the panel, and shut down the backend."""
	if delay <= 0 or backend is None:
		backend.shutdown(sleep=sleep_after)
		return

	minutes = delay / 60
	print(f"Auto-clear scheduled: clearing the panel in {minutes:.1f} minute(s). Press Ctrl+C to clear immediately.")
	try:
		time.sleep(delay)
	except KeyboardInterrupt:
		print("Interrupt received, clearing panel now...")

	try:
		backend.clear()
	except Exception as err:
		print(f"[WARN] Auto-clear failed: {err}")
	finally:
		backend.shutdown(sleep=sleep_after)
		print("EPD cleared and backend shut down.")


def main(argv: list[str] | None = None):
	args = parse_args(argv or sys.argv[1:])
	if args.epd_touch and args.epd_variant.lower() == "auto":
		args.epd_variant = "TP_V4"

	tz = ZoneInfo(TZ_NAME)
	if args.date:
		y, m, d = map(int, args.date.split("-"))
		chosen_date = datetime.date(y, m, d)
	else:
		chosen_date = test_date if test_date else datetime.date.today()

	# Load Skyfield resources
	ts, eph = load_ephemeris()

	# Phase calculations
	phase_deg = phase_angle_deg(eph, ts, chosen_date, tz)
	illum_pct = round((1 - math.cos(math.radians(phase_deg))) / 2 * 100)
	phase_desc = phase_description(phase_deg)

	# Rise/set calculations
	rise, set_time = moonrise_moonset_for_date(eph, ts, LATITUDE, LONGITUDE, chosen_date, tz)
	rise_str = rise.strftime("%H:%M") if rise else "N/A"
	set_str = set_time.strftime("%H:%M") if set_time else "N/A"

	# Canvas for 2.13" display (250x122 resolution, B&W)
	image = Image.new('1', (250, 122), 255)  # White background
	draw = ImageDraw.Draw(image)

	# Use system font (DejaVu) if available, fallback to default
	try:
		font_large = ImageFont.truetype("/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf", 16)
		font_small = ImageFont.truetype("/usr/share/fonts/dejavu/DejaVuSans.ttf", 12)
	except IOError:
		font_large = ImageFont.load_default()
		font_small = ImageFont.load_default()

	# Draw content
	draw.text((5, 5), chosen_date.strftime("%Y-%m-%d"), font=font_large, fill=0)
	draw.text((5, 25), f"Phase: {phase_desc}", font=font_small, fill=0)
	draw.text((5, 40), f"Illum: {illum_pct}%", font=font_small, fill=0)
	draw.text((5, 55), f"Rise: {rise_str}", font=font_small, fill=0)
	draw.text((5, 70), f"Set: {set_str}", font=font_small, fill=0)

	# Draw moon
	draw_moon_phase(draw, 190, 80, 30, phase_deg)

	# Optionally set EPD lib path before importing backend module
	if args.epd_lib_path:
		os.environ["EPD_LIB_PATH"] = args.epd_lib_path
		# Prepend to sys.path so display_backend can import immediately
		if os.path.isdir(args.epd_lib_path) and args.epd_lib_path not in sys.path:
			sys.path.insert(0, args.epd_lib_path)

	# Import backends only now, after env/path is configured
	from display_backend import FileBackend, WaveshareEPDBackend

	# Choose backend
	if args.backend == "file":
		backend = FileBackend(path=args.output)
	else:
		touch_mode = args.epd_touch or args.epd_variant.upper().startswith("TP")
		try:
			backend = WaveshareEPDBackend(
				model=args.epd_model,
				variant=args.epd_variant,
				rotate=args.rotate,
				sleep_after=not args.no_sleep,
				touch=touch_mode,
			)
		except Exception as e:
			print("[ERROR] Failed to initialize Waveshare EPD backend:")
			print(f"        {e}")
			print("\nHints:")
			print("- Run: python check_env.py")
			print("- If using the Waveshare repo, pass --epd-lib-path /path/to/e-Paper/RaspberryPi_Jetson_Nano/python/lib")
			print("- See README: Raspberry Pi setup (SPI enablement, Waveshare e-Paper repo)")
			sys.exit(2)

	if args.backend == "epd" and args.epd_clear:
		try:
			backend.clear()
		except Exception as e:
			print("[ERROR] Failed to clear EPD:")
			print(f"        {e}")
			sys.exit(4)
		backend.shutdown(sleep=not args.no_sleep)
		print("EPD cleared to white")
		return

	# Apply rotation at the backend level; for file backend we can rotate here to keep the saved file matching expectation
	if args.backend == "file" and args.rotate:
		rotated = image.rotate(-args.rotate, expand=True)
		backend.render(rotated)
	else:
		try:
			backend.render(image)
		except Exception as e:
			print("[ERROR] Failed to render to EPD:")
			print(f"        {e}")
			print("Try adjusting --rotate or --epd-variant, and ensure SPI and drivers are installed.")
			sys.exit(3)

	print(f"Lunar info for {chosen_date} @ ({LATITUDE}, {LONGITUDE}) [{TZ_NAME}]: {phase_desc} ({illum_pct}% illum, phase: {phase_deg:.1f}°)")
	print(f"Moon rise: {rise_str}, set: {set_str}")
	if args.backend == "file":
		print(f"Output saved as {args.output}")
	else:
		print("Output sent to Waveshare e-Paper display")
		if args.epd_auto_clear_delay <= 0:
			print("Auto-clear disabled; remember to clear the panel when you're done.")
		_epd_clear_after_delay(backend, args.epd_auto_clear_delay, not args.no_sleep)


if __name__ == "__main__":
	main()