import sys
import os
import datetime
import math
from astral import LocationInfo, moon
from astral.moon import moonrise, moonset
from PIL import Image, ImageDraw, ImageFont

# Optional: Test with specific date (set to None for current date)
test_date = None # datetime.date(2025, 10, 9)

# Set up location for Honey Brook, PA
location = LocationInfo(
 "Honey Brook",
 "PA",
 "America/New_York",
 latitude=40.094,
 longitude=-75.911
)

# Function to draw the moon phase shape (unchanged)
def draw_moon_phase(draw, center_x, center_y, radius, phase_deg):
 angle = math.radians(phase_deg)
 f = (1 - math.cos(angle)) / 2 # Illuminated fraction (0 to 1)
 
 # Determine offset direction: left shadow for waxing (0-180°), right for waning (180-360°)
 if phase_deg < 180:
 	offset_x = -2 * radius * f
 else:
 	offset_x = 2 * radius * f
 
 # Draw illuminated disk (black circle)
 bbox_moon = (center_x - radius, center_y - radius, center_x + radius, center_y + radius)
 draw.ellipse(bbox_moon, fill=0) # Black fill
 
 # Draw shadow (white circle, offset)
 shadow_center_x = center_x + offset_x
 bbox_shadow = (shadow_center_x - radius, center_y - radius, shadow_center_x + radius, center_y + radius)
 draw.ellipse(bbox_shadow, fill=255) # White fill to cover dark part

# Get current date and moon phase at noon UTC (for daily accuracy)
today = test_date if test_date else datetime.date.today()
dt = datetime.datetime(today.year, today.month, today.day, 12, 0, 0, tzinfo=datetime.timezone.utc)
phase_days = moon.phase(dt)
phase_deg = (phase_days / 29.530588853) * 360 # Convert days to degrees

# NEW: Standard 45° bins for phase descriptions (non-overlapping, symmetric)
if (0 <= phase_deg < 22.5) or (337.5 <= phase_deg <= 360):
 phase_desc = "New Moon"
elif 22.5 <= phase_deg < 67.5:
 phase_desc = "Waxing Crescent"
elif 67.5 <= phase_deg < 112.5:
 phase_desc = "First Quarter"
elif 112.5 <= phase_deg < 157.5:
 phase_desc = "Waxing Gibbous"
elif 157.5 <= phase_deg < 202.5:
 phase_desc = "Full Moon"
elif 202.5 <= phase_deg < 247.5:
 phase_desc = "Waning Gibbous"
elif 247.5 <= phase_deg < 292.5:
 phase_desc = "Last Quarter"
else: # 292.5 <= phase_deg < 337.5
 phase_desc = "Waning Crescent"

# NEW: Compute illumination percentage (for display/debug)
illum_pct = round((1 - math.cos(math.radians(phase_deg))) / 2 * 100)

# Compute moonrise and moonset times (local timezone)
rise = moonrise(location.observer, today, tzinfo=location.timezone)
set_time = moonset(location.observer, today, tzinfo=location.timezone)

# Format times or handle None
rise_str = rise.strftime("%H:%M") if rise else "N/A"
set_str = set_time.strftime("%H:%M") if set_time else "N/A"

# Simulate 2.13" display (250x122 resolution, B&W)
image = Image.new('1', (250, 122), 255) # White background
draw = ImageDraw.Draw(image)

# Use a system font (Fedora has DejaVu; adjust path if needed)
try:
 font_large = ImageFont.truetype("/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf", 16) # Slightly smaller for fit
 font_small = ImageFont.truetype("/usr/share/fonts/dejavu/DejaVuSans.ttf", 12)
except IOError:
 font_large = ImageFont.load_default()
 font_small = ImageFont.load_default()

# Draw content (adjusted positions for better fit)
draw.text((5, 5), today.strftime("%Y-%m-%d"), font=font_large, fill=0)
draw.text((5, 25), f"Phase: {phase_desc}", font=font_small, fill=0)
draw.text((5, 40), f"Illum: {illum_pct}%", font=font_small, fill=0)
draw.text((5, 55), f"Rise: {rise_str}", font=font_small, fill=0)
draw.text((5, 70), f"Set: {set_str}", font=font_small, fill=0)

# Draw the moon shape (adjusted position)
draw_moon_phase(draw, 190, 80, 30, phase_deg) # Larger radius, shifted left for balance

# Simulate display: Save as PNG
image.save("lunar_output.png")
# Uncomment for popup: image.show()

print(f"Lunar info for {today} in {location.name}: {phase_desc} ({illum_pct}% illum, phase: {phase_deg:.1f}°, {phase_days:.2f} days)")
print(f"Moon rise: {rise_str}, set: {set_str}")
print("Output saved as lunar_output.png")