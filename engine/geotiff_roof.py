"""
GeoTIFF Roof Geometry Extractor
================================
Downloads mask and DSM GeoTIFF layers from the Google Solar API dataLayers
endpoint, isolates the target building via connected-component labeling on
the mask, segments the roof into faces using DSM gradient analysis
(aspect / slope), and returns RoofFace objects ready for panel_placer.py.

Public API
----------
    get_roof_faces_from_geotiff(lat, lng, api_key)
        -> (List[RoofFace], scale_pts_per_ft)

    get_building_outline(lat, lng, api_key)
        -> List[tuple[float, float]]   # (x_ft, y_ft) polygon
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
from scipy.ndimage import gaussian_filter, label as ndimage_label
from shapely.geometry import MultiPolygon, Polygon

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_M_PER_FT = 0.3048
_FT_PER_M = 3.28084
_SQFT_PER_M2 = 10.7639

_PAGE_WIDTH = 792   # letter landscape pts
_PAGE_HEIGHT = 612

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

# Aspect-direction bins (degrees clockwise from north)
_DIRECTION_BINS = [
    ("N", 0, 45),
    ("E", 45, 135),
    ("S", 135, 225),
    ("W", 225, 315),
    ("N", 315, 360),
]


# ---------------------------------------------------------------------------
# Internal helpers — API download
# ---------------------------------------------------------------------------
def _fetch_data_layers(lat: float, lng: float, api_key: str) -> dict:
    """Call Google Solar API dataLayers:get and return the JSON response."""
    url = (
        "https://solar.googleapis.com/v1/dataLayers:get"
        f"?location.latitude={lat}&location.longitude={lng}"
        "&radiusMeters=50&view=FULL_LAYERS"
        "&requiredQuality=HIGH&pixelSizeMeters=0.1"
        f"&key={api_key}"
    )
    logger.info("Fetching dataLayers: lat=%.5f lng=%.5f", lat, lng)
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=30, context=_SSL_CTX) as resp:
        return json.loads(resp.read().decode())


def _download_geotiff(url: str, api_key: str) -> bytes:
    """Download a GeoTIFF from the given URL (appending api key)."""
    if "key=" not in url:
        sep = "&" if "?" in url else "?"
        url += f"{sep}key={api_key}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=60, context=_SSL_CTX) as resp:
        data = resp.read()
    logger.info("Downloaded GeoTIFF: %d bytes", len(data))
    return data


# ---------------------------------------------------------------------------
# GeoTIFF parsing with rasterio
# ---------------------------------------------------------------------------
@dataclass
class _GeoTiff:
    """Parsed GeoTIFF raster + affine transform."""
    data: np.ndarray           # 2D float32
    transform: "rasterio.Affine"
    crs: str
    resolution: float          # meters/pixel (from transform)

    def pixel_to_xy(self, row: int, col: int) -> Tuple[float, float]:
        """Convert (row, col) to CRS coordinates (x, y)."""
        x = self.transform.c + col * self.transform.a + row * self.transform.b
        y = self.transform.f + col * self.transform.d + row * self.transform.e
        return x, y

    def xy_to_pixel(self, x: float, y: float) -> Tuple[int, int]:
        """Convert CRS (x, y) to nearest (row, col)."""
        inv = ~self.transform
        col, row = inv * (x, y)
        return int(round(row)), int(round(col))


def _parse_geotiff(raw: bytes) -> _GeoTiff:
    """Parse raw GeoTIFF bytes into a _GeoTiff."""
    import rasterio
    with rasterio.open(io.BytesIO(raw)) as ds:
        data = ds.read(1).astype(np.float32)
        transform = ds.transform
        crs = str(ds.crs) if ds.crs else "unknown"
        res = abs(transform.a)
    return _GeoTiff(data=data, transform=transform, crs=crs, resolution=res)


# ---------------------------------------------------------------------------
# Coordinate helpers
# ---------------------------------------------------------------------------
def _latlng_to_utm(lat: float, lng: float, transform: "rasterio.Affine",
                   crs: str) -> Tuple[float, float]:
    """Convert lat/lng to the same UTM CRS as the GeoTIFF.

    Uses pyproj if available, otherwise a simplified formula.
    """
    try:
        from pyproj import Transformer
        transformer = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
        x, y = transformer.transform(lng, lat)
        return x, y
    except Exception:
        pass

    # Fallback: determine UTM zone from longitude
    zone = int((lng + 180) / 6) + 1
    # Simplified WGS-84 forward projection
    return _forward_utm(lat, lng, zone)


def _forward_utm(lat: float, lng: float, zone: int) -> Tuple[float, float]:
    """Simplified WGS-84 lat/lng -> UTM easting/northing."""
    a = 6378137.0
    f = 1 / 298.257223563
    e = math.sqrt(2 * f - f * f)
    e_prime_sq = e * e / (1 - e * e)
    k0 = 0.9996

    lat_r = math.radians(lat)
    lng_r = math.radians(lng)
    lng0_r = math.radians(zone * 6 - 183)

    N = a / math.sqrt(1 - e * e * math.sin(lat_r) ** 2)
    T = math.tan(lat_r) ** 2
    C = e_prime_sq * math.cos(lat_r) ** 2
    A = (lng_r - lng0_r) * math.cos(lat_r)

    M = a * (
        (1 - e**2 / 4 - 3 * e**4 / 64 - 5 * e**6 / 256) * lat_r
        - (3 * e**2 / 8 + 3 * e**4 / 32 + 45 * e**6 / 1024) * math.sin(2 * lat_r)
        + (15 * e**4 / 256 + 45 * e**6 / 1024) * math.sin(4 * lat_r)
        - (35 * e**6 / 3072) * math.sin(6 * lat_r)
    )

    easting = k0 * N * (
        A + (1 - T + C) * A**3 / 6
        + (5 - 18 * T + T**2 + 72 * C - 58 * e_prime_sq) * A**5 / 120
    ) + 500000.0

    northing = k0 * (
        M + N * math.tan(lat_r) * (
            A**2 / 2
            + (5 - T + 9 * C + 4 * C**2) * A**4 / 24
            + (61 - 58 * T + T**2 + 600 * C - 330 * e_prime_sq) * A**6 / 720
        )
    )

    return easting, northing


# ---------------------------------------------------------------------------
# Building isolation (mask layer)
# ---------------------------------------------------------------------------
def _isolate_building(mask: _GeoTiff, lat: float, lng: float) -> np.ndarray:
    """Return a boolean mask for the single building closest to (lat, lng).

    Uses connected-component labeling on the binary roof mask, then selects
    the component whose centroid is closest to the target coordinates.
    """
    binary = (mask.data > 0).astype(np.int32)

    # Connected-component labeling
    labels, n_components = ndimage_label(binary)
    if n_components == 0:
        logger.warning("No building pixels found in mask")
        return np.zeros_like(binary, dtype=bool)

    # Target pixel location
    tx, ty = _latlng_to_utm(lat, lng, mask.transform, mask.crs)
    target_row, target_col = mask.xy_to_pixel(tx, ty)
    target_row = max(0, min(mask.data.shape[0] - 1, target_row))
    target_col = max(0, min(mask.data.shape[1] - 1, target_col))

    # If the target pixel already sits on a component, prefer that one
    target_label = labels[target_row, target_col]
    if target_label > 0:
        building_mask = labels == target_label
        area_px = int(building_mask.sum())
        logger.info("Target pixel hit component %d (%d px)", target_label, area_px)
        # Sanity: must be >50 pixels (~0.5 m^2 at 0.1 m/px)
        if area_px > 50:
            return building_mask

    # Otherwise find the component whose centroid is closest
    best_label = 0
    best_dist = float("inf")
    for comp_id in range(1, n_components + 1):
        ys, xs = np.where(labels == comp_id)
        if len(ys) < 50:
            continue  # skip tiny noise
        cy, cx = ys.mean(), xs.mean()
        d = (cy - target_row) ** 2 + (cx - target_col) ** 2
        if d < best_dist:
            best_dist = d
            best_label = comp_id

    if best_label == 0:
        logger.warning("No building component found near target")
        return np.zeros_like(binary, dtype=bool)

    building_mask = labels == best_label
    logger.info("Selected component %d (dist=%.0f px, area=%d px)",
                best_label, math.sqrt(best_dist), int(building_mask.sum()))
    return building_mask


# ---------------------------------------------------------------------------
# Building outline extraction
# ---------------------------------------------------------------------------
def _mask_to_contour_coords(mask: np.ndarray) -> List[Tuple[int, int]]:
    """Extract the outer contour of a binary mask as (col, row) pixel coords.

    Uses the marching-squares approach from skimage if available, otherwise
    falls back to a simple boundary-pixel walk.
    """
    try:
        from skimage.measure import find_contours
        contours = find_contours(mask.astype(np.float64), 0.5)
        if not contours:
            return []
        # Longest contour
        contour = max(contours, key=len)
        # find_contours returns (row, col) floats
        return [(int(round(c)), int(round(r))) for r, c in contour]
    except ImportError:
        pass

    # Fallback: use shapely rasterio.features-style approach
    from scipy.ndimage import binary_fill_holes, binary_erosion
    filled = binary_fill_holes(mask)
    boundary = filled & ~binary_erosion(filled)
    rows, cols = np.where(boundary)
    if len(rows) == 0:
        return []
    # Order the boundary pixels (approximate convex hull via shapely)
    from shapely.geometry import MultiPoint
    pts = MultiPoint(list(zip(cols.tolist(), rows.tolist())))
    hull = pts.convex_hull
    if hull.is_empty:
        return []
    coords = list(hull.exterior.coords)
    return [(int(round(c)), int(round(r))) for c, r in coords]


def _simplify_pixel_contour(coords: List[Tuple[int, int]],
                            tolerance: float = 2.0
                            ) -> List[Tuple[int, int]]:
    """Simplify a pixel contour using Douglas-Peucker via shapely."""
    if len(coords) < 4:
        return coords
    from shapely.geometry import LineString
    ls = LineString(coords)
    simplified = ls.simplify(tolerance)
    return [(int(round(c[0])), int(round(c[1]))) for c in simplified.coords]


def _extract_outline(building_mask: np.ndarray, geotiff: _GeoTiff
                     ) -> List[Tuple[float, float]]:
    """Extract the outline polygon in CRS meters from a binary mask.

    Returns list of (x_m, y_m) in the GeoTIFF CRS.
    """
    from scipy.ndimage import binary_fill_holes

    filled = binary_fill_holes(building_mask)

    pixel_coords = _mask_to_contour_coords(filled)
    if not pixel_coords:
        return []

    pixel_coords = _simplify_pixel_contour(pixel_coords, tolerance=2.0)

    # Convert pixel coords to CRS coords (meters)
    outline = []
    for col, row in pixel_coords:
        x, y = geotiff.pixel_to_xy(row, col)
        outline.append((x, y))

    return outline


# ---------------------------------------------------------------------------
# Roof-face segmentation from DSM gradient
# ---------------------------------------------------------------------------
@dataclass
class _RawFace:
    """Intermediate roof face before conversion to RoofFace."""
    pixels: np.ndarray          # boolean mask
    area_m2: float
    area_sqft: float
    avg_pitch_deg: float
    avg_azimuth_deg: float
    label: str
    polygon_m: List[Tuple[float, float]]   # outline in CRS meters


def _segment_roof_faces(
    dsm: _GeoTiff,
    building_mask: np.ndarray,
    mask_geotiff: _GeoTiff,
) -> List[_RawFace]:
    """Segment the building roof into faces using DSM slope/aspect analysis.

    Steps:
        1. Apply building mask to DSM (align grids if resolutions differ).
        2. Smooth DSM with Gaussian filter.
        3. Compute gradient -> slope and aspect.
        4. Filter to elevated roof pixels (height > 2 m above ground).
        5. Cluster by aspect direction (N/E/S/W).
        6. For each cluster, compute stats and extract polygon.
    """
    # --- Align mask and DSM grids ---
    # Both should come from same dataLayers call with same resolution,
    # but handle minor size mismatches.
    bm = building_mask
    dsm_data = dsm.data

    if bm.shape != dsm_data.shape:
        # Resize mask to match DSM using scipy zoom
        from scipy.ndimage import zoom as ndimage_zoom
        zoom_y = dsm_data.shape[0] / bm.shape[0]
        zoom_x = dsm_data.shape[1] / bm.shape[1]
        bm = ndimage_zoom(bm.astype(np.float32), (zoom_y, zoom_x), order=0) > 0.5

    # --- Estimate ground level and filter to elevated roof ---
    roof_heights = dsm_data[bm]
    if len(roof_heights) == 0:
        logger.warning("No DSM pixels under building mask")
        return []

    # Ground level: look at pixels just outside the building mask
    from scipy.ndimage import binary_dilation
    ring = binary_dilation(bm, iterations=5) & ~bm
    ground_pixels = dsm_data[ring]
    if len(ground_pixels) > 0:
        ground_level = float(np.median(ground_pixels))
    else:
        ground_level = float(np.percentile(roof_heights, 5))

    height_above_ground = dsm_data - ground_level
    elevated = (height_above_ground > 2.0) & bm   # >2 m above ground

    if elevated.sum() < 20:
        logger.warning("Too few elevated roof pixels (%d)", elevated.sum())
        return []

    # --- Smooth DSM and compute gradient ---
    dsm_smooth = gaussian_filter(dsm_data.astype(np.float64), sigma=3)
    res = dsm.resolution  # meters per pixel

    # Gradient: dz/dx and dz/dy
    dz_dy, dz_dx = np.gradient(dsm_smooth, res, res)  # in m/m

    slope_rad = np.arctan(np.sqrt(dz_dx**2 + dz_dy**2))
    slope_deg = np.degrees(slope_rad)

    # Aspect: angle clockwise from north
    # np.arctan2(-dz_dy, dz_dx) gives angle from east, CCW positive
    # Convert to compass bearing (clockwise from north)
    aspect_rad = np.arctan2(-dz_dx, dz_dy)  # dz_dy points "south" in image coords
    aspect_deg = np.degrees(aspect_rad) % 360

    # --- Classify pixels by aspect direction ---
    direction_map = np.zeros(dsm_data.shape, dtype=np.int32)
    for idx, (name, lo, hi) in enumerate(_DIRECTION_BINS, start=1):
        in_bin = (aspect_deg >= lo) & (aspect_deg < hi)
        direction_map[in_bin] = idx

    # Merge the two "N" bins (idx 1 and 5)
    direction_map[direction_map == 5] = 1

    # Label connected components *within* each direction class on the roof
    faces: List[_RawFace] = []
    face_id = 0

    # Unique direction indices present on elevated roof
    dir_values = np.unique(direction_map[elevated])

    for dv in dir_values:
        if dv == 0:
            continue

        class_mask = (direction_map == dv) & elevated

        # Connected components within this direction class
        sub_labels, n_sub = ndimage_label(class_mask)
        for sub_id in range(1, n_sub + 1):
            px_mask = sub_labels == sub_id
            n_px = int(px_mask.sum())
            if n_px < 30:
                continue  # skip tiny fragments (<0.3 m^2)

            area_m2 = n_px * res * res
            area_sqft = area_m2 * _SQFT_PER_M2

            avg_pitch = float(slope_deg[px_mask].mean())
            avg_azimuth = float(_circular_mean(aspect_deg[px_mask]))

            # Direction label
            direction_label = _azimuth_to_label(avg_azimuth)

            # Extract polygon outline
            pixel_coords = _mask_to_contour_coords(px_mask)
            if not pixel_coords:
                continue
            pixel_coords = _simplify_pixel_contour(pixel_coords, tolerance=2.0)

            poly_m = []
            for col, row in pixel_coords:
                x, y = dsm.pixel_to_xy(row, col)
                poly_m.append((x, y))

            if len(poly_m) < 3:
                continue

            faces.append(_RawFace(
                pixels=px_mask,
                area_m2=area_m2,
                area_sqft=area_sqft,
                avg_pitch_deg=avg_pitch,
                avg_azimuth_deg=avg_azimuth,
                label=f"Roof-{face_id + 1} ({direction_label})",
                polygon_m=poly_m,
            ))
            face_id += 1

    # --- Merge small fragments into nearby larger faces ---
    faces = _merge_similar_faces(faces, dsm, elevated, slope_deg, aspect_deg, res)

    # Sort by area descending
    faces.sort(key=lambda f: f.area_m2, reverse=True)

    logger.info("Segmented %d roof faces from DSM gradient (after merge)", len(faces))
    for f in faces[:6]:
        logger.info("  %s: %.0f sqft, pitch=%.1f deg, azimuth=%.1f deg",
                    f.label, f.area_sqft, f.avg_pitch_deg, f.avg_azimuth_deg)

    return faces


def _merge_similar_faces(
    faces: list,
    dsm: '_GeoTiff',
    elevated: np.ndarray,
    slope_deg: np.ndarray,
    aspect_deg: np.ndarray,
    res: float,
) -> list:
    """Merge roof face fragments that have similar aspect/pitch into clean segments.

    Strategy:
    1. Group faces by compass direction (N/E/S/W)
    2. Within each group, merge faces with similar average azimuth (within 30°)
       and similar pitch (within 15°)
    3. Small faces (<50 sqft) get absorbed into the nearest large face
    4. Result: typically 2-6 clean roof faces instead of 100+
    """
    if len(faces) <= 4:
        return faces

    # Step 1: Group by general direction
    direction_groups: Dict[str, list] = {}
    for f in faces:
        d = _azimuth_to_label(f.avg_azimuth_deg)
        # Simplify to 4 cardinal directions
        simple = {"N": "N", "NE": "E", "E": "E", "SE": "S",
                  "S": "S", "SW": "W", "W": "W", "NW": "N"}.get(d, "S")
        direction_groups.setdefault(simple, []).append(f)

    # Step 2: Within each direction, merge faces with similar azimuth and pitch
    merged: list = []
    for direction, group in direction_groups.items():
        if not group:
            continue

        # Sort by area (largest first)
        group.sort(key=lambda f: f.area_m2, reverse=True)

        # Cluster: each face joins the first existing cluster within thresholds
        clusters: list = []  # list of lists of faces
        for face in group:
            joined = False
            for cluster in clusters:
                ref = cluster[0]  # compare to largest face in cluster
                az_diff = abs(face.avg_azimuth_deg - ref.avg_azimuth_deg)
                if az_diff > 180:
                    az_diff = 360 - az_diff
                pitch_diff = abs(face.avg_pitch_deg - ref.avg_pitch_deg)

                if az_diff < 30 and pitch_diff < 15:
                    cluster.append(face)
                    joined = True
                    break

            if not joined:
                clusters.append([face])

        # Step 3: Merge each cluster into one face
        for cluster in clusters:
            if not cluster:
                continue

            # Combine all pixel masks
            combined_pixels = cluster[0].pixels.copy()
            total_area_m2 = cluster[0].area_m2
            for f in cluster[1:]:
                combined_pixels = combined_pixels | f.pixels
                total_area_m2 += f.area_m2

            # Recompute stats from combined mask
            total_area_sqft = total_area_m2 * _SQFT_PER_M2
            avg_pitch = float(slope_deg[combined_pixels].mean())
            avg_azimuth = float(_circular_mean(aspect_deg[combined_pixels]))
            direction_label = _azimuth_to_label(avg_azimuth)

            # Extract contour from combined mask
            pixel_coords = _mask_to_contour_coords(combined_pixels)
            if not pixel_coords:
                # Use the largest face's polygon as fallback
                pixel_coords = _mask_to_contour_coords(cluster[0].pixels)
                if not pixel_coords:
                    continue
            pixel_coords = _simplify_pixel_contour(pixel_coords, tolerance=3.0)

            poly_m = []
            for col, row in pixel_coords:
                x, y = dsm.pixel_to_xy(row, col)
                poly_m.append((x, y))

            if len(poly_m) < 3:
                continue

            merged.append(_RawFace(
                pixels=combined_pixels,
                area_m2=total_area_m2,
                area_sqft=total_area_sqft,
                avg_pitch_deg=avg_pitch,
                avg_azimuth_deg=avg_azimuth,
                label=f"Roof ({direction_label})",
                polygon_m=poly_m,
            ))

    # Step 4: Filter out tiny faces (<50 sqft) and steep faces (>45° pitch = walls/edges)
    # Also filter very flat (<5° pitch) which are flat roof sections unlikely to have tilted panels
    merged = [f for f in merged if f.area_sqft >= 50 and 5 <= f.avg_pitch_deg <= 45]

    # Relabel
    for i, f in enumerate(merged):
        f.label = f"Roof-{i+1} ({_azimuth_to_label(f.avg_azimuth_deg)})"

    logger.info("Merged %d fragments → %d clean faces", len(faces), len(merged))
    return merged


def _circular_mean(angles_deg: np.ndarray) -> float:
    """Compute circular mean of angles in degrees."""
    rads = np.radians(angles_deg)
    mean_sin = np.sin(rads).mean()
    mean_cos = np.cos(rads).mean()
    return float(np.degrees(np.arctan2(mean_sin, mean_cos))) % 360


def _azimuth_to_label(az: float) -> str:
    """Convert azimuth to a compass label."""
    dirs = [
        (0, "N"), (45, "NE"), (90, "E"), (135, "SE"),
        (180, "S"), (225, "SW"), (270, "W"), (315, "NW"), (360, "N"),
    ]
    for deg, lbl in dirs:
        if abs(az - deg) <= 22.5:
            return lbl
    return "S"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def get_roof_faces_from_geotiff(
    lat: float,
    lng: float,
    api_key: Optional[str] = None,
    page_width: int = _PAGE_WIDTH,
    page_height: int = _PAGE_HEIGHT,
) -> Tuple[List, float]:
    """Download GeoTIFF layers, segment roof, return RoofFace list + scale.

    Returns:
        (roof_faces, pts_per_ft) — same interface as
        solar_insight_to_roof_faces() in google_solar.py.
    """
    from roof_detector import RoofFace

    api_key = api_key or os.environ.get("GOOGLE_SOLAR_API_KEY", "")
    if not api_key:
        raise ValueError("No Google Solar API key provided")

    # 1. Fetch data layer URLs
    layers = _fetch_data_layers(lat, lng, api_key)
    mask_url = layers.get("maskUrl", "")
    dsm_url = layers.get("dsmUrl", "")
    if not mask_url or not dsm_url:
        raise RuntimeError(
            f"dataLayers response missing maskUrl or dsmUrl: "
            f"keys={list(layers.keys())}"
        )

    # 2. Download and parse GeoTIFFs
    mask_tiff = _parse_geotiff(_download_geotiff(mask_url, api_key))
    dsm_tiff = _parse_geotiff(_download_geotiff(dsm_url, api_key))
    logger.info("Mask: %s, shape=%s, res=%.3f m/px",
                mask_tiff.crs, mask_tiff.data.shape, mask_tiff.resolution)
    logger.info("DSM:  %s, shape=%s, res=%.3f m/px",
                dsm_tiff.crs, dsm_tiff.data.shape, dsm_tiff.resolution)

    # 3. Isolate the target building
    building_mask = _isolate_building(mask_tiff, lat, lng)
    if building_mask.sum() < 20:
        logger.error("Could not isolate building from mask")
        return [], 1.0

    # 4. Segment roof faces
    raw_faces = _segment_roof_faces(dsm_tiff, building_mask, mask_tiff)
    if not raw_faces:
        logger.error("No roof faces segmented from DSM")
        return [], 1.0

    # 5. Convert to page-coordinate RoofFace objects
    #    Build a bounding box of all face polygons (in meters), then
    #    compute a scale so the building fills ~55% of the page.
    all_xs = []
    all_ys = []
    for f in raw_faces:
        for x, y in f.polygon_m:
            all_xs.append(x)
            all_ys.append(y)

    min_x_m, max_x_m = min(all_xs), max(all_xs)
    min_y_m, max_y_m = min(all_ys), max(all_ys)
    building_w_m = max_x_m - min_x_m
    building_h_m = max_y_m - min_y_m

    # Avoid division by zero
    building_w_m = max(building_w_m, 1.0)
    building_h_m = max(building_h_m, 1.0)

    building_w_ft = building_w_m * _FT_PER_M
    building_h_ft = building_h_m * _FT_PER_M

    usable_w = page_width * 0.55
    usable_h = page_height * 0.55
    pts_per_ft = min(usable_w / building_w_ft, usable_h / building_h_ft)

    cx_page = page_width / 2
    cy_page = page_height / 2
    cx_m = (min_x_m + max_x_m) / 2
    cy_m = (min_y_m + max_y_m) / 2

    roof_faces: List[RoofFace] = []

    for idx, face in enumerate(raw_faces):
        # Convert polygon from CRS meters to page points
        page_coords = []
        for x_m, y_m in face.polygon_m:
            dx_ft = (x_m - cx_m) * _FT_PER_M
            dy_ft = (y_m - cy_m) * _FT_PER_M
            px = cx_page + dx_ft * pts_per_ft
            py = cy_page - dy_ft * pts_per_ft   # y-axis flipped for page coords
            page_coords.append((px, py))

        if len(page_coords) < 3:
            continue

        poly = Polygon(page_coords)
        if not poly.is_valid:
            poly = poly.buffer(0)

        # Setback inset (3 ft)
        setback_pts = 3.0 * pts_per_ft
        usable = poly.buffer(-setback_pts)
        if usable.is_empty or usable.area < 100:
            usable = poly.buffer(-pts_per_ft)
        if usable.is_empty:
            usable = poly

        if isinstance(usable, MultiPolygon):
            usable = max(usable.geoms, key=lambda g: g.area)

        usable_sqft = usable.area / (pts_per_ft ** 2)

        rf = RoofFace(
            id=idx,
            polygon=poly,
            area_sqft=round(face.area_sqft, 1),
            pitch_deg=round(face.avg_pitch_deg, 1),
            azimuth_deg=round(face.avg_azimuth_deg, 1),
            usable_area_sqft=round(usable_sqft, 1),
            label=face.label,
            detection_method="geotiff_dsm",
            usable_polygon=usable,
        )
        roof_faces.append(rf)

    logger.info("Returning %d RoofFace objects, scale=%.3f pts/ft",
                len(roof_faces), pts_per_ft)
    return roof_faces, pts_per_ft


def get_building_outline(
    lat: float,
    lng: float,
    api_key: Optional[str] = None,
) -> List[Tuple[float, float]]:
    """Return building outline as (x_ft, y_ft) coordinates for property plan.

    Origin is at the building centroid.
    """
    api_key = api_key or os.environ.get("GOOGLE_SOLAR_API_KEY", "")
    if not api_key:
        raise ValueError("No Google Solar API key provided")

    layers = _fetch_data_layers(lat, lng, api_key)
    mask_url = layers.get("maskUrl", "")
    if not mask_url:
        raise RuntimeError("dataLayers response missing maskUrl")

    mask_tiff = _parse_geotiff(_download_geotiff(mask_url, api_key))
    building_mask = _isolate_building(mask_tiff, lat, lng)

    if building_mask.sum() < 20:
        logger.error("Could not isolate building from mask for outline")
        return []

    outline_m = _extract_outline(building_mask, mask_tiff)
    if not outline_m:
        return []

    # Convert to feet relative to centroid
    xs = [p[0] for p in outline_m]
    ys = [p[1] for p in outline_m]
    cx = sum(xs) / len(xs)
    cy = sum(ys) / len(ys)

    outline_ft = [
        ((x - cx) * _FT_PER_M, (y - cy) * _FT_PER_M)
        for x, y in outline_m
    ]
    return outline_ft


# ---------------------------------------------------------------------------
# CLI quick test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(levelname)s %(name)s: %(message)s")

    test_lat = 34.1578
    test_lng = -118.4956
    key = os.environ.get("GOOGLE_SOLAR_API_KEY", "")

    if not key:
        print("Set GOOGLE_SOLAR_API_KEY environment variable to run test")
    else:
        print(f"Testing with lat={test_lat}, lng={test_lng}")
        print("  (17001 Escalon Dr, Encino CA)")
        print()

        faces, scale = get_roof_faces_from_geotiff(test_lat, test_lng, key)
        print(f"Scale: {scale:.3f} pts/ft")
        print(f"Found {len(faces)} roof faces:")
        for f in faces:
            print(f"  {f.label}: {f.area_sqft:.0f} sqft, "
                  f"pitch={f.pitch_deg:.1f} deg, "
                  f"azimuth={f.azimuth_deg:.1f} deg "
                  f"({f.azimuth_label}-facing)")

        print()
        outline = get_building_outline(test_lat, test_lng, key)
        print(f"Building outline: {len(outline)} vertices")
        if outline:
            xs = [p[0] for p in outline]
            ys = [p[1] for p in outline]
            w = max(xs) - min(xs)
            h = max(ys) - min(ys)
            print(f"  Footprint: {w:.1f} ft x {h:.1f} ft")
