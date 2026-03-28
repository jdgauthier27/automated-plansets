"""Page builder helpers: Racking Plan bottom info band
=====================================================
Extracted from racking_plan.py to reduce file size.
Contains: elevation detail, module mechanical specs, scale bar,
compass rose, and structural loading table.
"""

import math


def build_racking_bottom_band(svg, renderer, address, today, calc):
    """Bottom info band for the racking plan page (A-102).

    Parameters
    ----------
    svg : list
        SVG parts list to append to.
    renderer : HtmlRenderer
        The renderer instance.
    address, today : str
        Address and date strings.
    calc : dict
        Pre-computed values: VW, VH, BORDER, DRAW_BOTTOM, px_per_m,
        _pitch_deg, _array_area_sqft, _roof_area_sqft, _array_pct.
    """
    VW = calc['VW']
    VH = calc['VH']
    BORDER = calc['BORDER']
    DRAW_BOTTOM = calc['DRAW_BOTTOM']
    px_per_m = calc['px_per_m']
    _pitch_deg = calc['_pitch_deg']
    _array_area_sqft = calc['_array_area_sqft']
    _roof_area_sqft = calc['_roof_area_sqft']
    _array_pct = calc['_array_pct']

    # ── BOTTOM INFO BAND (y=DRAW_BOTTOM+4 to y=840) ──────────────────
    bot_band_y = DRAW_BOTTOM + 4
    bot_band_h = 125  # height of bottom info band

    # ── ELEVATION DETAIL cross-section (bottom-left, NTS) ────────────
    ev_x, ev_y, ev_w, ev_h = BORDER + 10, bot_band_y, 215, bot_band_h
    svg.append(
        f'<rect x="{ev_x}" y="{ev_y}" width="{ev_w}" height="{ev_h}" fill="#fff" stroke="#000" stroke-width="1"/>'
    )
    svg.append(
        f'<rect x="{ev_x}" y="{ev_y}" width="{ev_w}" height="14" fill="#e8e8e8" stroke="#000" stroke-width="1"/>'
    )
    svg.append(
        f'<text x="{ev_x + ev_w // 2}" y="{ev_y + 10}" text-anchor="middle" '
        f'font-size="8" font-weight="700" font-family="Arial" fill="#000">STRUCTURAL ATTACHMENT</text>'
    )
    # Cross-section drawing (NTS)
    # Draw layers bottom→top in the box
    ed_lx, ed_rx = ev_x + 8, ev_x + 140
    ed_mid = (ed_lx + ed_rx) // 2
    # Truss / roof sheathing (bottom)
    ed_truss_y = ev_y + bot_band_h - 18
    svg.append(
        f'<rect x="{ed_lx}" y="{ed_truss_y - 8}" width="{ed_rx - ed_lx}" height="8" '
        f'fill="#ddd" stroke="#555" stroke-width="0.8"/>'
    )
    svg.append(
        f'<text x="{ed_rx + 4}" y="{ed_truss_y - 2}" font-size="6.5" '
        f'font-family="Arial" fill="#333">TRUSS @24&quot; OC : 2&quot;x8&quot;</text>'
    )
    # Asphalt shingles
    ed_shingle_y = ed_truss_y - 8
    svg.append(
        f'<rect x="{ed_lx}" y="{ed_shingle_y - 5}" width="{ed_rx - ed_lx}" height="5" '
        f'fill="#999" stroke="#555" stroke-width="0.6"/>'
    )
    svg.append(
        f'<text x="{ed_rx + 4}" y="{ed_shingle_y}" font-size="6.5" '
        f'font-family="Arial" fill="#333">ASPHALT-SHINGLES</text>'
    )
    # Structural attachment / L-foot
    ed_foot_y = ed_shingle_y - 5
    svg.append(
        f'<polygon points="{ed_mid - 6},{ed_foot_y} {ed_mid + 6},{ed_foot_y} '
        f'{ed_mid + 4},{ed_foot_y - 12} {ed_mid - 4},{ed_foot_y - 12}" '
        f'fill="#ccc" stroke="#444" stroke-width="0.8"/>'
    )
    svg.append(
        f'<text x="{ed_rx + 4}" y="{ed_foot_y - 4}" font-size="6.5" '
        f'font-family="Arial" fill="#333">STRUCTURAL ATTACHMENT</text>'
    )
    # Rail
    ed_rail_y = ed_foot_y - 14
    svg.append(
        f'<rect x="{ed_lx + 10}" y="{ed_rail_y}" width="{ed_rx - ed_lx - 20}" height="5" '
        f'fill="#aaa" stroke="#444" stroke-width="0.8"/>'
    )
    # Module
    ed_mod_y = ed_rail_y - 5
    svg.append(
        f'<rect x="{ed_lx + 5}" y="{ed_mod_y - 14}" width="{ed_rx - ed_lx - 10}" height="14" '
        f'fill="#ffffff" stroke="#000000" stroke-width="1.5"/>'
    )
    svg.append(
        f'<text x="{ed_rx + 4}" y="{ed_mod_y - 6}" font-size="6.5" font-family="Arial" fill="#333">MODULE</text>'
    )
    # NTS label
    svg.append(
        f'<text x="{ev_x + 8}" y="{ev_y + bot_band_h - 4}" font-size="7" '
        f'font-weight="700" font-family="Arial" fill="#555">NTS</text>'
    )
    svg.append(
        f'<text x="{ev_x + ev_w // 2}" y="{ev_y + bot_band_h - 4}" text-anchor="middle" '
        f'font-size="7" font-weight="700" font-family="Arial" fill="#000">ELEVATION DETAIL</text>'
    )

    # ── MODULE MECHANICAL SPECIFICATIONS table ────────────────────────
    ms2_x, ms2_y, ms2_w = BORDER + 235, bot_band_y, 275
    ms2_col1, ms2_col2 = 185, 90
    _wind_snow = (
        renderer._jurisdiction.get_wind_snow_loads(city=renderer._project.municipality)
        if hasattr(renderer._jurisdiction, "get_wind_snow_loads")
        else {"wind_mph": 105, "snow_psf": 40}
    )
    ms2_rows = [
        ("DESIGN WIND SPEED", f"{_wind_snow['wind_mph']} MPH"),
        ("DESIGN SNOW LOAD", f"{_wind_snow['snow_psf']} PSF"),
        ("# OF STORIES", "2"),
        ("ROOF PITCH", f"{_pitch_deg:.0f}\u00b0"),
        ("TOTAL ARRAY AREA (SQ. FT)", f"{_array_area_sqft:.2f}"),
        ("TOTAL ROOF AREA (SQ. FT)", f"{int(_roof_area_sqft)}"),
        ("ARRAY SQ. FT / TOTAL ROOF SQ. FT", f"{_array_pct:.2f}%"),
    ]
    ms2_row_h = 14
    ms2_total_h = 16 + len(ms2_rows) * ms2_row_h
    svg.append(
        f'<rect x="{ms2_x}" y="{ms2_y}" width="{ms2_w}" height="{ms2_total_h}" '
        f'fill="#fff" stroke="#000" stroke-width="1"/>'
    )
    svg.append(
        f'<rect x="{ms2_x}" y="{ms2_y}" width="{ms2_w}" height="16" fill="#e8e8e8" stroke="#000" stroke-width="1"/>'
    )
    svg.append(
        f'<text x="{ms2_x + ms2_w // 2}" y="{ms2_y + 11}" text-anchor="middle" '
        f'font-size="8" font-weight="700" font-family="Arial" fill="#000">'
        f"MODULE MECHANICAL SPECIFICATIONS</text>"
    )
    for i, (lbl, val) in enumerate(ms2_rows):
        ry3 = ms2_y + 16 + i * ms2_row_h
        bg3 = "#fafafa" if i % 2 == 0 else "#fff"
        svg.append(
            f'<rect x="{ms2_x}" y="{ry3}" width="{ms2_col1}" height="{ms2_row_h}" '
            f'fill="{bg3}" stroke="#000" stroke-width="0.4"/>'
        )
        svg.append(
            f'<rect x="{ms2_x + ms2_col1}" y="{ry3}" width="{ms2_col2}" height="{ms2_row_h}" '
            f'fill="{bg3}" stroke="#000" stroke-width="0.4"/>'
        )
        svg.append(
            f'<text x="{ms2_x + 4}" y="{ry3 + 10}" font-size="7" font-family="Arial" fill="#000">{lbl}</text>'
        )
        svg.append(
            f'<text x="{ms2_x + ms2_col1 + ms2_col2 // 2}" y="{ry3 + 10}" '
            f'text-anchor="middle" font-size="7" font-weight="700" '
            f'font-family="Arial" fill="#000">{val}</text>'
        )

    # ── Scale bar + compass rose (bottom-center) ──────────────────────
    sc_x2, sc_y2 = ms2_x + ms2_w + 30, bot_band_y + 20
    sc_m = 2
    sc_px = sc_m * px_per_m
    svg.append(
        f'<line x1="{sc_x2}" y1="{sc_y2}" x2="{sc_x2 + sc_px:.0f}" y2="{sc_y2}" stroke="#000" stroke-width="1.5"/>'
    )
    svg.append(
        f'<line x1="{sc_x2}" y1="{sc_y2 - 4}" x2="{sc_x2}" y2="{sc_y2 + 4}" stroke="#000" stroke-width="1.5"/>'
    )
    svg.append(
        f'<line x1="{sc_x2 + sc_px:.0f}" y1="{sc_y2 - 4}" '
        f'x2="{sc_x2 + sc_px:.0f}" y2="{sc_y2 + 4}" stroke="#000" stroke-width="1.5"/>'
    )
    svg.append(
        f'<text x="{sc_x2 + sc_px / 2:.0f}" y="{sc_y2 + 14}" text-anchor="middle" '
        f'font-size="8" font-family="Arial" fill="#000" font-weight="600">{sc_m} m</text>'
    )
    svg.append(f'<text x="{sc_x2}" y="{sc_y2 - 10}" font-size="7" font-family="Arial" fill="#555">SCALE BAR</text>')

    # Compass rose (above scale bar)
    cr_x, cr_y2 = sc_x2 + int(sc_px) + 45, bot_band_y + 50
    svg.append(
        f'<g transform="translate({cr_x},{cr_y2})">'
        f'<circle cx="0" cy="0" r="18" fill="none" stroke="#000" stroke-width="1"/>'
        f'<polygon points="0,-15 -4,6 0,3 4,6" fill="#000"/>'
        f'<polygon points="0,15 -4,-6 0,-3 4,-6" fill="#fff" stroke="#000" stroke-width="0.8"/>'
        f'<text x="0" y="-20" text-anchor="middle" font-size="9" font-weight="700" '
        f'font-family="Arial" fill="#000">N</text></g>'
    )

    # ── Structural Loading Table (ASCE 7-16 / IBC) ───────────────────
    if renderer._project:
        try:
            from engine.electrical_calc import calculate_structural_loads

            _sl = calculate_structural_loads(renderer._project)
            _sl_x = VW - 15 - 245  # right-aligned, 245px wide, 15px right margin
            _sl_y = bot_band_y  # top-aligned with other bottom-band elements
            _sl_w = 245
            _sl_col1 = 165  # label column width
            _sl_col2 = _sl_w - _sl_col1  # value column width
            _sl_rows = [
                ("PANEL DEAD LOAD", f"{_sl['panel_dead_load_psf']:.2f} PSF"),
                ("RACKING DEAD LOAD", f"{_sl['racking_dead_load_psf']:.1f} PSF"),
                ("TOTAL DEAD LOAD", f"{_sl['total_dead_load_psf']:.2f} PSF"),
                ("ROOF LIVE LOAD", f"{_sl['roof_live_load_psf']:.0f} PSF"),
                ("DESIGN SNOW LOAD", f"{_sl['snow_load_psf']:.0f} PSF"),
                ("WIND UPLIFT (INT.)", f"{_sl['wind_uplift_psf']:.0f} PSF"),
                ("CONTROLLING LOAD", f"{_sl['controlling_load_psf']:.2f} PSF"),
                ("ATTACHMENT SPACING", f"{_sl['attachment_spacing_ft']:.2f} FT O.C."),
            ]
            _sl_hdr_h = 14
            _sl_row_h = 11
            _sl_total_h = _sl_hdr_h + len(_sl_rows) * _sl_row_h
            svg.append(
                f'<rect x="{_sl_x}" y="{_sl_y}" width="{_sl_w}" height="{_sl_total_h}" '
                f'fill="#fff" stroke="#000" stroke-width="1"/>'
            )
            svg.append(
                f'<rect x="{_sl_x}" y="{_sl_y}" width="{_sl_w}" height="{_sl_hdr_h}" '
                f'fill="#e8e8e8" stroke="#000" stroke-width="1"/>'
            )
            svg.append(
                f'<text x="{_sl_x + _sl_w // 2}" y="{_sl_y + 10}" text-anchor="middle" '
                f'font-size="7.5" font-weight="700" font-family="Arial" fill="#000">'
                f"STRUCTURAL LOADING SUMMARY (ASCE 7-16)</text>"
            )
            for _i, (_lbl, _val) in enumerate(_sl_rows):
                _ry = _sl_y + _sl_hdr_h + _i * _sl_row_h
                _bg = "#fafafa" if _i % 2 == 0 else "#fff"
                svg.append(
                    f'<rect x="{_sl_x}" y="{_ry}" width="{_sl_col1}" height="{_sl_row_h}" '
                    f'fill="{_bg}" stroke="#000" stroke-width="0.3"/>'
                )
                svg.append(
                    f'<rect x="{_sl_x + _sl_col1}" y="{_ry}" width="{_sl_col2}" height="{_sl_row_h}" '
                    f'fill="{_bg}" stroke="#000" stroke-width="0.3"/>'
                )
                svg.append(
                    f'<text x="{_sl_x + 3}" y="{_ry + 8}" font-size="6.5" '
                    f'font-family="Arial" fill="#000">{_lbl}</text>'
                )
                svg.append(
                    f'<text x="{_sl_x + _sl_col1 + _sl_col2 // 2}" y="{_ry + 8}" '
                    f'text-anchor="middle" font-size="6.5" font-weight="700" '
                    f'font-family="Arial" fill="#000">{_val}</text>'
                )
        except Exception:
            pass

    # ── Title block ──────────────────────────────────────────────
    svg.append(
        renderer._svg_title_block(
            VW, VH, "A-102", "Racking and Framing Plan", "Setback, Rails, Panels", "4 of 15", address, today
        )
    )

