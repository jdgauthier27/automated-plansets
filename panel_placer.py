"""
Panel Placer Module
===================
Places solar panels onto RoofFace polygons using a grid-packing algorithm.
Respects setbacks, spacing, and orientation constraints.
"""

import logging
import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from shapely.geometry import Polygon, box, Point
from shapely.affinity import rotate

from roof_detector import RoofFace

# Optional import — RoofObstacle may live in either location
try:
    from models.roof_obstacle import RoofObstacle
except ImportError:
    from models.project import RoofObstacle  # type: ignore[no-redef]

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
    ridge_setback_ft: float = 1.5     # NEC 690.12(B)(2): 18" from ridge/hip/valley
    obstacles: list = field(default_factory=list)  # list[RoofObstacle]


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
    orientation: str = ""   # resolved orientation used for this face
    ridge_setback_ft: float = 0.0  # NEC 690.12(B)(2) ridge setback applied (ft)

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
    def __init__(self, roof_face, panels, panel_spec, sun_hours, orientation=""):
        super().__init__(roof_face=roof_face, panels=panels, orientation=orientation)
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
                    rf, [], self.panel, self.config.sun_hours_peak, ""))
                continue

            face_limit = min(remaining, per_face_cap)
            panels, resolved_orientation = self._place_on_face(
                rf, pts_per_ft, face_limit, panel_id)
            panel_id += len(panels)
            remaining -= len(panels)

            result = PlacementResultWithSpec(
                rf, panels, self.panel, self.config.sun_hours_peak, resolved_orientation)
            result.ridge_setback_ft = self.config.ridge_setback_ft
            results.append(result)

            logger.info(
                "%s: placed %d panels (azimuth=%.0f°, pitch=%.0f°, orientation=%s)",
                rf.label, len(panels), rf.azimuth_deg, rf.pitch_deg, resolved_orientation,
            )

        return results

    # ------------------------------------------------------------------
    # Core placement logic
    # ------------------------------------------------------------------

    def _build_obstacle_polygons(
        self,
        rf: RoofFace,
        pts_per_ft: float,
    ) -> List[Polygon]:
        """Convert RoofObstacle list to page-coordinate Shapely polygons.

        Obstacles are defined in roof-local feet (origin = bottom-left of the
        roof face bounding box).  We translate to page coordinates using the
        face's usable_polygon bounding box origin.
        """
        if not self.config.obstacles:
            return []

        poly = rf.usable_polygon
        if poly is None or poly.is_empty:
            return []

        minx, miny, _, _ = poly.bounds
        result = []
        for obs in self.config.obstacles:
            # Map roof-local (ft) → page pts
            cx_pts = minx + obs.x_ft * pts_per_ft
            cy_pts = miny + obs.y_ft * pts_per_ft
            hw = obs.width_ft * pts_per_ft / 2
            hh = obs.height_ft * pts_per_ft / 2
            result.append(box(cx_pts - hw, cy_pts - hh, cx_pts + hw, cy_pts + hh))
        return result

    def _place_on_face(
        self,
        rf: RoofFace,
        pts_per_ft: float,
        max_panels: int,
        start_id: int,
    ) -> Tuple[List[PanelPlacement], str]:
        """Place panels on a single roof face using a rotated grid.

        Returns a tuple of (panels, resolved_orientation).

        Steps:
        1. Apply fire-setback inset to the usable polygon.
        2. Determine panel orientation: explicit 'portrait'/'landscape' are
           used as-is; 'auto' picks per-face based on the face's aspect ratio
           in the roof-local coordinate frame (eave width vs slope height).
        3. Build a grid aligned to the roof azimuth (eave / slope axes).
        4. For each grid cell, create a rotated panel rectangle and keep
           it only if the setback-reduced polygon fully contains it.
        5. Return (panels, resolved_orientation).
        """
        poly = rf.usable_polygon
        if poly is None or poly.is_empty:
            return [], ""

        # --- 1. Fire setback ------------------------------------------------
        setback_pts = self.config.setback_ft * pts_per_ft
        usable_poly = poly.buffer(-setback_pts)
        if usable_poly.is_empty or not usable_poly.is_valid:
            logger.debug("%s: polygon too small after setback", rf.label)
            return [], ""
        # buffer() can return a MultiPolygon; keep the largest piece
        if usable_poly.geom_type == "MultiPolygon":
            usable_poly = max(usable_poly.geoms, key=lambda g: g.area)

        # --- 2. Orientation --------------------------------------------------
        orientation = self.config.orientation
        if orientation == "auto":
            # Measure the face extent along the eave axis vs the slope axis.
            # Rotate the polygon so the eave direction aligns with the x-axis,
            # then read the axis-aligned bounding box width and height.
            angle_rad = math.radians(rf.azimuth_deg)
            cos_a = math.cos(angle_rad)
            sin_a = math.sin(angle_rad)

            coords = list(usable_poly.exterior.coords)
            cx, cy = usable_poly.centroid.x, usable_poly.centroid.y

            # Project each vertex onto eave (x') and slope (y') axes
            eave_coords = [
                (vx - cx) * cos_a + (vy - cy) * sin_a for vx, vy in coords
            ]
            slope_coords = [
                -(vx - cx) * sin_a + (vy - cy) * cos_a for vx, vy in coords
            ]
            face_width = max(eave_coords) - min(eave_coords)   # eave extent
            face_height = max(slope_coords) - min(slope_coords)  # slope extent

            orientation = "landscape" if face_width > face_height else "portrait"
            logger.debug(
                "%s: auto orientation → %s (eave=%.1f, slope=%.1f)",
                rf.label, orientation, face_width, face_height,
            )

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
        rad = math.radians(angle)
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)

        # --- 3b. Ridge setback (NEC 690.12(B)(2)) ----------------------------
        # Panels must stay 18" (1.5 ft) from the ridge/hip line (top of slope).
        # We clip the usable polygon by a half-plane that removes the top
        # ridge_setback_ft of the face in the slope direction.
        ridge_setback_pts = self.config.ridge_setback_ft * pts_per_ft
        if ridge_setback_pts > 0 and not usable_poly.is_empty:
            poly_cx2, poly_cy2 = usable_poly.centroid.x, usable_poly.centroid.y
            # Project vertices onto slope axis: slope = -(x-cx)*sin + (y-cy)*cos
            slope_projs = [
                -(vx - poly_cx2) * sin_a + (vy - poly_cy2) * cos_a
                for vx, vy in usable_poly.exterior.coords
            ]
            max_slope_proj = max(slope_projs)
            clip_slope = max_slope_proj - ridge_setback_pts

            # Half-plane boundary line at slope = clip_slope (extends along eave axis)
            LARGE = 100000
            bx0 = poly_cx2 - clip_slope * sin_a - LARGE * cos_a
            by0 = poly_cy2 + clip_slope * cos_a - LARGE * sin_a
            bx1 = poly_cx2 - clip_slope * sin_a + LARGE * cos_a
            by1 = poly_cy2 + clip_slope * cos_a + LARGE * sin_a
            # "Keep" side: toward eave (negative slope direction = +sin_a, -cos_a)
            kx0 = bx0 + LARGE * sin_a
            ky0 = by0 - LARGE * cos_a
            kx1 = bx1 + LARGE * sin_a
            ky1 = by1 - LARGE * cos_a

            clip_half_plane = Polygon([(bx0, by0), (bx1, by1), (kx1, ky1), (kx0, ky0)])
            ridge_clipped = usable_poly.intersection(clip_half_plane)
            if not ridge_clipped.is_empty and ridge_clipped.is_valid:
                if ridge_clipped.geom_type == "MultiPolygon":
                    ridge_clipped = max(ridge_clipped.geoms, key=lambda g: g.area)
                usable_poly = ridge_clipped
            else:
                logger.debug("%s: polygon empty after ridge setback", rf.label)
                return [], ""

        # --- 4. Grid extents --------------------------------------------------
        # We need enough grid cells to cover the polygon.  Compute the
        # diagonal of the polygon bounding box to be safe.
        minx, miny, maxx, maxy = usable_poly.bounds
        diag = math.hypot(maxx - minx, maxy - miny)
        max_cols = int(diag / step_eave) + 2
        max_rows = int(diag / step_slope) + 2

        cx, cy = usable_poly.centroid.x, usable_poly.centroid.y

        # --- 5. Place panels --------------------------------------------------
        # Build obstacle exclusion polygons (page coordinates).
        obstacle_polys = self._build_obstacle_polygons(rf, pts_per_ft)

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

                        if not usable_poly.contains(panel_rotated):
                            continue

                        # Skip panel if it overlaps any obstacle exclusion zone
                        if any(panel_rotated.intersects(obs) for obs in obstacle_polys):
                            continue

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

        return panels, orientation
