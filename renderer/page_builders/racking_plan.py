"""Page builder: Racking Plan (PV-3.1 / A-102)
================================================
Extracted from HtmlRenderer._build_racking_plan_page.

Key challenge: closure-based coordinate transform (_make_pt2svg).
Preserved as nested function with default argument capture.
"""

import math
from typing import List, Optional

from renderer.shared.geo_utils import azimuth_label


def build_racking_plan_page(
    renderer, insight, num_api_panels: int, address: str, today: str,
    placements=None,
) -> str:
    """PV-3.1: Data-driven vector racking/framing plan.

    Uses actual roof segment areas from API to compute proportional rectangles.
    Shows individual panels at correct scale, fire setbacks with measurements,
    racking rails, and dimension annotations.
    """
    VW, VH = 1280, 960
    BORDER = 20
    TB_H = 100  # title block height at bottom
    DRAW_TOP = 195  # space for top info band (ROOF DETAIL + ROOF AREA table)
    DRAW_BOTTOM = 712  # bottom of main drawing; leaves room for bottom info band

    # Drawing area
    draw_x = BORDER + 10
    draw_y = DRAW_TOP
    draw_w = VW - 2 * BORDER - 20
    draw_h = DRAW_BOTTOM - DRAW_TOP

    # Scale: px per meter (compute from largest segment to fill drawing area)
    SETBACK_M = 0.914  # 36 inches (3 feet) in meters — California fire code setback (IFC 605.11.1 / CEC 690.12)
    PANEL_W_M = renderer.panel.width_ft * 0.3048  # convert ft → m
    PANEL_H_M = renderer.panel.height_ft * 0.3048
    GAP_M = 0.05  # 50mm gap between panels

    svg = []

    # Defs
    svg.append("<defs>")
    svg.append(
        '<pattern id="hatch-sb" patternUnits="userSpaceOnUse" width="6" height="6" patternTransform="rotate(45)">'
    )
    svg.append('<line x1="0" y1="0" x2="0" y2="6" stroke="#cc0000" stroke-width="0.5" opacity="0.25"/>')
    svg.append("</pattern>")
    # Dimension arrow markers
    svg.append(
        '<marker id="dim-l" markerWidth="6" markerHeight="6" refX="6" refY="3" orient="auto">'
        '<polygon points="0,1 6,3 0,5" fill="#444"/></marker>'
    )
    svg.append(
        '<marker id="dim-r" markerWidth="6" markerHeight="6" refX="0" refY="3" orient="auto">'
        '<polygon points="6,1 0,3 6,5" fill="#444"/></marker>'
    )
    svg.append("</defs>")

    # White background
    svg.append(f'<rect width="{VW}" height="{VH}" fill="#ffffff"/>')

    # Light construction grid (1m spacing will be computed per segment)
    for gx in range(draw_x, draw_x + draw_w, 30):
        svg.append(
            f'<line x1="{gx}" y1="{draw_y}" x2="{gx}" y2="{DRAW_BOTTOM}" stroke="#f2f2f2" stroke-width="0.3"/>'
        )
    for gy in range(draw_y, DRAW_BOTTOM, 30):
        svg.append(
            f'<line x1="{draw_x}" y1="{gy}" x2="{draw_x + draw_w}" y2="{gy}" stroke="#f2f2f2" stroke-width="0.3"/>'
        )

    # Engineering border
    svg.append(
        f'<rect x="{BORDER}" y="{BORDER}" width="{VW - 2 * BORDER}" '
        f'height="{VH - 2 * BORDER}" fill="none" stroke="#000" stroke-width="1.5"/>'
    )

    # Page title
    svg.append(
        f'<text x="{BORDER + 15}" y="{BORDER + 18}" font-size="14" font-weight="700" '
        f'font-family="Arial" fill="#000">A-102: RACKING AND FRAMING PLAN</text>'
    )
    svg.append(
        f'<text x="{BORDER + 15}" y="{BORDER + 31}" font-size="8" '
        f'font-family="Arial" fill="#555">SCALE: 1/8&quot; = 1&apos;-0&quot;</text>'
    )

    # ── TOP INFO BAND (y=38 to y=188) ────────────────────────────────
    # Compute roof/array metrics from segments (drawn later, need first pass)
    SQFT_PER_M2 = 10.7639
    panel_area_sqft = round(renderer.panel.width_ft * renderer.panel.height_ft, 2)
    # Find first roof segment that has panels — independent lookup (panels_by_seg not yet built)
    _segs_with_panels = set()
    if insight and insight.panels and num_api_panels:
        for _pp in insight.panels[:num_api_panels]:
            _segs_with_panels.add(getattr(_pp, "segment_index", 0))
    _first_seg = next(
        (
            s
            for s in (insight.roof_segments if insight and insight.roof_segments else [])
            if s.index in _segs_with_panels
        ),
        None,
    )
    if _first_seg is None and insight and insight.roof_segments:
        _first_seg = insight.roof_segments[0]
    # Use the project-authoritative panel count so every page is consistent.
    # When the placer places fewer panels than the design target (e.g. due to
    # API roof polygons being undersized), we still report the correct design
    # count — a building dept reviewer needs all pages to agree.
    _placed_count = sum(len(pr.panels) for pr in (placements or []))
    _proj_count = renderer._project.num_panels if (renderer._project and renderer._project.num_panels) else 0
    _total_panels_drawn = (
        max(_placed_count, _proj_count) if _proj_count > 0 else (_placed_count or num_api_panels or 0)
    )

    # Use total area of ALL roof segments so coverage % is realistic.
    # Using only the first segment produced a false "93% > 33%" alarm.
    _all_segs = insight.roof_segments if (insight and insight.roof_segments) else []
    _total_roof_sqft = (
        sum(s.area_m2 * SQFT_PER_M2 for s in _all_segs)
        if _all_segs
        else ((_first_seg.area_m2 * SQFT_PER_M2) if _first_seg else 100.0)
    )
    _roof_area_sqft = round(_total_roof_sqft, 0)
    _array_area_sqft = round(_total_panels_drawn * panel_area_sqft, 2)
    _array_pct = round((_array_area_sqft / _roof_area_sqft) * 100, 2) if _roof_area_sqft > 0 else 0
    _pitch_deg = round(_first_seg.pitch_deg, 0) if _first_seg else 0
    _azimuth_deg = round(_first_seg.azimuth_deg, 0) if _first_seg else 180
    _setback_note = (
        f"{_array_pct}% &lt; 33%, 18&quot; SETBACK IS VALID"
        if _array_pct < 33
        else f"{_array_pct}% &gt; 33% — VERIFY SETBACK"
    )

    # Pre-compute use_placements early so top info band can reference it
    use_placements = placements and any(pr.panels for pr in placements)

    # ── ROOF DETAIL block (top-left) ─────────────────────────────────
    rd_x, rd_y, rd_w, rd_h = BORDER + 10, 38, 260, 148
    svg.append(
        f'<rect x="{rd_x}" y="{rd_y}" width="{rd_w}" height="{rd_h}" fill="#fff" stroke="#000" stroke-width="1.2"/>'
    )
    svg.append(
        f'<rect x="{rd_x}" y="{rd_y}" width="{rd_w}" height="16" fill="#e8e8e8" stroke="#000" stroke-width="1"/>'
    )
    svg.append(
        f'<text x="{rd_x + rd_w // 2}" y="{rd_y + 11}" text-anchor="middle" '
        f'font-size="9" font-weight="700" font-family="Arial" fill="#000">ROOF DETAIL</text>'
    )
    # Circled section number (1)
    svg.append(
        f'<circle cx="{rd_x + rd_w - 18}" cy="{rd_y + rd_h // 2 + 12}" r="14" '
        f'fill="#fff" stroke="#000" stroke-width="1.5"/>'
    )
    svg.append(
        f'<text x="{rd_x + rd_w - 18}" y="{rd_y + rd_h // 2 + 17}" text-anchor="middle" '
        f'font-size="14" font-weight="700" font-family="Arial" fill="#000">1</text>'
    )
    # Roof type row
    roof_mat = (
        getattr(renderer._project, "roof_material_display", "ASPHALT-SHINGLES") if renderer._project else "ASPHALT-SHINGLES"
    )
    svg.append(
        f'<text x="{rd_x + 8}" y="{rd_y + 28}" font-size="9" font-weight="700" '
        f'font-family="Arial" fill="#000">ROOF TYPE:</text>'
    )
    svg.append(
        f'<text x="{rd_x + 8}" y="{rd_y + 40}" font-size="9" font-weight="400" '
        f'font-family="Arial" fill="#333">{roof_mat.upper()}</text>'
    )
    # Per-face detail rows from placements (or fallback to insight)
    _face_rows = []
    if use_placements:
        for _fi, _pr in enumerate(placements):
            if _pr.panels:
                _rf = _pr.roof_face
                _face_rows.append(
                    (
                        f"ROOF FACE {_fi + 1}: {len(_pr.panels)} MODULES",
                        f"AZM: {_rf.azimuth_deg:.0f}\u00b0 | TILT: {_rf.pitch_deg:.0f}\u00b0" if _rf else "—",
                    )
                )
    if not _face_rows:
        _face_rows = [
            (
                f"ROOF SECTION 1: {_total_panels_drawn} MODULES",
                f"AZM: {_azimuth_deg:.0f}\u00b0 | TILT: {_pitch_deg:.0f}\u00b0",
            ),
        ]
    for _fi, (_face_lbl, _face_det) in enumerate(_face_rows):
        _fy = rd_y + 54 + _fi * 34
        svg.append(
            f'<text x="{rd_x + 8}" y="{_fy}" font-size="8.5" font-weight="700" '
            f'font-family="Arial" fill="#000">{_face_lbl}</text>'
        )
        svg.append(
            f'<text x="{rd_x + 8}" y="{_fy + 14}" font-size="8" font-weight="400" '
            f'font-family="Arial" fill="#555">{_face_det}</text>'
        )

    # ── ROOF AREA / SOLAR PANEL AREA table (top-center) ──────────────
    ra_x, ra_y, ra_w, ra_h = BORDER + 280, 38, 700, 70
    svg.append(
        f'<rect x="{ra_x}" y="{ra_y}" width="{ra_w}" height="{ra_h}" fill="#fff" stroke="#000" stroke-width="1.2"/>'
    )
    # 3-column header
    ra_cols = [("ROOF AREA", 175), ("SOLAR PANEL AREA", 330), ("SOLAR % OF ROOF AREA", 195)]
    cx2 = ra_x
    for hdr, cw2 in ra_cols:
        svg.append(
            f'<rect x="{cx2}" y="{ra_y}" width="{cw2}" height="18" '
            f'fill="#e8e8e8" stroke="#000" stroke-width="0.8"/>'
        )
        svg.append(
            f'<text x="{cx2 + cw2 // 2}" y="{ra_y + 12}" text-anchor="middle" '
            f'font-size="8" font-weight="700" font-family="Arial" fill="#000">{hdr}</text>'
        )
        cx2 += cw2
    # Data row 1 (row headers)
    cx2 = ra_x
    subhdrs = [
        [f"{int(_roof_area_sqft)} SQ FT ROOF"],
        [
            f"{panel_area_sqft:.2f} SQ FT EACH",
            f"{_total_panels_drawn} PANELS",
            f"{_array_area_sqft:.2f} SQ FT ARRAY",
        ],
        [f"{_setback_note}"],
    ]
    col_widths2 = [175, 330, 195]
    for ci_x, (vals, cw2) in enumerate(zip(subhdrs, col_widths2)):
        # Sub-columns for middle col
        if len(vals) == 3:
            sub_w = cw2 // 3
            for j, v in enumerate(vals):
                scx = cx2 + j * sub_w
                svg.append(
                    f'<rect x="{scx}" y="{ra_y + 18}" width="{sub_w}" height="52" '
                    f'fill="#fafafa" stroke="#000" stroke-width="0.5"/>'
                )
                svg.append(
                    f'<text x="{scx + sub_w // 2}" y="{ra_y + 48}" text-anchor="middle" '
                    f'font-size="8" font-weight="600" font-family="Arial" fill="#000">{v}</text>'
                )
        else:
            svg.append(
                f'<rect x="{cx2}" y="{ra_y + 18}" width="{cw2}" height="52" '
                f'fill="#fafafa" stroke="#000" stroke-width="0.5"/>'
            )
            svg.append(
                f'<text x="{cx2 + cw2 // 2}" y="{ra_y + 48}" text-anchor="middle" '
                f'font-size="9" font-weight="600" font-family="Arial" fill="#000">{vals[0]}</text>'
            )
        cx2 += cw2

    # ── STRUCTURAL LOADING SUMMARY (below Roof Area table) ───────────
    _struct = renderer._project.structural_loads if renderer._project else {}
    sl2_x, sl2_y, sl2_w = ra_x, ra_y + ra_h + 3, ra_w
    _sl2_cols = [
        ("PANEL DL", f"{_struct.get('panel_dead_load_psf', 0):.2f} psf"),
        ("RACKING DL", f"{_struct.get('racking_dead_load_psf', 0):.1f} psf"),
        ("TOTAL DL", f"{_struct.get('total_dead_load_psf', 0):.2f} psf"),
        ("ROOF LL", f"{_struct.get('roof_live_load_psf', 0):.0f} psf"),
        ("SNOW LOAD", f"{_struct.get('snow_load_psf', 0):.0f} psf"),
        ("WIND UPLIFT", f"{_struct.get('wind_uplift_psf', 0):.0f} psf"),
        ("CTRL LOAD", f"{_struct.get('controlling_load_psf', 0):.2f} psf"),
        ("ATTACH SPC", f"{_struct.get('attachment_spacing_ft', 0):.2f} ft OC"),
    ]
    _sl2_col_w = sl2_w // len(_sl2_cols)
    _sl2_hdr_h, _sl2_val_h = 14, 22
    _sl2_total_h = 12 + _sl2_hdr_h + _sl2_val_h
    svg.append(
        f'<rect x="{sl2_x}" y="{sl2_y}" width="{sl2_w}" height="{_sl2_total_h}" '
        f'fill="#fff" stroke="#000" stroke-width="1"/>'
    )
    svg.append(
        f'<rect x="{sl2_x}" y="{sl2_y}" width="{sl2_w}" height="12" fill="#e8e8e8" stroke="#000" stroke-width="1"/>'
    )
    svg.append(
        f'<text x="{sl2_x + sl2_w // 2}" y="{sl2_y + 9}" text-anchor="middle" '
        f'font-size="7.5" font-weight="700" font-family="Arial" fill="#000">'
        f"STRUCTURAL LOADING SUMMARY (IBC / ASCE 7-16)</text>"
    )
    for _ci, (_col_hdr, _col_val) in enumerate(_sl2_cols):
        _cx = sl2_x + _ci * _sl2_col_w
        _is_ctrl = "CTRL" in _col_hdr or "ATTACH" in _col_hdr
        _bg = "#fff7e6" if _is_ctrl else "#fafafa"
        svg.append(
            f'<rect x="{_cx}" y="{sl2_y + 12}" width="{_sl2_col_w}" height="{_sl2_hdr_h}" '
            f'fill="#d8e8f8" stroke="#000" stroke-width="0.4"/>'
        )
        svg.append(
            f'<rect x="{_cx}" y="{sl2_y + 12 + _sl2_hdr_h}" width="{_sl2_col_w}" height="{_sl2_val_h}" '
            f'fill="{_bg}" stroke="#000" stroke-width="0.4"/>'
        )
        svg.append(
            f'<text x="{_cx + _sl2_col_w // 2}" y="{sl2_y + 12 + _sl2_hdr_h - 3}" '
            f'text-anchor="middle" font-size="6.5" font-family="Arial" fill="#333">{_col_hdr}</text>'
        )
        svg.append(
            f'<text x="{_cx + _sl2_col_w // 2}" y="{sl2_y + 12 + _sl2_hdr_h + 14}" '
            f'text-anchor="middle" font-size="7.5" font-weight="700" font-family="Arial" fill="#000">{_col_val}</text>'
        )

    # ── SYSTEM LEGEND (top-right) ─────────────────────────────────────
    sl_x, sl_y, sl_w, sl_h = BORDER + 990, 38, 245, 148
    svg.append(
        f'<rect x="{sl_x}" y="{sl_y}" width="{sl_w}" height="{sl_h}" fill="#fff" stroke="#000" stroke-width="1.2"/>'
    )
    svg.append(
        f'<rect x="{sl_x}" y="{sl_y}" width="{sl_w}" height="16" fill="#e8e8e8" stroke="#000" stroke-width="1"/>'
    )
    svg.append(
        f'<text x="{sl_x + sl_w // 2}" y="{sl_y + 11}" text-anchor="middle" '
        f'font-size="9" font-weight="700" font-family="Arial" fill="#000">SYSTEM LEGEND</text>'
    )
    leg_items_top = [
        ("dot", "#1a6ea8", "solid", "ROOF ATTACHMENT POINT"),
        ("line", "#d08020", "solid", "ROOF FRAMING (RAFTERS/TRUSS)"),
        ("line", "#4a9e4a", "solid", "RACKING"),
        ("rect", "#cc0000", "hatch", "FIRE CODE SETBACK (18\u2033 MIN / 36\u2033 MAX)"),
        ("line", "#e07000", "dashed", f"RIDGE SETBACK (18\u2033 {'NEC 690.12(B)(2)' if renderer._code_prefix == 'NEC' else 'CEC Rule 64-218'})"),
    ]
    for i, (sym, color, style, label) in enumerate(leg_items_top):
        iy = sl_y + 26 + i * 28
        if sym == "dot":
            svg.append(
                f'<circle cx="{sl_x + 14}" cy="{iy + 4}" r="4" fill="{color}" stroke="#000" stroke-width="0.8"/>'
            )
        elif sym == "line":
            dash_attr = ' stroke-dasharray="4,3"' if style == "dashed" else ""
            svg.append(
                f'<line x1="{sl_x + 4}" y1="{iy + 4}" x2="{sl_x + 24}" y2="{iy + 4}" '
                f'stroke="{color}" stroke-width="2"{dash_attr}/>'
            )
        elif sym == "rect":
            svg.append(
                f'<rect x="{sl_x + 4}" y="{iy}" width="20" height="10" '
                f'fill="url(#hatch-sb)" stroke="{color}" stroke-width="0.5"/>'
            )
        svg.append(
            f'<text x="{sl_x + 32}" y="{iy + 9}" font-size="7.5" font-family="Arial" fill="#000">{label}</text>'
        )

    # ── Draw roof faces and panels from placements data ──────────────
    # Default px_per_m for scale bar (updated below when segments available)
    px_per_m = 40

    if use_placements:
        # Layout each roof face in its own horizontal slot so all faces are
        # visible side by side regardless of their absolute coordinate positions.
        # Filter to faces that have a polygon; prefer faces with panels first.
        faces_to_draw = [pr for pr in placements if pr.roof_face and pr.roof_face.polygon and pr.panels]
        if not faces_to_draw:
            faces_to_draw = [pr for pr in placements if pr.roof_face and pr.roof_face.polygon]

        num_faces = max(len(faces_to_draw), 1)
        slot_gap = 50  # px gap between face slots
        slot_w = (draw_w - (num_faces - 1) * slot_gap) / num_faces
        available_h = draw_h - 70  # reserve space for labels above/below

        # Estimate px_per_m from the largest face for the scale bar
        largest_pr2 = max(faces_to_draw, key=lambda pr: pr.roof_face.area_sqft if pr.roof_face else 0)
        if largest_pr2.roof_face and largest_pr2.roof_face.area_sqft > 0:
            face_bb2 = largest_pr2.roof_face.polygon.bounds
            face_w2 = max(face_bb2[2] - face_bb2[0], 1.0)
            face_h2 = max(face_bb2[3] - face_bb2[1], 1.0)
            sc2 = min(slot_w * 0.8 / face_w2, available_h * 0.8 / face_h2)
            rf_area_sqft2 = largest_pr2.roof_face.area_sqft
            rf_diag_ft2 = math.sqrt(rf_area_sqft2 * 5.0)
            poly_diag_pts2 = math.hypot(face_w2, face_h2)
            pts_per_ft_est2 = poly_diag_pts2 / max(rf_diag_ft2, 1.0)
            px_per_m = sc2 * pts_per_ft_est2 * 3.281
            px_per_m = max(px_per_m, 8)

        # Draw each face in its allocated slot
        panel_num = 0
        for pri, pr in enumerate(faces_to_draw):
            rf = pr.roof_face
            face_bb = rf.polygon.bounds  # (minx, miny, maxx, maxy) in pts
            face_w = max(face_bb[2] - face_bb[0], 1.0)
            face_h = max(face_bb[3] - face_bb[1], 1.0)

            # Scale to fit slot with inner margin for annotations
            margin_inner = 30
            sc = min((slot_w - 2 * margin_inner) / face_w, (available_h - 2 * margin_inner) / face_h) * 0.88

            # Slot x origin (left edge of this face's column)
            slot_x0 = draw_x + pri * (slot_w + slot_gap)

            # Center the face within the slot
            face_draw_w = face_w * sc
            face_draw_h = face_h * sc
            ox = slot_x0 + margin_inner + (slot_w - 2 * margin_inner - face_draw_w) / 2
            oy = draw_y + 30 + (available_h - face_draw_h) / 2

            def _make_pt2svg(ox_=ox, oy_=oy, sc_=sc, bb_=face_bb):
                def pt2svg(px2, py2):
                    return (ox_ + (px2 - bb_[0]) * sc_, oy_ + (py2 - bb_[1]) * sc_)

                return pt2svg

            pt2svg = _make_pt2svg()

            # Face-local px_per_m for rafter spacing
            if rf.area_sqft > 0:
                rf_diag_ft = math.sqrt(rf.area_sqft * 5.0)
                poly_diag_pts = math.hypot(face_w, face_h)
                pts_per_ft_est = poly_diag_pts / max(rf_diag_ft, 1.0)
                face_px_per_m = sc * pts_per_ft_est * 3.281
                face_px_per_m = max(face_px_per_m, 8)
            else:
                face_px_per_m = px_per_m

            # Roof face outline
            coords = [pt2svg(x, y) for x, y in rf.polygon.exterior.coords]
            pts_str = " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
            svg.append(f'<polygon points="{pts_str}" fill="#fafafa" stroke="#000" stroke-width="2"/>')

            # Fire setback inner boundary (red dashed) from usable polygon
            if rf.usable_polygon and not rf.usable_polygon.is_empty:
                try:
                    u_pts = " ".join(
                        f"{pt2svg(x, y)[0]:.1f},{pt2svg(x, y)[1]:.1f}" for x, y in rf.usable_polygon.exterior.coords
                    )
                    svg.append(
                        f'<polygon points="{u_pts}" fill="none" '
                        f'stroke="#cc0000" stroke-width="1.2" '
                        f'stroke-dasharray="6,3"/>'
                    )
                except Exception:
                    pass

            # Ridge setback line — dashed orange
            _ridge_sb = getattr(pr, "ridge_setback_ft", 0.0)
            if _ridge_sb > 0 and rf.usable_polygon and not rf.usable_polygon.is_empty:
                try:
                    from shapely.geometry import Polygon as _SPoly

                    _ridge_sb_pts = _ridge_sb * pts_per_ft_est
                    _upoly = rf.usable_polygon
                    _rad2 = math.radians(rf.azimuth_deg)
                    _cos2 = math.cos(_rad2)
                    _sin2 = math.sin(_rad2)
                    _cx2 = _upoly.centroid.x
                    _cy2 = _upoly.centroid.y
                    _slope_projs = [
                        -(_vx - _cx2) * _sin2 + (_vy - _cy2) * _cos2 for _vx, _vy in _upoly.exterior.coords
                    ]
                    _max_s = max(_slope_projs)
                    _clip_s = _max_s - _ridge_sb_pts
                    _L = 100000
                    _bx0 = _cx2 - _clip_s * _sin2 - _L * _cos2
                    _by0 = _cy2 + _clip_s * _cos2 - _L * _sin2
                    _bx1 = _cx2 - _clip_s * _sin2 + _L * _cos2
                    _by1 = _cy2 + _clip_s * _cos2 + _L * _sin2
                    _kx0 = _bx0 + _L * _sin2
                    _ky0 = _by0 - _L * _cos2
                    _kx1 = _bx1 + _L * _sin2
                    _ky1 = _by1 - _L * _cos2
                    _clip2 = _SPoly([(_bx0, _by0), (_bx1, _by1), (_kx1, _ky1), (_kx0, _ky0)])
                    _rpoly = _upoly.intersection(_clip2)
                    if _rpoly.geom_type == "MultiPolygon":
                        _rpoly = max(_rpoly.geoms, key=lambda g: g.area)
                    if not _rpoly.is_empty:
                        r_pts = " ".join(
                            f"{pt2svg(_vx, _vy)[0]:.1f},{pt2svg(_vx, _vy)[1]:.1f}"
                            for _vx, _vy in _rpoly.exterior.coords
                        )
                        svg.append(
                            f'<polygon points="{r_pts}" fill="none" '
                            f'stroke="#e07000" stroke-width="1.2" '
                            f'stroke-dasharray="4,4"/>'
                        )
                except Exception:
                    pass

            # Rafter lines: orange vertical lines at 24" spacing across roof face
            RAFTER_M = 0.610
            rafter_px2 = RAFTER_M * face_px_per_m
            rf_sv_x0, rf_sv_y0 = pt2svg(face_bb[0], face_bb[1])
            rf_sv_x1, rf_sv_y1 = pt2svg(face_bb[2], face_bb[3])
            if rafter_px2 > 2:
                ri = 0
                while True:
                    rx2 = rf_sv_x0 + ri * rafter_px2
                    if rx2 > rf_sv_x1 + rafter_px2 * 0.1:
                        break
                    svg.append(
                        f'<line x1="{rx2:.1f}" y1="{rf_sv_y0:.1f}" '
                        f'x2="{rx2:.1f}" y2="{rf_sv_y1:.1f}" '
                        f'stroke="#d08020" stroke-width="0.9" opacity="0.55"/>'
                    )
                    ri += 1

            # Draw panels
            for panel in pr.panels:
                panel_num += 1
                svg_cx, svg_cy = pt2svg(panel.center_x, panel.center_y)
                pw2 = panel.width_pts * sc
                ph2 = panel.height_pts * sc
                rot = panel.rotation_deg

                svg.append(f'<g transform="translate({svg_cx:.1f},{svg_cy:.1f}) rotate({rot:.1f})">')
                svg.append(
                    f'<rect x="{-pw2 / 2:.1f}" y="{-ph2 / 2:.1f}" '
                    f'width="{pw2:.1f}" height="{ph2:.1f}" '
                    f'fill="#ffffff" stroke="#333" stroke-width="0.8"/>'
                )
                # Cell lines (3 subdivisions)
                for ci2 in range(1, 3):
                    cell_y2 = -ph2 / 2 + ph2 / 3 * ci2
                    svg.append(
                        f'<line x1="{-pw2 / 2:.1f}" y1="{cell_y2:.1f}" '
                        f'x2="{pw2 / 2:.1f}" y2="{cell_y2:.1f}" '
                        f'stroke="#bbb" stroke-width="0.3"/>'
                    )
                # Panel number
                fs = max(5, min(8, int(pw2 * 0.35)))
                svg.append(
                    f'<text x="0" y="{fs // 2}" text-anchor="middle" '
                    f'font-size="{fs}" font-family="Arial" fill="#000">'
                    f"{panel_num}</text>"
                )
                svg.append("</g>")

            # Racking rails: green lines at top/bottom of each panel row
            if pr.panels:
                # Group panels by approximate row (cluster by center_y)
                panels_sorted = sorted(pr.panels, key=lambda p: p.center_y)
                row_groups = []
                current_row = [panels_sorted[0]]
                for p in panels_sorted[1:]:
                    if abs(p.center_y - current_row[0].center_y) < p.height_pts * 0.8:
                        current_row.append(p)
                    else:
                        row_groups.append(current_row)
                        current_row = [p]
                row_groups.append(current_row)

                for row_panels in row_groups:
                    min_cx_pts = min(p.center_x for p in row_panels)
                    max_cx_pts = max(p.center_x for p in row_panels)
                    sample_p = row_panels[0]
                    half_w = sample_p.width_pts / 2
                    half_h = sample_p.height_pts / 2
                    rail_top_pts = sample_p.center_y - half_h + 2
                    rail_bot_pts = sample_p.center_y + half_h - 2
                    rx0, ry_t = pt2svg(min_cx_pts - half_w - 4, rail_top_pts)
                    rx1, _ = pt2svg(max_cx_pts + half_w + 4, rail_top_pts)
                    _, ry_b = pt2svg(min_cx_pts, rail_bot_pts)
                    svg.append(
                        f'<line x1="{rx0:.1f}" y1="{ry_t:.1f}" '
                        f'x2="{rx1:.1f}" y2="{ry_t:.1f}" '
                        f'stroke="#4a9e4a" stroke-width="1.8"/>'
                    )
                    svg.append(
                        f'<line x1="{rx0:.1f}" y1="{ry_b:.1f}" '
                        f'x2="{rx1:.1f}" y2="{ry_b:.1f}" '
                        f'stroke="#4a9e4a" stroke-width="1.8"/>'
                    )
                    # Attachment points at rail ends
                    for att_x_pts in [min_cx_pts - half_w, max_cx_pts + half_w]:
                        ax, _ = pt2svg(att_x_pts, rail_top_pts)
                        svg.append(
                            f'<circle cx="{ax:.1f}" cy="{ry_t:.1f}" r="3" '
                            f'fill="#1a6ea8" stroke="#000" stroke-width="0.5"/>'
                        )
                        svg.append(
                            f'<circle cx="{ax:.1f}" cy="{ry_b:.1f}" r="3" '
                            f'fill="#1a6ea8" stroke="#000" stroke-width="0.5"/>'
                        )

            # Segment label above polygon
            poly_cx2, _ = pt2svg(rf.polygon.centroid.x, rf.polygon.centroid.y)
            poly_top_svg = min(pt2svg(x, y)[1] for x, y in rf.polygon.exterior.coords)
            direction = azimuth_label(rf.azimuth_deg)
            svg.append(
                f'<text x="{poly_cx2:.1f}" y="{poly_top_svg - 18:.0f}" '
                f'text-anchor="middle" font-size="11" font-weight="700" '
                f'font-family="Arial" fill="#000">ROOF #{pri + 1}</text>'
            )
            svg.append(
                f'<text x="{poly_cx2:.1f}" y="{poly_top_svg - 6:.0f}" '
                f'text-anchor="middle" font-size="8" font-family="Arial" fill="#555">'
                f"{direction} ({rf.azimuth_deg:.0f}°) — {rf.pitch_deg:.0f}° tilt"
                f" — {len(pr.panels)} panels</text>"
            )

            # 3'-0" setback callout on right side of polygon
            poly_right_svg = max(pt2svg(x, y)[0] for x, y in rf.polygon.exterior.coords)
            sb_callout_px = SETBACK_M * face_px_per_m
            ann_x_r = poly_right_svg + 8
            ann_top = poly_top_svg
            svg.append(
                f'<line x1="{ann_x_r:.1f}" y1="{ann_top:.1f}" '
                f'x2="{ann_x_r:.1f}" y2="{ann_top + sb_callout_px:.1f}" '
                f'stroke="#cc0000" stroke-width="1" '
                f'marker-start="url(#dim-l)" marker-end="url(#dim-r)"/>'
            )
            svg.append(
                f'<text x="{ann_x_r + 4:.1f}" y="{ann_top + sb_callout_px / 2 + 3:.1f}" '
                f'font-size="7.5" font-weight="700" font-family="Arial" fill="#cc0000">'
                f"3'-0&quot; TYP.</text>"
            )

    else:
        # ── Fallback: draw abstract segments when no placements available ──
        panels_by_seg = {}
        if insight and insight.panels and num_api_panels:
            for p in insight.panels[:num_api_panels]:
                seg_idx = getattr(p, "segment_index", 0)
                panels_by_seg.setdefault(seg_idx, []).append(p)

        segments = insight.roof_segments if insight and insight.roof_segments else []
        num_segs = max(1, len([s for s in segments if s.index in panels_by_seg]))
        seg_gap = 60
        available_w_per_seg = (draw_w - (num_segs - 1) * seg_gap) / max(num_segs, 1)
        available_h = draw_h - 60

        if segments:
            largest_seg = max(segments, key=lambda s: s.area_m2)
            est_w = math.sqrt(largest_seg.area_m2 * 1.5)
            est_h = math.sqrt(largest_seg.area_m2 / 1.5)
            px_per_m = min(available_w_per_seg / est_w, available_h / est_h) * 0.85
        else:
            px_per_m = 40

        seg_x_cursor = draw_x + 40
        for seg in segments:
            seg_panels = panels_by_seg.get(seg.index, [])
            if not seg_panels and seg.index != 0:
                continue
            direction = azimuth_label(seg.azimuth_deg)
            seg_w_m = math.sqrt(seg.area_m2 * 1.5)
            seg_h_m = math.sqrt(seg.area_m2 / 1.5)
            seg_w_px = seg_w_m * px_per_m
            seg_h_px = seg_h_m * px_per_m
            sb_px = SETBACK_M * px_per_m
            panel_w_px = PANEL_W_M * px_per_m
            panel_h_px = PANEL_H_M * px_per_m
            gap_px = GAP_M * px_per_m
            seg_x = seg_x_cursor
            seg_y = draw_y + (draw_h - seg_h_px) / 2

            svg.append(
                f'<rect x="{seg_x:.1f}" y="{seg_y:.1f}" width="{seg_w_px:.1f}" '
                f'height="{seg_h_px:.1f}" fill="#fafafa" stroke="#000" stroke-width="2"/>'
            )
            svg.append(
                f'<rect x="{seg_x + sb_px:.1f}" y="{seg_y + sb_px:.1f}" '
                f'width="{seg_w_px - 2 * sb_px:.1f}" height="{seg_h_px - 2 * sb_px:.1f}" '
                f'fill="none" stroke="#cc0000" stroke-width="1" stroke-dasharray="6,3"/>'
            )

            usable_x = seg_x + sb_px + gap_px
            usable_y = seg_y + sb_px + gap_px
            usable_w = seg_w_px - 2 * sb_px - 2 * gap_px
            usable_h = seg_h_px - 2 * sb_px - 2 * gap_px
            pw, ph = panel_w_px, panel_h_px
            cols = max(1, int((usable_w + gap_px) / (pw + gap_px)))
            rows = max(1, int((usable_h + gap_px) / (ph + gap_px)))
            grid_w = cols * pw + (cols - 1) * gap_px
            grid_h = rows * ph + (rows - 1) * gap_px
            grid_x = usable_x + (usable_w - grid_w) / 2
            grid_y = usable_y + (usable_h - grid_h) / 2

            panel_count = 0
            max_to_draw = len(seg_panels) if seg_panels else cols * rows
            for r in range(rows):
                for c in range(cols):
                    if panel_count >= max_to_draw:
                        break
                    px2 = grid_x + c * (pw + gap_px)
                    py2 = grid_y + r * (ph + gap_px)
                    svg.append(
                        f'<rect x="{px2:.1f}" y="{py2:.1f}" width="{pw:.1f}" '
                        f'height="{ph:.1f}" fill="#ffffff" stroke="#333" stroke-width="0.8"/>'
                    )
                    panel_count += 1

            svg.append(
                f'<text x="{seg_x + seg_w_px / 2:.1f}" y="{seg_y - 18:.0f}" '
                f'text-anchor="middle" font-size="12" font-weight="700" '
                f'font-family="Arial" fill="#000">ROOF SEGMENT {seg.index + 1}</text>'
            )
            svg.append(
                f'<text x="{seg_x + seg_w_px / 2:.1f}" y="{seg_y - 5:.0f}" '
                f'text-anchor="middle" font-size="9" font-family="Arial" fill="#555">'
                f"{direction} ({seg.azimuth_deg:.0f}°) — Pitch {seg.pitch_deg:.0f}° — "
                f"{panel_count} panels</text>"
            )
            seg_x_cursor += seg_w_px + seg_gap + 60


    # ── BOTTOM INFO BAND + TITLE BLOCK — delegated to racking_plan_details ──
    from renderer.page_builders.racking_plan_details import build_racking_bottom_band
    _rp_calc = {
        'VW': VW, 'VH': VH, 'BORDER': BORDER, 'DRAW_BOTTOM': DRAW_BOTTOM,
        'px_per_m': px_per_m, '_pitch_deg': _pitch_deg,
        '_array_area_sqft': _array_area_sqft, '_roof_area_sqft': _roof_area_sqft,
        '_array_pct': _array_pct,
    }
    build_racking_bottom_band(svg, renderer, address, today, _rp_calc)

    content = "\n".join(svg)
    return (
        f'<div class="page"><svg width="100%" height="100%" '
        f'viewBox="0 0 {VW} {VH}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#fff;">{content}</svg></div>'
    )
