"""Page builder helpers: Single-Line Diagram tables and specs
=============================================================
Extracted from single_line_diagram.py to reduce file size.
Contains: conductor schedule, PV system summary, module/inverter specs,
branch circuit data, OCPD calculations, busbar/120% rule tables,
ground rod spec, and rapid shutdown callout.
"""


def build_conductor_schedule(svg_parts, renderer, calc):
    """CONDUCTOR AND CONDUIT SCHEDULE (top center of PV-4)."""
    n_branches = calc['n_branches']
    sys_ac_wire = calc['sys_ac_wire']
    sys_ac_conduit = calc['sys_ac_conduit']
    sys_egc_wire = calc['sys_egc_wire']
    _wt = renderer._wire_type

    cs_x, cs_y, cs_w, cs_h = 460, 47, 420, 106
    # 6 columns matching Cubillas PV-4 exactly (no CIRCUIT DESCRIPTION column)
    # TAG | WIRE TYPE | WIRE SIZE | # CONDUCTORS | CONDUIT TYPE | MIN. SIZE
    cs_cols = [36, 95, 68, 70, 75, 76]  # sums to 420
    cs_hdrs = ["TAG", "WIRE TYPE", "WIRE SIZE", "# CONDUCTORS", "CONDUIT TYPE", "MIN. SIZE"]

    # Outer border
    svg_parts.append(
        f'<rect x="{cs_x}" y="{cs_y}" width="{cs_w}" height="{cs_h}" '
        f'fill="#ffffff" stroke="#000" stroke-width="1.2"/>'
    )
    # Title bar
    svg_parts.append(
        f'<rect x="{cs_x}" y="{cs_y}" width="{cs_w}" height="12" fill="#e8e8e8" stroke="#000" stroke-width="1"/>'
    )
    svg_parts.append(
        f'<text x="{cs_x + cs_w // 2}" y="{cs_y + 9}" '
        f'text-anchor="middle" font-size="7.5" font-weight="700" '
        f'font-family="Arial" fill="#000">CONDUCTOR AND CONDUIT SCHEDULE</text>'
    )
    # Column headers (y=59..70)
    csh_x = cs_x
    for _cw, _ch in zip(cs_cols, cs_hdrs):
        svg_parts.append(
            f'<rect x="{csh_x}" y="{cs_y + 12}" width="{_cw}" height="11" '
            f'fill="#f2f2f2" stroke="#000" stroke-width="0.8"/>'
        )
        svg_parts.append(
            f'<text x="{csh_x + _cw // 2}" y="{cs_y + 20}" '
            f'text-anchor="middle" font-size="5.5" font-weight="700" '
            f'font-family="Arial" fill="#000">{_ch}</text>'
        )
        csh_x += _cw

    # Data rows: 11 rows × 7px = 77px; starts at y=70, ends at y=147 (within 106px box)
    # Conductor count notation matches Cubillas PV-4 standard:
    #   - 240V branch circuits (no neutral): "N - L1 L2"
    #   - System run past load center (120/240V service with neutral): "3 - L1 L2 N"
    #   - Each conduit segment has a paired EGC sub-row sharing the same tag (Cubillas standard)
    #   - Trunk (row 2) sized for combined system current (sys_ac_wire = #10 AWG)
    #     not branch_ac_wire — the trunk carries all branches' combined output
    _trunk_cond = f"{2 * n_branches} - L1 L2"  # e.g. "4 - L1 L2" for 2-circuit trunk
    # Enphase microinverter AC wiring topology:
    #   Tag 1 = AC trunk cable running in FREE AIR along module racking (Enphase Q Cable
    #           assembly). Carries combined output of all branch circuits from modules to
    #           junction box. Sized for total system current (sys_ac_wire).
    #           Matching Cubillas PV-4: "TRUNK CABLE / FREE AIR / N/A"
    #   Tag 2 = From junction box to PV load center — THWN-2 in EMT conduit
    #   Tags 3–5 = Downstream of load center — THWN-2 in EMT conduit
    #   EGC notation: "1 - GND" (matching Cubillas PV-4 verbatim)
    _wt = renderer._wire_type  # "THWN-2" for US, "RW90-XLPE" for CA
    cs_rows = [
        # tag, description, wire_type, wire_size, conductors, conduit_type, conduit_size, is_egc
        (
            "1",
            "AC TRUNK: MODULES \u2192 J-BOX (FREE AIR)",
            "TRUNK CABLE",
            sys_ac_wire,
            _trunk_cond,
            "FREE AIR",
            "N/A",
            False,
        ),
        ("1", "Trunk Bare Cu EGC (Free Air)", "BARE COPPER", "#6 AWG", "1 - BARE", "FREE AIR", "N/A", True),
        ("2", "J-BOX \u2192 PV Load Center", _wt, sys_ac_wire, _trunk_cond, "EMT", sys_ac_conduit, False),
        ("2", "J-BOX \u2192 Load Ctr EGC", f"{_wt} EGC", sys_egc_wire, "1 - GND", "EMT", sys_ac_conduit, True),
        ("3", "Load Center \u2192 AC OCPD", _wt, sys_ac_wire, "3 - L1 L2 N", "EMT", sys_ac_conduit, False),
        ("3", "Load Center \u2192 OCPD EGC", f"{_wt} EGC", sys_egc_wire, "1 - GND", "EMT", sys_ac_conduit, True),
        ("4", "AC OCPD \u2192 Main Service Panel", _wt, sys_ac_wire, "3 - L1 L2 N", "EMT", sys_ac_conduit, False),
        ("4", "OCPD \u2192 Main Panel EGC", f"{_wt} EGC", sys_egc_wire, "1 - GND", "EMT", sys_ac_conduit, True),
        ("5", "Main Panel \u2192 Utility Meter", _wt, sys_ac_wire, "3 - L1 L2 N", "EMT", sys_ac_conduit, False),
        ("5", "Main Panel \u2192 Meter EGC", f"{_wt} EGC", sys_egc_wire, "1 - GND", "EMT", sys_ac_conduit, True),
        ("G", "GEC: Grounding Electrode Cond.", "Bare Cu", "#6 AWG", "1 - GEC", "FREE AIR", "N/A", False),
    ]
    cs_row_y = cs_y + 23
    for _ri, _row in enumerate(cs_rows):
        _tag, _desc, _wtype, _wsize, _ncond, _ctype, _csize, _is_egc = _row
        # EGC sub-rows: light gray; main rows: white/near-white alternating
        if _is_egc:
            _bg = "#f0f0f0"
        else:
            _bg = "#fff" if (_ri // 2) % 2 == 0 else "#f8f8f8"
        _row_data = (_tag, _wtype, _wsize, _ncond, _ctype, _csize)  # _desc intentionally omitted (not in Cubillas)
        csr_x = cs_x
        for _ci, (_cw, _val) in enumerate(zip(cs_cols, _row_data)):
            svg_parts.append(
                f'<rect x="{csr_x}" y="{cs_row_y}" width="{_cw}" height="7" '
                f'fill="{_bg}" stroke="#000" stroke-width="0.6"/>'
            )
            # TAG column: bold for main rows, regular for EGC (share same tag visually)
            _fw = "700" if (_ci == 0 and not _is_egc) else "400"
            _fill = "#555" if _is_egc else "#000"
            svg_parts.append(
                f'<text x="{csr_x + _cw // 2}" y="{cs_row_y + 5}" '
                f'text-anchor="middle" font-size="5" font-weight="{_fw}" '
                f'font-family="Arial" fill="{_fill}">{_val}</text>'
            )
            csr_x += _cw
        cs_row_y += 7


def build_pv_system_summary(svg_parts, renderer, calc):
    """PHOTOVOLTAIC SYSTEM SUMMARY box (top right of PV-4)."""
    total_panels = calc['total_panels']
    total_kw = calc['total_kw']
    inv_kw = calc['inv_kw']
    total_ac_current = calc['total_ac_current']

    pvsys_x, pvsys_y = 884, 47
    pvsys_w, pvsys_h = 376, 106
    svg_parts.append(
        f'<rect x="{pvsys_x}" y="{pvsys_y}" width="{pvsys_w}" height="{pvsys_h}" '
        f'fill="#ffffff" stroke="#000" stroke-width="1.2"/>'
    )
    svg_parts.append(
        f'<rect x="{pvsys_x}" y="{pvsys_y}" width="{pvsys_w}" height="13" '
        f'fill="#e8e8e8" stroke="#000" stroke-width="1"/>'
    )
    svg_parts.append(
        f'<text x="{pvsys_x + pvsys_w // 2}" y="{pvsys_y + 9}" '
        f'text-anchor="middle" font-size="8" font-weight="700" '
        f'font-family="Arial" fill="#000">PHOTOVOLTAIC SYSTEM:</text>'
    )
    _pvs_rows = [
        ("DC SYSTEM SIZE:", f"{total_kw:.2f} kW"),
        ("AC SYSTEM SIZE:", f"{inv_kw:.2f} kW"),
        ("MODULE:", f"({total_panels}) {renderer.panel.name} [{renderer.panel.wattage}W]"),
        ("", f"WITH INTEGRATED MICROINVERTERS {renderer.INV_MODEL_SHORT}"),
        ("MONITORING:", "ENPHASE ENVOY (AC GATEWAY)"),
    ]
    _pvs_y = pvsys_y + 23
    for _pvl, _pvv in _pvs_rows:
        if _pvl:
            svg_parts.append(
                f'<text x="{pvsys_x + 8}" y="{_pvs_y}" '
                f'font-size="7" font-weight="700" font-family="Arial" fill="#000">{_pvl}</text>'
            )
        svg_parts.append(
            f'<text x="{pvsys_x + 108}" y="{_pvs_y}" font-size="7" font-family="Arial" fill="#000">{_pvv}</text>'
        )
        _pvs_y += 14


def build_sld_lower_tables(svg_parts, renderer, calc):
    """All tables below the circuit diagram on PV-4.

    Includes: PV Module Spec, Inverter Spec, Branch Circuit Data,
    OCPD Calculations, Busbar/120% Rule, Ground Rod, Rapid Shutdown.
    """
    total_panels = calc['total_panels']
    total_kw = calc['total_kw']
    inv_kw = calc['inv_kw']
    total_ac_current = calc['total_ac_current']
    max_branch_current = calc['max_branch_current']
    n_branches = calc['n_branches']
    branch_sizes = calc['branch_sizes']
    MAX_PER_BRANCH = calc['MAX_PER_BRANCH']
    BRANCH_BREAKER_A = calc['BRANCH_BREAKER_A']
    system_ocpd = calc['system_ocpd']
    main_breaker = calc['main_breaker']
    bus_rating = calc['bus_rating']
    rule_120_pass = calc['rule_120_pass']
    rule_120_lim = calc['rule_120_lim']
    voc_per_panel = calc['voc_per_panel']
    vmp_per_panel = calc['vmp_per_panel']
    isc_per_panel = calc['isc_per_panel']
    imp_per_panel = calc['imp_per_panel']
    temp_coeff_voc = calc['temp_coeff_voc']
    panel_efficiency = calc['panel_efficiency']
    sys_ac_wire = calc['sys_ac_wire']
    sys_ac_conduit = calc['sys_ac_conduit']
    sys_egc_wire = calc['sys_egc_wire']
    branch_ac_wire = calc['branch_ac_wire']
    branch_ac_conduit = calc['branch_ac_conduit']
    branch_egc_wire = calc['branch_egc_wire']
    ac_breaker = calc['ac_breaker']
    _cp = calc['_cp']
    _is_nec = calc['_is_nec']

    # ═══════════════════════════════════════════════════════════════
    # DIVIDER 1
    # ═══════════════════════════════════════════════════════════════
    div1 = 306
    # Divider stops at x=880 — right column (x=884..1260) holds the
    # ELECTRICAL NOTES box which spans past this y-level without interruption.
    svg_parts.append(
        f'<line x1="20" y1="{div1}" x2="880" y2="{div1}" stroke="#aaa" stroke-width="0.8" stroke-dasharray="4,4"/>'
    )

    # ═══════════════════════════════════════════════════════════════
    # TABLE 2: PV MODULE ELECTRICAL SPECIFICATIONS  (left half)
    # Moved from right (x=654) to left (x=25) — matching Cubillas PV-4
    # which places module specs bottom-left alongside inverter specs
    # center-right. The PHOTOVOLTAIC SYSTEM summary has moved to the
    # top-right column (alongside NOTES and Conductor Schedule).
    # ═══════════════════════════════════════════════════════════════
    ms_x, ms_y, ms_w = 25, 312, 601
    ms_cw = [ms_w - 160, 160]

    svg_parts.append(
        f'<rect x="{ms_x}" y="{ms_y}" width="{ms_w}" height="14" fill="#e8e8e8" stroke="#000" stroke-width="1"/>'
    )
    svg_parts.append(
        f'<text x="{ms_x + ms_w // 2}" y="{ms_y + 10}" text-anchor="middle" font-size="8" font-weight="700" font-family="Arial" fill="#000">PV MODULE ELECTRICAL SPECIFICATIONS</text>'
    )

    # Header
    mx = ms_x
    for cw, ch in zip(ms_cw, ["PARAMETER", "VALUE"]):
        svg_parts.append(
            f'<rect x="{mx}" y="{ms_y + 14}" width="{cw}" height="13" fill="#f2f2f2" stroke="#000" stroke-width="0.8"/>'
        )
        svg_parts.append(
            f'<text x="{mx + cw // 2}" y="{ms_y + 14 + 9}" text-anchor="middle" font-size="6.5" font-weight="700" font-family="Arial" fill="#000">{ch}</text>'
        )
        mx += cw

    mod_rows = [
        ("Module Model", renderer.panel.name),
        ("Rated Power (Pmax @ STC)", f"{renderer.panel.wattage} W"),
        ("Open Circuit Voltage (Voc)", f"{voc_per_panel:.1f} V"),
        ("Short Circuit Current (Isc)", f"{isc_per_panel:.1f} A"),
        ("Voltage at Pmax (Vmp)", f"{vmp_per_panel:.1f} V"),
        ("Current at Pmax (Imp)", f"{imp_per_panel:.1f} A"),
        ("Module Efficiency", f"{panel_efficiency} %"),
        ("Temp. Coefficient (Voc)", f"{temp_coeff_voc * 100:.2f} %/°C"),
        ("Max System Voltage", "1000 V DC"),
        ("Max Series Fuse Rating", "20 A"),
    ]
    mry = ms_y + 27
    for mi, (param, val) in enumerate(mod_rows):
        bg = "#fff" if mi % 2 == 0 else "#f8f8f8"
        mx = ms_x
        svg_parts.append(
            f'<rect x="{mx}" y="{mry}" width="{ms_cw[0]}" height="12" fill="{bg}" stroke="#000" stroke-width="0.7"/>'
        )
        svg_parts.append(
            f'<text x="{mx + 5}" y="{mry + 9}" font-size="6.5" font-family="Arial" fill="#333">{param}</text>'
        )
        mx += ms_cw[0]
        svg_parts.append(
            f'<rect x="{mx}" y="{mry}" width="{ms_cw[1]}" height="12" fill="{bg}" stroke="#000" stroke-width="0.7"/>'
        )
        svg_parts.append(
            f'<text x="{mx + 5}" y="{mry + 9}" font-size="6.5" font-weight="600" font-family="Arial" fill="#000">{val}</text>'
        )
        mry += 12

    # ═══════════════════════════════════════════════════════════════
    # DIVIDER 2
    # ═══════════════════════════════════════════════════════════════
    div2 = 504
    svg_parts.append(
        f'<line x1="20" y1="{div2}" x2="1260" y2="{div2}" stroke="#aaa" stroke-width="0.8" stroke-dasharray="4,4"/>'
    )

    # ═══════════════════════════════════════════════════════════════
    # TABLE 3: INVERTER ELECTRICAL SPECIFICATIONS  (right half)
    # Moved from (x=25, y=510) to (x=635, y=312) — now placed alongside
    # MODULE ELECTRICAL SPECS to match Cubillas PV-4 bottom layout:
    # MODULE SPECS (left) | INVERTER SPECS (right) at same vertical level.
    # ═══════════════════════════════════════════════════════════════
    is_x, is_y, is_w = 635, 312, 620
    is_cw = [is_w - 175, 175]

    svg_parts.append(
        f'<rect x="{is_x}" y="{is_y}" width="{is_w}" height="14" fill="#e8e8e8" stroke="#000" stroke-width="1"/>'
    )
    svg_parts.append(
        f'<text x="{is_x + is_w // 2}" y="{is_y + 10}" text-anchor="middle" font-size="8" font-weight="700" font-family="Arial" fill="#000">INVERTER ELECTRICAL SPECIFICATIONS</text>'
    )

    ix = is_x
    for cw, ch in zip(is_cw, ["PARAMETER", "VALUE"]):
        svg_parts.append(
            f'<rect x="{ix}" y="{is_y + 14}" width="{cw}" height="13" fill="#f2f2f2" stroke="#000" stroke-width="0.8"/>'
        )
        svg_parts.append(
            f'<text x="{ix + cw // 2}" y="{is_y + 14 + 9}" text-anchor="middle" font-size="6.5" font-weight="700" font-family="Arial" fill="#000">{ch}</text>'
        )
        ix += cw

    inv_rows_data = [
        ("Inverter Type", "Microinverter (Module-Level Power Electronics)"),
        ("Microinverter Model", renderer.INV_MODEL_SHORT),
        (
            "AC Output Power (per unit)",
            f"{renderer.INV_AC_WATTS_PER_UNIT} VA  ({renderer.INV_AC_AMPS_PER_UNIT:.1f} A @ 240 V)",
        ),
        ("Total System AC Power", f"{inv_kw:.2f} kW  ({total_panels} units × {renderer.INV_AC_WATTS_PER_UNIT} VA)"),
        ("AC Output Voltage / Freq.", "240 V, 1-Phase, 60 Hz"),
        ("Total Continuous AC Current", f"{total_ac_current:.1f} A"),
        ("DC Input Voltage Range", "16 – 60 V DC"),
        ("CEC Weighted Efficiency", "97.0 %"),
        ("Max Units per 15 A Branch", f"{MAX_PER_BRANCH}"),
        ("Operating Temp. Range", "−40°C to +65°C"),
    ]
    iry = is_y + 27
    for ii2, (param, val) in enumerate(inv_rows_data):
        bg = "#fff" if ii2 % 2 == 0 else "#f8f8f8"
        ix = is_x
        svg_parts.append(
            f'<rect x="{ix}" y="{iry}" width="{is_cw[0]}" height="12" fill="{bg}" stroke="#000" stroke-width="0.7"/>'
        )
        svg_parts.append(
            f'<text x="{ix + 5}" y="{iry + 9}" font-size="6.5" font-family="Arial" fill="#333">{param}</text>'
        )
        ix += is_cw[0]
        svg_parts.append(
            f'<rect x="{ix}" y="{iry}" width="{is_cw[1]}" height="12" fill="{bg}" stroke="#000" stroke-width="0.7"/>'
        )
        svg_parts.append(
            f'<text x="{ix + 5}" y="{iry + 9}" font-size="6.5" font-weight="600" font-family="Arial" fill="#000">{val}</text>'
        )
        iry += 12

    # ═══════════════════════════════════════════════════════════════
    # BRANCH CIRCUIT DATA — bottom-left (x=25, y=510)
    # Moved from right column; Cubillas has ELECTRICAL NOTES there instead.
    # Side-by-side with OCPD/BUSBAR tables on the right half.
    # ═══════════════════════════════════════════════════════════════
    bcd_x, bcd_y, bcd_w = 25, 510, 601
    _bcd_rows = [
        ("No. of Circuits:", f"{n_branches}", "Modules/Circuit:", f"max {MAX_PER_BRANCH}"),
        ("Branch Breaker:", f"{BRANCH_BREAKER_A}A 2P", "Sys. OCPD:", f"{system_ocpd}A 2P"),
        ("Max Branch Current:", f"{max_branch_current:.1f} A", "Total AC:", f"{total_ac_current:.1f} A"),
        ("Branch Wire:", branch_ac_wire, "System Wire:", sys_ac_wire),
        ("Branch Conduit:", branch_ac_conduit + " EMT", "Sys. Conduit:", sys_ac_conduit + " EMT"),
        ("Inverter (per panel):", renderer.INV_MODEL_SHORT, "CEC Eff.:", "97.0 %"),
    ]
    bcd_h = 16 + len(_bcd_rows) * 17 + 4
    svg_parts.append(
        f'<rect x="{bcd_x}" y="{bcd_y}" width="{bcd_w}" height="{bcd_h}" fill="#ffffff" stroke="#000" stroke-width="1.2"/>'
    )
    svg_parts.append(
        f'<rect x="{bcd_x}" y="{bcd_y}" width="{bcd_w}" height="13" fill="#e8e8e8" stroke="#000" stroke-width="1"/>'
    )
    svg_parts.append(
        f'<text x="{bcd_x + bcd_w // 2}" y="{bcd_y + 9}" text-anchor="middle" font-size="8" font-weight="700" font-family="Arial" fill="#000">BRANCH CIRCUIT DATA</text>'
    )
    bcd_dy = bcd_y + 27
    for _bll, _blv, _brl, _brv in _bcd_rows:
        svg_parts.append(
            f'<text x="{bcd_x + 8}" y="{bcd_dy}" font-size="7" font-family="Arial" fill="#555">{_bll}</text>'
        )
        svg_parts.append(
            f'<text x="{bcd_x + 170}" y="{bcd_dy}" font-size="7" font-weight="600" font-family="Arial" fill="#000">{_blv}</text>'
        )
        svg_parts.append(
            f'<text x="{bcd_x + 305}" y="{bcd_dy}" font-size="7" font-family="Arial" fill="#555">{_brl}</text>'
        )
        svg_parts.append(
            f'<text x="{bcd_x + 470}" y="{bcd_dy}" font-size="7" font-weight="600" font-family="Arial" fill="#000">{_brv}</text>'
        )
        bcd_dy += 17

    # ═══════════════════════════════════════════════════════════════
    # TABLE 4: SYSTEM OVER-CURRENT PROTECTION DEVICE (OCPD) CALCULATIONS
    # Cubillas compact format: 3 columns, 1 data row with inline formula
    # Columns: INVERTER TYPE | # OF INVERTERS / MAX CONT. OUTPUT CURRENT | OCPD RATING
    # ═══════════════════════════════════════════════════════════════
    oc_x, oc_y, oc_w = 638, 510, 617
    oc_title_h, oc_hdr_h, oc_row_h = 14, 13, 20
    oc_cw = [230, 200, 187]  # sums to 617
    oc_hdr = ["INVERTER TYPE", "# OF INVERTERS / MAX CONT. OUTPUT CURRENT", "OCPD RATING"]

    # Title bar
    svg_parts.append(
        f'<rect x="{oc_x}" y="{oc_y}" width="{oc_w}" height="{oc_title_h}" '
        f'fill="#e8e8e8" stroke="#000" stroke-width="1"/>'
    )
    svg_parts.append(
        f'<text x="{oc_x + oc_w // 2}" y="{oc_y + 10}" text-anchor="middle" '
        f'font-size="7.5" font-weight="700" font-family="Arial" fill="#000">'
        f"SYSTEM OVER-CURRENT PROTECTION DEVICE (OCPD) CALCULATIONS</text>"
    )
    # Column headers
    ox2 = oc_x
    for cw, ch in zip(oc_cw, oc_hdr):
        svg_parts.append(
            f'<rect x="{ox2}" y="{oc_y + oc_title_h}" width="{cw}" height="{oc_hdr_h}" '
            f'fill="#f2f2f2" stroke="#000" stroke-width="0.8"/>'
        )
        svg_parts.append(
            f'<text x="{ox2 + cw // 2}" y="{oc_y + oc_title_h + 9}" '
            f'text-anchor="middle" font-size="5.5" font-weight="700" '
            f'font-family="Arial" fill="#000">{ch}</text>'
        )
        ox2 += cw

    # Single data row  — inverter description | count / current | formula + result
    oc_data_y = oc_y + oc_title_h + oc_hdr_h
    inv_type_str = f"{renderer.panel.name}  WITH  {renderer.INV_MODEL_SHORT} MICROINVERTERS [240V]"
    inv_curr_str = f"{total_panels} / {renderer.INV_AC_AMPS_PER_UNIT:.1f} A"
    ocpd_calc_str = (
        f"({total_panels} \u00d7 {renderer.INV_AC_AMPS_PER_UNIT:.1f}A \u00d7 1.25)"
        f" = {total_ac_current * 1.25:.2f}A  \u2264  {system_ocpd}A  OK"
    )
    oc_row_data = [(inv_type_str, oc_cw[0]), (inv_curr_str, oc_cw[1]), (ocpd_calc_str, oc_cw[2])]
    ox2 = oc_x
    for val, cw in oc_row_data:
        svg_parts.append(
            f'<rect x="{ox2}" y="{oc_data_y}" width="{cw}" height="{oc_row_h}" '
            f'fill="#ffffff" stroke="#000" stroke-width="0.7"/>'
        )
        fs = "5.5" if len(val) > 35 else "7"
        svg_parts.append(
            f'<text x="{ox2 + 4}" y="{oc_data_y + 13}" '
            f'font-size="{fs}" font-family="Arial" fill="#000">{val}</text>'
        )
        ox2 += cw

    # ═══════════════════════════════════════════════════════════════
    # BUSBAR CALCULATIONS - PV BREAKER - 120% RULE  (Cubillas standard)
    # Format: 3-column header row (bus / main_disc / pv_breaker) showing
    # ratings, then formula row, then colour-coded calculation + result.
    # Matches Cubillas PV-4 "BUSBAR CALCULATIONS" table exactly.
    # ═══════════════════════════════════════════════════════════════
    bus_gap = 4
    bus_x = oc_x
    bus_y_top = oc_data_y + oc_row_h + bus_gap
    bus_w = oc_w
    bb_cw = [bus_w // 3, bus_w // 3, bus_w - 2 * (bus_w // 3)]  # 3 equal cols
    bb_hdr = ["MAIN BUS RATING", "MAIN DISCONNECT RATING", "PV BREAKER RATING"]
    bus_title_h, bus_hdr_h = 14, 13
    bus_val_h, bus_form_h, bus_res_h = 18, 14, 16
    bc_color = "#00aa00" if rule_120_pass else "#cc0000"

    # Title bar
    svg_parts.append(
        f'<rect x="{bus_x}" y="{bus_y_top}" width="{bus_w}" height="{bus_title_h}" '
        f'fill="#e8e8e8" stroke="#000" stroke-width="1"/>'
    )
    svg_parts.append(
        f'<text x="{bus_x + bus_w // 2}" y="{bus_y_top + 10}" text-anchor="middle" '
        f'font-size="7.5" font-weight="700" font-family="Arial" fill="#000">'
        f"BUSBAR CALCULATIONS - PV BREAKER - 120% RULE</text>"
    )
    # Column headers
    bx2 = bus_x
    for cw, ch in zip(bb_cw, bb_hdr):
        svg_parts.append(
            f'<rect x="{bx2}" y="{bus_y_top + bus_title_h}" width="{cw}" '
            f'height="{bus_hdr_h}" fill="#f2f2f2" stroke="#000" stroke-width="0.8"/>'
        )
        svg_parts.append(
            f'<text x="{bx2 + cw // 2}" y="{bus_y_top + bus_title_h + 9}" '
            f'text-anchor="middle" font-size="6.5" font-weight="700" '
            f'font-family="Arial" fill="#000">{ch}</text>'
        )
        bx2 += cw

    # Values row: bus rating | main disconnect | PV breaker
    bv_y = bus_y_top + bus_title_h + bus_hdr_h
    bx2 = bus_x
    for val, cw in zip([f"{bus_rating}", f"{main_breaker}", f"{system_ocpd}A 2P"], bb_cw):
        svg_parts.append(
            f'<rect x="{bx2}" y="{bv_y}" width="{cw}" height="{bus_val_h}" '
            f'fill="#ffffff" stroke="#000" stroke-width="0.7"/>'
        )
        svg_parts.append(
            f'<text x="{bx2 + cw // 2}" y="{bv_y + 13}" text-anchor="middle" '
            f'font-size="10" font-weight="700" font-family="Arial" fill="#000">{val}</text>'
        )
        bx2 += cw

    # Formula row — spans full width (grey background)
    form_y = bv_y + bus_val_h
    formula_str = "(MAIN BUS RATING \u00d7 1.2) \u2212 MAIN DISCONNECT RATING \u2265 OCPD RATING"
    svg_parts.append(
        f'<rect x="{bus_x}" y="{form_y}" width="{bus_w}" height="{bus_form_h}" '
        f'fill="#f8f8f8" stroke="#000" stroke-width="0.7"/>'
    )
    svg_parts.append(
        f'<text x="{bus_x + bus_w // 2}" y="{form_y + 10}" text-anchor="middle" '
        f'font-size="6.5" font-style="italic" font-family="Arial" fill="#444">'
        f"{formula_str}</text>"
    )

    # Calculation + PASS/FAIL row — colour-coded
    headroom = rule_120_lim - main_breaker  # e.g. 270 − 200 = 70
    calc_str = (
        f"({bus_rating}A \u00d7 1.2) \u2212 {main_breaker}A"
        f" = {rule_120_lim}A \u2212 {main_breaker}A"
        f" = {headroom}A \u2265 {system_ocpd}A"
    )
    pass_str = "  \u2714 OK" if rule_120_pass else "  \u2718 FAIL \u2014 UPGRADE PANEL OR REDUCE INVERTER"
    res_y = form_y + bus_form_h
    res_bg = "#ddf0dd" if rule_120_pass else "#ffdede"
    svg_parts.append(
        f'<rect x="{bus_x}" y="{res_y}" width="{bus_w}" height="{bus_res_h}" '
        f'fill="{res_bg}" stroke="{bc_color}" stroke-width="1"/>'
    )
    svg_parts.append(
        f'<text x="{bus_x + bus_w // 2}" y="{res_y + 11}" text-anchor="middle" '
        f'font-size="7" font-weight="700" font-family="Arial" fill="{bc_color}">'
        f"{calc_str}{pass_str}</text>"
    )

    # (ELECTRICAL NOTES moved to right column — see en_x/en_y block above)
    # (DIVIDER 3 removed — bottom zone freed now that notes are in right column)

    # Supplemental ground rod specification text block (matches Cubillas PV-4)
    # Positioned bottom-left, to the left of the rapid shutdown callout.
    # Supplemental electrode adjacent to the array (NEC 690.47 / CEC 64-104).
    gr_x, gr_y, gr_w, gr_h = 640, 790, 310, 32
    _grd_ref = f"{_cp} {'250.68(C)(1)' if _is_nec else '64-104'}"
    grd_lines = [
        "**SUPPLEMENTAL GROUND ROD SHALL BE 10' LONG \u00d7 5/8\" IN DIAMETER.",
        f'ROD IS TO BE EMBEDDED A MIN 8" INTO DIRECT SOIL [{_cp} {"250.53(D)" if _is_nec else "10-706(3)"}],',
        "MIN 5 FT APART. CONNECTION TO INTERIOR METAL WATER PIPING",
        f"SHALL BE WITHIN 5 FT OF ENTRY POINT. [{_grd_ref}]",
    ]
    svg_parts.append(
        f'<rect x="{gr_x}" y="{gr_y}" width="{gr_w}" height="{gr_h}" '
        f'fill="#ffffff" stroke="#000" stroke-width="0.8"/>'
    )
    for gi, gl in enumerate(grd_lines):
        # Strip leading ** bold marker for SVG text (no SVG bold spans here)
        gl_clean = gl.lstrip("*")
        fw = "700" if gl.startswith("**") else "400"
        svg_parts.append(
            f'<text x="{gr_x + 4}" y="{gr_y + 8 + gi * 7}" '
            f'font-size="5.5" font-weight="{fw}" font-family="Arial" fill="#000">{gl_clean}</text>'
        )

    # Rapid shutdown callout box
    rs_x2 = 960
    rs_y2 = 790
    svg_parts.append(
        f'<rect x="{rs_x2}" y="{rs_y2}" width="290" height="32" fill="#fff5f5" stroke="#cc0000" stroke-width="1" rx="2"/>'
    )
    svg_parts.append(
        f'<text x="{rs_x2 + 10}" y="{rs_y2 + 13}" font-size="7.5" font-weight="700" font-family="Arial" fill="#cc0000">\u26a1 RAPID SHUTDOWN ({_cp} {"690.12" if _is_nec else "64-218"})</text>'
    )
    svg_parts.append(
        f'<text x="{rs_x2 + 10}" y="{rs_y2 + 26}" font-size="7" font-family="Arial" fill="#333">Array ≤30 V within 30 s of initiating signal.</text>'
    )
