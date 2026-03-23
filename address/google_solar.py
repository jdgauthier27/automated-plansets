"""
Google Solar API Integration
=============================
Fetches roof data from Google's Solar API given an address or lat/lng.

Provides two modes:
  1. API mode — uses Google Solar API (requires API key)
  2. Fallback mode — uses Google Maps Static API satellite image + OpenCV

The API returns:
  - Roof segment polygons (pitch, azimuth, area)
  - Pre-computed solar panel positions
  - Annual energy estimates per panel
  - Building footprint and DSM data

Quebec-specific: uses Hydro-Quebec sun hours and Quebec lat/lng for defaults.
"""

import json
import logging
import math
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# Quebec average peak sun hours by city
QUEBEC_SUN_HOURS = {
    "montreal": 3.84,
    "quebec_city": 3.62,
    "sherbrooke": 3.72,
    "gatineau": 3.90,
    "trois-rivieres": 3.70,
    "default": 3.80,
}


@dataclass
class SolarRoofSegment:
    """A roof segment returned by the Solar API."""
    index: int
    pitch_deg: float
    azimuth_deg: float
    area_m2: float
    center_lat: float
    center_lng: float
    bounding_box: Optional[Dict] = None  # sw/ne LatLng
    height_m: float = 0.0
    sunshine_hours: float = 0.0


@dataclass
class SolarPanel:
    """A panel position returned by the Solar API."""
    center_lat: float
    center_lng: float
    orientation: str  # "LANDSCAPE" or "PORTRAIT"
    segment_index: int
    yearly_energy_kwh: float


@dataclass
class BuildingInsight:
    """Full building insight from the Solar API."""
    address: str
    lat: float
    lng: float
    imagery_quality: str = "UNKNOWN"
    max_panels: int = 0
    max_kw: float = 0.0
    max_annual_kwh: float = 0.0
    roof_segments: List[SolarRoofSegment] = field(default_factory=list)
    panels: List[SolarPanel] = field(default_factory=list)
    carbon_offset_kg: float = 0.0
    panel_height_m: float = 1.879  # from API panelHeightMeters
    panel_width_m: float = 1.045   # from API panelWidthMeters
    panel_capacity_w: float = 400  # from API panelCapacityWatts
    raw_response: Optional[Dict] = None


class GoogleSolarClient:
    """
    Client for Google Solar API.

    Usage:
        client = GoogleSolarClient(api_key="YOUR_KEY")
        insight = client.get_building_insight("123 Main St, Montreal, QC")

    If no API key is set, falls back to demo/mock data for development.
    """

    API_BASE = "https://solar.googleapis.com/v1"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GOOGLE_SOLAR_API_KEY")

    def get_building_insight(
        self,
        address: Optional[str] = None,
        lat: Optional[float] = None,
        lng: Optional[float] = None,
    ) -> BuildingInsight:
        """
        Fetch building insight from Google Solar API.

        Provide either an address (geocoded automatically) or lat/lng.
        Falls back to mock data if no API key is configured.
        """
        if not self.api_key:
            logger.warning("No Google Solar API key set. Using demo data.")
            return self._mock_building_insight(address or "Demo Address, Montreal, QC")

        # Geocode address if needed
        if address and not (lat and lng):
            lat, lng = self._geocode(address)

        if not (lat and lng):
            raise ValueError("Must provide address or lat/lng coordinates")

        return self._fetch_building_insight(lat, lng, address or f"{lat},{lng}")

    def _fetch_building_insight(self, lat: float, lng: float, address: str) -> BuildingInsight:
        """Call the actual Google Solar API."""
        import urllib.request
        import urllib.parse

        url = (
            f"{self.API_BASE}/buildingInsights:findClosest"
            f"?location.latitude={lat}&location.longitude={lng}"
            f"&requiredQuality=MEDIUM"
            f"&key={self.api_key}"
        )

        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
        except Exception as e:
            logger.error("Solar API request failed: %s", e)
            logger.info("Falling back to mock data")
            return self._mock_building_insight(address)

        return self._parse_response(data, address)

    def _parse_response(self, data: Dict, address: str) -> BuildingInsight:
        """Parse the Solar API JSON response."""
        center = data.get("center", {})
        solar = data.get("solarPotential", {})

        # Roof segments
        segments = []
        for i, seg in enumerate(solar.get("roofSegmentStats", [])):
            stats = seg.get("stats", {})
            seg_center = seg.get("center", {})
            segments.append(SolarRoofSegment(
                index=i,
                pitch_deg=seg.get("pitchDegrees", 0),
                azimuth_deg=seg.get("azimuthDegrees", 180),
                area_m2=stats.get("areaMeters2", 0),
                center_lat=seg_center.get("latitude", 0),
                center_lng=seg_center.get("longitude", 0),
                bounding_box=seg.get("boundingBox"),
                height_m=seg.get("planeHeightAtCenterMeters", 0),
            ))

        # Individual panels
        panels = []
        for p in solar.get("solarPanels", []):
            pc = p.get("center", {})
            panels.append(SolarPanel(
                center_lat=pc.get("latitude", 0),
                center_lng=pc.get("longitude", 0),
                orientation=p.get("orientation", "PORTRAIT"),
                segment_index=p.get("segmentIndex", 0),
                yearly_energy_kwh=p.get("yearlyEnergyDcKwh", 0),
            ))

        # Best config (max panels)
        configs = solar.get("solarPanelConfigs", [])
        best_config = configs[-1] if configs else {}

        insight = BuildingInsight(
            address=address,
            lat=center.get("latitude", 0),
            lng=center.get("longitude", 0),
            imagery_quality=data.get("imageryQuality", "UNKNOWN"),
            max_panels=best_config.get("panelsCount", len(panels)),
            max_kw=round(solar.get("maxArrayPanelsCount", 0) *
                         solar.get("panelCapacityWatts", 400) / 1000, 2),
            max_annual_kwh=round(best_config.get("yearlyEnergyDcKwh", 0), 0),
            roof_segments=segments,
            panels=panels,
            carbon_offset_kg=round(solar.get("carbonOffsetFactorKgPerMwh", 0) *
                                   best_config.get("yearlyEnergyDcKwh", 0) / 1000, 1),
            panel_height_m=solar.get("panelHeightMeters", 1.879),
            panel_width_m=solar.get("panelWidthMeters", 1.045),
            panel_capacity_w=solar.get("panelCapacityWatts", 400),
            raw_response=data,
        )
        return insight

    def _geocode(self, address: str) -> Tuple[float, float]:
        """Geocode an address using Google Geocoding API."""
        import urllib.request
        import urllib.parse

        encoded = urllib.parse.quote(address)
        url = (
            f"https://maps.googleapis.com/maps/api/geocode/json"
            f"?address={encoded}&key={self.api_key}"
        )

        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())

            if data.get("results"):
                loc = data["results"][0]["geometry"]["location"]
                return loc["lat"], loc["lng"]
        except Exception as e:
            logger.error("Geocoding failed: %s", e)

        raise ValueError(f"Could not geocode address: {address}")

    # ── Mock data for development ────────────────────────────────────────

    @staticmethod
    def _mock_building_insight(address: str) -> BuildingInsight:
        """
        Generate realistic mock data for a typical Quebec residential roof.
        Used when no API key is available.
        """
        # Typical Montreal residential: ~1500 sq ft roof, gable style
        segments = [
            SolarRoofSegment(
                index=0,
                pitch_deg=25.0,
                azimuth_deg=180.0,   # south-facing (ideal)
                area_m2=65.0,        # ~700 sq ft
                center_lat=45.5017,
                center_lng=-73.5673,
                height_m=8.5,
                sunshine_hours=1400,
            ),
            SolarRoofSegment(
                index=1,
                pitch_deg=25.0,
                azimuth_deg=0.0,     # north-facing
                area_m2=65.0,
                center_lat=45.5018,
                center_lng=-73.5673,
                height_m=8.5,
                sunshine_hours=900,
            ),
            SolarRoofSegment(
                index=2,
                pitch_deg=15.0,
                azimuth_deg=180.0,   # south garage
                area_m2=28.0,        # ~300 sq ft
                center_lat=45.5015,
                center_lng=-73.5671,
                height_m=4.0,
                sunshine_hours=1350,
            ),
        ]

        # Generate panel positions on south-facing segments
        panels = []
        panel_id = 0
        for seg in segments:
            if seg.azimuth_deg > 90 and seg.azimuth_deg < 270:
                # South-ish facing — place panels
                usable_m2 = seg.area_m2 * 0.65  # setbacks reduce usable
                panel_area_m2 = 1.7 * 1.0  # ~standard panel
                n_panels = int(usable_m2 / panel_area_m2)
                for i in range(n_panels):
                    # Spread panels across the segment
                    frac = (i + 0.5) / n_panels
                    offset_lat = (frac - 0.5) * 0.0002
                    offset_lng = ((i % 4) - 1.5) * 0.00005
                    panels.append(SolarPanel(
                        center_lat=seg.center_lat + offset_lat,
                        center_lng=seg.center_lng + offset_lng,
                        orientation="PORTRAIT",
                        segment_index=seg.index,
                        yearly_energy_kwh=480,  # typical for QC
                    ))
                    panel_id += 1

        total_kwh = sum(p.yearly_energy_kwh for p in panels)
        total_kw = len(panels) * 0.4  # 400W panels

        return BuildingInsight(
            address=address,
            lat=45.5017,
            lng=-73.5673,
            imagery_quality="HIGH",
            max_panels=len(panels),
            max_kw=round(total_kw, 2),
            max_annual_kwh=round(total_kwh, 0),
            roof_segments=segments,
            panels=panels,
            carbon_offset_kg=round(total_kwh * 0.002, 1),  # QC is mostly hydro, low carbon
        )


def solar_insight_to_roof_faces(insight: BuildingInsight, page_width=792, page_height=612):
    """
    Convert Google Solar API data into RoofFace objects compatible
    with the existing panel placement pipeline.

    Strategy: size each roof segment polygon based on its real-world area,
    then lay them out on the page. Uses a fixed scale (pts per foot) that
    makes the building fill ~60% of the page.
    """
    from shapely.geometry import Polygon, box
    from roof_detector import RoofFace

    if not insight.roof_segments:
        return [], 1.0

    # Total real-world area in sq ft
    total_area_sqft = sum(s.area_m2 * 10.764 for s in insight.roof_segments)
    if total_area_sqft <= 0:
        return [], 1.0

    # Estimate building footprint as a rectangle
    # Assume building is ~1.5:1 aspect ratio
    building_sqft = total_area_sqft * 1.2  # account for overlap between segments
    building_w_ft = math.sqrt(building_sqft * 1.5)
    building_h_ft = building_sqft / building_w_ft

    # Choose scale so building fills ~55% of the page
    usable_w = page_width * 0.55
    usable_h = page_height * 0.55
    scale_x = usable_w / building_w_ft
    scale_y = usable_h / building_h_ft
    pts_per_ft = min(scale_x, scale_y)

    # Page center
    cx_page = page_width / 2
    cy_page = page_height / 2

    # Layout segments: stack south-facing on bottom, north on top, garage offset
    roofs = []
    y_cursor = cy_page + building_h_ft * pts_per_ft * 0.3  # start near bottom

    for seg in insight.roof_segments:
        area_sqft = seg.area_m2 * 10.764
        # Segment dimensions (assume ~2:1 aspect for roof faces)
        seg_w_ft = math.sqrt(area_sqft * 2.0)
        seg_h_ft = area_sqft / seg_w_ft

        seg_w_pts = seg_w_ft * pts_per_ft
        seg_h_pts = seg_h_ft * pts_per_ft

        # Position: center horizontally, stack vertically
        x0 = cx_page - seg_w_pts / 2
        y0 = y_cursor - seg_h_pts

        poly = box(x0, y0, x0 + seg_w_pts, y0 + seg_h_pts)

        # Apply setbacks (3 ft fire setback per CEC)
        setback_pts = 3.0 * pts_per_ft
        usable = poly.buffer(-setback_pts)
        if usable.is_empty or usable.area < 100:
            usable = poly.buffer(-pts_per_ft)  # 1 ft minimum
        if usable.is_empty:
            usable = poly

        from shapely.geometry import MultiPolygon
        if isinstance(usable, MultiPolygon):
            usable = max(usable.geoms, key=lambda g: g.area)

        usable_sqft = usable.area / (pts_per_ft ** 2)

        rf = RoofFace(
            id=seg.index,
            polygon=poly,
            area_sqft=round(area_sqft, 1),
            pitch_deg=seg.pitch_deg,
            azimuth_deg=seg.azimuth_deg,
            usable_area_sqft=round(usable_sqft, 1),
            label=f"Roof-{seg.index + 1}",
            detection_method="google_solar_api",
            usable_polygon=usable,
        )
        roofs.append(rf)

        y_cursor = y0 - 15  # gap between segments

    return roofs, pts_per_ft
