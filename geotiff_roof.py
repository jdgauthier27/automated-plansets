"""
GeoTIFF Roof Geometry — Public Entry Point
==========================================
Thin adapter over engine/geotiff_roof.py that exposes the simple
GeoTiffRoofGeometry / get_roof_geometry_from_geotiff interface used by
panel_placer.py's use_geotiff=True path.

For the full DSM-segmented RoofFace API see engine.geotiff_roof.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public dataclass
# ---------------------------------------------------------------------------
@dataclass
class GeoTiffRoofGeometry:
    """Simplified roof geometry derived from the Google Solar mask GeoTIFF.

    Attributes:
        polygons:     List of polygon vertex lists.  Each polygon is a list of
                      (x_ft, y_ft) tuples relative to the building centroid.
        scale_factor: Page scale in pts/ft (same convention as solar_insight_to_roof_faces).
        roof_faces:   Full RoofFace list for passing directly to panel_placer.
    """
    polygons: List[List[Tuple[float, float]]]
    scale_factor: float
    roof_faces: list = field(default_factory=list)   # List[RoofFace]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def get_roof_geometry_from_geotiff(
    lat: float,
    lng: float,
    api_key: Optional[str] = None,
) -> GeoTiffRoofGeometry:
    """Download GeoTIFF layers and return roof geometry.

    Uses the full DSM-based segmentation in engine.geotiff_roof.
    Falls back to an empty geometry on failure so callers can detect and fall
    back to the Solar API path.

    Args:
        lat:     Latitude of the building.
        lng:     Longitude of the building.
        api_key: Google Solar API key.  Defaults to GOOGLE_SOLAR_API_KEY env var.

    Returns:
        GeoTiffRoofGeometry with polygons, scale_factor, and roof_faces populated.
    """
    api_key = api_key or os.environ.get("GOOGLE_SOLAR_API_KEY", "")
    if not api_key:
        raise ValueError("No Google Solar API key provided or GOOGLE_SOLAR_API_KEY not set")

    try:
        from engine.geotiff_roof import get_roof_faces_from_geotiff
        roof_faces, scale = get_roof_faces_from_geotiff(lat, lng, api_key)
    except Exception as exc:
        logger.error("GeoTIFF extraction failed: %s", exc)
        return GeoTiffRoofGeometry(polygons=[], scale_factor=1.0, roof_faces=[])

    if not roof_faces:
        logger.warning("GeoTIFF returned no roof faces for lat=%.5f lng=%.5f", lat, lng)
        return GeoTiffRoofGeometry(polygons=[], scale_factor=scale, roof_faces=[])

    # Convert RoofFace polygons to simple (x_ft, y_ft) lists
    polygons: List[List[Tuple[float, float]]] = []
    for rf in roof_faces:
        poly = rf.usable_polygon or rf.polygon
        if poly is None or poly.is_empty:
            continue
        coords = [(x / scale, y / scale) for x, y in poly.exterior.coords]
        polygons.append(coords)

    logger.info(
        "GeoTIFF geometry: %d faces, %d polygons, scale=%.3f pts/ft",
        len(roof_faces), len(polygons), scale,
    )
    return GeoTiffRoofGeometry(
        polygons=polygons,
        scale_factor=scale,
        roof_faces=roof_faces,
    )
