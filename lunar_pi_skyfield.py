import sys
import os
import datetime
import math
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


def main():
	tz = ZoneInfo(TZ_NAME)
	today = test_date if test_date else datetime.date.today()

	# Load Skyfield resources
	ts, eph = load_ephemeris()

	# Phase calculations
	phase_deg = phase_angle_deg(eph, ts, today, tz)
	illum_pct = round((1 - math.cos(math.radians(phase_deg))) / 2 * 100)
	phase_desc = phase_description(phase_deg)

	# Rise/set calculations
	rise, set_time = moonrise_moonset_for_date(eph, ts, LATITUDE, LONGITUDE, today, tz)
	rise_str = rise.strftime("%H:%M") if rise else "N/A"
	set_str = set_time.strftime("%H:%M") if set_time else "N/A"

	# Simulate 2.13" display (250x122 resolution, B&W)
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
	draw.text((5, 5), today.strftime("%Y-%m-%d"), font=font_large, fill=0)
	draw.text((5, 25), f"Phase: {phase_desc}", font=font_small, fill=0)
	draw.text((5, 40), f"Illum: {illum_pct}%", font=font_small, fill=0)
	draw.text((5, 55), f"Rise: {rise_str}", font=font_small, fill=0)
	draw.text((5, 70), f"Set: {set_str}", font=font_small, fill=0)

	# Draw moon
	draw_moon_phase(draw, 190, 80, 30, phase_deg)

	# Save PNG
	image.save("lunar_output.png")

	print(f"Lunar info for {today} @ ({LATITUDE}, {LONGITUDE}) [{TZ_NAME}]: {phase_desc} ({illum_pct}% illum, phase: {phase_deg:.1f}°)")
	print(f"Moon rise: {rise_str}, set: {set_str}")
	print("Output saved as lunar_output.png")


if __name__ == "__main__":
	main()