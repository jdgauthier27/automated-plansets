"""Page builder: Electrical Details (A-300)
========================================
Extracted from HtmlRenderer._build_electrical_details_page.
"""

import math
from datetime import date


def build_electrical_details_page(renderer, project, placements) -> str:
    """A-300: Electrical Details — grounding schedule, conduit routing, OCPD table."""
    VW, VH = 1280, 960
    svg = []

    # Arrow marker defs
    svg.append(
        "<defs>"
        '<marker id="a3_arr_dc" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">'
        '<path d="M0,0 L0,6 L8,3 z" fill="#0066cc"/></marker>'
        '<marker id="a3_arr_ac" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">'
        '<path d="M0,0 L0,6 L8,3 z" fill="#cc0000"/></marker>'
        "</defs>"
    )

    # Background + border
    svg.append('<rect width="1280" height="960" fill="#ffffff"/>')
    svg.append('<rect x="20" y="20" width="1240" height="820" fill="none" stroke="#000" stroke-width="2"/>')

    # Header band
    svg.append('<rect x="20" y="20" width="1240" height="42" fill="#f5f5f5" stroke="#000" stroke-width="1"/>')
    svg.append(
        '<text x="640" y="38" text-anchor="middle" font-size="14" font-weight="700" '
        'font-family="Arial" fill="#000000">ELECTRICAL DETAILS</text>'
    )
    svg.append(
        '<text x="640" y="54" text-anchor="middle" font-size="11" font-family="Arial" '
        'fill="#444444">Grounding &amp; Bonding  |  Conduit Routing  |  Overcurrent Protection</text>'
    )

    # Jurisdiction-aware code references
    is_canada = project and project.country == "CA"
    code_ref_egc = "CEC Rule 10-106" if is_canada else "NEC 690.47(A)"
    code_ref_gec = "CEC Rule 10-112" if is_canada else "NEC 250.166"
    code_ref_bond = "CEC Rule 10-700" if is_canada else "NEC 690.43"
    code_ref_rack = "CEC Rule 10-700" if is_canada else "NEC 690.43"

    # Gather project values
    total_panels = sum(pr.total_panels for pr in placements) if placements else 0
    if project and project.num_panels and project.num_panels > total_panels:
        total_panels = project.num_panels

    panel_w = project.panel.wattage_w if project and project.panel else 395
    isc = project.panel.isc_a if project and project.panel else 10.0
    inv_amps = project.inverter.max_ac_amps if project and project.inverter else 1.21
    inv_volt = project.inverter.ac_voltage_v if project and project.inverter else 240
    inv_model = project.inverter.model if project and project.inverter else "IQ8PLUS"
    is_micro = project.inverter.is_micro if project and project.inverter else True

    def _wg(amps):
        if amps <= 15:
            return "#14 AWG Cu"
        if amps <= 20:
            return "#12 AWG Cu"
        if amps <= 30:
            return "#10 AWG Cu"
        if amps <= 40:
            return "#8 AWG Cu"
        if amps <= 55:
            return "#6 AWG Cu"
        if amps <= 70:
            return "#4 AWG Cu"
        return "#2 AWG Cu"

    total_ac_amps = total_panels * inv_amps
    system_ocpd = math.ceil(total_ac_amps * 1.25 / 5) * 5
    egc_size = _wg(system_ocpd)
    gec_size = "#6 AWG Cu"
    ac_wire = _wg(total_ac_amps * 1.25)
    conduit_ac = '1" EMT' if total_ac_amps * 1.25 > 30 else '3/4" EMT'

    # ── Section 1: Grounding & Bonding Schedule (left half) ──────────────
    S1_X, S1_Y = 36, 80
    svg.append(
        f'<text x="{S1_X}" y="{S1_Y}" font-size="11" font-weight="700" '
        f'font-family="Arial" fill="#000">1.  GROUNDING &amp; BONDING SCHEDULE</text>'
    )

    tbl_x, tbl_y = S1_X, S1_Y + 16
    col_w = [185, 110, 90, 160]
    hdrs = ["COMPONENT", "WIRE SIZE", "MATERIAL", "CODE REF"]
    svg.append(
        f'<rect x="{tbl_x}" y="{tbl_y}" width="{sum(col_w)}" height="22" '
        f'fill="#1a3a5c" stroke="#000" stroke-width="0.5"/>'
    )
    hx = tbl_x
    for h, cw in zip(hdrs, col_w):
        svg.append(
            f'<text x="{hx + 5}" y="{tbl_y + 15}" font-size="9" font-weight="700" '
            f'font-family="Arial" fill="#fff">{h}</text>'
        )
        hx += cw

    grnd_rows = [
        ("Equipment Ground (EGC)", egc_size, "Copper", code_ref_egc),
        ("System Ground (GEC)", gec_size, "Copper", code_ref_gec),
        ("Array Frame Bond", "#10 AWG Cu", "Copper", code_ref_bond),
        ("Racking Bond (rail-to-rail)", "#10 AWG Cu", "Copper", code_ref_rack),
    ]
    for ri, row in enumerate(grnd_rows):
        ry = tbl_y + 22 + ri * 22
        bg = "#f0f4ff" if ri % 2 == 0 else "#ffffff"
        svg.append(
            f'<rect x="{tbl_x}" y="{ry}" width="{sum(col_w)}" height="22" '
            f'fill="{bg}" stroke="#ccc" stroke-width="0.5"/>'
        )
        rx = tbl_x
        for cell, cw in zip(row, col_w):
            svg.append(
                f'<text x="{rx + 5}" y="{ry + 15}" font-size="9" font-family="Arial" fill="#000">{cell}</text>'
            )
            rx += cw

    # ── Section 2: DC/AC Conduit Routing Diagram (right half) ────────────
    S2_X, S2_Y = 645, 80
    svg.append(
        f'<text x="{S2_X}" y="{S2_Y}" font-size="11" font-weight="700" '
        f'font-family="Arial" fill="#000">2.  DC / AC CONDUIT ROUTING DIAGRAM</text>'
    )

    BW, BH = 105, 58
    CY = S2_Y + 95
    box_cxs = [S2_X + 60, S2_X + 200, S2_X + 340, S2_X + 480]
    box_defs = [
        (f"PV ARRAY", f"{total_panels}× {panel_w}W", "#e8f0fe"),
        ("JUNCTION BOX", "NEMA 3R", "#fff3e0"),
        ("INVERTER / MSP", inv_model[:14], "#fce4ec"),
        ("UTILITY METER", "kWh", "#e0f2f1"),
    ]
    for cx, (t1, t2, fill) in zip(box_cxs, box_defs):
        bx, by = cx - BW // 2, CY - BH // 2
        svg.append(
            f'<rect x="{bx}" y="{by}" width="{BW}" height="{BH}" '
            f'fill="{fill}" stroke="#000" stroke-width="1.5" rx="4"/>'
        )
        svg.append(
            f'<text x="{cx}" y="{CY - 7}" text-anchor="middle" font-size="9" '
            f'font-weight="700" font-family="Arial" fill="#000">{t1}</text>'
        )
        svg.append(
            f'<text x="{cx}" y="{CY + 9}" text-anchor="middle" font-size="8" '
            f'font-family="Arial" fill="#444">{t2}</text>'
        )

    arrow_defs = [
        (box_cxs[0] + BW // 2, box_cxs[1] - BW // 2, CY, '3/4" EMT, 2×#10 DC', "#0066cc", "a3_arr_dc"),
        (box_cxs[1] + BW // 2, box_cxs[2] - BW // 2, CY, '3/4" EMT, 2×#10+EGC', "#0066cc", "a3_arr_dc"),
        (box_cxs[2] + BW // 2, box_cxs[3] - BW // 2, CY, f"{conduit_ac}, {ac_wire} AC", "#cc0000", "a3_arr_ac"),
    ]
    for x1, x2, ay, lbl, color, marker in arrow_defs:
        mid = (x1 + x2) // 2
        svg.append(
            f'<line x1="{x1}" y1="{ay}" x2="{x2}" y2="{ay}" '
            f'stroke="{color}" stroke-width="2" marker-end="url(#{marker})"/>'
        )
        svg.append(
            f'<text x="{mid}" y="{ay - 8}" text-anchor="middle" font-size="7.5" '
            f'font-family="Arial" fill="{color}">{lbl}</text>'
        )

    # Legend for conduit diagram
    leg_y = CY + BH // 2 + 20
    for i, (color, label) in enumerate([("#0066cc", "DC Wiring"), ("#cc0000", "AC Wiring")]):
        lx = S2_X + i * 180
        svg.append(f'<line x1="{lx}" y1="{leg_y}" x2="{lx + 32}" y2="{leg_y}" stroke="{color}" stroke-width="2"/>')
        svg.append(
            f'<text x="{lx + 38}" y="{leg_y + 4}" font-size="8" font-family="Arial" fill="#000">{label}</text>'
        )

    # ── Section 3: Overcurrent Protection (OCPD) Table — full width ──────
    S3_Y = 310
    svg.append(
        f'<text x="{S1_X}" y="{S3_Y}" font-size="11" font-weight="700" '
        f'font-family="Arial" fill="#000">3.  OVERCURRENT PROTECTION SCHEDULE (OCPD)</text>'
    )

    tbl2_x, tbl2_y = S1_X, S3_Y + 16
    col_w2 = [240, 130, 160, 220]
    hdrs2 = ["CIRCUIT", "OCPD RATING", "TYPE", "LOCATION"]
    svg.append(
        f'<rect x="{tbl2_x}" y="{tbl2_y}" width="{sum(col_w2)}" height="22" '
        f'fill="#1a3a5c" stroke="#000" stroke-width="0.5"/>'
    )
    hx2 = tbl2_x
    for h, cw in zip(hdrs2, col_w2):
        svg.append(
            f'<text x="{hx2 + 5}" y="{tbl2_y + 15}" font-size="9" font-weight="700" '
            f'font-family="Arial" fill="#fff">{h}</text>'
        )
        hx2 += cw

    if is_micro:
        src_ocpd = "N/A (Self-protected)"
        src_type = "Microinverter"
        out_ocpd = "15A, 2-Pole"
        out_type = "Branch CB"
    else:
        src_ocpd = f"{math.ceil(isc * 1.25 / 5) * 5}A, 2-Pole"
        src_type = "String Fuse / CB"
        out_ocpd = f"{math.ceil(isc * 1.56 / 5) * 5}A, 2-Pole"
        out_type = "DC Disconnect CB"

    ocpd_rows = [
        ("PV Source Circuit (DC)", src_ocpd, src_type, "Junction Box"),
        ("PV Output Circuit (DC/AC)", out_ocpd, out_type, "AC Combiner / IQ Combiner"),
        ("AC Output Circuit", f"{system_ocpd}A, 2-Pole", "Backfeed Breaker", "Main Service Panel"),
        ("Main Breaker Backfeed", f"{system_ocpd}A, 2-Pole", "Backfeed Breaker", "MSP Bus (Interconnect)"),
    ]
    for ri, row in enumerate(ocpd_rows):
        ry = tbl2_y + 22 + ri * 22
        bg = "#f0f4ff" if ri % 2 == 0 else "#ffffff"
        svg.append(
            f'<rect x="{tbl2_x}" y="{ry}" width="{sum(col_w2)}" height="22" '
            f'fill="{bg}" stroke="#ccc" stroke-width="0.5"/>'
        )
        rx = tbl2_x
        for cell, cw in zip(row, col_w2):
            svg.append(
                f'<text x="{rx + 5}" y="{ry + 15}" font-size="9" font-family="Arial" fill="#000">{cell}</text>'
            )
            rx += cw

    # Notes below OCPD table
    notes_y = tbl2_y + 22 + len(ocpd_rows) * 22 + 20
    code_grnd = "NEC 690.47" if not is_canada else "CEC Rule 10"
    notes = [
        "1.  All conductors copper, 75°C THWN-2 in EMT conduit unless otherwise noted.",
        f"2.  System OCPD: {total_panels} modules × {inv_amps:.2f}A × 1.25 = "
        f"{total_ac_amps * 1.25:.1f}A → {system_ocpd}A 2-pole breaker.",
        f"3.  {code_grnd} — Grounding electrode system required for all PV arrays.",
        f"4.  EGC sized per {'NEC Table 250.122' if not is_canada else 'CEC Table 16'}, "
        f"based on {system_ocpd}A OCPD rating.",
        "5.  All equipment installed per manufacturer instructions and applicable electrical codes.",
    ]
    for ni, note in enumerate(notes):
        svg.append(
            f'<text x="{S1_X}" y="{notes_y + ni * 16}" font-size="8" font-family="Arial" fill="#333">{note}</text>'
        )

    # Title block
    _addr = project.address if project else ""
    _today = date.today().strftime("%Y-%m-%d")
    svg.append(
        renderer._svg_title_block(
            VW, VH, "A-300", "ELECTRICAL DETAILS", "Grounding · Conduit · OCPD", "15 of 15", _addr, _today
        )
    )

    content = "\n".join(svg)
    return (
        f'<div class="page">'
        f'<svg width="100%" height="100%" viewBox="0 0 {VW} {VH}" '
        f'xmlns="http://www.w3.org/2000/svg" style="background:#fff;">'
        f"{content}</svg></div>"
    )
