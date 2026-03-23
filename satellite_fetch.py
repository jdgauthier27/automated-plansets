"""
satellite_fetch.py — Google Map Tiles API satellite imagery fetcher.

Replaces the Static Maps API approach with the Map Tiles API, which gives
pixel-precise control over centering and supports stitching multiple tiles.

Usage:
    from satellite_fetch import fetch_satellite_mosaic

    img_array = fetch_satellite_mosaic(
        lat=45.498548, lng=-75.803043,
        api_key="...",
        zoom=20,
        out_w=1280, out_h=960,
    )
    # → numpy H×W×3 uint8 RGB, centered exactly on (lat, lng)

Coordinates returned:
    The center pixel of the returned image corresponds exactly to (lat, lng).
    All mpp / _latlng_to_pixel calls in html_renderer.py continue to work
    correctly as long as the same (lat, lng) is used as the reference.
"""

from __future__ import annotations

import io
import json
import logging
import math
import urllib.request
from typing import Tuple

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

TILE_PX = 256  # Google tile size in pixels


# ── Coordinate helpers ────────────────────────────────────────────────────────

def lat_lng_to_tile(lat: float, lng: float, zoom: int) -> Tuple[int, int]:
    """Return (tile_x, tile_y) for the tile containing (lat, lng) at *zoom*."""
    n = 2 ** zoom
    tx = int((lng + 180.0) / 360.0 * n)
    lat_r = math.radians(lat)
    ty = int((1.0 - math.asinh(math.tan(lat_r)) / math.pi) / 2.0 * n)
    return tx, ty


def lat_lng_to_pixel(lat: float, lng: float, zoom: int) -> Tuple[float, float]:
    """
    Return the fractional pixel position (px, py) in the *global* tile-space
    at *zoom*.  The global canvas is (2^zoom × TILE_PX) pixels wide/tall.
    """
    n = 2 ** zoom
    total_px = n * TILE_PX
    px = (lng + 180.0) / 360.0 * total_px
    lat_r = math.radians(lat)
    py = (1.0 - math.asinh(math.tan(lat_r)) / math.pi) / 2.0 * total_px
    return px, py


# ── Session management ────────────────────────────────────────────────────────

def _create_session(api_key: str) -> str:
    """Create a Map Tiles API session and return the session token."""
    url = f"https://tile.googleapis.com/v1/createSession?key={api_key}"
    body = json.dumps(
        {"mapType": "satellite", "language": "en-US", "region": "CA"}
    ).encode()
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode())
    token = data.get("session", "")
    if not token:
        raise RuntimeError(f"Map Tiles session creation failed: {data}")
    logger.debug("Map Tiles session created (first 20): %s…", token[:20])
    return token


# ── Tile fetcher ──────────────────────────────────────────────────────────────

def _fetch_tile(tx: int, ty: int, zoom: int, session: str, api_key: str) -> np.ndarray:
    """Fetch a single 256×256 tile and return as H×W×3 uint8 RGB array."""
    url = (
        f"https://tile.googleapis.com/v1/2dtiles/{zoom}/{tx}/{ty}"
        f"?session={session}&key={api_key}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Quebec-Solaire/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = resp.read()
    return np.array(Image.open(io.BytesIO(data)).convert("RGB"))


# ── Main public function ──────────────────────────────────────────────────────

def fetch_satellite_mosaic(
    lat: float,
    lng: float,
    api_key: str,
    zoom: int = 20,
    out_w: int = 1280,
    out_h: int = 960,
) -> np.ndarray:
    """
    Fetch a satellite mosaic centered *exactly* on (lat, lng).

    Steps:
      1. Create a Map Tiles session.
      2. Compute which tiles cover (out_w × out_h) pixels centred on (lat, lng).
      3. Fetch and stitch those tiles into one large canvas.
      4. Crop the canvas to (out_w × out_h) with (lat, lng) at the centre pixel.

    Returns
    -------
    numpy.ndarray  — shape (out_h, out_w, 3), dtype uint8, RGB
    """
    session = _create_session(api_key)

    # Global pixel position of the centre point
    cx_global, cy_global = lat_lng_to_pixel(lat, lng, zoom)

    # Which tiles do we need?
    # We need tiles whose combined area covers [cx - out_w/2, cx + out_w/2]
    # and [cy - out_h/2, cy + out_h/2] in global pixel space.
    half_w = out_w / 2.0
    half_h = out_h / 2.0

    tile_x_min = int(math.floor((cx_global - half_w) / TILE_PX))
    tile_x_max = int(math.floor((cx_global + half_w) / TILE_PX))
    tile_y_min = int(math.floor((cy_global - half_h) / TILE_PX))
    tile_y_max = int(math.floor((cy_global + half_h) / TILE_PX))

    n_tiles_x = tile_x_max - tile_x_min + 1
    n_tiles_y = tile_y_max - tile_y_min + 1
    canvas_w = n_tiles_x * TILE_PX
    canvas_h = n_tiles_y * TILE_PX

    logger.info(
        "Fetching %d×%d tile grid at zoom %d (%.6f, %.6f)",
        n_tiles_x, n_tiles_y, zoom, lat, lng,
    )

    # Build canvas
    canvas = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)
    total = n_tiles_x * n_tiles_y
    fetched = 0
    for row, ty in enumerate(range(tile_y_min, tile_y_max + 1)):
        for col, tx in enumerate(range(tile_x_min, tile_x_max + 1)):
            tile = _fetch_tile(tx, ty, zoom, session, api_key)
            y0 = row * TILE_PX
            x0 = col * TILE_PX
            canvas[y0:y0 + TILE_PX, x0:x0 + TILE_PX] = tile
            fetched += 1

    logger.info("Stitched %d/%d tiles → canvas %dx%d", fetched, total, canvas_w, canvas_h)

    # Crop: the top-left corner of the canvas in global pixels
    canvas_origin_x = tile_x_min * TILE_PX
    canvas_origin_y = tile_y_min * TILE_PX

    # Position of (lat, lng) within the canvas
    cx_canvas = cx_global - canvas_origin_x
    cy_canvas = cy_global - canvas_origin_y

    # Crop window centred on (cx_canvas, cy_canvas)
    x0 = int(round(cx_canvas - half_w))
    y0 = int(round(cy_canvas - half_h))
    x1 = x0 + out_w
    y1 = y0 + out_h

    # Clamp (shouldn't happen if tile grid was computed correctly)
    x0 = max(0, x0)
    y0 = max(0, y0)
    x1 = min(canvas_w, x1)
    y1 = min(canvas_h, y1)

    result = canvas[y0:y1, x0:x1]

    # Pad if the crop landed outside the canvas (edge case)
    if result.shape != (out_h, out_w, 3):
        padded = np.zeros((out_h, out_w, 3), dtype=np.uint8)
        h, w = result.shape[:2]
        padded[:h, :w] = result
        result = padded

    logger.info("Final mosaic: %s", result.shape)
    return result
