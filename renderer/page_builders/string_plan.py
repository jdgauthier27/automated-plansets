"""Page builder: String Plan (PV-7)
========================================
Extracted from HtmlRenderer._build_string_plan_page.
"""

import math
from typing import List


def build_string_plan_page(renderer, insight, total_panels: int, address: str, today: str) -> str:
    """PV-7: Microinverter & Circuit Map — Cubillas-standard clean professional layout.

    Layout (1280x960):
      Top-left: CIRCUIT DETAIL box (Cubillas format: white swatches + "CIRCUIT # N: M MODULES")
      Main area: Panel array rotated to roof azimuth, white panels, green circuit lines
      Circuit labels: horizontal labels with leader lines (outside rotation)
      Footer: FOR INSTALLER USE ONLY
      Bottom-right: Standard _svg_title_block
      Bottom-right: Standard _svg_title_block
    """
    VW, VH = 1280, 960
    BORDER = 20

    # ── Circuit assignment ─────────────────────────────────────────────
    # Max inverter units per branch circuit — from catalog or default
    n_panels = max(total_panels, 1)
    MAX_PER_CIRCUIT = renderer._max_per_branch

    if n_panels <= MAX_PER_CIRCUIT:
        circuit_sizes = [n_panels]
    else:
        n_circ = math.ceil(n_panels / MAX_PER_CIRCUIT)
        base = n_panels // n_circ
        rem = n_panels % n_circ
        circuit_sizes = [base + (1 if i < rem else 0) for i in range(n_circ)]
    # Note: with MAX_PER_CIRCUIT=7, 8+ panel systems naturally produce 2+ circuits.
    # No need to force-split; circuit sizes match PV-4 CIRCUIT-1/2 labels exactly.

    n_circuits = len(circuit_sizes)

    # ── Azimuth / rotation ─────────────────────────────────────────────
    azimuth = 175.0  # default: nearly south (Gatineau QC)
    if insight and insight.roof_segments:
        azimuth = insight.roof_segments[0].azimuth_deg
    # SVG rotation: azimuth − 180 so 180° (true south) = 0° (vertical column top-down)
    rot_deg = azimuth - 180.0

    # ── Panel / array dimensions ───────────────────────────────────────
    pw_m = renderer.panel.width_ft * 0.3048  # short side (portrait)
    ph_m = renderer.panel.height_ft * 0.3048  # long side (portrait)
    gap_m = 0.05  # 5 cm gap between panels in column
    col_gap_m = pw_m * 0.25  # gap between circuit columns

    # Array height = tallest column; width = all columns side-by-side
    max_rows = max(circuit_sizes)
    array_h_m = max_rows * ph_m + max(max_rows - 1, 0) * gap_m
    array_w_m = n_circuits * pw_m + max(n_circuits - 1, 0) * col_gap_m

    # Scale to fit array in 65% of vertical drawing space (leaving room for title/header)
    avail_h = VH - 130 - 60  # minus title block (130) + top margin (60)
    avail_w = VW * 0.55  # use ~55% of width for array (labels on right)
    px_per_m = min(avail_h * 0.65 / array_h_m, avail_w * 0.65 / array_w_m, 70.0)  # cap at 70 px/m

    pw_px = pw_m * px_per_m
    ph_px = ph_m * px_per_m
    gap_px = gap_m * px_per_m
    col_gap_px = col_gap_m * px_per_m

    # ── Drawing center (slightly left of page center to leave room for labels) ──
    draw_cx = VW * 0.46
    draw_cy = (60 + VH - 130) / 2  # vertically centered in drawing area

    # ── Pre-compute column layout in un-rotated space ──────────────────
    total_array_w_px = n_circuits * pw_px + max(n_circuits - 1, 0) * col_gap_px
    col_info: List[tuple] = []  # (col_x_left, col_y_top, col_height_px)
    for ci, sz in enumerate(circuit_sizes):
        col_x = draw_cx - total_array_w_px / 2 + ci * (pw_px + col_gap_px)
        col_h = sz * ph_px + max(sz - 1, 0) * gap_px
        col_y = draw_cy - col_h / 2
        col_info.append((col_x, col_y, col_h))

    # ── Rotation helper ────────────────────────────────────────────────
    _rot_rad = math.radians(rot_deg)
    _cos_r = math.cos(_rot_rad)
    _sin_r = math.sin(_rot_rad)

    def _rot(px: float, py: float):
        dx, dy = px - draw_cx, py - draw_cy
        return draw_cx + dx * _cos_r - dy * _sin_r, draw_cy + dx * _sin_r + dy * _cos_r

    # ── SVG pieces ────────────────────────────────────────────────────
    svg: List[str] = []

    # ── Defs: arrowhead marker ─────────────────────────────────────────
    svg.append("<defs>")
    svg.append(
        '<marker id="pv7arr" markerWidth="8" markerHeight="6" '
        'refX="0" refY="3" orient="auto" markerUnits="strokeWidth">'
        '<path d="M0,0 L0,6 L8,3 z" fill="#000"/></marker>'
    )
    svg.append("</defs>")

    # ── White background + engineering border ─────────────────────────
    svg.append(f'<rect width="{VW}" height="{VH}" fill="#ffffff"/>')

    svg.append(
        f'<rect x="{BORDER}" y="{BORDER}" width="{VW - 2 * BORDER}" height="{VH - 2 * BORDER}" '
        f'fill="none" stroke="#000" stroke-width="1.5"/>'
    )

    # ── CIRCUIT DETAIL BOX (top-left) — Cubillas style ─────────────────
    # Format: gray header "CIRCUIT DETAIL", sub-header "ARRAY CIRCUITS",
    # one row per circuit: white panel swatch + green line + "CIRCUIT # N: M MODULES"
    cd_x, cd_y = BORDER + 15, BORDER + 15
    cd_w = 310
    cd_row_h = 50
    cd_h = 42 + n_circuits * cd_row_h

    # Outer box
    svg.append(
        f'<rect x="{cd_x}" y="{cd_y}" width="{cd_w}" height="{cd_h}" fill="#fff" stroke="#000" stroke-width="1.2"/>'
    )
    # Gray title header
    svg.append(
        f'<rect x="{cd_x}" y="{cd_y}" width="{cd_w}" height="22" fill="#d0d0d0" stroke="#000" stroke-width="0.8"/>'
    )
    svg.append(
        f'<text x="{cd_x + cd_w // 2}" y="{cd_y + 15}" text-anchor="middle" '
        f'font-size="12" font-weight="700" font-family="Arial" fill="#000">'
        f"CIRCUIT DETAIL</text>"
    )
    # Sub-header "ARRAY CIRCUITS"
    sub_y = cd_y + 22
    svg.append(
        f'<rect x="{cd_x}" y="{sub_y}" width="{cd_w}" height="20" fill="#ebebeb" stroke="#000" stroke-width="0.4"/>'
    )
    svg.append(
        f'<text x="{cd_x + cd_w // 2}" y="{sub_y + 14}" text-anchor="middle" '
        f'font-size="10" font-weight="700" font-family="Arial" fill="#000">'
        f"ARRAY CIRCUITS</text>"
    )

    # One row per circuit
    for ci, sz in enumerate(circuit_sizes):
        ry = cd_y + 42 + ci * cd_row_h
        bg = "#ffffff" if ci % 2 == 0 else "#f9f9f9"
        svg.append(
            f'<rect x="{cd_x}" y="{ry}" width="{cd_w}" height="{cd_row_h}" '
            f'fill="{bg}" stroke="#cccccc" stroke-width="0.5"/>'
        )
        # White panel swatch (Cubillas style: white rect with black border)
        sw, sh = 56, 36
        swatch_x = cd_x + 12
        swatch_y = ry + 7
        svg.append(
            f'<rect x="{swatch_x}" y="{swatch_y}" width="{sw}" height="{sh}" '
            f'fill="#ffffff" stroke="#000" stroke-width="1.5"/>'
        )
        # Green circuit line through swatch vertical center
        slx = swatch_x + sw // 2
        svg.append(
            f'<line x1="{slx}" y1="{swatch_y}" x2="{slx}" y2="{swatch_y + sh}" '
            f'stroke="#009900" stroke-width="2.0"/>'
        )
        # "CIRCUIT # N: M MODULES" label
        svg.append(
            f'<text x="{cd_x + 82}" y="{ry + cd_row_h // 2 + 5}" '
            f'font-size="13" font-weight="700" font-family="Arial" fill="#000">'
            f"CIRCUIT # {ci + 1}:  {sz} MODULES</text>"
        )

    # ── ROTATED PANEL ARRAY ────────────────────────────────────────────
    # All panels rendered inside a group rotated by (azimuth - 180°) around draw center.
    # This matches the Cubillas PV-7 style where the array is shown at the actual
    # roof orientation (north-up plan view).
    svg.append(f'<g transform="rotate({rot_deg:.1f},{draw_cx:.1f},{draw_cy:.1f})">')

    for ci, (col_x, col_y, col_h) in enumerate(col_info):
        sz = circuit_sizes[ci]

        # Green circuit trunk line (vertical, through horizontal center of column)
        lx = col_x + pw_px / 2
        svg.append(
            f'<line x1="{lx:.1f}" y1="{col_y - 8:.1f}" '
            f'x2="{lx:.1f}" y2="{col_y + col_h + 8:.1f}" '
            f'stroke="#009900" stroke-width="2.5" stroke-linecap="round"/>'
        )

        # Individual panels: white fill, black border
        for pi in range(sz):
            px = col_x
            py = col_y + pi * (ph_px + gap_px)
            svg.append(
                f'<rect x="{px:.1f}" y="{py:.1f}" '
                f'width="{pw_px:.1f}" height="{ph_px:.1f}" '
                f'fill="#ffffff" stroke="#000000" stroke-width="1.5"/>'
            )
            # Subtle mid-panel horizontal line (like cell grid in Cubillas)
            mid_y = py + ph_px * 0.5
            svg.append(
                f'<line x1="{px:.1f}" y1="{mid_y:.1f}" '
                f'x2="{px + pw_px:.1f}" y2="{mid_y:.1f}" '
                f'stroke="#cccccc" stroke-width="0.4"/>'
            )

    svg.append("</g>")  # end rotation group

    # ── CIRCUIT LABELS (horizontal text, outside rotation) ─────────────
    # For each circuit column: compute rotated center of column, draw leader line
    # and horizontal label to the right of the array.
    lbl_area_x = int(draw_cx + total_array_w_px * 0.7 + 80)
    lbl_area_x = min(lbl_area_x, VW - BORDER - 180)  # keep inside page

    for ci, (col_x, col_y, col_h) in enumerate(col_info):
        # Mid-point of right edge of this column (unrotated)
        anchor_ux = col_x + pw_px
        anchor_uy = col_y + col_h / 2
        # Rotate to get screen position
        arx, ary = _rot(anchor_ux, anchor_uy)
        arx = float(arx)
        ary = float(ary)

        # Label y: spread circuits vertically around draw_cy
        lbl_y = draw_cy + (ci - (n_circuits - 1) / 2.0) * 45
        lbl_y = max(70.0, min(float(VH - 150), lbl_y))

        # Leader line: from rotated anchor to label box left edge
        lbl_box_x = float(lbl_area_x)
        svg.append(
            f'<line x1="{arx:.1f}" y1="{ary:.1f}" '
            f'x2="{lbl_box_x:.1f}" y2="{lbl_y:.1f}" '
            f'stroke="#000000" stroke-width="0.8"/>'
        )
        # Small dot at anchor
        svg.append(f'<circle cx="{arx:.1f}" cy="{ary:.1f}" r="3.5" fill="#000000"/>')
        # Label text "CIRCUIT - N"
        svg.append(
            f'<text x="{lbl_box_x + 5:.1f}" y="{lbl_y + 5:.1f}" '
            f'font-size="13" font-weight="700" font-family="Arial" fill="#000">'
            f"CIRCUIT - {ci + 1}</text>"
        )

    # ── FOR INSTALLER USE ONLY footer (bottom-left) ────────────────────
    svg.append(
        f'<text x="{BORDER + 15}" y="{VH - 140}" '
        f'font-size="11" font-weight="700" font-style="italic" '
        f'font-family="Arial" fill="#555">FOR INSTALLER USE ONLY</text>'
    )

    # ── Title block ────────────────────────────────────────────────────
    svg.append(
        renderer._svg_title_block(
            VW, VH, "A-103", "STRING PLAN", "Array Branch Circuit Assignment", "5 of 15", address, today
        )
    )

    svg_content = "\n".join(svg)
    return (
        f'<div class="page"><svg width="100%" height="100%" '
        f'viewBox="0 0 {VW} {VH}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#fff;">{svg_content}</svg></div>'
    )
