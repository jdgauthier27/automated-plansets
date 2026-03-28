"""
Google Solar API Pipeline — Task 1.2
=====================================
Fetches building insights and data layers from the Google Solar API,
downloads aerial imagery and building masks, extracts building footprints,
and populates a SolarDesign dataclass with panels, roof segments, and
projected coordinates.

Functions:
    fetch_building_insights   — buildingInsights:findClosest
    fetch_data_layers         — dataLayers:get
    download_aerial_image     — download RGB GeoTIFF
    download_building_mask    — download mask GeoTIFF
    extract_building_footprint — contour extraction from mask
    parse_building_insights   — the KEY function: API response → SolarDesign
"""

from __future__ import annotations

import logging
import math
import time
from collections import defaultdict
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np
import rasterio
import requests
from pyproj import Transformer
from shapely.geometry import MultiPoint, Polygon

from engine.exceptions import (
    AddressNotSupportedError,
    InsufficientCoverageError,
    SolarAPIError,
)
from engine.models.solar_design import (
    EquipmentSpec,
    PanelPlacement,
    RoofSegment,
    SolarDesign,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_BUILDING_INSIGHTS_URL = (
    "https://solar.googleapis.com/v1/buildingInsights:findClosest"
)
_DATA_LAYERS_URL = "https://solar.googleapis.com/v1/dataLayers:get"

# Google Solar API internally assumes ~400W panels with these dimensions (meters)
_GOOGLE_DEFAULT_PANEL_WIDTH_M = 1.045  # ~41.1"
_GOOGLE_DEFAULT_PANEL_HEIGHT_M = 1.879  # ~74.0"

# Retry configuration for rate limiting
_MAX_RETRIES = 3
_RETRY_BACKOFF_SECONDS = 2.0


# ---------------------------------------------------------------------------
# 1. fetch_building_insights
# ---------------------------------------------------------------------------


def fetch_building_insights(lat: float, lng: float, api_key: str) -> dict:
    """Fetch building insights from the Google Solar API.

    Calls ``buildingInsights:findClosest`` with HIGH quality requirement.

    Args:
        lat: Latitude of the building.
        lng: Longitude of the building.
        api_key: Google Cloud API key with Solar API enabled.

    Returns:
        Raw JSON response dict from the API.

    Raises:
        AddressNotSupportedError: When the API returns NOT_FOUND (no data
            for this location).
        SolarAPIError: For rate limiting, auth failures, or other API errors.
    """
    params = {
        "location.latitude": lat,
        "location.longitude": lng,
        "requiredQuality": "HIGH",
        "key": api_key,
    }

    response = _request_with_retry("GET", _BUILDING_INSIGHTS_URL, params=params)

    if response.status_code == 404:
        # Check for NOT_FOUND in the response body
        try:
            body = response.json()
            error_status = body.get("error", {}).get("status", "")
        except (ValueError, KeyError):
            error_status = ""
        if error_status == "NOT_FOUND" or response.status_code == 404:
            raise AddressNotSupportedError(lat, lng)

    if response.status_code != 200:
        _raise_api_error(response)

    return response.json()


# ---------------------------------------------------------------------------
# 2. fetch_data_layers
# ---------------------------------------------------------------------------


def fetch_data_layers(
    lat: float,
    lng: float,
    api_key: str,
    radius_meters: float = 50,
) -> dict:
    """Fetch data layer URLs from the Google Solar API.

    Calls ``dataLayers:get`` with FULL_LAYERS view. The returned dict
    contains URLs for RGB imagery, mask, DSM, annual flux, and monthly flux
    that can be downloaded separately.

    Args:
        lat: Latitude of the building.
        lng: Longitude of the building.
        api_key: Google Cloud API key.
        radius_meters: Radius around the location to fetch (default 50m).

    Returns:
        Dict with keys: ``rgbUrl``, ``maskUrl``, ``dsmUrl``,
        ``annualFluxUrl``, ``monthlyFluxUrl``, etc.

    Raises:
        AddressNotSupportedError: When the API returns NOT_FOUND.
        SolarAPIError: For other API errors.
    """
    params = {
        "location.latitude": lat,
        "location.longitude": lng,
        "radiusMeters": radius_meters,
        "view": "FULL_LAYERS",
        "key": api_key,
    }

    response = _request_with_retry("GET", _DATA_LAYERS_URL, params=params)

    if response.status_code == 404:
        raise AddressNotSupportedError(lat, lng)
    if response.status_code != 200:
        _raise_api_error(response)

    return response.json()


# ---------------------------------------------------------------------------
# 3. download_aerial_image
# ---------------------------------------------------------------------------


def download_aerial_image(url: str, api_key: str, output_path: str) -> str:
    """Download the RGB aerial image GeoTIFF from a dataLayers URL.

    Args:
        url: The ``rgbUrl`` from :func:`fetch_data_layers`.
        api_key: Google Cloud API key (appended as query param).
        output_path: Local file path to save the image.

    Returns:
        The output file path.

    Raises:
        SolarAPIError: On download failure.
    """
    return _download_geotiff(url, api_key, output_path)


# ---------------------------------------------------------------------------
# 4. download_building_mask
# ---------------------------------------------------------------------------


def download_building_mask(url: str, api_key: str, output_path: str) -> str:
    """Download the building mask GeoTIFF from a dataLayers URL.

    Args:
        url: The ``maskUrl`` from :func:`fetch_data_layers`.
        api_key: Google Cloud API key.
        output_path: Local file path to save the mask.

    Returns:
        The output file path.

    Raises:
        SolarAPIError: On download failure.
    """
    return _download_geotiff(url, api_key, output_path)


# ---------------------------------------------------------------------------
# 5. extract_building_footprint
# ---------------------------------------------------------------------------


def extract_building_footprint(mask_path: str) -> List[Tuple[float, float]]:
    """Extract the building footprint polygon from a mask GeoTIFF.

    Loads the mask, converts to binary, finds the largest contour using
    OpenCV, simplifies it with Douglas-Peucker, and converts pixel
    coordinates back to lat/lng using the GeoTIFF's affine transform.

    Args:
        mask_path: Path to the building mask GeoTIFF file.

    Returns:
        List of (lat, lng) coordinate pairs forming the building footprint
        polygon. Empty list if no contour is found.
    """
    with rasterio.open(mask_path) as src:
        mask_data = src.read(1)
        transform = src.transform
        crs = src.crs

    # Convert to binary mask (any non-zero value = building)
    binary = (mask_data > 0).astype(np.uint8) * 255

    # Find contours
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        logger.warning("No contours found in mask %s", mask_path)
        return []

    # Take the largest contour (by area) — this is the building
    largest = max(contours, key=cv2.contourArea)

    # Simplify with Douglas-Peucker
    perimeter = cv2.arcLength(largest, closed=True)
    epsilon = 0.01 * perimeter
    simplified = cv2.approxPolyDP(largest, epsilon, closed=True)

    # Convert pixel coordinates → CRS coordinates via the affine transform
    coords_crs = []
    for pt in simplified:
        col, row = pt[0]
        x, y = rasterio.transform.xy(transform, row, col)
        coords_crs.append((x, y))

    # If CRS is not EPSG:4326, transform to lat/lng
    if crs and not crs.is_geographic:
        transformer = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
        footprint = []
        for x, y in coords_crs:
            lng, lat = transformer.transform(x, y)
            footprint.append((lat, lng))
    else:
        # CRS is already geographic — coords are (lng, lat) from rasterio
        footprint = [(y, x) for x, y in coords_crs]

    return footprint


# ---------------------------------------------------------------------------
# 6. parse_building_insights  — the KEY function
# ---------------------------------------------------------------------------


def parse_building_insights(
    response: dict,
    equipment: EquipmentSpec,
    max_panels: Optional[int] = None,
) -> SolarDesign:
    """Parse a buildingInsights response into a fully populated SolarDesign.

    This is the primary entry point for converting raw Google Solar API data
    into the canonical data model. Steps:

    a. Extract lat/lng from center
    b. Parse roofSegmentStats → RoofSegment objects
    c. Parse solarPanels → PanelPlacement objects (sorted by energy desc, capped)
    d. Project lat/lng to local UTM coordinates (meters)
    e. Compute roof face polygons via convex hull of panel corners
    f. Scale panel rectangles to actual module dimensions
    g. Assign panel orientation
    h. Populate dc_kw, annual_kwh

    Args:
        response: Raw JSON dict from ``buildingInsights:findClosest``.
        equipment: Equipment specifications (module wattage, dimensions, etc.).
        max_panels: Maximum number of panels to place. If None, uses all
            panels returned by the API.

    Returns:
        Fully populated SolarDesign with panels, roof segments, and
        projected coordinates.

    Raises:
        InsufficientCoverageError: If fewer panels are available than
            ``max_panels``.
    """
    if not response:
        return SolarDesign(equipment=equipment)

    # ── a. Extract center coordinates ─────────────────────────────────────
    center = response.get("center", {})
    building_lat = center.get("latitude", 0.0)
    building_lng = center.get("longitude", 0.0)

    solar_potential = response.get("solarPotential", {})

    # ── b. Parse roof segments ────────────────────────────────────────────
    roof_segments = []
    for idx, seg in enumerate(solar_potential.get("roofSegmentStats", [])):
        stats = seg.get("stats", {})
        roof_segments.append(
            RoofSegment(
                segment_id=idx,
                pitch_degrees=seg.get("pitchDegrees", 0.0),
                azimuth_degrees=seg.get("azimuthDegrees", 0.0),
                area_sq_meters=stats.get("areaMeters2", 0.0),
            )
        )

    # ── c. Parse and select panels ────────────────────────────────────────
    raw_panels = []
    for i, sp in enumerate(solar_potential.get("solarPanels", [])):
        panel_center = sp.get("center", {})
        orientation_raw = sp.get("orientation", "PORTRAIT")
        raw_panels.append(
            PanelPlacement(
                panel_id=i,
                lat=panel_center.get("latitude", 0.0),
                lng=panel_center.get("longitude", 0.0),
                segment_id=sp.get("segmentIndex", 0),
                orientation="landscape" if orientation_raw == "LANDSCAPE" else "portrait",
                yearly_energy_kwh=sp.get("yearlyEnergyDcKwh", 0.0),
            )
        )

    # Sort by energy descending — take the best panels
    raw_panels.sort(key=lambda p: p.yearly_energy_kwh, reverse=True)

    if max_panels is not None:
        if len(raw_panels) < max_panels:
            raise InsufficientCoverageError(
                available=len(raw_panels), required=max_panels
            )
        panels = raw_panels[:max_panels]
    else:
        panels = raw_panels

    # Re-assign sequential IDs after filtering
    for idx, panel in enumerate(panels):
        panel.panel_id = idx

    # ── d. Coordinate projection: lat/lng → local UTM (meters) ───────────
    if panels:
        _project_to_local_coords(panels, building_lat, building_lng)

    # ── e. Compute roof face polygons via convex hull ─────────────────────
    module_w_m, module_h_m = _get_module_dimensions_meters(equipment)
    _compute_roof_polygons(panels, roof_segments, module_w_m, module_h_m)

    # ── f–g. Scale and orientation are already captured ───────────────────
    # Panel centers from Google are accurate regardless of module size.
    # The minor offset from 400W default vs actual module is <2% and
    # acceptable. Orientation is already set from the API response.

    # ── h. Populate system totals ─────────────────────────────────────────
    wattage = equipment.module.wattage if equipment.module.wattage > 0 else 395
    dc_kw = round(len(panels) * wattage / 1000, 2)
    annual_kwh = round(sum(p.yearly_energy_kwh for p in panels), 1)

    design = SolarDesign(
        lat=building_lat,
        lng=building_lng,
        address=response.get("name", ""),
        roof_segments=roof_segments,
        panels=panels,
        equipment=equipment,
        annual_kwh=annual_kwh,
        production_source="Google Solar API",
    )

    # Populate basic electrical summary (full electrical calc is Task 1.3)
    design.electrical.dc_kw = dc_kw
    design.electrical.total_panels = len(panels)

    return design


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _request_with_retry(
    method: str,
    url: str,
    params: dict | None = None,
    **kwargs,
) -> requests.Response:
    """Make an HTTP request with retry logic for rate limiting (429)."""
    for attempt in range(_MAX_RETRIES):
        response = requests.request(method, url, params=params, timeout=30, **kwargs)

        if response.status_code == 429:
            wait = _RETRY_BACKOFF_SECONDS * (2**attempt)
            logger.warning(
                "Rate limited (429), retrying in %.1fs (attempt %d/%d)",
                wait,
                attempt + 1,
                _MAX_RETRIES,
            )
            time.sleep(wait)
            continue

        return response

    # Exhausted retries — return the last 429 response so caller can handle
    return response  # type: ignore[possibly-undefined]


def _raise_api_error(response: requests.Response) -> None:
    """Raise a SolarAPIError from a non-200 API response."""
    try:
        body = response.json()
        message = body.get("error", {}).get("message", response.text)
    except (ValueError, KeyError):
        message = response.text

    raise SolarAPIError(
        f"Google Solar API error ({response.status_code}): {message}",
        status_code=response.status_code,
    )


def _download_geotiff(url: str, api_key: str, output_path: str) -> str:
    """Download a GeoTIFF file from a Google Solar API data layer URL."""
    separator = "&" if "?" in url else "?"
    full_url = f"{url}{separator}key={api_key}"

    response = _request_with_retry("GET", full_url)

    if response.status_code != 200:
        raise SolarAPIError(
            f"Failed to download GeoTIFF from {url}: HTTP {response.status_code}",
            status_code=response.status_code,
        )

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(response.content)

    return output_path


def _get_utm_zone(lng: float) -> int:
    """Determine the UTM zone number for a given longitude."""
    return int((lng + 180) / 6) + 1


def _get_utm_epsg(lat: float, lng: float) -> int:
    """Get the EPSG code for the UTM zone covering the given lat/lng.

    Northern hemisphere uses EPSG 326xx, southern uses 327xx.
    """
    zone = _get_utm_zone(lng)
    if lat >= 0:
        return 32600 + zone
    else:
        return 32700 + zone


def _project_to_local_coords(
    panels: List[PanelPlacement],
    center_lat: float,
    center_lng: float,
) -> None:
    """Project panel lat/lng positions to local flat coordinates (meters).

    Uses pyproj to transform from WGS84 (EPSG:4326) to the appropriate
    UTM zone, then offsets so the building center is at (0, 0).
    """
    utm_epsg = _get_utm_epsg(center_lat, center_lng)
    transformer = Transformer.from_crs("EPSG:4326", f"EPSG:{utm_epsg}", always_xy=True)

    # Project building center
    center_x, center_y = transformer.transform(center_lng, center_lat)

    # Project each panel and store as offset from center
    for panel in panels:
        px, py = transformer.transform(panel.lng, panel.lat)
        panel.local_x = round(px - center_x, 4)
        panel.local_y = round(py - center_y, 4)


def _get_module_dimensions_meters(equipment: EquipmentSpec) -> Tuple[float, float]:
    """Get module width and height in meters from equipment spec.

    Falls back to Google's default 400W panel dimensions if not specified.

    Returns:
        (width_meters, height_meters) — width is the shorter dimension.
    """
    if equipment.module.width_inches > 0 and equipment.module.height_inches > 0:
        w_m = equipment.module.width_inches * 0.0254
        h_m = equipment.module.height_inches * 0.0254
        return (w_m, h_m)
    return (_GOOGLE_DEFAULT_PANEL_WIDTH_M, _GOOGLE_DEFAULT_PANEL_HEIGHT_M)


def _compute_roof_polygons(
    panels: List[PanelPlacement],
    roof_segments: List[RoofSegment],
    module_width_m: float,
    module_height_m: float,
) -> None:
    """Compute convex hull polygons for each roof segment from panel corners.

    Groups panels by segment_id, computes all four corners of each panel
    (using local_x/local_y center + module dimensions + orientation),
    then builds a convex hull per segment and buffers by 0.5m.

    The resulting polygon is stored in the RoofSegment's ``polygon`` field
    as a list of (x, y) tuples in local coordinates (meters from center).
    """
    # Group panels by segment
    segment_panels: dict[int, list[PanelPlacement]] = defaultdict(list)
    for panel in panels:
        segment_panels[panel.segment_id].append(panel)

    # Build a lookup for roof segments by ID
    segment_map = {seg.segment_id: seg for seg in roof_segments}

    for seg_id, seg_panels in segment_panels.items():
        all_corners = []
        for panel in seg_panels:
            corners = _panel_corners(
                panel.local_x,
                panel.local_y,
                module_width_m,
                module_height_m,
                panel.orientation,
            )
            all_corners.extend(corners)

        if len(all_corners) < 3:
            continue

        # Convex hull
        hull = MultiPoint(all_corners).convex_hull

        # Buffer by 0.5m
        buffered = hull.buffer(0.5)

        # Store as list of (x, y) tuples
        if isinstance(buffered, Polygon):
            coords = list(buffered.exterior.coords)
        else:
            # Fallback for degenerate geometry
            coords = list(hull.convex_hull.exterior.coords) if hasattr(hull, "exterior") else []

        if seg_id in segment_map:
            segment_map[seg_id].polygon = [(round(x, 3), round(y, 3)) for x, y in coords]


def _panel_corners(
    cx: float,
    cy: float,
    module_width_m: float,
    module_height_m: float,
    orientation: str,
) -> List[Tuple[float, float]]:
    """Compute the four corners of a panel from its center.

    In portrait orientation, the shorter side (width) runs east-west.
    In landscape, the shorter side runs north-south.

    Returns:
        List of 4 (x, y) corner coordinates.
    """
    if orientation == "landscape":
        half_w = module_height_m / 2  # longer side is horizontal
        half_h = module_width_m / 2
    else:
        half_w = module_width_m / 2
        half_h = module_height_m / 2

    return [
        (cx - half_w, cy - half_h),
        (cx + half_w, cy - half_h),
        (cx + half_w, cy + half_h),
        (cx - half_w, cy + half_h),
    ]
