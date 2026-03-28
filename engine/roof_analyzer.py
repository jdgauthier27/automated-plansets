"""
Roof Analyzer
=============
Extracts roof pitch, azimuth, obstruction data, and segment rankings from
Google Solar API buildingInsights response. Auto-populates ProjectSpec with
real measurements instead of manual/default values.
"""

import logging
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class RoofSegmentInfo:
    """Analyzed roof segment with solar potential data."""

    index: int
    pitch_deg: float
    azimuth_deg: float
    area_m2: float
    area_sqft: float
    height_m: float  # planeHeightAtCenterMeters
    center_lat: float
    center_lng: float

    # Solar potential
    sunshine_hours_per_year: float = 0.0
    sunshine_quantiles: List[float] = field(default_factory=list)  # 11 buckets
    panel_count: int = 0  # panels Google placed on this segment

    # Derived
    direction_label: str = ""  # "South", "SSW", "NE", etc.
    solar_score: float = 0.0  # 0-100 ranking
    obstruction_score: float = 0.0  # 0-100 (100 = heavily obstructed)
    is_viable: bool = True  # recommended for panels?

    @property
    def area_display(self) -> str:
        return f"{self.area_sqft:.0f} ft² ({self.area_m2:.0f} m²)"


SQFT_PER_M2 = 10.7639


def _azimuth_to_direction(azimuth_deg: float) -> str:
    """Convert azimuth degrees to compass direction label."""
    dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    idx = round(azimuth_deg / 22.5) % 16
    return dirs[idx]


def _solar_score(pitch_deg: float, azimuth_deg: float, sunshine_hours: float, max_sunshine: float) -> float:
    """Calculate a 0-100 solar score for a roof segment.

    Factors:
      - South-facing is best (azimuth 180°)
      - Moderate pitch (20-35°) is best for Quebec latitudes
      - Higher sunshine hours = better
    """
    # Azimuth score: 180° (due south) = 100, north = 0
    az_diff = abs(azimuth_deg - 180)
    azimuth_score = max(0, 100 - (az_diff / 180 * 100))

    # Pitch score: 25° is optimal for ~45° latitude (Quebec)
    pitch_diff = abs(pitch_deg - 25)
    pitch_score = max(0, 100 - (pitch_diff / 45 * 100))

    # Sunshine score
    sunshine_score = (sunshine_hours / max_sunshine * 100) if max_sunshine > 0 else 50

    # Weighted combination
    return round(azimuth_score * 0.4 + pitch_score * 0.2 + sunshine_score * 0.4, 1)


def _obstruction_score(sunshine_quantiles: List[float]) -> float:
    """Estimate obstruction level from sunshine quantile distribution.

    If sunshine is uniform across the segment, obstruction is low.
    If there's high variance (some areas very shaded), obstruction is high.

    Returns 0-100 (100 = heavily obstructed).
    """
    if not sunshine_quantiles or len(sunshine_quantiles) < 2:
        return 0.0

    # Standard deviation of quantiles — high spread = obstructions
    mean = sum(sunshine_quantiles) / len(sunshine_quantiles)
    variance = sum((q - mean) ** 2 for q in sunshine_quantiles) / len(sunshine_quantiles)
    std_dev = math.sqrt(variance)

    # Normalize: if std_dev > 200 hours, likely significant obstructions
    score = min(100, (std_dev / 200) * 100)
    return round(score, 1)


def analyze_roof(insight) -> List[RoofSegmentInfo]:
    """Analyze all roof segments from a BuildingInsight.

    Args:
        insight: BuildingInsight from Google Solar API.

    Returns:
        List of RoofSegmentInfo sorted by solar_score (best first).
    """
    if not insight or not insight.roof_segments:
        logger.warning("No roof segments in building insight")
        return []

    # Count panels per segment
    panels_per_seg = {}
    if insight.panels:
        for p in insight.panels:
            seg_idx = getattr(p, "segment_index", 0)
            panels_per_seg[seg_idx] = panels_per_seg.get(seg_idx, 0) + 1

    # Find max sunshine for normalization
    max_sunshine = (
        max(
            (
                getattr(seg, "sunshine_hours_per_year", 0)
                or getattr(getattr(seg, "stats", None), "sunshine_hours_per_year", 0)
                or 0
            )
            for seg in insight.roof_segments
        )
        or 1500
    )  # default fallback

    segments = []
    for seg in insight.roof_segments:
        # Extract sunshine data
        stats = getattr(seg, "stats", None)
        sunshine_hours = getattr(seg, "sunshine_hours_per_year", 0)
        if not sunshine_hours and stats:
            sunshine_hours = getattr(stats, "sunshine_hours_per_year", 0)
        quantiles = getattr(seg, "sunshine_quantiles", [])
        if not quantiles and stats:
            quantiles = getattr(stats, "sunshine_quantiles", [])

        area_m2 = getattr(seg, "area_m2", 0)
        if not area_m2 and stats:
            area_m2 = getattr(stats, "area_m2", getattr(stats, "areaMeters2", 0))

        info = RoofSegmentInfo(
            index=seg.index,
            pitch_deg=seg.pitch_deg,
            azimuth_deg=seg.azimuth_deg,
            area_m2=area_m2,
            area_sqft=area_m2 * SQFT_PER_M2,
            height_m=getattr(seg, "plane_height_at_center_meters", getattr(seg, "height_m", 0)) or 0,
            center_lat=getattr(seg, "center_lat", getattr(getattr(seg, "center", None), "lat", 0)) or 0,
            center_lng=getattr(seg, "center_lng", getattr(getattr(seg, "center", None), "lng", 0)) or 0,
            sunshine_hours_per_year=sunshine_hours or 0,
            sunshine_quantiles=quantiles or [],
            panel_count=panels_per_seg.get(seg.index, 0),
            direction_label=_azimuth_to_direction(seg.azimuth_deg),
        )

        # Calculate scores
        info.solar_score = _solar_score(
            info.pitch_deg,
            info.azimuth_deg,
            info.sunshine_hours_per_year,
            max_sunshine,
        )
        info.obstruction_score = _obstruction_score(info.sunshine_quantiles)
        info.is_viable = info.solar_score >= 30 and info.area_m2 >= 4.0

        segments.append(info)

    # Sort by solar score, best first
    segments.sort(key=lambda s: s.solar_score, reverse=True)

    logger.info("Roof analysis: %d segments, %d viable", len(segments), sum(1 for s in segments if s.is_viable))
    for s in segments[:5]:
        logger.info(
            "  Seg %d: %s-facing, pitch=%.0f°, score=%.0f, obstruction=%.0f, %d panels",
            s.index,
            s.direction_label,
            s.pitch_deg,
            s.solar_score,
            s.obstruction_score,
            s.panel_count,
        )

    return segments


def get_building_dimensions(insight) -> Dict:
    """Extract building footprint dimensions from roof segment bounding boxes.

    Returns approximate building width and depth in feet.
    """
    if not insight or not insight.roof_segments:
        return {"width_ft": 0, "depth_ft": 0, "height_ft": 0}

    all_lats = []
    all_lngs = []
    max_height = 0

    for seg in insight.roof_segments:
        bb = getattr(seg, "bounding_box", None)
        if bb:
            ne = bb.get("ne", bb.get("high", {}))
            sw = bb.get("sw", bb.get("low", {}))
            if ne and sw:
                all_lats.extend([ne.get("lat", ne.get("latitude", 0)), sw.get("lat", sw.get("latitude", 0))])
                all_lngs.extend([ne.get("lng", ne.get("longitude", 0)), sw.get("lng", sw.get("longitude", 0))])

        height = getattr(seg, "plane_height_at_center_meters", getattr(seg, "height_m", 0)) or 0
        max_height = max(max_height, height)

    if not all_lats or not all_lngs:
        return {"width_ft": 0, "depth_ft": 0, "height_ft": 0}

    # Convert lat/lng span to feet
    lat_span = max(all_lats) - min(all_lats)
    lng_span = max(all_lngs) - min(all_lngs)
    avg_lat = sum(all_lats) / len(all_lats)

    depth_m = lat_span * 111319.5
    width_m = lng_span * 111319.5 * math.cos(math.radians(avg_lat))

    return {
        "width_ft": round(width_m * 3.28084, 1),
        "depth_ft": round(depth_m * 3.28084, 1),
        "height_ft": round(max_height * 3.28084, 1),
        "width_m": round(width_m, 1),
        "depth_m": round(depth_m, 1),
        "height_m": round(max_height, 1),
    }
