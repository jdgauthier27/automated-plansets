"""
Terrain Mesh Builder
====================
Converts DSM GeoTIFF elevation grid + satellite imagery into terrain data
for THREE.js 3D viewer. Replicates OpenSolar's OsTerrain approach:
a BufferGeometry mesh textured with satellite imagery.

The heightmap is sent as JSON, the satellite image as JPEG.
THREE.js constructs the BufferGeometry in the browser.
"""

import logging
import math
from typing import Dict, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


def build_terrain_data(
    dsm_data,  # DSMData from dsm_processor
    center_lat: float,
    center_lng: float,
    radius_m: float = 50.0,
    grid_size: int = 200,
) -> Optional[Dict]:
    """Build terrain mesh data from DSM elevation grid.

    Args:
        dsm_data: DSMData with heights array and geographic bounds.
        center_lat, center_lng: Building center coordinates.
        radius_m: Half-width of terrain area in meters (default 50m = 100m×100m).
        grid_size: Output grid resolution (default 200×200 = 40K vertices).

    Returns:
        Dict with heightmap grid, bounds, and metadata for THREE.js.
    """
    if dsm_data is None or dsm_data.heights is None:
        return None

    heights = dsm_data.heights
    src_h, src_w = heights.shape
    min_lng, min_lat, max_lng, max_lat = dsm_data.bounds

    # Compute crop bounds in geographic coords (center ± radius_m)
    cos_lat = math.cos(math.radians(center_lat))
    dlat = radius_m / 111319.0
    dlng = radius_m / (111319.0 * cos_lat)

    crop_min_lat = center_lat - dlat
    crop_max_lat = center_lat + dlat
    crop_min_lng = center_lng - dlng
    crop_max_lng = center_lng + dlng

    # Clamp to DSM bounds
    crop_min_lat = max(crop_min_lat, min_lat)
    crop_max_lat = min(crop_max_lat, max_lat)
    crop_min_lng = max(crop_min_lng, min_lng)
    crop_max_lng = min(crop_max_lng, max_lng)

    # Convert geographic crop bounds to pixel coords
    def geo_to_pixel(lat, lng):
        px = int((lng - min_lng) / (max_lng - min_lng) * src_w)
        py = int((max_lat - lat) / (max_lat - min_lat) * src_h)
        return max(0, min(src_w - 1, px)), max(0, min(src_h - 1, py))

    px0, py0 = geo_to_pixel(crop_max_lat, crop_min_lng)  # top-left
    px1, py1 = geo_to_pixel(crop_min_lat, crop_max_lng)  # bottom-right

    # Ensure we have a valid crop region
    if px1 <= px0 or py1 <= py0:
        logger.warning("Invalid crop region: (%d,%d) to (%d,%d)", px0, py0, px1, py1)
        return None

    # Crop the height grid
    cropped = heights[py0:py1, px0:px1]
    crop_h, crop_w = cropped.shape

    if crop_h < 2 or crop_w < 2:
        logger.warning("Cropped DSM too small: %dx%d", crop_w, crop_h)
        return None

    # Downsample to target grid size using bilinear interpolation
    from scipy.ndimage import zoom as scipy_zoom

    scale_y = grid_size / crop_h
    scale_x = grid_size / crop_w
    grid = scipy_zoom(cropped, (scale_y, scale_x), order=1)  # bilinear

    # Replace NaN/invalid values with ground estimate
    valid_mask = np.isfinite(grid) & (grid > 0)
    if valid_mask.any():
        ground_est = float(np.percentile(grid[valid_mask], 10))
    else:
        ground_est = 0.0
    grid[~valid_mask] = ground_est

    # Compute ground elevation (10th percentile = typical ground level)
    ground_elevation = float(np.percentile(grid[valid_mask], 10)) if valid_mask.any() else 0.0

    # Normalize: subtract ground so ground=0, roof=building_height
    grid_normalized = grid - ground_elevation

    # Clamp extreme spikes (trees, poles, DSM artifacts) to max 12m above ground
    # Typical 2-story building is ~8m; anything above 12m is likely a tree/artifact
    max_height = 12.0
    grid_normalized = np.clip(grid_normalized, -1.0, max_height)

    # Smoothing pass to reduce sharp DSM edges (building walls, tree spikes)
    # The DSM is 2.5D — building edges create near-vertical triangles that look
    # like floating fragments. Smoothing rounds these transitions.
    # sigma=1.5 at 200px grid ≈ 0.75m spatial smoothing — preserves roof shape
    from scipy.ndimage import gaussian_filter

    grid_normalized = gaussian_filter(grid_normalized, sigma=1.5)

    logger.info(
        "Terrain mesh: %dx%d grid, ground=%.1fm, range=[%.1f, %.1f]m above ground",
        grid_size,
        grid_size,
        ground_elevation,
        float(grid_normalized.min()),
        float(grid_normalized.max()),
    )

    # Convert to list of lists for JSON serialization (round to 2 decimal places)
    heightmap = np.round(grid_normalized, 2).tolist()

    return {
        "heightmap": heightmap,
        "gridSize": grid_size,
        "bounds": {
            "minLng": crop_min_lng,
            "minLat": crop_min_lat,
            "maxLng": crop_max_lng,
            "maxLat": crop_max_lat,
        },
        "groundElevation": round(ground_elevation, 2),
        "centerLat": center_lat,
        "centerLng": center_lng,
        "radiusM": radius_m,
        # Physical dimensions in meters for THREE.js PlaneGeometry sizing
        "widthM": round((crop_max_lng - crop_min_lng) * 111319.0 * cos_lat, 1),
        "heightM": round((crop_max_lat - crop_min_lat) * 111319.0, 1),
    }
