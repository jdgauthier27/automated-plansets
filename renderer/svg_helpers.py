"""
Shared SVG utilities for the planset renderer.
================================================

Provides:
  - COLORS dict        — professional engineering-drawing color palette
  - PAGE constants     — standard page dimensions
  - svg_page_wrapper() — wraps SVG content in a <div class="page"> container
  - extract_municipality() / make_ahj_label() — address helpers
  - image_to_b64()     — numpy array to base64 PNG
  - azimuth_label()    — degrees to compass direction
"""

import base64
import io
from typing import Tuple

import numpy as np
from PIL import Image

# ── Standard page dimensions (11 x 8.5" landscape at screen resolution) ────

PAGE_WIDTH = 1280
PAGE_HEIGHT = 960


# ── Professional color palette (engineering drawing standard) ───────────────

COLORS = {
    # Paper and text
    "paper_bg": "#ffffff",
    "paper_border": "#000000",
    "text_primary": "#000000",
    "text_secondary": "#333333",
    "text_light": "#666666",
    # Panels on satellite (realistic)
    "panel_fill": "#0c1a2e",  # dark navy
    "panel_cell_grid": "rgba(30,58,138,0.3)",  # dark blue grid
    "panel_frame": "rgba(160,175,195,0.55)",  # silver aluminum
    # Vector drawing
    "roof_outline": "#000000",
    "setback_line": "#cc0000",
    "dimension_line": "#444444",
    "dimension_text": "#222222",
    "grid_light": "#f0f0f0",
    "grid_medium": "#d8d8d8",
    # Electrical
    "wire_dc": "#0066cc",
    "wire_ac": "#cc0000",
    "wire_ground": "#00aa00",
    "inverter": "#e8e8e8",
    "breaker": "#f0f0f0",
    # Wiring (string plan)
    "string_1": "#0066cc",
    "string_2": "#ff6600",
    "string_3": "#00aa00",
    "string_4": "#aa00aa",
    "string_5": "#ffaa00",
}


# ── SVG page wrapper ───────────────────────────────────────────────────────


def svg_page_wrapper(
    svg_content: str,
    vw: int = PAGE_WIDTH,
    vh: int = PAGE_HEIGHT,
    bg: str = "#fff",
) -> str:
    """Wrap raw SVG elements in a standard page container.

    Returns an HTML string: ``<div class="page"><svg ...>content</svg></div>``
    """
    return (
        f'<div class="page">'
        f'<svg width="100%" height="100%" viewBox="0 0 {vw} {vh}" '
        f'xmlns="http://www.w3.org/2000/svg" style="background:{bg};">'
        f"{svg_content}"
        f"</svg></div>"
    )


# ── Address / AHJ helpers ──────────────────────────────────────────────────


def extract_municipality(address: str) -> str:
    """Extract the municipality name from a comma-separated address string.

    Examples:
      "34 rue Bernier, Gatineau, QC J8Z 1E8"  ->  "Gatineau"
      "42 Ch. de Charlotte, Chelsea, QC J9B 2E7" ->  "Chelsea"
      "123 Main St"  ->  "Quebec"  (fallback)
    """
    parts = [p.strip() for p in address.split(",")]
    if len(parts) >= 2:
        city = parts[1].strip()
        # Remove any postal code that accidentally ends up in this segment
        city = city.split(" ")[0] if city else city
        if city:
            return city
    return "Québec"


def make_ahj_label(address: str) -> str:
    """Return the AHJ label string for a given address.

    Returns: "Ville de {Municipality} / RBQ"
    (Regie du batiment du Quebec is the provincial AHJ for electrical)
    """
    city = extract_municipality(address)
    return f"Ville de {city} / RBQ"


# ── Image / geometry utilities ──────────────────────────────────────────────


def image_to_b64(img_array: np.ndarray) -> str:
    """Convert a numpy image array to a base64-encoded PNG string."""
    img = Image.fromarray(img_array)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def azimuth_label(az: float) -> str:
    """Convert azimuth degrees to a compass direction string."""
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
        if abs(az - deg) <= 22.5:
            return lbl
    return "S"
