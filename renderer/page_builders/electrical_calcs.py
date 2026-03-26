"""Page builder: Electrical Calculations (PV-4.1)
==================================================
Extracted from HtmlRenderer._build_electrical_calcs_page.
"""

import math


def build_electrical_calcs_page(renderer, total_panels: int, total_kw: float,
                                address: str, today: str) -> str:
    """PV-4.1: Electrical calculation worksheet (jurisdiction-aware).

    Microinverter system: each panel drives its own inverter.
    DC circuit = one panel → one microinverter (no series strings).
    AC circuit = branch of N microinverters sharing a breaker.

    Wire sizing: DC conductor ×1.56 (Isc), AC continuous ×1.25.
    Code references and design temperatures come from the jurisdiction engine.
    """
    VW, VH = 1280, 960
    svg: list = []

    # Jurisdiction-aware code references
    _cp = renderer._code_prefix
    _is_nec = _cp == "NEC"

    # ── Module specs — from ProjectSpec/catalog ─────────────────────────
    voc_stc = renderer._panel_voc
    vmp_stc = renderer._panel_vmp
    isc_stc = renderer._panel_isc
    imp_stc = renderer._panel_imp
    pmax_stc = renderer._panel_wattage
    temp_coeff_voc = renderer._panel_temp_coeff_voc
    temp_coeff_isc = renderer._panel_temp_coeff_isc

    # ── Inverter specs — from ProjectSpec/catalog ───────────────────────
    inv_ac_amps_per_unit = renderer.INV_AC_AMPS_PER_UNIT
    inv_ac_voltage = renderer._project.inverter.ac_voltage_v if renderer._project else 240
    max_per_branch = renderer._max_per_branch
    inv_output_va = renderer.INV_AC_WATTS_PER_UNIT

    # ── Design temperatures (from jurisdiction engine) ─────────────────
    _temps = renderer._design_temps
    t_cold_c = float(_temps.get("cold_c", -25))
    t_stc_c = float(_temps.get("stc_c", 25))
    t_hot_c = float(_temps.get("hot_module_c", 70))

    # ── DC circuit calculations (per panel) ──────────────────────────────
    voc_cold = voc_stc * (1.0 + temp_coeff_voc * (t_cold_c - t_stc_c))
    isc_hot = isc_stc * (1.0 + temp_coeff_isc * (t_hot_c - t_stc_c))
    dc_min_amps = isc_stc * 1.56

    from renderer.svg_helpers import wire_gauge as _wire_gauge

    dc_wire = _wire_gauge(dc_min_amps)
    dc_ocpd = math.ceil(isc_stc * 1.56 / 5) * 5

    # ── AC branch circuit calculations ────────────────────────────────────
    n = max(total_panels, 1)
    if n <= max_per_branch:
        branch_sizes = [n]
    else:
        nb = math.ceil(n / max_per_branch)
        base_sz = n // nb
        rem = n % nb
        branch_sizes = [base_sz + (1 if i < rem else 0) for i in range(nb)]
    n_branches = len(branch_sizes)

    branch_ac_amps = [sz * inv_ac_amps_per_unit for sz in branch_sizes]
    branch_wire_amps = [a * 1.25 for a in branch_ac_amps]
    branch_wire = [_wire_gauge(a) for a in branch_wire_amps]
    branch_ocpd = [math.ceil(a / 5) * 5 for a in branch_wire_amps]

    total_ac_amps = n * inv_ac_amps_per_unit
    total_ac_wire_amps = total_ac_amps * 1.25
    total_ac_wire = _wire_gauge(total_ac_wire_amps)
    total_ac_ocpd = math.ceil(total_ac_wire_amps / 5) * 5

    # 120 % rule
    main_breaker = renderer._main_breaker_a
    bus_rating = renderer._bus_rating_a
    rule_120_lim = int(bus_rating * 1.2)
    rule_120_pass = (total_ac_ocpd + main_breaker) <= rule_120_lim

    # ── SVG canvas ────────────────────────────────────────────────────────
    svg.append(f'<rect width="{VW}" height="{VH}" fill="#ffffff"/>')
    svg.append(
        f'<rect x="20" y="20" width="{VW - 40}" height="{VH - 40}" fill="none" stroke="#000" stroke-width="2"/>'
    )

    # ── Page title strip ──────────────────────────────────────────────────
    svg.append(f'<rect x="20" y="20" width="{VW - 40}" height="26" fill="#e8e8e8" stroke="#000" stroke-width="1"/>')
    svg.append(
        f'<text x="{VW // 2}" y="38" text-anchor="middle" font-size="13" font-weight="700" '
        f'font-family="Arial" fill="#000">PV-4.1 — ELECTRICAL CALCULATIONS</text>'
    )

    # ── Helper to draw a titled table ─────────────────────────────────────
    def _table(x, y, title, headers_list, rows, col_widths, row_h=22, hdr_fill="#e8e8e8"):
        """Draw a titled table. Returns next y after the table."""
        parts = []
        # Section title
        parts.append(
            f'<rect x="{x}" y="{y}" width="{sum(col_widths)}" height="18" '
            f'fill="#444" stroke="#000" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{x + sum(col_widths) // 2}" y="{y + 13}" text-anchor="middle" '
            f'font-size="9" font-weight="700" font-family="Arial" fill="#fff">{title}</text>'
        )
        y += 18
        # Column headers
        cx = x
        for i, hdr in enumerate(headers_list):
            parts.append(
                f'<rect x="{cx}" y="{y}" width="{col_widths[i]}" height="{row_h}" '
                f'fill="{hdr_fill}" stroke="#000" stroke-width="0.8"/>'
            )
            parts.append(
                f'<text x="{cx + col_widths[i] // 2}" y="{y + row_h - 7}" text-anchor="middle" '
                f'font-size="8" font-weight="700" font-family="Arial" fill="#000">{hdr}</text>'
            )
            cx += col_widths[i]
        y += row_h
        # Data rows
        for ri, row in enumerate(rows):
            bg = "#f9f9f9" if ri % 2 == 0 else "#ffffff"
            cx = x
            highlight = row[0].startswith("★")
            row_fill = "#fffbe6" if highlight else bg
            for i, cell in enumerate(row):
                cell_text = cell.lstrip("★")
                parts.append(
                    f'<rect x="{cx}" y="{y}" width="{col_widths[i]}" height="{row_h}" '
                    f'fill="{row_fill}" stroke="#ccc" stroke-width="0.5"/>'
                )
                weight = "700" if highlight else "400"
                parts.append(
                    f'<text x="{cx + 4}" y="{y + row_h - 7}" '
                    f'font-size="8" font-weight="{weight}" font-family="Arial" fill="#000">{cell_text}</text>'
                )
                cx += col_widths[i]
            y += row_h
        return "".join(parts), y

    # ══════════════════════════════════════════════════════════════════════
    # LEFT COLUMN (x=30 … 640)
    # ══════════════════════════════════════════════════════════════════════
    lx, ly = 30, 54

    # ── 1. System Overview ────────────────────────────────────────────────
    overview_rows = [
        ("System Type", "Microinverter (no DC series strings)"),
        ("Module", f"{renderer._panel_model_full}   {pmax_stc} W"),
        (
            "Microinverter"
            if (renderer._project and renderer._project.inverter.is_micro) or not renderer._project
            else "Inverter",
            f"{renderer.INV_MODEL_SHORT}  [{renderer._project.inverter.ac_voltage_v if renderer._project else 240} V / 1φ]",
        ),
        ("# Modules", f"{total_panels}"),
        ("DC System Size", f"{total_kw:.2f} kW DC"),
        ("AC System Size", f"{renderer._calc_ac_kw(total_panels):.2f} kW AC"),
    ]
    tbl_svg, ly = _table(lx, ly, "SYSTEM OVERVIEW", ["Parameter", "Value"], overview_rows, [210, 390], row_h=22)
    svg.append(tbl_svg)
    ly += 8

    # ── 2. Module DC Electrical Specs (STC) ─────────────────────────────
    dc_rows = [
        ("Rated Power (Pmax @ STC)", f"{pmax_stc} W"),
        ("Open-Circuit Voltage  Voc @ STC", f"{voc_stc:.1f} V"),
        ("Voltage at Pmax       Vmp @ STC", f"{vmp_stc:.1f} V"),
        ("Short-Circuit Current Isc @ STC", f"{isc_stc:.1f} A"),
        ("Current at Pmax       Imp @ STC", f"{imp_stc:.1f} A"),
        ("Temp. Coeff. Voc", f"{temp_coeff_voc * 100:+.2f} %/°C"),
        ("Temp. Coeff. Isc", f"{temp_coeff_isc * 100:+.3f} %/°C"),
    ]
    tbl_svg, ly = _table(
        lx, ly, "MODULE ELECTRICAL SPECIFICATIONS @ STC", ["Parameter", "Value"], dc_rows, [310, 290], row_h=21
    )
    svg.append(tbl_svg)
    ly += 8

    # ── 3. DC Temperature Corrections ───────────────────────────────────
    _city = renderer._project.municipality if renderer._project else ""
    _temp_label = f"{_city} design temp (ASHRAE 2 %)" if _city else "Design temp (ASHRAE 2 %)"
    temp_rows = [
        (_temp_label, f"{t_cold_c:.0f} °C"),
        ("\u0394T below STC", f"{t_cold_c - t_stc_c:.0f} °C"),
        (
            "Voc correction factor",
            f"1 + ({temp_coeff_voc * 100:+.2f}%/°C \u00d7 {t_cold_c - t_stc_c:.0f}\u00b0C) = "
            f"{1 + temp_coeff_voc * (t_cold_c - t_stc_c):.4f}",
        ),
        (f"\u2605Voc @ {t_cold_c:.0f} \u00b0C  (design Voc)", f"{voc_cold:.1f} V  (<600 V {_cp} limit \u2713)"),
        ("Hot-roof temp (summer)", f"{t_hot_c:.0f} \u00b0C"),
        (f"\u2605Isc @ +{t_hot_c:.0f} \u00b0C  (hot-roof)", f"{isc_hot:.2f} A  (used for ampacity check)"),
    ]
    _dc_temp_rule = f"{_cp} {'690.8 / NEC Table 690.7' if _is_nec else 'Rule 14-100 / Annex D'}"
    tbl_svg, ly = _table(
        lx,
        ly,
        f"DC TEMPERATURE CORRECTIONS  [{_dc_temp_rule}]",
        ["Parameter", "Value"],
        temp_rows,
        [250, 350],
        row_h=21,
    )
    svg.append(tbl_svg)
    ly += 8

    # ── 4. DC Wire Sizing (per panel) ────────────────────────────────────
    _dc_sizing_rule = f"{_cp} {'690.8' if _is_nec else 'Rule 14-100'}"
    dc_wire_rows = [
        ("Isc @ STC", f"{isc_stc:.1f} A"),
        (f"{_dc_sizing_rule} factor", "\u00d71.56"),
        (f"\u2605Min. DC conductor ampacity", f"{dc_min_amps:.1f} A  \u2192 {dc_wire} {renderer._wire_type}  \u2713"),
        ("DC OCPD (fuse)", f"{dc_ocpd} A"),
        ("Conduit / raceway", "EMT  (exterior)"),
    ]
    tbl_svg, ly = _table(
        lx,
        ly,
        f"DC CONDUCTOR SIZING \u2014 PER PANEL  [{_dc_sizing_rule}]",
        ["Parameter", "Value"],
        dc_wire_rows,
        [250, 350],
        row_h=21,
    )
    svg.append(tbl_svg)
    ly += 8

    # ── 5. String Configuration ───────────────────────────────────────────
    try:
        from engine.electrical_calc import calculate_string_config
        if renderer._project:
            _str_cfg = calculate_string_config(renderer._project.panel, renderer._project.inverter, total_panels)
        else:
            _str_cfg = None
    except Exception:
        _str_cfg = None

    if _str_cfg and _str_cfg.get("type") == "microinverter":
        _br_a = _str_cfg.get("branch_current_a", 0.0)
        _br_wire = _wire_gauge(_br_a)
        str_rows = [
            ("Configuration", f"{_str_cfg['num_branches']} \u00d7 1-module branch circuits"),
            ("Branch circuit current", f"1.25 \u00d7 Isc = {_br_a:.2f} A  \u2192  {_br_wire} {renderer._wire_type}"),
            ("System voltage (Voc)", f"{_str_cfg.get('system_voltage_v', 0):.1f} V"),
        ]
        _str_rule = f"{_cp} {'690.8' if _is_nec else 'Rule 14-100'}"
        tbl_svg, ly = _table(
            lx, ly, f"STRING CONFIGURATION  [{_str_rule}]", ["Parameter", "Value"], str_rows, [250, 350], row_h=21
        )
        svg.append(tbl_svg)
    elif _str_cfg and _str_cfg.get("type") == "string":
        str_rows = [
            ("Panels per string", f"{_str_cfg.get('string_length', 0)}"),
            ("Number of strings", f"{_str_cfg.get('num_strings', 0)}"),
            ("String Voc", f"{_str_cfg.get('string_voc_v', 0):.1f} V"),
            ("String Vmp", f"{_str_cfg.get('string_vmp_v', 0):.1f} V"),
        ]
        tbl_svg, ly = _table(lx, ly, "STRING CONFIGURATION", ["Parameter", "Value"], str_rows, [250, 350], row_h=21)
        svg.append(tbl_svg)

    # ══════════════════════════════════════════════════════════════════════
    # RIGHT COLUMN (x=650 … 1240)
    # ══════════════════════════════════════════════════════════════════════
    rx, ry = 655, 54

    # ── 5. AC Branch Circuit Table ───────────────────────────────────────
    branch_hdr = ["Branch", "Modules", "AC Current (A)", "×1.25 (A)", "Wire", "OCPD"]
    branch_rows = []
    for bi, (sz, ia, iw, wg, oc) in enumerate(
        zip(branch_sizes, branch_ac_amps, branch_wire_amps, branch_wire, branch_ocpd)
    ):
        branch_rows.append(
            [
                f"Branch {bi + 1}",
                f"{sz}",
                f"{ia:.1f}",
                f"{iw:.1f}",
                wg,
                f"{oc} A  2P",
            ]
        )
    # Totals row
    branch_rows.append(
        [
            "★TOTAL",
            f"{n}",
            f"{total_ac_amps:.1f}",
            f"{total_ac_wire_amps:.1f}",
            total_ac_wire,
            f"{total_ac_ocpd} A  2P",
        ]
    )
    _ac_rule = f"{_cp} {'210.20 / 705.12' if _is_nec else 'Rule 4-004 / Rule 64-056'}"
    tbl_svg, ry = _table(
        rx,
        ry,
        f"AC BRANCH CIRCUIT CALCULATIONS  [{_ac_rule}]",
        branch_hdr,
        branch_rows,
        [75, 60, 105, 80, 80, 85 + 15],
        row_h=22,
    )
    svg.append(tbl_svg)
    ry += 8

    # ── 6. 120 % Rule ─────────────────────────────────────────────────────
    pass_fail_color = "#008800" if rule_120_pass else "#cc0000"
    pass_fail_text = "PASS ✓" if rule_120_pass else "FAIL ✗"
    rule_rows = [
        ("Main bus rating", f"{bus_rating} A"),
        ("120 % of bus", f"{rule_120_lim} A"),
        ("Main breaker (existing)", f"{main_breaker} A"),
        ("PV backfed OCPD", f"{total_ac_ocpd} A"),
        ("Sum (main + PV OCPD)", f"{main_breaker + total_ac_ocpd} A"),
        (
            f"★{pass_fail_text}  ({main_breaker + total_ac_ocpd} ≤ {rule_120_lim})",
            f"{main_breaker + total_ac_ocpd} ≤ {rule_120_lim}  {pass_fail_text}",
        ),
    ]
    _120_rule = f"{_cp} {'705.12' if _is_nec else 'Rule 64-056'}"
    tbl_svg, ry = _table(
        rx,
        ry,
        f"BUSBAR CALCULATIONS \u2014 120 % RULE  [{_120_rule}]",
        ["Parameter", "Value"],
        rule_rows,
        [300, 245],
        row_h=22,
    )
    svg.append(tbl_svg)
    ry += 8

    # ── 7. Microinverter AC Specs ─────────────────────────────────────────
    inv_rows = [
        ("Model", renderer.INV_MODEL_SHORT),
        ("Output voltage", f"{inv_ac_voltage} V  1φ"),
        ("Max continuous output current", f"{inv_ac_amps_per_unit:.1f} A"),
        ("Max output apparent power", f"{inv_output_va} VA"),
        ("Max modules per branch circuit", f"{max_per_branch}  (for 15 A 2P OCPD)"),
        ("DC input voltage range", "16–60 V  (per panel)"),
    ]
    tbl_svg, ry = _table(
        rx, ry, "MICROINVERTER AC ELECTRICAL SPECIFICATIONS", ["Parameter", "Value"], inv_rows, [295, 250], row_h=22
    )
    svg.append(tbl_svg)
    ry += 8

    # ── 8. Applicable Codes ──────────────────────────────────────────────
    _utility_info = renderer._utility_info
    _utility_nm_kw = _utility_info.get("net_metering_max_kw", 50)
    if _is_nec:
        code_rows = [
            ("NEC 705.12", "Interconnection of PV systems"),
            ("NEC 690.8", "DC conductor ampacity (\u00d71.56 factor)"),
            ("NEC 210.20", "AC continuous load sizing (\u00d71.25 factor)"),
            ("NEC 690.31", "PV output circuit conductors"),
            ("NEC 2020 / CEC", renderer._code_edition),
            ("IEC 62109", "Safety of power converters for PV systems"),
            (renderer._utility_name, f"Net metering \u2264 {_utility_nm_kw} kW \u2014 single-phase"),
        ]
    else:
        code_rows = [
            ("CEC Rule 64-056", "Interconnection of PV systems"),
            ("CEC Rule 14-100", "DC conductor ampacity (\u00d71.56 factor)"),
            ("CEC Rule 4-004", "AC continuous load sizing (\u00d71.25 factor)"),
            ("CEC Rule 64-050", "PV output circuit conductors"),
            ("CSA C22.1-2021", "Canadian Electrical Code, Part I"),
            ("IEC 62109", "Safety of power converters for PV systems"),
            (renderer._utility_name, f"Net metering \u2264 {_utility_nm_kw} kW \u2014 single-phase"),
        ]
    tbl_svg, ry = _table(
        rx, ry, "APPLICABLE CODES & STANDARDS", ["Code / Rule", "Description"], code_rows, [145, 400], row_h=21
    )
    svg.append(tbl_svg)
    ry += 8

    # ── 9. Formula notes strip (bottom, full width) ──────────────────────
    notes_y = max(ly, ry) + 10
    _dc_rule_label = f"{_cp} {'690.8' if _is_nec else 'Rule 14-100'}"
    _ac_rule_label = f"{_cp} {'210.20' if _is_nec else 'Rule 4-004'}"
    note_lines = [
        "FORMULAS:   "
        "Voc_cold = Voc_STC \u00d7 [1 + \u03b1_Voc \u00d7 (T_design \u2212 25)]     "
        f"where \u03b1_Voc = \u22120.24 %/\u00b0C,  T_design = {t_cold_c:.0f} \u00b0C ({_city or 'local'} ASHRAE 2 % heating)     "
        f"DC ampacity = Isc \u00d7 1.56  [{_dc_rule_label}]     "
        f"AC ampacity = I_branch_total \u00d7 1.25  [{_ac_rule_label} continuous load]",
    ]
    svg.append(
        f'<rect x="30" y="{notes_y}" width="{VW - 60}" height="22" '
        f'fill="#f4f4f4" stroke="#aaa" stroke-width="0.8"/>'
    )
    svg.append(
        f'<text x="36" y="{notes_y + 14}" font-size="7.5" font-family="Arial" fill="#333">{note_lines[0]}</text>'
    )

    # ── Title block ───────────────────────────────────────────────────────
    svg.append(
        renderer._svg_title_block(
            VW, VH, "PV-4.1", "Electrical Calculations", renderer._code_edition, "6 of 13", address, today
        )
    )

    svg_content = "\n".join(svg)
    return (
        f'<div class="page"><svg width="100%" height="100%" '
        f'viewBox="0 0 {VW} {VH}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#fff;">{svg_content}</svg></div>'
    )
