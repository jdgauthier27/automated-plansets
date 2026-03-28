"""Shared geographic utilities used by site plan and other page builders.

Provides:
  - meters_per_pixel() — Mercator projection constant
  - latlng_to_pixel() — lat/lng to satellite pixel coordinate conversion
  - azimuth_label() — compass direction from azimuth degrees
"""

import math
from typing import Tuple


def meters_per_pixel(lat_deg: float, zoom: int = 20, scale: int = 2) -> float:
    """Compute meters-per-pixel for a Google Maps Static API image.

    Formula: 156543.03392 × cos(lat) / 2^zoom / scale
    At lat 45.46°, zoom 20, scale 2: ~0.05235 m/pixel
    """
    lat_rad = math.radians(lat_deg)
    return 156543.03392 * math.cos(lat_rad) / (2**zoom) / scale


def latlng_to_pixel(
    lat: float,
    lng: float,
    center_lat: float,
    center_lng: float,
    mpp: float,
    img_w: int = 1280,
    img_h: int = 960,
) -> Tuple[float, float]:
    """Convert a lat/lng to pixel coordinates on the satellite image.

    Uses equirectangular approximation (accurate at this scale).

    dx_meters = (lng - center_lng) × cos(center_lat) × 111319.5
    dy_meters = (lat - center_lat) × 111319.5
    pixel_x = img_w/2 + dx_meters / mpp
    pixel_y = img_h/2 - dy_meters / mpp  (Y inverted)
    """
    center_lat_rad = math.radians(center_lat)
    dx_meters = (lng - center_lng) * math.cos(center_lat_rad) * 111319.5
    dy_meters = (lat - center_lat) * 111319.5
    pixel_x = img_w / 2 + dx_meters / mpp
    pixel_y = img_h / 2 - dy_meters / mpp
    return pixel_x, pixel_y


def azimuth_label(az: float) -> str:
    """Convert azimuth degrees to compass direction."""
    dirs = [
        (0, "N"),
        (45, "NE"),
        (90, "E"),
        (135, "SE"),
        (180, "S"),
        (225, "SW"),
        (270, "W"),
        (315, "NW"),
        (360, "N"),
    ]
    for deg, lbl in dirs:
        if abs(az - deg) <= 22.5:
            return lbl
    return "S"
