"""Page builder: Site Plan — Satellite view (PV-3)
=================================================
Satellite background with Mercator-projected panels.
Split from site_plan.py.
"""

import math

from renderer.shared.geo_utils import latlng_to_pixel


def build_site_plan_satellite(
    renderer, insight, sat_b64, page_w, page_h, panels,
    mpp, n_panels, total_kw_display, address, today,
) -> str:
    """PV-3 Satellite: Satellite background with Mercator-projected panels."""
    VW, VH = 1280, 960
    BORDER = 20

    # ── Layout zones ────────────────────────────────────────────────────
    DIVIDER_X = 935  # x where right column starts
    DRAW_X = BORDER
    DRAW_Y = 50  # below page title strip
    DRAW_W = DIVIDER_X - BORDER - 5  # ≈ 910 px
    DRAW_H = VH - DRAW_Y - BORDER - 10  # ≈ 880 px (title block overlaps bottom-right)
    RC_X = DIVIDER_X + 8
    RC_W = VW - DIVIDER_X - BORDER - 8  # ≈ 317 px

    # ── Panel data in satellite pixel space ──────────────────────────────
    # Compute 4 corner positions per panel using the same geometry as
    # SolarMap.jsx: bearing = atan2(y,x) + orientation + azimuth
    # This ensures the planset panels match the 2D viewer exactly.
    panel_data = []
    half_w = insight.panel_width_m / 2
    half_h = insight.panel_height_m / 2
    corners_local = [(+half_w, +half_h), (+half_w, -half_h), (-half_w, -half_h), (-half_w, +half_h)]
    cos_clat = math.cos(math.radians(insight.lat))

    for idx, p in enumerate(panels):
        orientation = 90 if p.orientation == "PORTRAIT" else 0
        seg_idx = getattr(p, "segment_index", 0)
        seg = insight.roof_segments[seg_idx] if seg_idx < len(insight.roof_segments) else None
        azimuth = seg.azimuth_deg if seg else 180

        corner_pixels = []
        for x, y in corners_local:
            distance = math.sqrt(x * x + y * y)
            bearing_deg = math.degrees(math.atan2(y, x)) + orientation + azimuth
            bearing_rad = math.radians(bearing_deg)
            dlat = distance * math.cos(bearing_rad) / 111319.5
            dlng = distance * math.sin(bearing_rad) / (111319.5 * cos_clat)
            cpx, cpy = latlng_to_pixel(
                p.center_lat + dlat,
                p.center_lng + dlng,
                insight.lat,
                insight.lng,
                mpp,
                page_w,
                page_h,
            )
            corner_pixels.append((cpx, cpy))
        panel_data.append({"corners": corner_pixels, "idx": idx})

    # ── Cluster centre & zoom factor ─────────────────────────────────────
    all_corner_x = [cx for pd in panel_data for cx, cy in pd["corners"]]
    all_corner_y = [cy for pd in panel_data for cx, cy in pd["corners"]]
    cluster_cx = (min(all_corner_x) + max(all_corner_x)) / 2
    cluster_cy = (min(all_corner_y) + max(all_corner_y)) / 2
    cluster_span = max(
        max(all_corner_x) - min(all_corner_x),
        max(all_corner_y) - min(all_corner_y),
        1,
    )

    # Panel cluster should span ~38 % of the smaller drawing dimension
    target_span = min(DRAW_W, DRAW_H) * 0.38
    sat_scale = max(0.35, min(3.5, target_span / cluster_span))

    # Centre of drawing area in SVG coords (shift slightly up for room below)
    draw_cx_svg = DRAW_X + DRAW_W / 2
    draw_cy_svg = DRAW_Y + DRAW_H * 0.44

    # Transform: satellite pixel → SVG screen coordinate
    sat_tx = draw_cx_svg - cluster_cx * sat_scale
    sat_ty = draw_cy_svg - cluster_cy * sat_scale

    def _s(sat_x, sat_y):
        """Convert satellite pixel coordinate → SVG screen coordinate."""
        return sat_tx + sat_x * sat_scale, sat_ty + sat_y * sat_scale

    # ── Panel screen positions ────────────────────────────────────────────
    screen_panels = []
    for pd in panel_data:
        scr_corners = [_s(cx, cy) for cx, cy in pd["corners"]]
        screen_panels.append({"corners": scr_corners, "idx": pd["idx"]})

    # Array bounding box in screen space (from all corners)
    all_scr_x = [cx for sp in screen_panels for cx, cy in sp["corners"]]
    all_scr_y = [cy for sp in screen_panels for cx, cy in sp["corners"]]
    arr_xmin = min(all_scr_x)
    arr_xmax = max(all_scr_x)
    arr_ymin = min(all_scr_y)
    arr_ymax = max(all_scr_y)

    # Fire setback in screen pixels: 18 in = 0.457 m
    sb_scr = max(8.0, (0.457 / mpp) * sat_scale)

    # Roof segment info
    seg0 = insight.roof_segments[0] if insight.roof_segments else None
    az_deg = round(seg0.azimuth_deg, 0) if seg0 else 180
    pitch_deg = round(seg0.pitch_deg, 0) if seg0 else 0

    AC_kw = renderer._calc_ac_kw(n_panels)  # n_panels × 384VA = proper AC capacity

    # ═══════════════════════════════════════════════════════════════════
    # BUILD SVG
    # ═══════════════════════════════════════════════════════════════════
    svg = []

    # ── Defs ─────────────────────────────────────────────────────────────
    svg.append("<defs>")
    svg.append(
        f'<clipPath id="pv3-clip"><rect x="{DRAW_X}" y="{DRAW_Y}" width="{DRAW_W}" height="{DRAW_H}"/></clipPath>'
    )
    svg.append(
        '<pattern id="pv3-fire" patternUnits="userSpaceOnUse" '
        'width="7" height="7" patternTransform="rotate(45)">'
        '<line x1="0" y1="0" x2="0" y2="7" stroke="#dd0000" '
        'stroke-width="1.2" opacity="0.45"/></pattern>'
    )
    svg.append("</defs>")

    # ── White page background ─────────────────────────────────────────────
    svg.append(f'<rect width="{VW}" height="{VH}" fill="#ffffff"/>')

    # ── Engineering border ────────────────────────────────────────────────
    svg.append(
        f'<rect x="{BORDER}" y="{BORDER}" '
        f'width="{VW - 2 * BORDER}" height="{VH - 2 * BORDER}" '
        f'fill="none" stroke="#000" stroke-width="1.5"/>'
    )

    # ── Vertical divider: drawing area | right column ─────────────────────
    svg.append(
        f'<line x1="{DIVIDER_X}" y1="{BORDER}" '
        f'x2="{DIVIDER_X}" y2="{VH - BORDER}" '
        f'stroke="#000" stroke-width="0.8"/>'
    )

    # ── Page title ────────────────────────────────────────────────────────
    svg.append(
        f'<text x="{DRAW_X + 8}" y="{BORDER + 16}" font-size="13" '
        f'font-weight="700" font-family="Arial" fill="#000">'
        f"PV-3: SITE PLAN \u2014 AERIAL &amp; PANELS</text>"
    )
    svg.append(
        f'<text x="{DRAW_X + 8}" y="{BORDER + 29}" font-size="7.5" '
        f'font-family="Arial" fill="#555">'
        f"SCALE: 1/8&quot; = 1&apos;-0&quot;</text>"
    )

    # ── Satellite image (clipped to drawing area) ─────────────────────────
    svg.append(f'<g clip-path="url(#pv3-clip)">')
    svg.append(
        f'<image href="data:image/png;base64,{sat_b64}" '
        f'x="{sat_tx:.1f}" y="{sat_ty:.1f}" '
        f'width="{page_w * sat_scale:.1f}" '
        f'height="{page_h * sat_scale:.1f}" '
        f'preserveAspectRatio="none"/>'
    )

    # ── Fire setback hatched border (inside clip) ─────────────────────────
    fsb_x = arr_xmin - sb_scr
    fsb_y = arr_ymin - sb_scr
    fsb_w = arr_xmax - arr_xmin + 2 * sb_scr
    fsb_h = arr_ymax - arr_ymin + 2 * sb_scr
    svg.append(
        f'<rect x="{fsb_x:.1f}" y="{fsb_y:.1f}" '
        f'width="{fsb_w:.1f}" height="{fsb_h:.1f}" '
        f'fill="url(#pv3-fire)" stroke="#dd0000" '
        f'stroke-width="1.2" stroke-dasharray="5,3" opacity="0.85"/>'
    )

    # ── Panel overlays: white engineering style (polygon corners) ─────────
    for sp in screen_panels:
        corners = sp["corners"]
        idx = sp["idx"]
        pts = " ".join(f"{cx:.1f},{cy:.1f}" for cx, cy in corners)
        svg.append(f'<polygon points="{pts}" fill="rgba(255,255,255,0.82)" stroke="#000" stroke-width="1.4"/>')
        # 2 internal cell-column lines (interpolated along edges)
        for ci in range(1, 3):
            t = ci / 3.0
            # Interpolate along top edge (corner 0→1) and bottom edge (corner 3→2)
            lx1 = corners[0][0] + t * (corners[1][0] - corners[0][0])
            ly1 = corners[0][1] + t * (corners[1][1] - corners[0][1])
            lx2 = corners[3][0] + t * (corners[2][0] - corners[3][0])
            ly2 = corners[3][1] + t * (corners[2][1] - corners[3][1])
            svg.append(
                f'<line x1="{lx1:.1f}" y1="{ly1:.1f}" '
                f'x2="{lx2:.1f}" y2="{ly2:.1f}" '
                f'stroke="#555" stroke-width="0.4"/>'
            )
        # Panel number at centroid
        pcx = sum(cx for cx, cy in corners) / 4
        pcy = sum(cy for cx, cy in corners) / 4
        # Estimate panel screen height for font sizing
        edge_h = math.sqrt((corners[1][0] - corners[2][0]) ** 2 + (corners[1][1] - corners[2][1]) ** 2)
        fsize = max(5, min(9, edge_h * 0.42))
        svg.append(
            f'<text x="{pcx:.1f}" y="{pcy + fsize * 0.35:.1f}" text-anchor="middle" '
            f'font-size="{fsize:.0f}" font-family="Arial" fill="#000" '
            f'font-weight="600">{idx + 1}</text>'
        )

    svg.append("</g>")  # end pv3-clip

    # ── Setback dimension callout (screen space, outside clip) ────────────
    if DRAW_X + 5 < fsb_x < DRAW_X + DRAW_W - 5:
        sb_ann_x = fsb_x - 4
        sb_ann_y = arr_ymin - sb_scr - 6
        svg.append(
            f'<text x="{sb_ann_x:.0f}" y="{sb_ann_y:.0f}" '
            f'text-anchor="end" font-size="7.5" font-weight="600" '
            f'font-family="Arial" fill="#dd0000">1&apos;-6&quot; TYP.</text>'
        )
        svg.append(
            f'<line x1="{fsb_x:.0f}" y1="{sb_ann_y + 1:.0f}" '
            f'x2="{fsb_x:.0f}" y2="{arr_ymin:.0f}" '
            f'stroke="#dd0000" stroke-width="0.8"/>'
        )

    # ── Equipment callout symbols ─────────────────────────────────────────
    # Row of circles below the panel array (connected by dashed leader lines)
    # Microinverter system: NO DC disconnect, NO separate combiner box.
    # Equipment: UM (meter) → MP (main panel) → JB (junction box) → LC (load center)
    eq_row_y = min(arr_ymax + sb_scr + 38, DRAW_Y + DRAW_H - 85)
    eq_row_y = max(eq_row_y, arr_ymax + 30)
    equipment = [
        ("UM", "MAIN BILLING METER\nAND SERVICE POINT"),
        ("MP", "MAIN SERVICE PANEL"),
        ("JB", "JUNC. BOX\nNEMA 3R"),
        ("LC", "125A RATED PV\nLOAD CENTER"),
    ]
    eq_spacing = 76
    eq_total_w = len(equipment) * eq_spacing
    eq_start_x = max(DRAW_X + 20, min(draw_cx_svg - eq_total_w / 2, DRAW_X + DRAW_W - eq_total_w - 15))

    for i, (abbr, desc_raw) in enumerate(equipment):
        ex = eq_start_x + i * eq_spacing + 30
        ey = eq_row_y
        if ex < DRAW_X or ex > DRAW_X + DRAW_W - 10:
            continue

        # Dashed leader from array bottom to symbol
        anchor_x = min(max(ex, arr_xmin), arr_xmax)
        svg.append(
            f'<line x1="{anchor_x:.0f}" y1="{arr_ymax + sb_scr:.0f}" '
            f'x2="{ex:.0f}" y2="{ey - 16:.0f}" '
            f'stroke="#555" stroke-width="0.8" stroke-dasharray="4,2"/>'
        )

        # Equipment circle with abbreviation
        svg.append(f'<circle cx="{ex:.0f}" cy="{ey:.0f}" r="13" fill="#fff" stroke="#000" stroke-width="1.5"/>')
        fz = "6.5" if len(abbr) > 2 else "8"
        svg.append(
            f'<text x="{ex:.0f}" y="{ey + 4:.0f}" text-anchor="middle" '
            f'font-size="{fz}" font-weight="700" font-family="Arial" '
            f'fill="#000">{abbr}</text>'
        )

        # Description box below circle
        desc_lines = desc_raw.split("\n")
        box_w = 74
        box_h = len(desc_lines) * 11 + 8
        box_x = ex - box_w / 2
        box_y = ey + 16
        svg.append(
            f'<rect x="{box_x:.0f}" y="{box_y:.0f}" '
            f'width="{box_w}" height="{box_h}" '
            f'fill="#f8f8f8" stroke="#000" stroke-width="0.8"/>'
        )
        for j, line in enumerate(desc_lines):
            svg.append(
                f'<text x="{ex:.0f}" y="{box_y + 9 + j * 11:.0f}" '
                f'text-anchor="middle" font-size="6.5" '
                f'font-family="Arial" fill="#000">{line}</text>'
            )

    # ── Conduit runs ──────────────────────────────────────────────────────
    # All wiring is AC in a microinverter system — no DC conduit runs.
    # AC trunk cables: center of array → JB (junction box, index 2)
    jb_idx = 2  # JB is the 3rd symbol (0-based index 2)
    jb_x = eq_start_x + jb_idx * eq_spacing + 30
    ac_trunk_ax = min(max(jb_x, arr_xmin), arr_xmax)  # anchor at array bottom
    ac_trunk_sy = arr_ymax + sb_scr
    ac_trunk_ey = eq_row_y - 16

    svg.append(
        f'<line x1="{ac_trunk_ax:.0f}" y1="{ac_trunk_sy:.0f}" '
        f'x2="{jb_x:.0f}" y2="{ac_trunk_ey:.0f}" '
        f'fill="none" stroke="#cc0000" stroke-width="1.5" '
        f'stroke-dasharray="8,5"/>'
    )
    svg.append(
        f'<text x="{(ac_trunk_ax + jb_x) / 2 + 5:.0f}" '
        f'y="{(ac_trunk_sy + ac_trunk_ey) / 2:.0f}" '
        f'font-size="6.5" font-weight="700" font-family="Arial" '
        f'fill="#cc0000">AC TRUNK</text>'
    )

    # AC conduit (dashed red): LC position (index 3) → right of drawing area
    lc_idx = 3  # LC is the 4th symbol (0-based index 3)
    ac_start_x = eq_start_x + lc_idx * eq_spacing + 30
    ac_start_y = eq_row_y
    ac_end_x = min(ac_start_x + 110, DRAW_X + DRAW_W - 15)
    if ac_end_x > ac_start_x + 20:
        svg.append(
            f'<line x1="{ac_start_x:.0f}" y1="{ac_start_y:.0f}" '
            f'x2="{ac_end_x:.0f}" y2="{ac_start_y:.0f}" '
            f'fill="none" stroke="#cc0000" stroke-width="1.5" '
            f'stroke-dasharray="8,5"/>'
        )
        svg.append(
            f'<text x="{(ac_start_x + ac_end_x) / 2:.0f}" '
            f'y="{ac_start_y - 5:.0f}" text-anchor="middle" '
            f'font-size="7" font-weight="700" font-family="Arial" '
            f'fill="#cc0000">AC</text>'
        )

    # ── North arrow (top-right of drawing area) ───────────────────────────
    na_cx = DRAW_X + DRAW_W - 40
    na_cy = DRAW_Y + 48
    svg.append(
        f'<polygon points="{na_cx},{na_cy - 19} {na_cx - 7},{na_cy + 10} '
        f'{na_cx},{na_cy + 4} {na_cx + 7},{na_cy + 10}" fill="#000"/>'
    )
    svg.append(
        f'<polygon points="{na_cx},{na_cy + 4} {na_cx - 7},{na_cy + 10} '
        f'{na_cx + 7},{na_cy + 10}" fill="#fff" stroke="#000" stroke-width="0.8"/>'
    )
    svg.append(
        f'<text x="{na_cx}" y="{na_cy - 23}" text-anchor="middle" '
        f'font-size="14" font-weight="700" font-family="Arial" fill="#000">N</text>'
    )

    # ── Scale bar (bottom-left of drawing area) ───────────────────────────
    px_per_m = (1.0 / mpp) * sat_scale
    _use_imperial = (renderer._code_prefix == "NEC")
    if _use_imperial:
        bar_m = 5 * 0.3048  # 5 feet in meters
        bar_label = "5'"
    else:
        bar_m = 5  # 5 meters
        bar_label = "5m"
    bar_px = px_per_m * bar_m
    sbar_x = DRAW_X + 20
    sbar_y = DRAW_Y + DRAW_H - 28
    # Alternating black/white segments
    svg.append(f'<rect x="{sbar_x:.0f}" y="{sbar_y - 6:.0f}" width="{bar_px / 2:.0f}" height="6" fill="#000"/>')
    svg.append(
        f'<rect x="{sbar_x + bar_px / 2:.0f}" y="{sbar_y - 6:.0f}" '
        f'width="{bar_px / 2:.0f}" height="6" '
        f'fill="#fff" stroke="#000" stroke-width="0.8"/>'
    )
    svg.append(
        f'<line x1="{sbar_x:.0f}" y1="{sbar_y - 6:.0f}" '
        f'x2="{sbar_x:.0f}" y2="{sbar_y:.0f}" '
        f'stroke="#000" stroke-width="1"/>'
    )
    svg.append(
        f'<line x1="{sbar_x + bar_px:.0f}" y1="{sbar_y - 6:.0f}" '
        f'x2="{sbar_x + bar_px:.0f}" y2="{sbar_y:.0f}" '
        f'stroke="#000" stroke-width="1"/>'
    )
    svg.append(
        f'<text x="{sbar_x:.0f}" y="{sbar_y + 9:.0f}" font-size="7.5" font-family="Arial" fill="#000">0</text>'
    )
    svg.append(
        f'<text x="{sbar_x + bar_px:.0f}" y="{sbar_y + 9:.0f}" '
        f'text-anchor="end" font-size="7.5" font-family="Arial" '
        f'fill="#000">{bar_label}</text>'
    )
    svg.append(
        f'<text x="{sbar_x + bar_px / 2:.0f}" y="{sbar_y - 9:.0f}" '
        f'text-anchor="middle" font-size="7" font-family="Arial" '
        f'fill="#555">SCALE BAR</text>'
    )

    # ═══ RIGHT COLUMN ════════════════════════════════════════════════════
    RC_Y_TOP = BORDER + 8

    # ── SYSTEM LEGEND ─────────────────────────────────────────────────────
    sl_y = RC_Y_TOP
    sl_h = 335
    svg.append(
        f'<rect x="{RC_X}" y="{sl_y}" width="{RC_W}" height="{sl_h}" fill="#fff" stroke="#000" stroke-width="1.2"/>'
    )
    svg.append(
        f'<rect x="{RC_X}" y="{sl_y}" width="{RC_W}" height="17" fill="#e8e8e8" stroke="#000" stroke-width="1"/>'
    )
    svg.append(
        f'<text x="{RC_X + RC_W // 2}" y="{sl_y + 12}" '
        f'text-anchor="middle" font-size="9" font-weight="700" '
        f'font-family="Arial" fill="#000">SYSTEM LEGEND</text>'
    )

    # System summary
    ly = sl_y + 23
    for txt, bold in [
        ("PHOTOVOLTAIC SYSTEM:", True),
        (f"DC SYSTEM SIZE: {total_kw_display:.2f} kW", False),
        (f"AC SYSTEM SIZE: {AC_kw:.2f} kW", False),
    ]:
        w700 = "700" if bold else "400"
        fsz = "8.5" if bold else "8"
        svg.append(
            f'<text x="{RC_X + 6}" y="{ly}" font-size="{fsz}" '
            f'font-weight="{w700}" font-family="Arial" fill="#000">{txt}</text>'
        )
        ly += 13

    svg.append(
        f'<line x1="{RC_X + 4}" y1="{ly + 2}" '
        f'x2="{RC_X + RC_W - 4}" y2="{ly + 2}" '
        f'stroke="#ccc" stroke-width="0.6"/>'
    )
    ly += 8

    # Equipment entries (small rectangle with abbreviation + description)
    # Microinverter system: NO DC disconnect, NO separate combiner box.
    eq_legend = [
        ("UM", "MAIN BILLING METER AND SERVICE POINT"),
        ("MP", "MAIN SERVICE PANEL"),
        ("JB", "JUNCTION BOX (NEMA 3R) — AC TRUNK MERGE"),
        ("LC", "125A RATED PV LOAD CENTER"),
    ]
    for abbr, desc in eq_legend:
        svg.append(
            f'<rect x="{RC_X + 5}" y="{ly - 1}" width="26" height="14" fill="#fff" stroke="#000" stroke-width="1"/>'
        )
        fz2 = "6.5" if len(abbr) > 2 else "7.5"
        svg.append(
            f'<text x="{RC_X + 18}" y="{ly + 9}" text-anchor="middle" '
            f'font-size="{fz2}" font-weight="700" font-family="Arial" '
            f'fill="#000">{abbr}</text>'
        )
        if len(desc) > 28:
            mid = desc.rfind(" ", 0, len(desc) // 2 + 5)
            l1, l2 = desc[:mid], desc[mid + 1 :]
            svg.append(
                f'<text x="{RC_X + 36}" y="{ly + 5}" font-size="6.2" font-family="Arial" fill="#000">{l1}</text>'
            )
            svg.append(
                f'<text x="{RC_X + 36}" y="{ly + 14}" font-size="6.2" font-family="Arial" fill="#000">{l2}</text>'
            )
            ly += 22
        else:
            svg.append(
                f'<text x="{RC_X + 36}" y="{ly + 9}" font-size="7" font-family="Arial" fill="#000">{desc}</text>'
            )
            ly += 17

    # ── Module / microinverter legend entry (Cubillas PV-3 standard) ────────
    # Shows a small panel icon + "(N) [MODULE MODEL] [W] WITH [INVERTER] [V]
    # MICROINVERTERS MOUNTED UNDER EACH MODULE." — matches the entry that
    # appears in the Cubillas PV-3 System Legend between the equipment symbols
    # and the conduit/fire-setback line style entries.
    _mi_icon_x = RC_X + 5
    _mi_icon_y = ly
    _mi_icon_w = 28
    _mi_icon_h = 16
    # Panel icon: white rectangle with internal grid lines (suggests a PV module)
    svg.append(
        f'<rect x="{_mi_icon_x}" y="{_mi_icon_y}" width="{_mi_icon_w}" '
        f'height="{_mi_icon_h}" fill="#ffffff" stroke="#000000" stroke-width="1"/>'
    )
    for _ci in range(1, 3):
        _gcx = _mi_icon_x + _ci * _mi_icon_w // 3
        svg.append(
            f'<line x1="{_gcx}" y1="{_mi_icon_y + 2}" '
            f'x2="{_gcx}" y2="{_mi_icon_y + _mi_icon_h - 2}" '
            f'stroke="#aaaaaa" stroke-width="0.5"/>'
        )
    svg.append(
        f'<line x1="{_mi_icon_x + 2}" y1="{_mi_icon_y + _mi_icon_h // 2}" '
        f'x2="{_mi_icon_x + _mi_icon_w - 2}" y2="{_mi_icon_y + _mi_icon_h // 2}" '
        f'stroke="#aaaaaa" stroke-width="0.5"/>'
    )
    # Module + inverter description text (3 wrapped lines at font-size 6)
    if renderer._is_micro:
        _mi_lines = [
            f"({n_panels}) {renderer.panel.name} [{renderer.panel.wattage}W]",
            f"WITH {renderer.INV_MODEL_SHORT} [240V]",
            "MICROINVERTERS MOUNTED UNDER EACH MODULE.",
        ]
    else:
        _mi_lines = [
            f"({n_panels}) {renderer.panel.name} [{renderer.panel.wattage}W]",
            f"WITH {renderer.INV_MODEL_SHORT} STRING INVERTER",
            "CENTRAL INVERTER — DC STRING WIRING.",
        ]
    for _li, _lt in enumerate(_mi_lines):
        svg.append(
            f'<text x="{RC_X + 38}" y="{ly + 7 + _li * 11}" '
            f'font-size="6" font-family="Arial" fill="#000">{_lt}</text>'
        )
    ly += max(_mi_icon_h + 4, len(_mi_lines) * 11 + 4)

    svg.append(
        f'<line x1="{RC_X + 4}" y1="{ly + 2}" '
        f'x2="{RC_X + RC_W - 4}" y2="{ly + 2}" '
        f'stroke="#ccc" stroke-width="0.6"/>'
    )
    ly += 8

    # Line style entries
    # Microinverter system has no DC conduit — only AC conduit runs.
    for style, label in [
        ("red-dash", "AC CONDUIT RUN"),
        ("hatch-fire", 'FIRE CODE SETBACK\n(18" MIN / 36" MAX)'),
        ("gray-dash", "CONDUIT RUN"),
    ]:
        lines_l = label.split("\n")
        if style == "red-dash":
            svg.append(
                f'<line x1="{RC_X + 5}" y1="{ly + 6}" '
                f'x2="{RC_X + 32}" y2="{ly + 6}" '
                f'stroke="#cc0000" stroke-width="2" stroke-dasharray="6,3"/>'
            )
        elif style == "hatch-fire":
            svg.append(
                f'<rect x="{RC_X + 5}" y="{ly}" width="27" height="13" '
                f'fill="url(#pv3-fire)" stroke="#dd0000" '
                f'stroke-width="0.6" stroke-dasharray="3,2" opacity="0.85"/>'
            )
        elif style == "gray-dash":
            svg.append(
                f'<line x1="{RC_X + 5}" y1="{ly + 6}" '
                f'x2="{RC_X + 32}" y2="{ly + 6}" '
                f'stroke="#666" stroke-width="1.5" stroke-dasharray="6,3"/>'
            )
        for j_l, line_l in enumerate(lines_l):
            svg.append(
                f'<text x="{RC_X + 36}" y="{ly + 7 + j_l * 10}" '
                f'font-size="7" font-family="Arial" fill="#000">{line_l}</text>'
            )
        ly += max(14, len(lines_l) * 11)

    # ── Conduit routing paragraph (Cubillas PV-3 System Legend standard) ──
    # In Cubillas, this paragraph appears inside the System Legend box,
    # immediately after the "CONDUIT RUN" dashed-line entry — it explains
    # conduit routing rules to the permit reviewer without requiring them
    # to look elsewhere.  Our previous implementation put this text in
    # ADDITIONAL NOTES (wrong location); it belongs here, in the legend.
    svg.append(
        f'<line x1="{RC_X + 4}" y1="{ly + 3}" '
        f'x2="{RC_X + RC_W - 4}" y2="{ly + 3}" '
        f'stroke="#ccc" stroke-width="0.6"/>'
    )
    ly += 9
    _conduit_para = [
        "CONDUIT TO BE RUN IN ATTIC IF POSSIBLE,",
        'OTHERWISE CONDUIT BLOCKS MIN. 1"/MAX 6"',
        "ABOVE ROOF SURFACE, CLOSE TO RIDGE LINES",
        "AND UNDER EAVES; TO BE PAINTED TO MATCH",
        "EXTERIOR/EXISTING BACKGROUND COLOUR;",
        "LABELED AT MAX 10\u2019 INTERVALS. CONDUIT RUNS",
        "ARE APPROXIMATE — FIELD DETERMINED.",
    ]
    for _pl in _conduit_para:
        svg.append(f'<text x="{RC_X + 6}" y="{ly + 9}" font-size="6" font-family="Arial" fill="#333">{_pl}</text>')
        ly += 10
    ly += 4  # bottom margin

    # ── ROOF DETAIL ───────────────────────────────────────────────────────
    rd_y = sl_y + sl_h + 8
    rd_h = 140
    svg.append(
        f'<rect x="{RC_X}" y="{rd_y}" width="{RC_W}" height="{rd_h}" fill="#fff" stroke="#000" stroke-width="1.2"/>'
    )
    svg.append(
        f'<rect x="{RC_X}" y="{rd_y}" width="{RC_W}" height="17" fill="#e8e8e8" stroke="#000" stroke-width="1"/>'
    )
    svg.append(
        f'<text x="{RC_X + RC_W // 2}" y="{rd_y + 12}" '
        f'text-anchor="middle" font-size="9" font-weight="700" '
        f'font-family="Arial" fill="#000">ROOF DETAIL</text>'
    )
    # Section circle
    svg.append(
        f'<circle cx="{RC_X + RC_W - 22}" cy="{rd_y + rd_h // 2 + 10}" '
        f'r="14" fill="#fff" stroke="#000" stroke-width="1.5"/>'
    )
    svg.append(
        f'<text x="{RC_X + RC_W - 22}" y="{rd_y + rd_h // 2 + 16}" '
        f'text-anchor="middle" font-size="15" font-weight="700" '
        f'font-family="Arial" fill="#000">1</text>'
    )
    rd_rows = [
        ("ROOF TYPE:", "ASPHALT-SHINGLES"),
        ("ROOF SECTION 1:", f"{n_panels} MODULES"),
        ("AZIMUTH:", f"{az_deg:.0f}\u00b0"),
        ("PITCH:", f"{pitch_deg:.0f}\u00b0"),
        ("SCALE:", '1/8" = 1\'-0"'),
    ]
    for i, (lbl, val) in enumerate(rd_rows):
        ry2 = rd_y + 22 + i * 22
        svg.append(
            f'<text x="{RC_X + 7}" y="{ry2}" font-size="7.5" '
            f'font-weight="700" font-family="Arial" fill="#000">{lbl}</text>'
        )
        svg.append(
            f'<text x="{RC_X + 7}" y="{ry2 + 13}" font-size="8" font-family="Arial" fill="#333">{val}</text>'
        )

    # ── ADDITIONAL NOTES ──────────────────────────────────────────────────
    # Cubillas PV-3 standard: two specific fire/safety code notes only.
    # (The conduit routing paragraph has moved to the SYSTEM LEGEND above.)
    an_y = rd_y + rd_h + 8
    an_h = 60
    svg.append(
        f'<rect x="{RC_X}" y="{an_y}" width="{RC_W}" height="{an_h}" fill="#fff" stroke="#000" stroke-width="1.2"/>'
    )
    svg.append(
        f'<rect x="{RC_X}" y="{an_y}" width="{RC_W}" height="17" fill="#e8e8e8" stroke="#000" stroke-width="1"/>'
    )
    svg.append(
        f'<text x="{RC_X + RC_W // 2}" y="{an_y + 12}" '
        f'text-anchor="middle" font-size="9" font-weight="700" '
        f'font-family="Arial" fill="#000">ADDITIONAL NOTES</text>'
    )
    # Two specific code-compliance safety notes (verbatim Cubillas PV-3 standard)
    add_notes = [
        ("NO CONDUIT SHALL PASS OVER FIREFIGHTER", "ROOF ACCESS OR VENTILATION PATHS."),
        ("CONDUIT RUN IN THE ATTIC SHALL BE", "MOUNTED 18\u2033 BELOW THE RIDGE."),
    ]
    _an_y = an_y + 24
    for _n1, _n2 in add_notes:
        svg.append(f'<text x="{RC_X + 7}" y="{_an_y}" font-size="6.5" font-family="Arial" fill="#333">{_n1}</text>')
        svg.append(
            f'<text x="{RC_X + 7}" y="{_an_y + 9}" font-size="6.5" font-family="Arial" fill="#333">{_n2}</text>'
        )
        _an_y += 22

    # ── Standard title block ──────────────────────────────────────────────
    svg.append(
        renderer._svg_title_block(
            VW,
            VH,
            sheet_id="PV-3",
            sheet_title="SITE PLAN",
            subtitle="Aerial + Mercator Panels",
            page_of="3 of 13",
            address=address,
            today=today,
        )
    )

    content = "\n".join(svg)
    return (
        f'<div class="page">'
        f'<svg width="100%" height="100%" viewBox="0 0 {VW} {VH}" '
        f'xmlns="http://www.w3.org/2000/svg" style="background:#fff;">'
        f"{content}</svg></div>"
    )

