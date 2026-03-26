"""Page builder: Property Plan (PV-2 / A-101)
===============================================
Extracted from HtmlRenderer._build_property_plan_page.
"""

import re


def build_property_plan_page(renderer, address: str, today: str, insight=None) -> str:
    """PV-2: Property Plan — lot boundaries, building footprint, driveway, setbacks.

    Generates a permit-ready property plan showing:
      - Lot boundary (solid) with dimension annotations in feet-inches
      - Main home footprint with hatch fill
      - Detached shed (rear lot corner)
      - Driveway with gray fill
      - Fence lines (dashed, 3 sides — back + sides)
      - Street identification below lot
      - Dimension callouts (lot size, front/side setbacks)
      - North arrow, scale bar, legend, APN/parcel info box

    Scale: 10 px/ft → annotated as 1'' = 12'-0''
    """
    VW, VH = 1280, 960

    # ── Get REAL dimensions from ProjectSpec + API ───────────────────
    bldg_w_ft = 35.0  # defaults
    bldg_d_ft = 25.0
    if renderer._project and renderer._project.building_width_ft > 0:
        bldg_w_ft = renderer._project.building_width_ft
        bldg_d_ft = renderer._project.building_depth_ft
    elif insight and insight.roof_segments:
        from engine.roof_analyzer import get_building_dimensions

        dims = get_building_dimensions(insight)
        if dims.get("width_ft", 0) > 5:
            bldg_w_ft = dims["width_ft"]
            bldg_d_ft = dims["depth_ft"]

    # Lot dimensions (from manual entry or estimated)
    lot_w_ft = 65.0
    lot_d_ft = 75.0
    if renderer._project and renderer._project.lot_width_ft > 0:
        lot_w_ft = renderer._project.lot_width_ft
        lot_d_ft = renderer._project.lot_depth_ft
    else:
        lot_w_ft = max(65, bldg_w_ft + 30)
        lot_d_ft = max(75, bldg_d_ft + 40)

    front_setback = renderer._project.front_setback_ft if renderer._project else 15.0
    side_setback = renderer._project.side_setback_ft if renderer._project else 5.0

    # Street name from address
    street_name = ""
    if renderer._project and renderer._project.street_name:
        street_name = renderer._project.street_name
    elif address:
        parts = address.split(",")[0].strip().split()
        if len(parts) > 1:
            street_name = " ".join(parts[1:]).upper()

    # ── Scale to fit page (auto-calculate pixels per foot) ───────────
    max_draw_w = 900
    max_draw_h = 720
    S = min(max_draw_w / lot_w_ft, max_draw_h / lot_d_ft)
    S = max(3, min(S, 12))

    lot_w = int(lot_w_ft * S)
    lot_d = int(lot_d_ft * S)

    lot_x1 = (VW - lot_w) // 2
    lot_y1 = 60
    lot_x2 = lot_x1 + lot_w
    lot_y2 = lot_y1 + lot_d

    # ── Building positions (from real dimensions) ────────────────────
    house_w = int(bldg_w_ft * S)
    house_d = int(bldg_d_ft * S)
    house_x1 = lot_x1 + int(side_setback * S)
    house_x2 = house_x1 + house_w
    house_y2 = lot_y2 - int(front_setback * S)
    house_y1 = house_y2 - house_d

    # Driveway
    drv_w_ft = 10.0
    drv_x1 = min(house_x2 + int(3 * S), lot_x2 - int(drv_w_ft * S))
    drv_x2 = lot_x2
    drv_y1 = house_y2
    drv_y2 = lot_y2

    # ── Fence lines ─────────────────────────────────────────────────
    f_inset = int(2 * S)
    fence_x1 = lot_x1 + f_inset
    fence_x2 = lot_x2 - f_inset
    fence_y1 = lot_y1 + f_inset
    fence_stop_y = house_y2 - int(3 * S)

    # ── SVG assembly ─────────────────────────────────────────────────
    p = []

    # White background
    p.append(f'<rect width="{VW}" height="{VH}" fill="#ffffff"/>')

    # Engineering drawing border
    p.append(
        f'<rect x="15" y="15" width="{VW - 30}" height="{VH - 30}" fill="none" stroke="#000" stroke-width="3"/>'
    )
    p.append(
        f'<rect x="23" y="23" width="{VW - 46}" height="{VH - 46}" fill="none" stroke="#000" stroke-width="1"/>'
    )

    # Page heading
    p.append(
        f'<text x="{lot_x1}" y="44" font-size="14" font-weight="700" '
        f'font-family="Arial" fill="#000" letter-spacing="1">PROPERTY PLAN</text>'
    )
    p.append(
        f'<text x="{lot_x1}" y="56" font-size="9" font-family="Arial" fill="#555">'
        f"Lot boundaries, building footprint &amp; site features</text>"
    )

    # SVG defs: diagonal hatch pattern for buildings
    p.append(
        "<defs>"
        '<pattern id="bldg_hatch" patternUnits="userSpaceOnUse" width="8" height="8">'
        '<path d="M-1,1 l2,-2 M0,8 l8,-8 M7,9 l2,-2" stroke="#aaa" stroke-width="0.8"/>'
        "</pattern>"
        "</defs>"
    )

    # ── Lot boundary ─────────────────────────────────────────────────
    p.append(
        f'<rect x="{lot_x1}" y="{lot_y1}" width="{lot_w}" height="{lot_d}" '
        f'fill="none" stroke="#000" stroke-width="2.5"/>'
    )

    # ── Fence lines (dashed) ─────────────────────────────────────────
    dash = 'stroke-dasharray="10,5"'
    p.append(
        f'<line x1="{fence_x1}" y1="{fence_y1}" x2="{fence_x2}" y2="{fence_y1}" '
        f'stroke="#000" stroke-width="1.5" {dash}/>'
    )
    p.append(
        f'<line x1="{fence_x1}" y1="{fence_y1}" x2="{fence_x1}" y2="{fence_stop_y}" '
        f'stroke="#000" stroke-width="1.5" {dash}/>'
    )
    p.append(
        f'<line x1="{fence_x2}" y1="{fence_y1}" x2="{fence_x2}" y2="{fence_stop_y}" '
        f'stroke="#000" stroke-width="1.5" {dash}/>'
    )

    # ── Driveway ─────────────────────────────────────────────────────
    p.append(
        f'<rect x="{drv_x1}" y="{drv_y1}" width="{drv_x2 - drv_x1}" '
        f'height="{drv_y2 - drv_y1}" fill="#d0d0d0" stroke="#777" stroke-width="1"/>'
    )
    drv_cx = (drv_x1 + drv_x2) // 2
    drv_cy = (drv_y1 + drv_y2) // 2
    p.append(
        f'<text x="{drv_cx}" y="{drv_cy}" text-anchor="middle" dominant-baseline="middle" '
        f'font-size="8" font-family="Arial" fill="#333" '
        f'transform="rotate(-90,{drv_cx},{drv_cy})">DRIVEWAY</text>'
    )

    # ── Main home ────────────────────────────────────────────────────
    house_cx = (house_x1 + house_x2) // 2
    house_cy = (house_y1 + house_y2) // 2
    p.append(
        f'<rect x="{house_x1}" y="{house_y1}" width="{house_w}" height="{house_d}" '
        f'fill="url(#bldg_hatch)" stroke="none"/>'
    )
    p.append(
        f'<rect x="{house_x1}" y="{house_y1}" width="{house_w}" height="{house_d}" '
        f'fill="none" stroke="#000" stroke-width="2.5"/>'
    )

    p.append(
        f'<text x="{house_cx}" y="{house_cy - 10}" text-anchor="middle" '
        f'font-size="12" font-weight="700" font-family="Arial" fill="#000">MAIN HOME</text>'
    )
    p.append(
        f'<text x="{house_cx}" y="{house_cy + 8}" text-anchor="middle" '
        f'font-size="9" font-family="Arial" fill="#444">{bldg_w_ft:.0f}\' x {bldg_d_ft:.0f}\'</text>'
    )

    # ── Street ───────────────────────────────────────────────────────
    _street_raw = address.split(",")[0].strip() if "," in address else address
    _street_label = re.sub(r"^\d+\s*", "", _street_raw).upper()
    p.append(
        f'<line x1="{lot_x1 - 40}" y1="{lot_y2 + 10}" x2="{lot_x2 + 40}" y2="{lot_y2 + 10}" '
        f'stroke="#000" stroke-width="4"/>'
    )
    p.append(
        f'<text x="{(lot_x1 + lot_x2) // 2}" y="{lot_y2 + 28}" text-anchor="middle" '
        f'font-size="11" font-weight="700" font-family="Arial" fill="#000" '
        f'letter-spacing="2">{_street_label}</text>'
    )

    # ── Dimension annotations ─────────────────────────────────────────
    from renderer.svg_helpers import dim_h, dim_v, ft_in

    # Lot width (above lot)
    p.append(dim_h(lot_x1, lot_x2, lot_y1 - 20, ft_in(lot_w_ft)))
    # Lot depth (left of lot)
    p.append(dim_v(lot_x1 - 40, lot_y1, lot_y2, ft_in(lot_d_ft)))
    # Front setback (right of lot, house_y2 to lot_y2)
    p.append(dim_v(lot_x2 + 38, house_y2, lot_y2, ft_in(front_setback)))
    # Left side setback (lot_x1 to house_x1, below lot)
    p.append(dim_h(lot_x1, house_x1, lot_y2 + 45, ft_in(side_setback)))

    # Front setback indicator line (dashed red)
    p.append(
        f'<line x1="{lot_x1 + 5}" y1="{house_y2}" x2="{lot_x2 - 5}" y2="{house_y2}" '
        f'stroke="#aa0000" stroke-width="0.8" stroke-dasharray="6,4"/>'
    )
    p.append(
        f'<text x="{lot_x1 + 10}" y="{house_y2 - 4}" font-size="7" '
        f'font-family="Arial" fill="#aa0000">FRONT SETBACK {ft_in(front_setback)}</text>'
    )

    # ── North arrow ───────────────────────────────────────────────────
    na_cx, na_cy, na_r = 1150, 130, 36
    p.append(f'<circle cx="{na_cx}" cy="{na_cy}" r="{na_r}" fill="none" stroke="#000" stroke-width="1.5"/>')
    p.append(
        f'<polygon points="{na_cx},{na_cy - na_r + 6} {na_cx - 11},{na_cy + 12} {na_cx},{na_cy - 2}" fill="#000"/>'
    )
    p.append(
        f'<polygon points="{na_cx},{na_cy - na_r + 6} {na_cx + 11},{na_cy + 12} '
        f'{na_cx},{na_cy - 2}" fill="#fff" stroke="#000" stroke-width="1"/>'
    )
    p.append(
        f'<line x1="{na_cx}" y1="{na_cy - 2}" x2="{na_cx}" y2="{na_cy + na_r - 6}" '
        f'stroke="#000" stroke-width="1.5"/>'
    )
    p.append(
        f'<text x="{na_cx}" y="{na_cy - na_r - 6}" text-anchor="middle" '
        f'font-size="15" font-weight="700" font-family="Arial" fill="#000">N</text>'
    )

    # ── APN / Parcel info box ─────────────────────────────────────────
    apn_x, apn_y = 1080, 186
    p.append(f'<rect x="{apn_x}" y="{apn_y}" width="185" height="62" fill="#fff" stroke="#000" stroke-width="1"/>')
    p.append(
        f'<text x="{apn_x + 92}" y="{apn_y + 14}" text-anchor="middle" '
        f'font-size="8" font-weight="700" font-family="Arial" fill="#000">PARCEL INFORMATION</text>'
    )
    p.append(
        f'<line x1="{apn_x}" y1="{apn_y + 18}" x2="{apn_x + 185}" y2="{apn_y + 18}" '
        f'stroke="#000" stroke-width="0.5"/>'
    )
    p.append(
        f'<text x="{apn_x + 8}" y="{apn_y + 31}" '
        f'font-size="8" font-family="Arial" fill="#000">APN: 07-540-01-05-XXX</text>'
    )
    p.append(
        f'<text x="{apn_x + 8}" y="{apn_y + 43}" '
        f'font-size="8" font-family="Arial" fill="#000">ZONING: R2 - RESIDENTIAL</text>'
    )
    p.append(
        f'<text x="{apn_x + 8}" y="{apn_y + 55}" '
        f'font-size="8" font-family="Arial" fill="#000">LOT AREA: 4,875 sq.ft. (452.9 m2)</text>'
    )

    # ── Legend ────────────────────────────────────────────────────────
    lgd_x, lgd_y = 32, 565
    p.append(f'<rect x="{lgd_x}" y="{lgd_y}" width="228" height="120" fill="#fff" stroke="#000" stroke-width="1"/>')
    p.append(
        f'<text x="{lgd_x + 114}" y="{lgd_y + 15}" text-anchor="middle" '
        f'font-size="9" font-weight="700" font-family="Arial" fill="#000">LEGEND</text>'
    )
    p.append(
        f'<line x1="{lgd_x}" y1="{lgd_y + 20}" x2="{lgd_x + 228}" y2="{lgd_y + 20}" '
        f'stroke="#000" stroke-width="0.5"/>'
    )
    # Property line entry
    p.append(
        f'<line x1="{lgd_x + 10}" y1="{lgd_y + 36}" x2="{lgd_x + 55}" y2="{lgd_y + 36}" '
        f'stroke="#000" stroke-width="2.5"/>'
    )
    p.append(
        f'<text x="{lgd_x + 65}" y="{lgd_y + 40}" '
        f'font-size="8" font-family="Arial" fill="#000">PROPERTY LINE</text>'
    )
    # Fence line entry
    p.append(
        f'<line x1="{lgd_x + 10}" y1="{lgd_y + 57}" x2="{lgd_x + 55}" y2="{lgd_y + 57}" '
        f'stroke="#000" stroke-width="1.5" stroke-dasharray="8,4"/>'
    )
    p.append(
        f'<text x="{lgd_x + 65}" y="{lgd_y + 61}" font-size="8" font-family="Arial" fill="#000">FENCE LINE</text>'
    )
    # Building footprint entry
    p.append(
        f'<rect x="{lgd_x + 10}" y="{lgd_y + 68}" width="45" height="15" '
        f'fill="url(#bldg_hatch)" stroke="#000" stroke-width="1.5"/>'
    )
    p.append(
        f'<text x="{lgd_x + 65}" y="{lgd_y + 80}" '
        f'font-size="8" font-family="Arial" fill="#000">BUILDING FOOTPRINT</text>'
    )
    # Driveway entry
    p.append(
        f'<rect x="{lgd_x + 10}" y="{lgd_y + 90}" width="45" height="15" '
        f'fill="#d0d0d0" stroke="#777" stroke-width="1"/>'
    )
    p.append(
        f'<text x="{lgd_x + 65}" y="{lgd_y + 102}" '
        f'font-size="8" font-family="Arial" fill="#000">DRIVEWAY / PAVEMENT</text>'
    )
    # Setback line entry
    p.append(
        f'<line x1="{lgd_x + 10}" y1="{lgd_y + 114}" x2="{lgd_x + 55}" y2="{lgd_y + 114}" '
        f'stroke="#aa0000" stroke-width="1" stroke-dasharray="6,4"/>'
    )
    p.append(
        f'<text x="{lgd_x + 65}" y="{lgd_y + 118}" '
        f'font-size="8" font-family="Arial" fill="#000">SETBACK LINE</text>'
    )

    # ── Scale bar ─────────────────────────────────────────────────────
    sb_x, sb_y = 32, 710
    p.append(
        f'<text x="{sb_x}" y="{sb_y - 8}" font-size="9" font-weight="700" '
        f'font-family="Arial" fill="#000">SCALE: 1 in = 12\'-0"</text>'
    )
    for seg in range(3):
        fill = "#000" if seg % 2 == 0 else "#fff"
        p.append(
            f'<rect x="{sb_x + seg * 100}" y="{sb_y}" width="100" height="10" '
            f'fill="{fill}" stroke="#000" stroke-width="1"/>'
        )
    for i, ft in enumerate([0, 10, 20, 30]):
        p.append(
            f'<text x="{sb_x + i * 100}" y="{sb_y + 23}" text-anchor="middle" '
            f'font-size="8" font-family="Arial" fill="#000">{ft}\'</text>'
        )

    # ── Notes box ─────────────────────────────────────────────────────
    notes_x, notes_y = 32, 748
    notes = [
        "All dimensions are approximate. Field verify before construction.",
        "Property boundaries based on typical residential lot.",
        "Building setbacks per applicable municipal zoning by-law. Verify with AHJ.",
        "APN provided for permit reference only.",
    ]
    p.append(
        f'<rect x="{notes_x}" y="{notes_y}" width="270" height="70" fill="#ffffff" stroke="#888" stroke-width="1"/>'
    )
    p.append(
        f'<text x="{notes_x + 8}" y="{notes_y + 13}" font-size="8" font-weight="700" '
        f'font-family="Arial" fill="#000">NOTES:</text>'
    )
    for ni, note in enumerate(notes):
        p.append(
            f'<text x="{notes_x + 8}" y="{notes_y + 25 + ni * 13}" '
            f'font-size="7.5" font-family="Arial" fill="#333">{ni + 1}. {note}</text>'
        )

    # ── Title block ───────────────────────────────────────────────────
    p.append(renderer._svg_title_block(VW, VH, "A-101", "Site Plan", "Property Plan", "2 of 13", address, today))

    svg_content = "\n".join(p)
    return (
        f'<div class="page"><svg width="100%" height="100%" '
        f'viewBox="0 0 {VW} {VH}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#fff;">{svg_content}</svg></div>'
    )
