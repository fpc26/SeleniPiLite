import argparse
import contextlib
import datetime
import io
import math
import os
import sys
import threading
import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont
from skyfield import almanac
from skyfield.api import load, wgs84
from zoneinfo import ZoneInfo

# Optional: Test with specific date (set to None for current date)
TEST_DATE: Optional[datetime.date] = None  # e.g., datetime.date(2025, 9, 21)

DEFAULT_LATITUDE = 40.7128
DEFAULT_LONGITUDE = -74.0060
DEFAULT_TZ = "America/New_York"
DEFAULT_LOCATION_NAME = "New York City, NY"

BUTTON_POWER = "power"
BUTTON_PREV = "prev"
BUTTON_NEXT = "next"

TOUCH_MAP_CHOICES = {
    "auto",
    "default",
    "swap",
    "swap_invert_x",
    "swap_invert_y",
    "swap_invert_xy",
    "transpose",
    "transpose_invert_x",
    "transpose_invert_y",
    "transpose_invert_xy",
}


@dataclass
class TouchSample:
    pressed: bool
    x: Optional[int]
    y: Optional[int]


class AutoClearScheduler:
    """Schedule deferred panel clears so that ghosting is avoided."""

    def __init__(self) -> None:
        self._timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()
        self._triggered = False
        self._on_complete = None

    def schedule(self, backend, delay: int, sleep_after: bool, on_complete=None) -> None:
        """Schedule a deferred clear. Existing schedules are cancelled."""
        with self._lock:
            self._cancel_locked()
            self._triggered = False
            self._on_complete = on_complete
            if delay <= 0:
                self._run_clear(backend, sleep_after)
                return
            self._timer = threading.Timer(delay, self._timer_entry, args=(backend, sleep_after))
            self._timer.daemon = True
            self._timer.start()
        minutes = delay / 60.0
        print(
            f"Auto-clear scheduled: clearing the panel in {minutes:.1f} minute(s)."
            " Press Ctrl+C to clear immediately."
        )

    def _timer_entry(self, backend, sleep_after: bool) -> None:
        self._run_clear(backend, sleep_after)

    def _run_clear(self, backend, sleep_after: bool) -> None:
        try:
            try:
                backend.clear()
            except Exception as err:  # pragma: no cover - hardware dependent
                print(f"[WARN] Auto-clear failed: {err}")
            finally:
                backend.shutdown(sleep=sleep_after)
        finally:
            if self._on_complete:
                try:
                    self._on_complete()
                except Exception:
                    pass
            with self._lock:
                self._timer = None
                self._triggered = True
        print("EPD cleared and backend shut down.")

    def triggered(self) -> bool:
        with self._lock:
            return self._triggered

    def cancel(self) -> None:
        with self._lock:
            self._cancel_locked()

    def _cancel_locked(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
        self._timer = None
        self._triggered = False
        self._on_complete = None

    def wait(self) -> None:
        timer = None
        with self._lock:
            timer = self._timer
        if timer is not None:
            timer.join()

    def clear_now(self, backend, sleep_after: bool) -> None:
        self.cancel()
        self._run_clear(backend, sleep_after)


def load_ephemeris():
    """Load Skyfield timescale and ephemeris with local cache support."""
    ts = load.timescale()
    eph_path = os.environ.get("SKYFIELD_EPH")
    if eph_path and os.path.exists(eph_path):
        return ts, load(eph_path)

    local_eph = os.path.join(os.path.dirname(os.path.abspath(__file__)), "de421.bsp")
    if os.path.exists(local_eph):
        return ts, load(local_eph)

    try:
        return ts, load("de421.bsp")
    except Exception as exc:  # pragma: no cover - depends on network
        raise RuntimeError(
            "Skyfield ephemeris not found. Set SKYFIELD_EPH or place de421.bsp next to the script."
        ) from exc


def local_midnight_bounds(day: datetime.date, tz: ZoneInfo) -> tuple[datetime.datetime, datetime.datetime]:
    start = datetime.datetime(day.year, day.month, day.day, 0, 0, 0, tzinfo=tz)
    end = start + datetime.timedelta(days=1)
    return start, end


def moonrise_moonset_for_date(
    eph, ts, lat: float, lon: float, day: datetime.date, tz: ZoneInfo
):
    topos = wgs84.latlon(lat, lon)
    start_local, end_local = local_midnight_bounds(day, tz)
    t0 = ts.from_datetime(start_local.astimezone(datetime.timezone.utc))
    t1 = ts.from_datetime(end_local.astimezone(datetime.timezone.utc))

    f = almanac.risings_and_settings(eph, eph["Moon"], topos)
    t, y = almanac.find_discrete(t0, t1, f)

    rise_dt: Optional[datetime.datetime] = None
    set_dt: Optional[datetime.datetime] = None
    for ti, yi in zip(t, y):
        dt_utc = ti.utc_datetime().replace(tzinfo=datetime.timezone.utc)
        dt_local = dt_utc.astimezone(tz)
        if yi == 1 and rise_dt is None:
            rise_dt = dt_local
        elif yi == 0 and set_dt is None:
            set_dt = dt_local

    return rise_dt, set_dt


def phase_angle_deg(eph, ts, day: datetime.date, tz: ZoneInfo) -> float:
    noon_local = datetime.datetime(day.year, day.month, day.day, 12, 0, 0, tzinfo=tz)
    t = ts.from_datetime(noon_local.astimezone(datetime.timezone.utc))
    angle = almanac.moon_phase(eph, t)
    return angle.degrees % 360.0


def phase_description(deg: float) -> str:
    if (0 <= deg < 22.5) or (337.5 <= deg <= 360):
        return "New Moon"
    if 22.5 <= deg < 67.5:
        return "Waxing Crescent"
    if 67.5 <= deg < 112.5:
        return "First Quarter"
    if 112.5 <= deg < 157.5:
        return "Waxing Gibbous"
    if 157.5 <= deg < 202.5:
        return "Full Moon"
    if 202.5 <= deg < 247.5:
        return "Waning Gibbous"
    if 247.5 <= deg < 292.5:
        return "Last Quarter"
    return "Waning Crescent"


def draw_moon_phase(draw: ImageDraw.ImageDraw, center_x: int, center_y: int, radius: int, phase_deg: float) -> None:
    angle = math.radians(phase_deg)
    illuminated = (1 - math.cos(angle)) / 2
    offset = -2 * radius * illuminated if phase_deg < 180 else 2 * radius * illuminated

    bbox_moon = (center_x - radius, center_y - radius, center_x + radius, center_y + radius)
    draw.ellipse(bbox_moon, fill=0)

    shadow_cx = center_x + offset
    bbox_shadow = (shadow_cx - radius, center_y - radius, shadow_cx + radius, center_y + radius)
    draw.ellipse(bbox_shadow, fill=255)


def load_fonts() -> Tuple[ImageFont.ImageFont, ImageFont.ImageFont]:
    try:
        return (
            ImageFont.truetype("/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf", 16),
            ImageFont.truetype("/usr/share/fonts/dejavu/DejaVuSans.ttf", 12),
        )
    except IOError:
        default = ImageFont.load_default()
        return default, default


def compute_lunar_metrics(
    eph, ts, chosen_date: datetime.date, lat: float, lon: float, tz: ZoneInfo
) -> Dict[str, object]:
    phase_deg = phase_angle_deg(eph, ts, chosen_date, tz)
    illum_pct = round((1 - math.cos(math.radians(phase_deg))) / 2 * 100)
    phase_desc = phase_description(phase_deg)
    rise_dt, set_dt = moonrise_moonset_for_date(eph, ts, lat, lon, chosen_date, tz)
    rise_str = rise_dt.strftime("%H:%M") if rise_dt else "N/A"
    set_str = set_dt.strftime("%H:%M") if set_dt else "N/A"
    return {
        "date": chosen_date,
        "phase_deg": phase_deg,
        "illum_pct": illum_pct,
        "phase_desc": phase_desc,
        "rise": rise_str,
        "set": set_str,
    }


def build_lunar_image(
    metrics: Dict[str, object],
    _lat: float,
    _lon: float,
    _tz_display: str,
    location_name: str,
    include_touch_ui: bool,
    fonts: Tuple[ImageFont.ImageFont, ImageFont.ImageFont],
) -> Tuple[Image.Image, Dict[str, Tuple[int, int, int, int]]]:
    font_large, font_small = fonts
    image = Image.new("1", (250, 122), 255)
    draw = ImageDraw.Draw(image)

    padding = 5
    button_reserved = 32 if include_touch_ui else 0
    content_bottom = image.size[1] - button_reserved - padding

    date_text = metrics["date"].strftime("%Y-%m-%d")
    if location_name:
        headline = f"{date_text} – {location_name}"
    else:
        headline = date_text
    draw.text((padding, padding), headline, font=font_large, fill=0)
    headline_height = font_large.getbbox(headline)[3]
    y = padding + headline_height + 3

    line_height = font_small.getbbox("Ag")[3]
    line_spacing = line_height + 1

    info_lines = [
        f"Phase: {metrics['phase_desc']}",
        f"Illum: {metrics['illum_pct']}%",
        f"Rise: {metrics['rise']}",
        f"Set: {metrics['set']}",
    ]

    for line in info_lines:
        draw.text((padding, y), line, font=font_small, fill=0)
        y += line_spacing

    moon_radius = 26
    top_of_moon = y + 4
    center_y = min(top_of_moon + moon_radius, content_bottom - moon_radius)
    center_y = max(padding + moon_radius + 2, center_y)
    draw_moon_phase(draw, 190, center_y, moon_radius, float(metrics["phase_deg"]))

    buttons: Dict[str, Tuple[int, int, int, int]] = {}
    if include_touch_ui:
        buttons = draw_touch_buttons(draw, image.size, font_small)

    return image, buttons


def draw_touch_buttons(
    draw: ImageDraw.ImageDraw, image_size: Tuple[int, int], font: ImageFont.ImageFont
) -> Dict[str, Tuple[int, int, int, int]]:
    width, height = image_size
    padding = 4
    button_height = 28
    y0 = height - button_height - padding
    button_width = (width - padding * 4) // 3

    buttons: Dict[str, Tuple[int, int, int, int]] = {}
    specs = [
        (BUTTON_PREV, "Prev"),
        (BUTTON_NEXT, "Next"),
        (BUTTON_POWER, "Sleep"),
    ]

    for idx, (name, label) in enumerate(specs):
        x1 = padding + idx * (button_width + padding)
        x2 = x1 + button_width
        box = (x1, y0, x2, height - padding)
        draw.rectangle(box, outline=0, fill=255)
        text_bbox = font.getbbox(label)
        text_w = text_bbox[2] - text_bbox[0]
        text_h = text_bbox[3] - text_bbox[1]
        tx = x1 + (button_width - text_w) // 2
        ty = y0 + (button_height - text_h) // 2
        draw.text((tx, ty), label, font=font, fill=0)
        buttons[name] = box

    return buttons


def render_processing_screen(
    backend,
    fonts: Tuple[ImageFont.ImageFont, ImageFont.ImageFont],
    headline: str = "Updating",
    body: str = "Fetching lunar data...",
) -> None:
    font_large, font_small = fonts
    image = Image.new("1", (250, 122), 255)
    draw = ImageDraw.Draw(image)

    draw.rectangle((5, 5, 245, 117), outline=0, width=1)
    w = font_large.getlength(headline)
    draw.text(((250 - w) / 2, 22), headline, font=font_large, fill=0)
    w_body = font_small.getlength(body)
    draw.text(((250 - w_body) / 2, 48), body, font=font_small, fill=0)

    # Simple hourglass icon
    cx, cy = 125, 80
    size = 26
    draw.polygon([
        (cx - size // 2, cy - size // 2),
        (cx + size // 2, cy - size // 2),
        (cx, cy),
    ], outline=0, fill=0)
    draw.polygon([
        (cx - size // 2, cy + size // 2),
        (cx + size // 2, cy + size // 2),
        (cx, cy),
    ], outline=0, fill=0)
    draw.line((cx - size // 2, cy - size // 2, cx - size // 2, cy + size // 2), fill=0)
    draw.line((cx + size // 2, cy - size // 2, cx + size // 2, cy + size // 2), fill=0)
    draw.rectangle((cx - 5, cy - 1, cx + 5, cy + 1), fill=255)
    draw.rectangle((cx - 2, cy - size // 2 + 3, cx + 2, cy - 2), fill=255)
    draw.rectangle((cx - 2, cy + 2, cx + 2, cy + size // 2 - 3), fill=255)
    backend.render(image)


def transform_touch_point(
    x_touch: int,
    y_touch: int,
    image_size: Tuple[int, int],
    backend,
    mapping: str,
    rotate: int,
) -> Optional[Tuple[int, int]]:
    if rotate % 360 != 0:
        return None

    epd = getattr(backend, "_epd", None)
    hw_width = max(1, getattr(epd, "width", image_size[1]) if epd else image_size[1])
    hw_height = max(1, getattr(epd, "height", image_size[0]) if epd else image_size[0])

    norm_x = max(0.0, min(1.0, x_touch / (hw_width - 1)))
    norm_y = max(0.0, min(1.0, y_touch / (hw_height - 1)))

    mapping = (mapping or "default").lower()
    if mapping == "default":
        img_x_ratio = norm_y
        img_y_ratio = 1.0 - norm_x
    elif mapping == "swap":
        img_x_ratio = norm_x
        img_y_ratio = norm_y
    elif mapping == "swap_invert_x":
        img_x_ratio = 1.0 - norm_x
        img_y_ratio = norm_y
    elif mapping == "swap_invert_y":
        img_x_ratio = norm_x
        img_y_ratio = 1.0 - norm_y
    elif mapping == "swap_invert_xy":
        img_x_ratio = 1.0 - norm_x
        img_y_ratio = 1.0 - norm_y
    elif mapping == "transpose":
        img_x_ratio = norm_y
        img_y_ratio = norm_x
    elif mapping == "transpose_invert_x":
        img_x_ratio = 1.0 - norm_y
        img_y_ratio = norm_x
    elif mapping == "transpose_invert_y":
        img_x_ratio = norm_y
        img_y_ratio = 1.0 - norm_x
    elif mapping == "transpose_invert_xy":
        img_x_ratio = 1.0 - norm_y
        img_y_ratio = 1.0 - norm_x
    else:
        img_x_ratio = norm_y
        img_y_ratio = 1.0 - norm_x

    width, height = image_size
    px = int(round(img_x_ratio * (width - 1)))
    py = int(round(img_y_ratio * (height - 1)))
    return px, py


def detect_button(point: Tuple[int, int], buttons: Dict[str, Tuple[int, int, int, int]]) -> Optional[str]:
    x, y = point
    for name, (x1, y1, x2, y2) in buttons.items():
        if x1 <= x <= x2 and y1 <= y <= y2:
            return name
    return None


def resolve_touch_mapping(
    requested: str,
    backend,
    image_size: Tuple[int, int],
) -> Tuple[str, Optional[str]]:
    mapping = (requested or "auto").lower()
    if mapping != "auto":
        return mapping, None

    epd = getattr(backend, "_epd", None)
    hw_width = max(1, getattr(epd, "width", image_size[1]) if epd else image_size[1])
    hw_height = max(1, getattr(epd, "height", image_size[0]) if epd else image_size[0])

    # Typical 2.13" touch panel reports width ~= 122, height ~= 250.
    if hw_width <= image_size[1] and hw_height >= image_size[0]:
        return (
            "transpose_invert_x",
            "Auto touch-map selected 'transpose_invert_x' (swap axes, invert horizontal) based on panel geometry.",
        )
    if hw_height > image_size[1] and hw_width <= image_size[0]:
        return "swap", "Auto touch-map selected 'swap' based on panel geometry."
    if hw_width > image_size[0] and hw_height <= image_size[1]:
        return "default", "Auto touch-map selected 'default' based on panel geometry."

    return (
        "transpose_invert_x",
        "Auto touch-map could not infer orientation cleanly; defaulting to 'transpose_invert_x'. "
        "Use --touch-map to override if button zones still feel offset.",
    )


def wait_for_touch_release(touch, poll_interval: float, scheduler: AutoClearScheduler) -> None:
    while not scheduler.triggered():
        sample = touch.sample()
        if not sample.pressed:
            return
        time.sleep(poll_interval)


class TouchController:
    def __init__(self) -> None:
        try:
            from TP_lib import gt1151  # type: ignore
        except ImportError as err:
            raise ImportError(
                "Touch drivers not found. Clone waveshare/Touch_e-Paper_HAT and add its python/lib to PYTHONPATH."
            ) from err

        self._gt1151 = gt1151
        self.gt = gt1151.GT1151()
        self.dev = gt1151.GT_Development()
        self.prev = gt1151.GT_Development()

        # Reset the touch controller and attempt to read firmware information.
        try:
            self.gt.GT_Reset()
            version_bytes = self.gt.GT_Read(0x8140, 4)
        except Exception as err:  # pragma: no cover - hardware dependent
            raise RuntimeError(f"Failed to initialise GT1151 touch controller: {err}") from err

        if version_bytes:
            readable = "".join(chr(b) for b in version_bytes if 32 <= b <= 126)
            if readable:
                print(f"Touch controller ready (GT1151 firmware: {readable})")

    def sample(self) -> TouchSample:
        try:
            pressed = self.gt.digital_read(self.gt.INT) == 0
            if pressed:
                self.dev.Touch = 1
                with contextlib.redirect_stdout(io.StringIO()):
                    self.gt.GT_Scan(self.dev, self.prev)
                if getattr(self.dev, "TouchCount", 0) > 0:
                    return TouchSample(True, self.dev.X[0], self.dev.Y[0])
            else:
                self.dev.Touch = 0
                with contextlib.redirect_stdout(io.StringIO()):
                    self.gt.GT_Scan(self.dev, self.prev)
        except Exception as err:
            raise RuntimeError(f"Touch controller read failed: {err}") from err
        return TouchSample(False, None, None)

    def close(self) -> None:
        return


def resolve_location(args: argparse.Namespace) -> Tuple[float, float, ZoneInfo, str, str, str]:
    env_lat = os.environ.get("LUNAR_LAT")
    env_lon = os.environ.get("LUNAR_LON")
    env_tz = os.environ.get("LUNAR_TZ")
    env_loc = os.environ.get("LUNAR_LOCATION_NAME")

    if any(value is not None for value in (args.lat, args.lon, args.timezone, args.location_name)):
        source = "cli"
    elif any(value for value in (env_lat, env_lon, env_tz, env_loc)):
        source = "env"
    else:
        source = "default"

    lat_val = args.lat if args.lat is not None else (float(env_lat) if env_lat else DEFAULT_LATITUDE)
    lon_val = args.lon if args.lon is not None else (float(env_lon) if env_lon else DEFAULT_LONGITUDE)
    tz_name = args.timezone or env_tz or DEFAULT_TZ
    if args.location_name:
        location_name = args.location_name
    elif env_loc:
        location_name = env_loc
    elif source == "default":
        location_name = DEFAULT_LOCATION_NAME
    else:
        location_name = f"Lat {lat_val:.3f}, Lon {lon_val:.3f}"

    if not -90 <= lat_val <= 90:
        raise ValueError(f"Latitude {lat_val} out of range (-90 to 90).")
    if not -180 <= lon_val <= 180:
        raise ValueError(f"Longitude {lon_val} out of range (-180 to 180).")

    if args.lat is not None and args.lon is not None:
        if abs(lat_val) > 66 and abs(lon_val) < 66:
            print(
                "[WARN] Latitude and longitude inputs look swapped. If you intended a mid-latitude location, "
                "try exchanging the values (e.g., --lat 40.0942 --lon -75.9097)."
            )

    try:
        tz_obj = ZoneInfo(tz_name)
    except Exception as err:
        raise ValueError(
            f"Unknown timezone '{tz_name}'. See https://en.wikipedia.org/wiki/List_of_tz_database_time_zones"
        ) from err

    tz_display = getattr(tz_obj, "key", tz_name)
    return lat_val, lon_val, tz_obj, tz_display, location_name, source


def print_location_hint(source: str) -> None:
    if source == "default":
        print(
            "Using default location (New York City, NY). Provide --lat, --lon, and --timezone to customize. "
            "Try https://www.latlong.net/ and the IANA time zone list for reference."
        )


def print_summary(
    metrics: Dict[str, object], lat: float, lon: float, tz_display: str, location_name: str
) -> None:
    print(
        f"Lunar info for {metrics['date']} @ ({lat:.3f}, {lon:.3f}) [{tz_display}] {location_name}: "
        f"{metrics['phase_desc']} ({metrics['illum_pct']}% illum, phase: {metrics['phase_deg']:.1f}°)"
    )
    print(f"Moon rise: {metrics['rise']}, set: {metrics['set']}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lunar info renderer with pluggable display backend")
    parser.add_argument("--date", help="ISO date (YYYY-MM-DD) to render; default today", default=None)
    parser.add_argument("--backend", choices=["file", "epd"], default="file", help="Output backend")
    parser.add_argument("--output", "-o", default="lunar_output.png", help="Output PNG path when using file backend")
    parser.add_argument("--rotate", type=int, default=0, help="Rotate output clockwise in degrees (0/90/180/270)")
    parser.add_argument("--epd-model", default="2in13", help="Waveshare model, e.g., 2in13 (default), 7in5, 7in5b")
    parser.add_argument("--epd-variant", default="auto", help="Waveshare variant (model-specific). Non-touch: auto, V4, V3, V2, V1. Touch: TP_V4, TP_V3, TP_V2.")
    parser.add_argument("--epd-touch", action="store_true", help="Use Waveshare touch drivers (TP_lib) for 2.13\" panels")
    parser.add_argument("--epd-clear", action="store_true", help="Clear Waveshare display to white and exit")
    parser.add_argument("--no-sleep", action="store_true", help="Do not put the EPD to sleep after rendering")
    parser.add_argument("--epd-auto-clear-delay", type=int, default=600, help="Seconds to wait before automatically clearing the EPD and shutting down the driver. Use 0 to disable (default: 600 seconds / 10 minutes).")
    parser.add_argument("--epd-lib-path", default=None, help="Path to Waveshare e-Paper python lib (RaspberryPi_Jetson_Nano/python/lib). If set, this is added to sys.path and EPD_LIB_PATH is exported before loading the backend.")
    parser.add_argument("--lat", type=float, help="Latitude in decimal degrees (positive north)")
    parser.add_argument("--lon", type=float, help="Longitude in decimal degrees (positive east)")
    parser.add_argument("--timezone", help="IANA timezone name, e.g., America/New_York")
    parser.add_argument("--location-name", help="Friendly location name to print on screen")
    parser.add_argument("--power-hold-seconds", type=float, default=5.0, help="Seconds to hold the touch power button before clearing and exiting (touch mode)")
    parser.add_argument("--touch-poll-ms", type=int, default=80, help="Touch polling interval in milliseconds (touch mode)")
    parser.add_argument(
        "--touch-map",
        choices=sorted(TOUCH_MAP_CHOICES),
        default="auto",
        help="Touch coordinate mapping mode (auto attempts to select the correct orientation)",
    )

    args = parser.parse_args(argv)

    if args.epd_clear and args.backend != "epd":
        parser.error("--epd-clear requires --backend epd")
    if args.epd_auto_clear_delay < 0:
        parser.error("--epd-auto-clear-delay must be zero or a positive number of seconds")
    if args.power_hold_seconds <= 0:
        parser.error("--power-hold-seconds must be positive")
    if args.touch_poll_ms <= 0:
        parser.error("--touch-poll-ms must be positive")
    if args.epd_touch and args.rotate % 360 != 0:
        parser.error("--epd-touch currently requires --rotate 0 for touch mapping support")

    return args


def wait_for_touch_events(
    args: argparse.Namespace,
    touch: TouchController,
    backend,
    scheduler: AutoClearScheduler,
    buttons: Dict[str, Tuple[int, int, int, int]],
    image_size: Tuple[int, int],
    poll_interval: float,
    touch_map: str,
) -> str:
    power_hold_start: Optional[float] = None
    power_hold_count: int = 0
    last_button: Optional[str] = None
    try:
        while True:
            if scheduler.triggered():
                return "timeout"
            try:
                sample = touch.sample()
            except RuntimeError as err:
                print(f"[ERROR] Touch read failed: {err}")
                return "touch_error"
            if not sample.pressed:
                power_hold_start = None
                power_hold_count = 0
                last_button = None
                time.sleep(poll_interval)
                continue
            if sample.x is None or sample.y is None:
                time.sleep(poll_interval)
                continue
            point = transform_touch_point(sample.x, sample.y, image_size, backend, touch_map, args.rotate)
            if point is None:
                time.sleep(poll_interval)
                continue
            button = detect_button(point, buttons)
            if button is None:
                power_hold_start = None
                power_hold_count = 0
                last_button = None
                time.sleep(poll_interval)
                continue
            if button in (BUTTON_PREV, BUTTON_NEXT):
                if last_button == button:
                    time.sleep(poll_interval)
                    continue
                wait_for_touch_release(touch, poll_interval, scheduler)
                return button
            if button == BUTTON_POWER:
                threshold_count = max(1, int(round(args.power_hold_seconds / poll_interval)))
                effective_threshold = min(threshold_count, 10)
                if power_hold_start is None:
                    power_hold_start = time.time()
                    power_hold_count = 0
                    print(
                        f"Hold the power button zone for {args.power_hold_seconds:.1f}s to clear and exit."
                    )
                else:
                    power_hold_count += 1
                    if time.time() - power_hold_start >= args.power_hold_seconds:
                        return "power"
                    if power_hold_count >= effective_threshold:
                        return "power"
            last_button = button
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        return "interrupt"


def run_touch_session(
    args: argparse.Namespace,
    backend,
    scheduler: AutoClearScheduler,
    eph,
    ts,
    lat: float,
    lon: float,
    tz_obj: ZoneInfo,
    tz_display: str,
    location_name: str,
    fonts: Tuple[ImageFont.ImageFont, ImageFont.ImageFont],
    start_date: datetime.date,
) -> None:
    try:
        touch = TouchController()
    except ImportError as err:
        print(f"[ERROR] {err}")
        return
    except RuntimeError as err:
        print(f"[ERROR] Failed to initialise touch controller: {err}")
        return

    poll_interval = args.touch_poll_ms / 1000.0
    backend_state = {"active": True}
    resolved_touch_map: Optional[str] = None

    def mark_backend_inactive() -> None:
        backend_state["active"] = False

    current_date = start_date
    running = True

    try:
        while running:
            scheduler.cancel()
            if not backend_state["active"]:
                break

            metrics = compute_lunar_metrics(eph, ts, current_date, lat, lon, tz_obj)
            image, buttons = build_lunar_image(
                metrics,
                lat,
                lon,
                tz_display,
                location_name,
                include_touch_ui=True,
                fonts=fonts,
            )
            backend.render(image)
            print_summary(metrics, lat, lon, tz_display, location_name)

            if resolved_touch_map is None:
                resolved_touch_map, mapping_msg = resolve_touch_mapping(args.touch_map, backend, image.size)
                if mapping_msg:
                    print(mapping_msg)

            if args.epd_auto_clear_delay > 0:
                scheduler.schedule(
                    backend,
                    args.epd_auto_clear_delay,
                    sleep_after=not args.no_sleep,
                    on_complete=mark_backend_inactive,
                )
            else:
                print("Auto-clear disabled; remember to clear the panel before shutdown.")

            outcome = wait_for_touch_events(
                args,
                touch,
                backend,
                scheduler,
                buttons,
                image.size,
                poll_interval,
                resolved_touch_map,
            )

            if outcome == BUTTON_PREV:
                render_processing_screen(backend, fonts, headline="Loading", body="Previous day")
                current_date -= datetime.timedelta(days=1)
                continue
            if outcome == BUTTON_NEXT:
                render_processing_screen(backend, fonts, headline="Loading", body="Next day")
                current_date += datetime.timedelta(days=1)
                continue
            if outcome == "power":
                print("Power gesture recognised; clearing panel and shutting down.")
                scheduler.clear_now(backend, sleep_after=not args.no_sleep)
                break
            if outcome == "timeout":
                print("Auto-clear completed; exiting touch session.")
                break
            if outcome == "interrupt":
                print("Keyboard interrupt received; clearing panel now.")
                scheduler.clear_now(backend, sleep_after=not args.no_sleep)
                break
            if outcome == "touch_error":
                print("Touch controller error encountered; clearing panel for a safe exit.")
                scheduler.clear_now(backend, sleep_after=not args.no_sleep)
                break
            print(f"Unknown outcome '{outcome}', exiting.")
            break
    finally:
        scheduler.cancel()
        try:
            touch.close()
        except Exception:
            pass


def epd_render_once(
    backend,
    scheduler: AutoClearScheduler,
    metrics: Dict[str, object],
    lat: float,
    lon: float,
    tz_display: str,
    location_name: str,
    fonts: Tuple[ImageFont.ImageFont, ImageFont.ImageFont],
    args: argparse.Namespace,
) -> None:
    image, _buttons = build_lunar_image(
        metrics,
        lat,
        lon,
        tz_display,
        location_name,
        include_touch_ui=False,
        fonts=fonts,
    )
    backend.render(image)
    print_summary(metrics, lat, lon, tz_display, location_name)

    if args.epd_auto_clear_delay > 0:
        scheduler.schedule(backend, args.epd_auto_clear_delay, sleep_after=not args.no_sleep)
        try:
            while not scheduler.triggered():
                time.sleep(0.5)
        except KeyboardInterrupt:
            print("Keyboard interrupt received; clearing panel now.")
            scheduler.clear_now(backend, sleep_after=not args.no_sleep)
    else:
        print(
            "Auto-clear disabled. Press Ctrl+C when ready to clear and shut down the display."
        )
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            print("Clearing panel on request.")
            scheduler.clear_now(backend, sleep_after=not args.no_sleep)


def main(argv: Optional[list[str]] = None) -> None:
    args = parse_args(argv or sys.argv[1:])

    if args.epd_touch and args.epd_variant.lower() == "auto":
        args.epd_variant = "TP_V4"

    if args.epd_lib_path:
        os.environ["EPD_LIB_PATH"] = args.epd_lib_path
        if os.path.isdir(args.epd_lib_path) and args.epd_lib_path not in sys.path:
            sys.path.insert(0, args.epd_lib_path)

    from display_backend import FileBackend, WaveshareEPDBackend

    lat, lon, tz_obj, tz_display, location_name, location_source = resolve_location(args)
    print_location_hint(location_source)

    if args.date:
        try:
            chosen_date = datetime.datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError as err:
            raise SystemExit(f"Invalid date '{args.date}': {err}")
    else:
        chosen_date = TEST_DATE if TEST_DATE else datetime.date.today()

    ts, eph = load_ephemeris()
    fonts = load_fonts()

    metrics = compute_lunar_metrics(eph, ts, chosen_date, lat, lon, tz_obj)

    if args.backend == "file":
        image, _ = build_lunar_image(
            metrics,
            lat,
            lon,
            tz_display,
            location_name,
            include_touch_ui=False,
            fonts=fonts,
        )
        if args.rotate:
            image = image.rotate(-args.rotate, expand=True)
        file_backend = FileBackend(path=args.output)
        file_backend.render(image)
        print_summary(metrics, lat, lon, tz_display, location_name)
        print(f"Output saved as {args.output}")
        return

    touch_mode = args.epd_touch or args.epd_variant.upper().startswith("TP")
    render_sleep_after = not args.no_sleep
    if args.epd_touch:
        render_sleep_after = False
        if not args.no_sleep:
            print("Touch mode detected; keeping the display awake between updates.")
    try:
        backend = WaveshareEPDBackend(
            model=args.epd_model,
            variant=args.epd_variant,
            rotate=args.rotate,
            sleep_after=render_sleep_after,
            touch=touch_mode,
        )
    except Exception as err:
        print("[ERROR] Failed to initialize Waveshare EPD backend:")
        print(f"        {err}")
        print("\nHints:")
        print("- Run: python check_env.py")
        print("- If using the Waveshare repo, pass --epd-lib-path /path/to/e-Paper/RaspberryPi_Jetson_Nano/python/lib")
        print("- See README: Raspberry Pi setup (SPI enablement, Waveshare e-Paper repo)")
        raise SystemExit(2) from err

    if args.epd_clear:
        try:
            backend.clear()
        except Exception as err:
            print("[ERROR] Failed to clear EPD:")
            print(f"        {err}")
            raise SystemExit(4) from err
        backend.shutdown(sleep=not args.no_sleep)
        print("EPD cleared to white")
        return

    scheduler = AutoClearScheduler()

    if args.epd_touch:
        run_touch_session(
            args,
            backend,
            scheduler,
            eph,
            ts,
            lat,
            lon,
            tz_obj,
            tz_display,
            location_name,
            fonts,
            start_date=chosen_date,
        )
    else:
        epd_render_once(
            backend,
            scheduler,
            metrics,
            lat,
            lon,
            tz_display,
            location_name,
            fonts,
            args,
        )


if __name__ == "__main__":
    main()
