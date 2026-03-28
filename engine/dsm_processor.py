"""
DSM Processor
=============
Parses Digital Surface Model GeoTIFF from Google Solar API dataLayers endpoint.
Provides height lookups at specific lat/lng positions and detects roof features
(chimneys, skylights) from height anomalies.

Used to:
1. Place panels at correct roof elevation in 3D view
2. Detect obstructions on the roof
3. Auto-determine eave/ridge heights for planset drawings
"""

import io
import json
import logging
import math
import os
import ssl
import urllib.request
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE

# Cache DSM data per building to avoid re-fetching
_dsm_cache: Dict[str, "DSMData"] = {}


@dataclass
class DSMData:
    """Parsed DSM GeoTIFF data."""

    heights: np.ndarray  # 2D height grid (height × width)
    width: int
    height: int
    bounds: Tuple[float, float, float, float]  # (minLng, minLat, maxLng, maxLat)
    resolution_m: float  # meters per pixel

    def lat_lng_to_pixel(self, lat: float, lng: float) -> Tuple[int, int]:
        """Convert lat/lng to pixel coordinates in the height grid."""
        min_lng, min_lat, max_lng, max_lat = self.bounds
        if max_lng == min_lng or max_lat == min_lat:
            return 0, 0
        px = int((lng - min_lng) / (max_lng - min_lng) * self.width)
        py = int((max_lat - lat) / (max_lat - min_lat) * self.height)  # Y inverted
        px = max(0, min(self.width - 1, px))
        py = max(0, min(self.height - 1, py))
        return px, py

    def get_height(self, lat: float, lng: float) -> float:
        """Get elevation at a lat/lng position."""
        px, py = self.lat_lng_to_pixel(lat, lng)
        return float(self.heights[py, px])

    def get_heights_batch(self, positions: List[Tuple[float, float]]) -> List[float]:
        """Get heights for multiple (lat, lng) positions."""
        return [self.get_height(lat, lng) for lat, lng in positions]


@dataclass
class RoofFeature:
    """A detected roof feature (chimney, skylight, etc.)."""

    type: str  # "chimney", "skylight", "vent", "dormer"
    lat: float
    lng: float
    height_m: float  # absolute height
    height_above_roof_m: float  # height above surrounding roof plane
    radius_m: float  # approximate size


@dataclass
class DSMAnalysis:
    """Complete DSM analysis for a building."""

    eave_height_m: float = 0.0
    ridge_height_m: float = 0.0
    building_height_m: float = 0.0
    ground_elevation_m: float = 0.0
    roof_features: List[RoofFeature] = field(default_factory=list)
    panel_heights: Dict[int, float] = field(default_factory=dict)  # panel_index → height


def fetch_dsm(lat: float, lng: float, radius_m: float = 100) -> Optional[DSMData]:
    """Fetch and parse DSM GeoTIFF from Google Solar API.

    Args:
        lat, lng: Building center coordinates.
        radius_m: Radius around center to fetch (default 100m).

    Returns:
        DSMData with parsed height grid, or None if unavailable.
    """
    cache_key = f"{lat:.5f},{lng:.5f}"
    if cache_key in _dsm_cache:
        logger.info("DSM cache hit for %s", cache_key)
        return _dsm_cache[cache_key]

    api_key = os.environ.get("GOOGLE_SOLAR_API_KEY", "")
    if not api_key:
        logger.warning("No API key — cannot fetch DSM")
        return None

    # Step 1: Get data layer URLs
    layers_url = (
        f"https://solar.googleapis.com/v1/dataLayers:get"
        f"?location.latitude={lat}&location.longitude={lng}"
        f"&radiusMeters={radius_m}"
        f"&view=DSM_LAYER"
        f"&requiredQuality=MEDIUM"
        f"&pixelSizeMeters=0.5"
        f"&key={api_key}"
    )

    try:
        req = urllib.request.Request(layers_url)
        with urllib.request.urlopen(req, timeout=30, context=_ssl_ctx) as resp:
            layers = json.loads(resp.read().decode())
    except Exception as e:
        logger.error("Failed to fetch data layer URLs: %s", e)
        return None

    dsm_url = layers.get("dsmUrl", "")
    if not dsm_url:
        logger.warning("No DSM URL in data layers response")
        return None

    # Append API key if needed
    if "key=" not in dsm_url:
        dsm_url += f"&key={api_key}" if "?" in dsm_url else f"?key={api_key}"

    # Step 2: Download GeoTIFF
    try:
        req = urllib.request.Request(dsm_url)
        with urllib.request.urlopen(req, timeout=60, context=_ssl_ctx) as resp:
            tiff_bytes = resp.read()
        logger.info("DSM GeoTIFF downloaded: %d bytes", len(tiff_bytes))
    except Exception as e:
        logger.error("Failed to download DSM GeoTIFF: %s", e)
        return None

    # Step 3: Parse GeoTIFF
    try:
        import tifffile

        with io.BytesIO(tiff_bytes) as buf:
            tiff = tifffile.TiffFile(buf)
            page = tiff.pages[0]
            heights = page.asarray().astype(np.float32)

            # Extract geo bounds from GeoTIFF tags
            # ModelTiepointTag (33922) and ModelPixelScaleTag (33550)
            bounds = _extract_bounds(page, heights.shape)

        dsm = DSMData(
            heights=heights,
            width=heights.shape[1],
            height=heights.shape[0],
            bounds=bounds,
            resolution_m=0.5,
        )

        _dsm_cache[cache_key] = dsm
        logger.info("DSM parsed: %dx%d, bounds=%s", dsm.width, dsm.height, bounds)
        return dsm

    except Exception as e:
        logger.error("Failed to parse DSM GeoTIFF: %s", e)
        return None


def _extract_bounds(page, shape) -> Tuple[float, float, float, float]:
    """Extract geographic bounds from GeoTIFF tags.

    Google Solar API DSMs use UTM projection (e.g., EPSG:32618 for zone 18N).
    The ModelTransformationTag gives UTM coordinates which we convert to lat/lng.
    """
    tags = page.tags

    # Try ModelTransformationTag (34264) — used by Google Solar API
    if 34264 in tags:
        transform = tags[34264].value
        # transform = [scaleX, 0, 0, originX, 0, scaleY, 0, originY, ...]
        # scaleX = pixel width in meters, scaleY = -pixel height (negative = top-down)
        scale_x = transform[0]  # 0.5 meters/pixel
        origin_x = transform[3]  # UTM easting of top-left pixel
        scale_y = transform[5]  # -0.5 meters/pixel
        origin_y = transform[7]  # UTM northing of top-left pixel

        # Determine UTM zone from GeoKeys
        utm_zone = 18  # default
        if 34735 in tags:
            geokeys = tags[34735].value
            # Look for ProjectedCSTypeGeoKey (3072)
            for i in range(4, len(geokeys), 4):
                if geokeys[i] == 3072:
                    epsg = geokeys[i + 3]
                    # EPSG 326xx = UTM zone xx North
                    if 32600 < epsg < 32661:
                        utm_zone = epsg - 32600
                    break

        # Convert UTM corners to lat/lng
        min_x_utm = origin_x
        max_y_utm = origin_y
        max_x_utm = origin_x + scale_x * shape[1]
        min_y_utm = origin_y + scale_y * shape[0]  # scale_y is negative

        sw_lat, sw_lng = _utm_to_latlng(min_x_utm, min_y_utm, utm_zone)
        ne_lat, ne_lng = _utm_to_latlng(max_x_utm, max_y_utm, utm_zone)

        logger.info(
            "DSM bounds: UTM zone %d, origin=(%.0f, %.0f), lat=[%.6f, %.6f], lng=[%.6f, %.6f]",
            utm_zone,
            origin_x,
            origin_y,
            sw_lat,
            ne_lat,
            sw_lng,
            ne_lng,
        )

        return (sw_lng, sw_lat, ne_lng, ne_lat)

    # Try ModelTiepointTag + ModelPixelScaleTag (standard GeoTIFF)
    if 33922 in tags and 33550 in tags:
        tiepoint = tags[33922].value
        scale = tags[33550].value
        origin_lng = tiepoint[3]
        origin_lat = tiepoint[4]
        min_lng = origin_lng
        max_lat = origin_lat
        max_lng = origin_lng + scale[0] * shape[1]
        min_lat = origin_lat - scale[1] * shape[0]
        return (min_lng, min_lat, max_lng, max_lat)

    logger.warning("Could not extract bounds from GeoTIFF tags")
    return (0, 0, 0, 0)


def _utm_to_latlng(easting: float, northing: float, zone: int, northern: bool = True) -> Tuple[float, float]:
    """Convert UTM coordinates to WGS84 lat/lng.

    Simplified conversion (accurate to ~1m for most use cases).
    """
    # WGS84 ellipsoid parameters
    a = 6378137.0
    f = 1 / 298.257223563
    e = math.sqrt(2 * f - f * f)
    e_prime = e / math.sqrt(1 - e * e)

    k0 = 0.9996
    x = easting - 500000.0  # remove false easting
    y = northing if northern else northing - 10000000.0

    M = y / k0
    mu = M / (a * (1 - e * e / 4 - 3 * e**4 / 64 - 5 * e**6 / 256))

    e1 = (1 - math.sqrt(1 - e * e)) / (1 + math.sqrt(1 - e * e))
    phi1 = mu + (3 * e1 / 2 - 27 * e1**3 / 32) * math.sin(2 * mu)
    phi1 += (21 * e1**2 / 16 - 55 * e1**4 / 32) * math.sin(4 * mu)
    phi1 += (151 * e1**3 / 96) * math.sin(6 * mu)

    N1 = a / math.sqrt(1 - e * e * math.sin(phi1) ** 2)
    T1 = math.tan(phi1) ** 2
    C1 = e_prime**2 * math.cos(phi1) ** 2
    R1 = a * (1 - e * e) / (1 - e * e * math.sin(phi1) ** 2) ** 1.5
    D = x / (N1 * k0)

    lat = phi1 - (N1 * math.tan(phi1) / R1) * (
        D * D / 2
        - (5 + 3 * T1 + 10 * C1 - 4 * C1 * C1 - 9 * e_prime**2) * D**4 / 24
        + (61 + 90 * T1 + 298 * C1 + 45 * T1 * T1 - 252 * e_prime**2 - 3 * C1 * C1) * D**6 / 720
    )

    lng = (
        D
        - (1 + 2 * T1 + C1) * D**3 / 6
        + (5 - 2 * C1 + 28 * T1 - 3 * C1 * C1 + 8 * e_prime**2 + 24 * T1 * T1) * D**5 / 120
    ) / math.cos(phi1)

    lat_deg = math.degrees(lat)
    lng_deg = math.degrees(lng) + (zone * 6 - 183)

    return lat_deg, lng_deg


def analyze_building_dsm(
    dsm: DSMData,
    lat: float,
    lng: float,
    panel_positions: Optional[List[Tuple[float, float]]] = None,
) -> DSMAnalysis:
    """Analyze DSM data for a building to extract heights and features.

    Args:
        dsm: Parsed DSMData.
        lat, lng: Building center.
        panel_positions: List of (lat, lng) for panel center height lookups.

    Returns:
        DSMAnalysis with heights and detected features.
    """
    analysis = DSMAnalysis()

    # Sample heights around building center (approximate footprint)
    center_h = dsm.get_height(lat, lng)

    # Sample a grid around the center to find roof characteristics
    sample_radius_m = 15  # ~30m x 30m area
    deg_per_m_lat = 1.0 / 111319.5
    deg_per_m_lng = 1.0 / (111319.5 * math.cos(math.radians(lat)))

    roof_heights = []
    for dy in range(-10, 11, 2):
        for dx in range(-10, 11, 2):
            sample_lat = lat + dy * deg_per_m_lat
            sample_lng = lng + dx * deg_per_m_lng
            h = dsm.get_height(sample_lat, sample_lng)
            if h > 0:  # valid height
                roof_heights.append(h)

    if roof_heights:
        heights_arr = np.array(roof_heights)
        analysis.ground_elevation_m = float(np.percentile(heights_arr, 5))
        analysis.eave_height_m = float(np.percentile(heights_arr, 25))
        analysis.ridge_height_m = float(np.percentile(heights_arr, 95))
        analysis.building_height_m = analysis.ridge_height_m - analysis.ground_elevation_m

        # Detect chimney-like features (>1m above mean roof height)
        mean_roof = float(np.mean(heights_arr))
        std_roof = float(np.std(heights_arr))

        if std_roof > 0.5:  # significant height variation
            # Re-scan for anomalies
            for dy in range(-10, 11, 1):
                for dx in range(-10, 11, 1):
                    sample_lat = lat + dy * deg_per_m_lat
                    sample_lng = lng + dx * deg_per_m_lng
                    h = dsm.get_height(sample_lat, sample_lng)
                    if h > mean_roof + 2.5:  # >2.5m above mean roof = chimney/vent
                        feature = RoofFeature(
                            type="chimney",
                            lat=sample_lat,
                            lng=sample_lng,
                            height_m=h,
                            height_above_roof_m=h - mean_roof,
                            radius_m=0.5,
                        )
                        # Avoid duplicates (cluster nearby detections)
                        is_dup = any(
                            abs(f.lat - feature.lat) < 2 * deg_per_m_lat
                            and abs(f.lng - feature.lng) < 2 * deg_per_m_lng
                            for f in analysis.roof_features
                        )
                        if not is_dup:
                            analysis.roof_features.append(feature)

    # Get heights at panel positions
    if panel_positions:
        for i, (plat, plng) in enumerate(panel_positions):
            analysis.panel_heights[i] = dsm.get_height(plat, plng)

    logger.info(
        "DSM analysis: ground=%.1fm, eave=%.1fm, ridge=%.1fm, building=%.1fm, features=%d",
        analysis.ground_elevation_m,
        analysis.eave_height_m,
        analysis.ridge_height_m,
        analysis.building_height_m,
        len(analysis.roof_features),
    )

    return analysis
