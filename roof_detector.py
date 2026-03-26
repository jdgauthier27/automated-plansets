"""
Roof Detector Module
====================
Defines RoofFace — a data class representing a detected or API-provided
roof segment with its polygon, usable area, and solar attributes.
"""

from dataclasses import dataclass, field
from typing import Optional
from shapely.geometry import Polygon


@dataclass
class RoofFace:
    """A single roof face / segment for panel placement."""

    id: int
    polygon: Polygon  # full outline in page-pts
    area_sqft: float
    pitch_deg: float = 0.0
    azimuth_deg: float = 180.0  # 180 = due south
    usable_area_sqft: float = 0.0
    label: str = ""
    detection_method: str = "unknown"  # "opencv", "google_solar_api", etc.
    usable_polygon: Optional[Polygon] = None  # after setback insets

    def __post_init__(self):
        if self.usable_polygon is None:
            self.usable_polygon = self.polygon
        if not self.label:
            self.label = f"Roof-{self.id + 1}"

    @property
    def azimuth_label(self) -> str:
        """Human-friendly compass direction."""
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
            if abs(self.azimuth_deg - deg) <= 22.5:
                return lbl
        return "S"

    @property
    def is_south_facing(self) -> bool:
        return 90 < self.azimuth_deg < 270
