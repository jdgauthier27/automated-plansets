"""Page builder: Mounting Details and BOM (PV-5 / A-104)
========================================================
Extracted from HtmlRenderer._build_mounting_details_page.
"""

import math


def build_mounting_details_page(renderer, total_panels: int, total_kw: float,
                                address: str, today: str, insight) -> str:
    """PV-5: Mounting Details and Bill of Materials (Cubillas PV-5 equivalent).

    Layout (1280×960 landscape) — matches Cubillas PV-5 standard:
      Left column  (x=30–490):  Attachment elevation cross-section +
                                4 clamp detail drawings (2×2 grid, generous height)
      Center column (x=510–1040): Large attachment spec text (17pt) + BOM table
      Far right: standard title block
    """
    svg = []

    # ── Background & border ──────────────────────────────────────────
    svg.append('<rect width="1280" height="960" fill="#ffffff"/>')
    svg.append('<rect x="20" y="20" width="1240" height="820" fill="none" stroke="#000" stroke-width="2"/>')

    # Vertical divider: left column | center column
    svg.append('<line x1="490" y1="28" x2="490" y2="838" stroke="#000" stroke-width="1"/>')

    # ─────────────────────────────────────────────────────────────────
    # PANEL DIMENSIONS — from ProjectSpec/catalog
    if renderer._project:
        _p = renderer._project.panel
        panel_h_m = _p.dimensions.length_mm / 1000
        panel_w_m = _p.dimensions.width_mm / 1000
        panel_weight_lbs = _p.weight_lbs
    else:
        panel_h_m = 1.800
        panel_w_m = 1.134
        panel_weight_lbs = 58.4

    panel_h_in = panel_h_m / 0.0254
    panel_w_in = panel_w_m / 0.0254
    panel_h_str = f"{int(panel_h_in // 12)}'-{int(panel_h_in % 12):02d}\""
    panel_w_str = f"{int(panel_w_in // 12)}'-{int(panel_w_in % 12):02d}\""
    panel_area_sqft = (panel_h_m * panel_w_m) / (0.3048**2)
    panel_weight_per_sqft = panel_weight_lbs / panel_area_sqft if panel_area_sqft > 0 else 0

    pitch_deg = "19\u00b0"
    if insight and insight.roof_segments:
        pitch_deg = f"{insight.roof_segments[0].pitch_deg:.0f}\u00b0"

    n = total_panels
    _cost_summary = None

    # BOM calculation (import safely)
    try:
        from engine.bom_calculator import calculate_bom
        HAS_BOM = True
    except ImportError:
        HAS_BOM = False

    if HAS_BOM and renderer._project:
        _bom_result = calculate_bom(renderer._project)
        _bom_items = _bom_result["line_items"]
        _bom = {item["description"]: item["qty"] for item in _bom_items}
        _cost_summary = _bom_result
        n_rails = _bom.get("MOUNTING RAIL", max(4, round(n * 0.77)))
        n_end_clamps = _bom.get("END CLAMP", n_rails * 2)
        n_mid_clamps = _bom.get("MID CLAMP", max(4, round(n * 1.85)))
        n_mounts = _bom.get("MOUNTING POINT", max(8, round(n * 1.38)))
        if renderer._project.inverter.is_micro:
            n_inverters = _bom.get("MICROINVERTER", n)
            inverter_row_label = "MICROINVERTERS"
        else:
            n_inverters = _bom.get("STRING INVERTER", 1)
            inverter_row_label = "STRING INVERTER"
    else:
        n_rails = max(4, round(n * 0.77))
        n_end_clamps = n_rails * 2
        n_mid_clamps = max(4, round(n * 1.85))
        n_mounts = max(8, round(n * 1.38))
        n_inverters = n
        inverter_row_label = "MICROINVERTERS"
    total_ac_current_bom = n * renderer.INV_AC_AMPS_PER_UNIT
    system_ocpd_bom = math.ceil(total_ac_current_bom * 1.25 / 5) * 5

    # ════════════════════════════════════════════════════════════════
    # LEFT COLUMN: Elevation Drawing + Clamp Details
    # ════════════════════════════════════════════════════════════════

    # ── Section header ──────────────────────────────────────────────
    svg.append(
        '<text x="40" y="48" font-size="12" font-weight="700" font-family="Arial" fill="#000">ATTACHMENT DETAILS</text>'
    )
    svg.append('<circle cx="265" cy="43" r="9" fill="none" stroke="#000" stroke-width="1.5"/>')
    svg.append(
        '<text x="265" y="47" text-anchor="middle" font-size="9" font-weight="700" font-family="Arial" fill="#000">1</text>'
    )
    svg.append('<text x="278" y="47" font-size="9" font-family="Arial" fill="#555">(N.T.S.)</text>')
    svg.append('<line x1="30" y1="55" x2="488" y2="55" stroke="#000" stroke-width="1"/>')

    # ── Elevation Cross-Section Drawing ──────────────────────────────
    ex, ey = 35, 65
    dw, dh = 455, 255
    cx_drw = ex + dw // 2

    svg.append(
        f'<rect x="{ex}" y="{ey}" width="{dw}" height="{dh}" fill="#ffffff" stroke="#000" stroke-width="0.8"/>'
    )

    # Component y-positions
    _el_mod_y0 = ey + 67
    _el_mod_h = 42
    _el_rail_y0 = _el_mod_y0 + _el_mod_h + 11
    _el_rail_h = 18
    _el_ff2_y0 = _el_rail_y0 + _el_rail_h
    _el_ff2_h = 22
    _el_shingle_y = _el_ff2_y0 + _el_ff2_h
    _el_shingle_h = 9
    _el_rafter_y = _el_shingle_y + _el_shingle_h
    _el_rafter_h = 18

    _el_lx = ex + 17
    _el_rx = ex + 290
    _el_lbl_x = ex + 300

    # ── XR-10 Rail ────────────────────────────────────────────────────
    _el_rl_x = _el_lx - 6
    _el_rl_w = _el_rx - _el_lx + 12
    svg.append(
        f'<rect x="{_el_rl_x}" y="{_el_rail_y0}" width="{_el_rl_w}" '
        f'height="{_el_rail_h}" fill="#4a9e4a" stroke="#000" stroke-width="1.5"/>'
    )
    svg.append(
        f'<line x1="{_el_rl_x + 2}" y1="{_el_rail_y0 + 5}" '
        f'x2="{_el_rl_x + _el_rl_w - 2}" y2="{_el_rail_y0 + 5}" '
        f'stroke="#2d7a2d" stroke-width="0.5"/>'
    )
    svg.append(
        f'<line x1="{_el_rl_x + 2}" y1="{_el_rail_y0 + _el_rail_h - 5}" '
        f'x2="{_el_rl_x + _el_rl_w - 2}" y2="{_el_rail_y0 + _el_rail_h - 5}" '
        f'stroke="#2d7a2d" stroke-width="0.5"/>'
    )

    # ── FlashFoot2 bases ──────────────────────────────────────────────
    _el_span = _el_rx - _el_lx
    _el_ff2_xs = [
        _el_lx + _el_span // 4,
        _el_lx + _el_span // 2,
        _el_lx + 3 * _el_span // 4,
    ]
    for _fx in _el_ff2_xs:
        svg.append(
            f'<rect x="{_fx - 15}" y="{_el_ff2_y0}" width="30" height="10" '
            f'fill="#c8c8c8" stroke="#000" stroke-width="1"/>'
        )
        svg.append(
            f'<line x1="{_fx}" y1="{_el_ff2_y0 + 10}" '
            f'x2="{_fx}" y2="{_el_rafter_y + _el_rafter_h - 3}" '
            f'stroke="#555" stroke-width="2.0"/>'
        )
        svg.append(
            f'<polygon points="{_fx - 3},{_el_rafter_y + _el_rafter_h - 3} '
            f"{_fx + 3},{_el_rafter_y + _el_rafter_h - 3} "
            f'{_fx},{_el_rafter_y + _el_rafter_h + 3}" fill="#555"/>'
        )

    # ── Shingles ─────────────────────────────────────────────────────
    svg.append(
        f'<rect x="{_el_rl_x - 8}" y="{_el_shingle_y}" '
        f'width="{_el_rl_w + 16}" height="{_el_shingle_h}" '
        f'fill="#888888" stroke="#555" stroke-width="0.8"/>'
    )
    for _sxi in range(_el_rl_x - 8, _el_rl_x + _el_rl_w + 20, 30):
        svg.append(
            f'<rect x="{_sxi}" y="{_el_shingle_y}" width="30" height="5" '
            f'fill="none" stroke="#555" stroke-width="0.35"/>'
        )

    # ── Rafters ──────────────────────────────────────────────────────
    for _fx in _el_ff2_xs:
        svg.append(
            f'<rect x="{_fx - 13}" y="{_el_rafter_y}" width="26" '
            f'height="{_el_rafter_h}" fill="#d4b896" stroke="#000" stroke-width="1.2"/>'
        )
        for _gx in range(_fx - 11, _fx + 13, 5):
            svg.append(
                f'<line x1="{_gx}" y1="{_el_rafter_y + 2}" '
                f'x2="{_gx}" y2="{_el_rafter_y + _el_rafter_h - 2}" '
                f'stroke="#b8936a" stroke-width="0.4"/>'
            )

    # ── Two PV modules ───────────────────────────────────────────────
    _el_mod_gap = 10
    _el_mod_w = (_el_rx - _el_lx - _el_mod_gap) // 2
    for _mi in range(2):
        _mx = _el_lx + _mi * (_el_mod_w + _el_mod_gap)
        svg.append(
            f'<rect x="{_mx}" y="{_el_mod_y0}" '
            f'width="{_el_mod_w}" height="{_el_mod_h}" '
            f'fill="#ffffff" stroke="#000000" stroke-width="1.5"/>'
        )
        for _ci in range(1, 5):
            _gcx = _mx + _ci * _el_mod_w // 5
            svg.append(
                f'<line x1="{_gcx}" y1="{_el_mod_y0 + 2}" '
                f'x2="{_gcx}" y2="{_el_mod_y0 + _el_mod_h - 2}" '
                f'stroke="#cccccc" stroke-width="0.4"/>'
            )
        for _ri in range(1, 3):
            svg.append(
                f'<line x1="{_mx + 2}" y1="{_el_mod_y0 + _ri * _el_mod_h // 3}" '
                f'x2="{_mx + _el_mod_w - 2}" y2="{_el_mod_y0 + _ri * _el_mod_h // 3}" '
                f'stroke="#cccccc" stroke-width="0.4"/>'
            )

    # ── End clamps ───────────────────────────────────────────────────
    _el_ec_w = 9
    svg.append(
        f'<rect x="{_el_lx - _el_ec_w}" y="{_el_mod_y0 + 6}" '
        f'width="{_el_ec_w}" height="28" fill="#c8c8c8" stroke="#000" stroke-width="1.2"/>'
    )
    svg.append(
        f'<rect x="{_el_rx}" y="{_el_mod_y0 + 6}" '
        f'width="{_el_ec_w}" height="28" fill="#c8c8c8" stroke="#000" stroke-width="1.2"/>'
    )

    # ── Mid clamp ────────────────────────────────────────────────────
    _el_mc_cx = _el_lx + _el_mod_w + _el_mod_gap // 2
    svg.append(
        f'<rect x="{_el_mc_cx - 8}" y="{_el_mod_y0 + 6}" width="16" height="28" '
        f'fill="#c8c8c8" stroke="#000" stroke-width="1.2"/>'
    )
    svg.append(
        f'<circle cx="{_el_mc_cx}" cy="{_el_mod_y0 + 20}" r="3.5" fill="#888" stroke="#555" stroke-width="0.8"/>'
    )

    # ── Component labels ─────────────────────────────────────────────
    _el_leader_x = _el_rx + 5
    _el_lbl_items = [
        (_el_mod_y0 + _el_mod_h // 2, "PV MODULE FRAME"),
        (_el_rail_y0 + _el_rail_h // 2, "{self._racking_full} RAIL"),
        (_el_ff2_y0 + _el_ff2_h // 2, "{self._attachment_full}"),
        (_el_shingle_y + _el_shingle_h // 2, "ASPHALT SHINGLES"),
        (_el_rafter_y + _el_rafter_h // 2, 'RAFTER @ 24" O.C.'),
    ]
    for _ly, _lt in _el_lbl_items:
        svg.append(
            f'<line x1="{_el_leader_x}" y1="{_ly}" '
            f'x2="{_el_lbl_x - 4}" y2="{_ly}" '
            f'stroke="#555" stroke-width="0.8" stroke-dasharray="4,2"/>'
        )
        svg.append(
            f'<text x="{_el_lbl_x}" y="{_ly + 3}" font-size="7.5" font-family="Arial" fill="#000">{_lt}</text>'
        )

    # ── 4 Clamp Detail Drawings (2×2 grid) ──────────────────────────
    cd_start_y = ey + dh + 10
    cd_area_h = 838 - cd_start_y - 10
    cd_col_w = (490 - 30) // 2
    cd_row_h = cd_area_h // 2 - 8

    def _clamp_lbl(text, cx2, cy2):
        svg.append(
            f'<text x="{cx2}" y="{cy2}" text-anchor="middle" '
            f'font-size="8.5" font-weight="700" font-family="Arial" fill="#000">{text}</text>'
        )

    row0_top = cd_start_y
    row1_top = cd_start_y + cd_row_h + 16

    # ── MID CLAMP — PLAN VIEW (row 0, col 0) ─────────────────────
    mc_px = 30 + cd_col_w // 2
    mc_py = row0_top + cd_row_h // 2 + 8
    _clamp_lbl("DETAIL, MID CLAMP — PLAN VIEW", mc_px, row0_top + 12)

    mf_w, mf_h = 85, 55
    mf_y = mc_py - mf_h // 2
    m_gap = 10
    for mx_off in [mc_px - mf_w - m_gap // 2, mc_px + m_gap // 2]:
        svg.append(
            f'<rect x="{mx_off}" y="{mf_y}" width="{mf_w}" height="{mf_h}" fill="#ffffff" stroke="#000000" stroke-width="2"/>'
        )
        svg.append(
            f'<text x="{mx_off + mf_w // 2}" y="{mf_y + mf_h // 2 + 4}" text-anchor="middle" font-size="7" font-family="Arial" fill="#000000">PV MODULE FRAME</text>'
        )

    rail_plan_y = mc_py - 7
    svg.append(
        f'<rect x="{mc_px - mf_w - m_gap // 2 - 8}" y="{rail_plan_y}" width="{2 * mf_w + m_gap + 16}" height="13" fill="#4a9e4a" stroke="#000" stroke-width="1"/>'
    )
    svg.append(
        f'<text x="{mc_px - mf_w - m_gap // 2 - 8}" y="{rail_plan_y + 22}" font-size="7" font-family="Arial" fill="#000">{renderer._racking_full} RAIL</text>'
    )

    svg.append(
        f'<rect x="{mc_px - 8}" y="{mc_py - 18}" width="16" height="36" fill="#c8c8c8" stroke="#000" stroke-width="1.5"/>'
    )
    svg.append(f'<circle cx="{mc_px}" cy="{mc_py}" r="5" fill="#888" stroke="#000" stroke-width="1"/>')
    svg.append(
        f'<text x="{mc_px + 18}" y="{mc_py + 4}" font-size="7" font-family="Arial" fill="#000">{renderer._racking_manufacturer} CLAMP</text>'
    )
    svg.append(
        f'<text x="{mc_px + 18}" y="{mc_py + 13}" font-size="7" font-family="Arial" fill="#000">FASTENING OBJECT</text>'
    )

    # ── MID CLAMP — FRONT VIEW (row 0, col 1) ─────────────────────
    mc_fx = 30 + cd_col_w + cd_col_w // 2
    mc_fy = mc_py
    _clamp_lbl("DETAIL, MID CLAMP — FRONT VIEW", mc_fx, row0_top + 12)

    fe_w = 13
    fe_h = 44
    fe_y = mc_fy - fe_h // 2
    svg.append(
        f'<rect x="{mc_fx - 52}" y="{fe_y}" width="{fe_w}" height="{fe_h}" fill="#ffffff" stroke="#000000" stroke-width="1.5"/>'
    )
    svg.append(
        f'<text x="{mc_fx - 52 + fe_w // 2}" y="{fe_y - 4}" text-anchor="middle" font-size="7" font-family="Arial" fill="#000">PV MODULE FRAME</text>'
    )
    svg.append(
        f'<rect x="{mc_fx + 52 - fe_w}" y="{fe_y}" width="{fe_w}" height="{fe_h}" fill="#ffffff" stroke="#000000" stroke-width="1.5"/>'
    )

    rail_fe_y = mc_fy + fe_h // 2 - 16
    svg.append(
        f'<rect x="{mc_fx - 58}" y="{rail_fe_y}" width="116" height="20" fill="#4a9e4a" stroke="#000" stroke-width="1"/>'
    )
    svg.append(
        f'<text x="{mc_fx}" y="{rail_fe_y + 33}" text-anchor="middle" font-size="7" font-family="Arial" fill="#000">{renderer._racking_full} RAIL</text>'
    )

    cap_y = fe_y - 11
    svg.append(
        f'<rect x="{mc_fx - 32}" y="{cap_y}" width="64" height="11" fill="#d0d0d0" stroke="#000" stroke-width="1.5"/>'
    )
    svg.append(f'<line x1="{mc_fx}" y1="{cap_y}" x2="{mc_fx}" y2="{rail_fe_y}" stroke="#555" stroke-width="2"/>')

    sleeve_y = rail_fe_y - 7
    svg.append(
        f'<rect x="{mc_fx - 52 + fe_w}" y="{sleeve_y}" width="{2 * (52 - fe_w)}" height="7" fill="#f0f0f0" stroke="#000" stroke-width="1"/>'
    )
    svg.append(
        f'<text x="{mc_fx}" y="{sleeve_y - 4}" text-anchor="middle" font-size="7" font-family="Arial" fill="#555">{renderer._racking_manufacturer} END CLAMP</text>'
    )
    svg.append(
        f'<text x="{mc_fx + 37}" y="{cap_y + 9}" font-size="7" font-family="Arial" fill="#000">{renderer._racking_manufacturer} CLAMP</text>'
    )

    # ── END CLAMP — PLAN VIEW (row 1, col 0) ──────────────────────
    ec_px = mc_px
    ec_py = row1_top + cd_row_h // 2 + 8
    _clamp_lbl("DETAIL, END CLAMP — PLAN VIEW", ec_px, row1_top + 12)

    ef_w, ef_h = 95, 55
    ef_y2 = ec_py - ef_h // 2
    svg.append(
        f'<rect x="{ec_px - ef_w // 2}" y="{ef_y2}" width="{ef_w}" height="{ef_h}" fill="#ffffff" stroke="#000000" stroke-width="2"/>'
    )
    svg.append(
        f'<text x="{ec_px}" y="{ef_y2 + ef_h // 2 + 4}" text-anchor="middle" font-size="7" font-family="Arial" fill="#000000">PV MODULE FRAME</text>'
    )

    rail_ec_y = ec_py - 7
    svg.append(
        f'<rect x="{ec_px - ef_w // 2 - 12}" y="{rail_ec_y}" width="{ef_w + 24}" height="13" fill="#4a9e4a" stroke="#000" stroke-width="1"/>'
    )
    svg.append(
        f'<text x="{ec_px - ef_w // 2 - 12}" y="{rail_ec_y + 22}" font-size="7" font-family="Arial" fill="#000">{renderer._racking_full} RAIL</text>'
    )

    ec_body_x = ec_px + ef_w // 2
    svg.append(
        f'<rect x="{ec_body_x}" y="{ec_py - 14}" width="22" height="28" fill="#d0d0d0" stroke="#000" stroke-width="1.5"/>'
    )
    svg.append(f'<circle cx="{ec_body_x + 11}" cy="{ec_py}" r="5" fill="#888" stroke="#000" stroke-width="1"/>')
    svg.append(
        f'<text x="{ec_body_x + 28}" y="{ec_py + 4}" font-size="7" font-family="Arial" fill="#000">{renderer._racking_manufacturer} CLAMP</text>'
    )
    svg.append(
        f'<text x="{ec_body_x + 28}" y="{ec_py + 13}" font-size="7" font-family="Arial" fill="#000">FASTENING OBJECT</text>'
    )
    svg.append(
        f'<rect x="{ec_body_x - 6}" y="{ec_py - 7}" width="6" height="13" fill="#f0f0f0" stroke="#000" stroke-width="0.8"/>'
    )
    svg.append(
        f'<text x="{ec_body_x - 8}" y="{ec_py - 11}" text-anchor="end" font-size="7" font-family="Arial" fill="#555">{renderer._racking_manufacturer} END CLAMP</text>'
    )

    # ── END CLAMP — FRONT VIEW (row 1, col 1) ─────────────────────
    ef_fx = mc_fx
    ef_fy = ec_py
    _clamp_lbl("DETAIL, END CLAMP — FRONT VIEW", ef_fx, row1_top + 12)

    svg.append(
        f'<rect x="{ef_fx - 32}" y="{ef_fy - 24}" width="{fe_w}" height="{fe_h}" fill="#ffffff" stroke="#000000" stroke-width="1.5"/>'
    )
    svg.append(
        f'<text x="{ef_fx - 32 + fe_w // 2}" y="{ef_fy - 28}" text-anchor="middle" font-size="7" font-family="Arial" fill="#000">PV MODULE FRAME</text>'
    )

    svg.append(
        f'<rect x="{ef_fx - 58}" y="{ef_fy + fe_h // 2 - 28}" width="84" height="20" fill="#4a9e4a" stroke="#000" stroke-width="1"/>'
    )
    svg.append(
        f'<text x="{ef_fx - 16}" y="{ef_fy + fe_h // 2 + 6}" text-anchor="middle" font-size="7" font-family="Arial" fill="#000">{renderer._racking_full} RAIL</text>'
    )

    cap2_y = ef_fy - 24 - 12
    svg.append(
        f'<rect x="{ef_fx - 32}" y="{cap2_y}" width="32" height="12" fill="#d0d0d0" stroke="#000" stroke-width="1.5"/>'
    )
    svg.append(
        f'<rect x="{ef_fx}" y="{cap2_y}" width="12" height="36" fill="#d0d0d0" stroke="#000" stroke-width="1.5"/>'
    )
    svg.append(
        f'<line x1="{ef_fx - 26}" y1="{cap2_y}" x2="{ef_fx - 26}" y2="{ef_fy + fe_h // 2 - 8}" stroke="#555" stroke-width="2"/>'
    )
    svg.append(
        f'<text x="{ef_fx + 18}" y="{cap2_y + 9}" font-size="7" font-family="Arial" fill="#000">{renderer._racking_manufacturer} CLAMP</text>'
    )
    svg.append(
        f'<text x="{ef_fx + 18}" y="{cap2_y + 20}" font-size="7" font-family="Arial" fill="#555">PV MODULE FRAME / {renderer._racking_manufacturer} END CLAMP</text>'
    )

    # ════════════════════════════════════════════════════════════════
    # CENTER COLUMN: Large Attachment Spec Text + BOM Table
    # ════════════════════════════════════════════════════════════════
    cc_x = 510
    cc_cx = 775
    title_blk_x = 1050

    # ── Large Attachment Spec Text ──────────────────────────────────
    spec_y = 60
    spec_lh = 29

    large_spec_lines = [
        f"ATTACHMENT TYPE: {renderer._attachment_full}",
        f"WITH {renderer._racking_full} RAILS",
        f"ROOF TYPE: ASPHALT-SHINGLES,  ROOF PITCH: {pitch_deg}",
        "",
        f"MODULE WEIGHT: {panel_weight_lbs:.0f} LBS",
        f"MODULE DIMENSIONS: {panel_h_str} X {panel_w_str}",
        f"MODULE WEIGHT / SQ. FOOT: {panel_weight_per_sqft:.2f} LBS",
        "",
        f"TOTAL NO. OF MODULES: {n}",
        f"MODULE WEIGHT: {n * panel_weight_lbs:.0f} LBS",
    ]

    for line in large_spec_lines:
        if line:
            svg.append(
                f'<text x="{cc_cx}" y="{spec_y}" text-anchor="middle" '
                f'font-size="17" font-weight="700" font-family="Arial" fill="#000">{line}</text>'
            )
        spec_y += spec_lh

    # Divider between spec block and BOM
    bom_divider_y = spec_y + 6
    svg.append(
        f'<line x1="{cc_x}" y1="{bom_divider_y}" x2="{title_blk_x - 10}" y2="{bom_divider_y}" stroke="#000" stroke-width="1"/>'
    )

    # ── Bill of Material table ──────────────────────────────────────
    bom_y = bom_divider_y + 14
    svg.append(
        f'<text x="{cc_cx}" y="{bom_y}" text-anchor="middle" '
        f'font-size="11" font-weight="700" font-family="Arial" fill="#000">BILL OF MATERIAL</text>'
    )

    col_widths = [120, 330, 60]
    col_labels = ["EQUIPMENT", "MAKE / DESCRIPTION", "QTY"]
    col_x = [cc_x, cc_x + col_widths[0], cc_x + col_widths[0] + col_widths[1]]
    row_h_bom = 22
    hdr_y = bom_y + 14

    for i, lbl in enumerate(col_labels):
        svg.append(
            f'<rect x="{col_x[i]}" y="{hdr_y}" width="{col_widths[i]}" height="{row_h_bom}" '
            f'fill="#000000" stroke="#000" stroke-width="1"/>'
        )
        tx = col_x[i] + col_widths[i] // 2
        svg.append(
            f'<text x="{tx}" y="{hdr_y + 15}" text-anchor="middle" '
            f'font-size="9" font-weight="700" font-family="Arial" fill="#ffffff">{lbl}</text>'
        )

    bom_rows = [
        (
            "MODULE",
            f"{renderer._panel_model_full}  [{renderer._panel_wattage}W {renderer._project.panel.technology.upper() if renderer._project else 'HPBC BIFACIAL'}]",
            str(n),
        ),
        ("END CLAMPS", f"{renderer._racking_manufacturer} END CLAMP STANDARD", str(n_end_clamps)),
        ("MID CLAMPS", f"{renderer._racking_manufacturer} MID CLAMP (INTEGRATED GROUNDING)", str(n_mid_clamps)),
        ("MOUNTING POINTS", f"{renderer._attachment_full}", str(n_mounts)),
        ("MOUNTING RAILS", f"{renderer._racking_full} RAILS", str(n_rails)),
        (inverter_row_label, f"{renderer.INV_MODEL_FULL}", str(n_inverters)),
        ("LOAD CENTER", "125A RATED PV LOAD CENTER (BACKFED FROM MAIN SERVICE PANEL)", "1"),
        ("PV BREAKER", f"2P/{system_ocpd_bom}A BACKFED PV BREAKER (AT PV LOAD CENTER)", "1"),
        ("DATA MONITORING", "ENPHASE ENVOY-S METERED WITH (1) 15A/2P BREAKER", "1"),
        ("CONDUIT", '3/4" EMT CONDUIT (EXTERIOR RUNS) + 1/2" EMT (INTERIOR RUNS)', "AS REQ."),
        (
            "WIRE",
            f"TRUNK CABLE (FREE AIR, ALONG RACKING) / {renderer._wire_type} #10 AWG CU (IN EMT, J-BOX ONWARD)",
            "AS REQ.",
        ),
    ]

    # Labor row
    if _cost_summary and isinstance(_cost_summary, dict) and "labor_cost_usd" in _cost_summary:
        _labor_usd = _cost_summary["labor_cost_usd"]
        _sys_w = n * (renderer._project.panel.wattage_w if renderer._project else 395)
        bom_rows.append(
            (
                "INSTALLATION LABOR",
                f"Roof-mounted installation — $0.25/W \u00d7 {_sys_w:,}W",
                f"${_labor_usd:,.0f}",
            )
        )

    row_y_bom = hdr_y + row_h_bom
    for ri, (equip, make, qty) in enumerate(bom_rows):
        row_fill = "#f9f9f9" if ri % 2 == 0 else "#ffffff"
        for ci, (text, cw) in enumerate(zip([equip, make, qty], col_widths)):
            svg.append(
                f'<rect x="{col_x[ci]}" y="{row_y_bom}" width="{cw}" height="{row_h_bom}" '
                f'fill="{row_fill}" stroke="#ccc" stroke-width="0.5"/>'
            )
            if ci == 2:
                tx = col_x[ci] + cw // 2
                anchor = "middle"
            else:
                tx = col_x[ci] + 4
                anchor = "start"
            fs = "7.5" if len(text) > 48 else "8.5"
            svg.append(
                f'<text x="{tx}" y="{row_y_bom + 15}" text-anchor="{anchor}" '
                f'font-size="{fs}" font-family="Arial" fill="#000">{text}</text>'
            )
        row_y_bom += row_h_bom

    # Total weight note
    total_wt = n * panel_weight_lbs
    svg.append(
        f'<text x="{cc_x}" y="{row_y_bom + 18}" font-size="8" font-family="Arial" fill="#555">'
        f"TOTAL PV MODULE WEIGHT: {total_wt:.0f} LBS ({total_wt * 0.4536:.1f} KG)</text>"
    )

    # ── Cost Summary ─────────────────────────────────────────────────
    cost_summary_y = row_y_bom + 36
    if _cost_summary and cost_summary_y < 820:
        _costs = _cost_summary
        svg.append(
            f'<line x1="{cc_x}" y1="{cost_summary_y}" x2="{title_blk_x - 10}" y2="{cost_summary_y}" '
            f'stroke="#000" stroke-width="0.75"/>'
        )
        svg.append(
            f'<text x="{cc_cx}" y="{cost_summary_y + 12}" text-anchor="middle" '
            f'font-size="9" font-weight="700" font-family="Arial" fill="#000">ESTIMATED PROJECT COST (USD)</text>'
        )
        _cost_rows = [
            ("Equipment", f"${_costs['equipment_cost_usd']:,.0f}"),
            ("Labor", f"${_costs['labor_cost_usd']:,.0f}"),
            ("TOTAL", f"${_costs['total_cost_usd']:,.0f}"),
        ]
        for ci, (label, value) in enumerate(_cost_rows):
            _cy = cost_summary_y + 24 + ci * 14
            _bold = "700" if label == "TOTAL" else "400"
            svg.append(
                f'<text x="{cc_x + 4}" y="{_cy}" font-size="8.5" font-weight="{_bold}" '
                f'font-family="Arial" fill="#000">{label}</text>'
            )
            svg.append(
                f'<text x="{title_blk_x - 14}" y="{_cy}" text-anchor="end" font-size="8.5" '
                f'font-weight="{_bold}" font-family="Arial" fill="#000">{value}</text>'
            )
        notes_y = cost_summary_y + 24 + len(_cost_rows) * 14 + 10
    else:
        notes_y = row_y_bom + 38

    # Installation notes (if there is room)
    note_items = [
        "1. ALL HARDWARE SHALL BE STAINLESS STEEL OR HOT-DIPPED GALVANIZED UNLESS OTHERWISE NOTED.",
        f'2. LAG SCREWS SHALL PENETRATE MIN. 63mm (2.5") INTO SOLID WOOD FRAMING MEMBERS ({renderer._code_prefix} {"690.43" if renderer._code_prefix == "NEC" else "RULE 64-104"}).',
        f"3. RACKING SYSTEM SHALL BE RATED FOR DESIGN WIND (53 m/s / 190 km/h) AND SNOW LOADS PER {renderer._building_code}.",
        "4. {self._racking_full} RAILS ARE FIELD-SPLICED WITH BONDED SPLICE CONNECTORS; MAX. SPAN PER MFGR.",
        "5. ATTACHMENT SPACING SHALL COMPLY WITH {self._racking_manufacturer.upper()} SPAN TABLES FOR LOCAL WIND/SNOW CONDITIONS.",
    ]
    if notes_y < 800:
        svg.append(
            f'<text x="{cc_x}" y="{notes_y - 4}" font-size="9" font-weight="700" font-family="Arial" fill="#000">NOTES:</text>'
        )
        for ni, note in enumerate(note_items):
            if notes_y + ni * 14 < 830:
                svg.append(
                    f'<text x="{cc_x}" y="{notes_y + ni * 14}" font-size="7.5" font-family="Arial" fill="#333">{note}</text>'
                )

    # ── Title block ──────────────────────────────────────────────────
    svg.append(
        renderer._svg_title_block(
            1280,
            960,
            "PV-5",
            "Mounting Details and BOM",
            "IronRidge FlashFoot2 / XR-10 Rails",
            "7 of 13",
            address,
            today,
        )
    )

    svg_content = "\n".join(svg)
    return (
        f'<div class="page">'
        f'<svg width="100%" height="100%" viewBox="0 0 1280 960" '
        f'xmlns="http://www.w3.org/2000/svg" style="background:#fff;">'
        f"{svg_content}"
        f"</svg>"
        f"</div>"
    )
