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


def wire_gauge(amps: float) -> str:
    """Return AWG wire gauge string for given ampacity.

    Shared utility — replaces duplicated inline ``_wire_gauge`` helpers
    in several page builders.
    """
    if amps <= 15:
        return "#14 AWG"
    if amps <= 20:
        return "#12 AWG"
    if amps <= 30:
        return "#10 AWG"
    if amps <= 40:
        return "#8 AWG"
    if amps <= 55:
        return "#6 AWG"
    if amps <= 70:
        return "#4 AWG"
    return "#2 AWG"


def svg_page_frame(svg: list, vw: int = PAGE_WIDTH, vh: int = PAGE_HEIGHT,
                   border: int = 20) -> None:
    """Append the standard white-background + border rect pair to *svg*.

    Nearly every SVG page builder starts with this identical boilerplate.
    """
    svg.append(f'<rect width="{vw}" height="{vh}" fill="#ffffff"/>')
    svg.append(
        f'<rect x="{border}" y="{border}" '
        f'width="{vw - 2 * border}" height="{vh - 2 * border}" '
        f'fill="none" stroke="#000" stroke-width="2"/>'
    )


def svg_arrow_marker_defs() -> str:
    """Return SVG ``<defs>`` block with dimension-line arrow markers.

    The markers are used in site plans, racking plans, and detail sheets.
    Include once per SVG page that needs dimension arrows.
    """
    return (
        '<defs>'
        '  <marker id="dim-arrow-l" markerWidth="8" markerHeight="6" refX="0" refY="3" orient="auto">'
        '    <polygon points="0,3 8,0 8,6" fill="#000"/>'
        '  </marker>'
        '  <marker id="dim-arrow-r" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">'
        '    <polygon points="8,3 0,0 0,6" fill="#000"/>'
        '  </marker>'
        '</defs>'
    )


def dim_h(x1: float, x2: float, y: float, lbl: str,
           gap: int = -14, color: str = "#222") -> str:
    """Return SVG for a horizontal dimension line with label.

    Draws a horizontal line between *(x1, y)* and *(x2, y)* with tick marks
    at each end, arrowhead polygons, a white-background label rect, and the
    label text centred above/below the line.
    """
    mx = (x1 + x2) // 2
    return (
        f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" stroke="{color}" stroke-width="0.8"/>'
        f'<line x1="{x1}" y1="{y - 5}" x2="{x1}" y2="{y + 5}" stroke="{color}" stroke-width="0.8"/>'
        f'<line x1="{x2}" y1="{y - 5}" x2="{x2}" y2="{y + 5}" stroke="{color}" stroke-width="0.8"/>'
        f'<polygon points="{x1},{y} {x1 + 9},{y - 3} {x1 + 9},{y + 3}" fill="{color}"/>'
        f'<polygon points="{x2},{y} {x2 - 9},{y - 3} {x2 - 9},{y + 3}" fill="{color}"/>'
        f'<rect x="{mx - 24}" y="{y + gap - 7}" width="48" height="10" fill="#fff"/>'
        f'<text x="{mx}" y="{y + gap}" text-anchor="middle" '
        f'font-size="9" font-family="Arial" fill="{color}">{lbl}</text>'
    )


def dim_v(x: float, y1: float, y2: float, lbl: str,
           gap: int = -14, color: str = "#222") -> str:
    """Return SVG for a vertical dimension line with label (rotated text)."""
    my = (y1 + y2) // 2
    return (
        f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{y2}" stroke="{color}" stroke-width="0.8"/>'
        f'<line x1="{x - 5}" y1="{y1}" x2="{x + 5}" y2="{y1}" stroke="{color}" stroke-width="0.8"/>'
        f'<line x1="{x - 5}" y1="{y2}" x2="{x + 5}" y2="{y2}" stroke="{color}" stroke-width="0.8"/>'
        f'<polygon points="{x},{y1} {x - 3},{y1 + 9} {x + 3},{y1 + 9}" fill="{color}"/>'
        f'<polygon points="{x},{y2} {x - 3},{y2 - 9} {x + 3},{y2 - 9}" fill="{color}"/>'
        f'<rect x="{x + gap - 24}" y="{my - 7}" width="48" height="12" fill="#fff"/>'
        f'<text x="{x + gap}" y="{my + 3}" text-anchor="middle" dominant-baseline="middle" '
        f'font-size="9" font-family="Arial" fill="{color}" '
        f'transform="rotate(-90,{x + gap},{my})">{lbl}</text>'
    )


def ft_in(ft_val: float) -> str:
    """Convert decimal feet to a feet-inches string like ``5'-6\"``."""
    feet = int(ft_val)
    inches = round((ft_val - feet) * 12)
    if inches == 12:
        feet += 1
        inches = 0
    return f"{feet}'-{inches}\""


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
