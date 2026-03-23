"""
Panel Placer Module
===================
Places solar panels onto RoofFace polygons using a grid-packing algorithm.
Respects setbacks, spacing, and orientation constraints.
"""

import logging
import math
from dataclasses import dataclass, field
from typing import List, Optional

from shapely.geometry import Polygon, box, Point
from shapely.affinity import rotate

from roof_detector import RoofFace

logger = logging.getLogger(__name__)


@dataclass
class PanelSpec:
    """Physical specifications of a solar panel."""
    name: str = "Generic 400W"
    wattage: int = 400
    width_ft: float = 3.46    # ~1055mm
    height_ft: float = 6.17   # ~1879mm
    efficiency: float = 0.21

    @property
    def area_sqft(self) -> float:
        return self.width_ft * self.height_ft

    @property
    def kw(self) -> float:
        return self.wattage / 1000.0


@dataclass
class PlacementConfig:
    """Configuration for panel placement."""
    row_spacing_ft: float = 0.5       # gap between rows
    col_spacing_ft: float = 0.25      # gap between columns
    orientation: str = "auto"         # "portrait", "landscape", or "auto"
    max_panels: int = 999
    sun_hours_peak: float = 3.80      # Quebec default
    setback_ft: float = 3.0           # fire setback from edges


@dataclass
class PanelPlacement:
    """A single placed panel."""
    id: int
    center_x: float        # page-pts
    center_y: float        # page-pts
    width_pts: float
    height_pts: float
    orientation: str        # "portrait" or "landscape"
    roof_id: int
    rotation_deg: float = 0.0

    @property
    def polygon(self) -> Polygon:
        x, y = self.center_x, self.center_y
        hw, hh = self.width_pts / 2, self.height_pts / 2
        p = box(x - hw, y - hh, x + hw, y + hh)
        if self.rotation_deg:
            p = rotate(p, self.rotation_deg, origin=(x, y))
        return p


@dataclass
class PlacementResult:
    """Result of placing panels on one roof face."""
    roof_face: RoofFace
    panels: List[PanelPlacement] = field(default_factory=list)

    @property
    def total_panels(self) -> int:
        return len(self.panels)

    @property
    def total_kw(self) -> float:
        return 0.0  # computed externally with panel spec

    @property
    def estimated_annual_kwh(self) -> float:
        return 0.0  # computed externally


class PlacementResultWithSpec(PlacementResult):
    """Extends PlacementResult with spec-aware calculations."""
    def __init__(self, roof_face, panels, panel_spec, sun_hours):
        super().__init__(roof_face=roof_face, panels=panels)
        self._spec = panel_spec
        self._sun_hours = sun_hours

    @property
    def total_kw(self) -> float:
        return round(len(self.panels) * self._spec.kw, 2)

    @property
    def estimated_annual_kwh(self) -> float:
        return round(self.total_kw * self._sun_hours * 365, 0)


class PanelPlacer:
    """
    Places solar panels onto RoofFace usable polygons using a
    rotation-aware grid-packing strategy.

    Panels are rotated to match the roof azimuth so they align with the
    slope direction.  They are packed in portrait orientation (long edge
    up-slope, short edge along the eave) on racking rails that run
    along the eave direction, producing contiguous rectangular arrays.
    """

    def __init__(self, panel: PanelSpec, config: PlacementConfig, use_geotiff: bool = False):
        self.panel = panel
        self.config = config
        self.use_geotiff = use_geotiff

    def place_on_roofs_geotiff(
        self,
        lat: float,
        lng: float,
        api_key: Optional[str] = None,
    ) -> List[PlacementResult]:
        """Place panels using GeoTIFF-derived roof geometry.

        Downloads the Google Solar dataLayers mask + DSM GeoTIFF to get
        accurate roof polygons (the buildingInsights polygons are ~40% too
        small), then delegates to the normal place_on_roofs() logic.

        Falls back to an empty list if GeoTIFF extraction fails.
        """
        try:
            from geotiff_roof import get_roof_geometry_from_geotiff
            geom = get_roof_geometry_from_geotiff(lat, lng, api_key)
        except Exception as exc:
            logger.error("GeoTIFF roof extraction failed: %s", exc)
            return []

        if not geom.roof_faces:
            logger.warning("GeoTIFF returned no roof faces — cannot place panels")
            return []

        return self.place_on_roofs(geom.roof_faces, geom.scale_factor)

    def place_on_roofs(
        self,
        roofs: List[RoofFace],
        pts_per_ft: float,
    ) -> List[PlacementResult]:
        """Place panels across all roof faces, respecting max_panels."""
        results = []
        remaining = self.config.max_panels
        panel_id = 0

        # Prioritize non-north faces, then sort by area descending so the
        # largest roof segments (not just the most southerly) get panels first.
        # North is defined as azimuth < 45° or > 315°.
        def _sort_key(r: RoofFace):
            is_north = r.azimuth_deg < 45 or r.azimuth_deg > 315
            return (1 if is_north else 0, -r.area_sqft)

        sorted_roofs = sorted(roofs, key=_sort_key)

        # Per-face cap: when ≥2 productive faces exist, limit any single face
        # to ceil(max_panels / 2) so panels are spread across both array faces.
        # This mirrors real installer practice (gable roofs get two arrays).
        productive_count = sum(
            1 for r in roofs
            if not (r.azimuth_deg < 45 or r.azimuth_deg > 315)
        )
        if productive_count >= 2 and self.config.max_panels > 1:
            per_face_cap = math.ceil(self.config.max_panels / 2)
        else:
            per_face_cap = self.config.max_panels

        for rf in sorted_roofs:
            if remaining <= 0:
                results.append(PlacementResultWithSpec(
                    rf, [], self.panel, self.config.sun_hours_peak))
                continue

            face_limit = min(remaining, per_face_cap)
            panels = self._place_on_face(rf, pts_per_ft, face_limit, panel_id)
            panel_id += len(panels)
            remaining -= len(panels)

            results.append(PlacementResultWithSpec(
                rf, panels, self.panel, self.config.sun_hours_peak))

            logger.info(
                "%s: placed %d panels (azimuth=%.0f°, pitch=%.0f°)",
                rf.label, len(panels), rf.azimuth_deg, rf.pitch_deg,
            )

        return results

    # ------------------------------------------------------------------
    # Core placement logic
    # ------------------------------------------------------------------

    def _place_on_face(
        self,
        rf: RoofFace,
        pts_per_ft: float,
        max_panels: int,
        start_id: int,
    ) -> List[PanelPlacement]:
        """Place panels on a single roof face using a rotated grid.

        Steps:
        1. Apply fire-setback inset to the usable polygon.
        2. Determine panel orientation (portrait preferred).
        3. Build a grid aligned to the roof azimuth (eave / slope axes).
        4. For each grid cell, create a rotated panel rectangle and keep
           it only if the setback-reduced polygon fully contains it.
        5. Return the list of placed panels.
        """
        poly = rf.usable_polygon
        if poly is None or poly.is_empty:
            return []

        # --- 1. Fire setback ------------------------------------------------
        setback_pts = self.config.setback_ft * pts_per_ft
        usable_poly = poly.buffer(-setback_pts)
        if usable_poly.is_empty or not usable_poly.is_valid:
            logger.debug("%s: polygon too small after setback", rf.label)
            return []
        # buffer() can return a MultiPolygon; keep the largest piece
        if usable_poly.geom_type == "MultiPolygon":
            usable_poly = max(usable_poly.geoms, key=lambda g: g.area)

        # --- 2. Orientation --------------------------------------------------
        orientation = self.config.orientation
        if orientation == "auto":
            # Default to portrait; panels are more efficient on racking
            orientation = "portrait"

        if orientation == "landscape":
            pw_ft = self.panel.height_ft   # along eave
            ph_ft = self.panel.width_ft    # along slope
        else:
            pw_ft = self.panel.width_ft    # along eave
            ph_ft = self.panel.height_ft   # along slope

        pw_pts = pw_ft * pts_per_ft
        ph_pts = ph_ft * pts_per_ft
        col_gap = self.config.col_spacing_ft * pts_per_ft   # eave dir
        row_gap = self.config.row_spacing_ft * pts_per_ft   # slope dir

        # Step between panel centres
        step_eave = pw_pts + col_gap
        step_slope = ph_pts + row_gap

        # --- 3. Rotation angle -----------------------------------------------
        # Azimuth gives the compass direction the roof faces (down-slope).
        # We need the rotation to apply in the 2-D page coordinate system.
        angle = rf.azimuth_deg

        # --- 4. Grid extents --------------------------------------------------
        # We need enough grid cells to cover the polygon.  Compute the
        # diagonal of the polygon bounding box to be safe.
        minx, miny, maxx, maxy = usable_poly.bounds
        diag = math.hypot(maxx - minx, maxy - miny)
        max_cols = int(diag / step_eave) + 2
        max_rows = int(diag / step_slope) + 2

        cx, cy = usable_poly.centroid.x, usable_poly.centroid.y
        rad = math.radians(angle)
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)

        # --- 5. Place panels --------------------------------------------------
        # Try several grid origin offsets to maximise packing.  A centroid-
        # centred grid can miss panels at the edges; shifting the origin by
        # fractional steps often recovers an extra row or column.
        best_panels: List[PanelPlacement] = []

        offsets = [0.0, 0.5]   # fraction of step to shift
        for off_e in offsets:
            for off_s in offsets:
                candidate: List[PanelPlacement] = []
                origin_shift_eave = off_e * step_eave
                origin_shift_slope = off_s * step_slope

                for i in range(-max_cols // 2, max_cols // 2 + 1):
                    for j in range(-max_rows // 2, max_rows // 2 + 1):
                        if len(candidate) >= max_panels:
                            break

                        # Position in roof-local frame (eave, slope)
                        local_eave = i * step_eave + origin_shift_eave
                        local_slope = j * step_slope + origin_shift_slope

                        # Rotate into page coordinates
                        x = cx + local_eave * cos_a - local_slope * sin_a
                        y = cy + local_eave * sin_a + local_slope * cos_a

                        # Build axis-aligned box then rotate in place
                        panel_box = box(
                            x - pw_pts / 2, y - ph_pts / 2,
                            x + pw_pts / 2, y + ph_pts / 2,
                        )
                        panel_rotated = rotate(panel_box, angle, origin=(x, y))

                        if usable_poly.contains(panel_rotated):
                            candidate.append(PanelPlacement(
                                id=start_id + len(candidate),
                                center_x=x,
                                center_y=y,
                                width_pts=pw_pts,
                                height_pts=ph_pts,
                                orientation=orientation,
                                roof_id=rf.id,
                                rotation_deg=angle,
                            ))

                if len(candidate) > len(best_panels):
                    best_panels = candidate

        panels = best_panels

        # --- 6. Sort for tidy array grouping ----------------------------------
        # Sort so panels in the same rail row are adjacent (by slope index
        # first, then eave index) for downstream wiring / stringing.
        if panels:
            panels.sort(key=lambda p: (
                round((p.center_y - cy) * cos_a + (p.center_x - cx) * sin_a, 1),
                round((p.center_x - cx) * cos_a - (p.center_y - cy) * sin_a, 1),
            ))
            # Re-number ids sequentially after sort
            for idx, p in enumerate(panels):
                p.id = start_id + idx

        return panels
