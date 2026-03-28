"""Page builder: Single Line Diagram (A-200)
========================================
Extracted from HtmlRenderer._build_single_line_diagram_page.
"""

import math
from datetime import date


def build_single_line_diagram_page(renderer, project, placements) -> str:
    """A-200: Electrical Single Line Diagram — SVG component flow.

    Shows: PV Array → Microinverters → AC Branch Circuits → AC Combiner
           → Main Service Panel → Utility Meter → Grid
    Labels each segment with wire gauges and component model numbers.
    """
    VW, VH = 1280, 960
    svg = []

    # Background + border
    svg.append('<rect width="1280" height="960" fill="#ffffff"/>')
    svg.append('<rect x="20" y="20" width="1240" height="820" fill="none" stroke="#000" stroke-width="2"/>')

    # Header band
    svg.append('<rect x="20" y="20" width="1240" height="42" fill="#f5f5f5" stroke="#000" stroke-width="1"/>')
    svg.append(
        '<text x="640" y="38" text-anchor="middle" font-size="14" font-weight="700" '
        'font-family="Arial" fill="#000000">ELECTRICAL SINGLE LINE DIAGRAM</text>'
    )
    svg.append(
        '<text x="640" y="54" text-anchor="middle" font-size="11" font-family="Arial" '
        f'fill="#444444">AC System — {"Microinverter" if renderer._is_micro else "String Inverter"} Configuration</text>'
    )

    # Gather equipment values
    total_panels = sum(pr.total_panels for pr in placements) if placements else 0
    if project and project.num_panels and project.num_panels > total_panels:
        total_panels = project.num_panels

    panel_model = project.panel.model if project and project.panel else renderer._panel_model_short
    panel_mfr = project.panel.manufacturer if project and project.panel else "—"
    panel_w = project.panel.wattage_w if project and project.panel else renderer._panel_wattage
    inv_model = project.inverter.model if project and project.inverter else renderer.INV_MODEL_SHORT
    inv_mfr = project.inverter.manufacturer if project and project.inverter else "Enphase"
    inv_amps = project.inverter.max_ac_amps if project and project.inverter else renderer.INV_AC_AMPS_PER_UNIT
    inv_voltage = project.inverter.ac_voltage_v if project and project.inverter else 240

    MAX_PER_BRANCH = renderer._max_per_branch
    n_branches = max(1, math.ceil(total_panels / MAX_PER_BRANCH))
    max_branch_amps = MAX_PER_BRANCH * inv_amps
    total_ac_amps = total_panels * inv_amps

    def _wg(amps):
        if amps <= 15:
            return "14 AWG"
        if amps <= 20:
            return "12 AWG"
        if amps <= 30:
            return "10 AWG"
        if amps <= 55:
            return "8 AWG"
        return "6 AWG"

    branch_wire = _wg(max_branch_amps * 1.25)
    system_wire = _wg(total_ac_amps * 1.25)
    system_ocpd = math.ceil(total_ac_amps * 1.25 / 5) * 5

    DIAG_Y = 370
    BOX_W = 110
    BOX_H = 72
    X_PV = 95
    X_MICRO = 265
    X_BRANCH = 440
    X_COMBINER = 630
    X_MSP = 820
    X_METER = 990
    X_GRID = 1155

    def _box(cx, cy, w, h, fill, l1, l2="", l3=""):
        bx, by = cx - w // 2, cy - h // 2
        parts = [
            f'<rect x="{bx}" y="{by}" width="{w}" height="{h}" '
            f'fill="{fill}" stroke="#000" stroke-width="1.5" rx="4"/>',
            f'<text x="{cx}" y="{cy - (9 if l2 else 0)}" text-anchor="middle" '
            f'font-size="9" font-weight="700" font-family="Arial" fill="#000">{l1}</text>',
        ]
        if l2:
            parts.append(
                f'<text x="{cx}" y="{cy + 8}" text-anchor="middle" '
                f'font-size="8" font-family="Arial" fill="#333">{l2}</text>'
            )
        if l3:
            parts.append(
                f'<text x="{cx}" y="{cy + 20}" text-anchor="middle" '
                f'font-size="7" font-family="Arial" fill="#555">{l3}</text>'
            )
        return "\n".join(parts)

    def _wire(x1, y, x2, label="", color="#cc0000"):
        mid = (x1 + x2) // 2
        out = f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" stroke="{color}" stroke-width="2.5"/>'
        if label:
            out += (
                f'<text x="{mid}" y="{y - 8}" text-anchor="middle" font-size="8" '
                f'font-family="Arial" fill="{color}">{label}</text>'
            )
        return out

    # PV Array box with mini panel cells
    svg.append(
        _box(
            X_PV,
            DIAG_Y,
            BOX_W,
            BOX_H,
            "#e8f0fe",
            "PV ARRAY",
            f"{total_panels}x {panel_model[:12]}",
            f"{panel_w}W ea.",
        )
    )
    px0, py0 = X_PV - 38, DIAG_Y - 28
    for pi in range(3):
        for pj in range(2):
            svg.append(
                f'<rect x="{px0 + pi * 27}" y="{py0 + pj * 12}" width="24" height="10" '
                f'fill="#0c1a2e" stroke="#4a90d9" stroke-width="0.5" rx="1"/>'
            )

    # Inverter box
    _inv_box_label = "MICROINVERTER" if renderer._is_micro else "STRING INVERTER"
    _inv_box_qty = f"{total_panels}x units" if renderer._is_micro else "1x unit"
    svg.append(
        _box(
            X_MICRO,
            DIAG_Y,
            BOX_W,
            BOX_H,
            "#fff3e0",
            _inv_box_label,
            f"{inv_mfr[:10]} {inv_model[:10]}",
            _inv_box_qty,
        )
    )

    # AC Branch circuit box
    svg.append(
        _box(
            X_BRANCH, DIAG_Y, BOX_W, BOX_H, "#fce4ec", f"{n_branches} BRANCH CKT", "15A 2P OCPD", f"#{branch_wire}"
        )
    )

    # AC Combiner box
    combiner_lbl = "IQ Combiner" if "nphase" in inv_mfr.lower() else "AC Combiner"
    svg.append(
        _box(X_COMBINER, DIAG_Y, BOX_W + 10, BOX_H, "#e8f5e9", "AC COMBINER", combiner_lbl, f"{system_ocpd}A OCPD")
    )

    # Main Service Panel box
    svg.append(_box(X_MSP, DIAG_Y, BOX_W, BOX_H, "#f3e5f5", "MAIN SERVICE", "PANEL (MSP)", "200A / 240V"))

    # Utility Meter with kWh dial symbol
    svg.append(_box(X_METER, DIAG_Y, 82, BOX_H, "#e0f2f1", "UTILITY METER", "", ""))
    svg.append(f'<circle cx="{X_METER}" cy="{DIAG_Y - 12}" r="20" fill="none" stroke="#000" stroke-width="1.5"/>')
    svg.append(
        f'<text x="{X_METER}" y="{DIAG_Y - 7}" text-anchor="middle" '
        f'font-size="8" font-weight="700" font-family="Arial" fill="#000">kWh</text>'
    )

    # Grid with three-line symbol
    svg.append(_box(X_GRID, DIAG_Y, 82, BOX_H, "#e8eaf6", "UTILITY GRID", "240V / 60Hz", ""))
    for gi, gw in enumerate([3, 2, 1.5]):
        w2 = 20 - gi * 2
        gy_off = -30 + gi * 8
        svg.append(
            f'<line x1="{X_GRID - w2}" y1="{DIAG_Y + gy_off}" '
            f'x2="{X_GRID + w2}" y2="{DIAG_Y + gy_off}" '
            f'stroke="#000" stroke-width="{gw}"/>'
        )

    # Wires
    svg.append(_wire(X_PV + BOX_W // 2, DIAG_Y, X_MICRO - BOX_W // 2, "DC", "#0066cc"))
    svg.append(_wire(X_MICRO + BOX_W // 2, DIAG_Y, X_BRANCH - BOX_W // 2, f"#{branch_wire} CU"))
    svg.append(_wire(X_BRANCH + BOX_W // 2, DIAG_Y, X_COMBINER - (BOX_W + 10) // 2, f"#{branch_wire}"))
    svg.append(
        _wire(X_COMBINER + (BOX_W + 10) // 2, DIAG_Y, X_MSP - BOX_W // 2, f"#{system_wire} / {system_ocpd}A")
    )
    svg.append(_wire(X_MSP + BOX_W // 2, DIAG_Y, X_METER - 41, f"#{system_wire}"))
    svg.append(_wire(X_METER + 41, DIAG_Y, X_GRID - 41, ""))

    # Component labels below boxes
    label_y = DIAG_Y + BOX_H // 2 + 18
    for cx, lbl in [
        (X_PV, f"{panel_mfr} {panel_model}"[:22]),
        (X_MICRO, f"{inv_mfr} {inv_model}"[:22]),
        (X_COMBINER, combiner_lbl),
    ]:
        svg.append(
            f'<text x="{cx}" y="{label_y}" text-anchor="middle" '
            f'font-size="7" font-family="Arial" fill="#666">{lbl}</text>'
        )

    # Legend
    leg_y = DIAG_Y + BOX_H // 2 + 55
    for i, (color, lbl) in enumerate(
        [("#0066cc", "DC Wiring"), ("#cc0000", "AC Wiring"), ("#00aa00", "EGC / Ground")]
    ):
        lx = 50 + i * 200
        svg.append(
            f'<line x1="{lx}" y1="{leg_y}" x2="{lx + 40}" y2="{leg_y}" stroke="{color}" stroke-width="2.5"/>'
        )
        svg.append(
            f'<text x="{lx + 48}" y="{leg_y + 4}" font-size="9" font-family="Arial" fill="#000">{lbl}</text>'
        )

    # Conductor Schedule table
    tbl_x = 50
    tbl_y = leg_y + 30
    svg.append(
        f'<text x="{tbl_x}" y="{tbl_y}" font-size="10" font-weight="700" '
        f'font-family="Arial" fill="#000">CONDUCTOR SCHEDULE</text>'
    )
    tbl_y += 16
    headers = ["SEGMENT", "WIRE SIZE", "CONDUIT", "VOLTAGE", "OCPD"]
    col_w = [280, 100, 80, 90, 90]
    hdr_x = tbl_x
    svg.append(
        f'<rect x="{tbl_x}" y="{tbl_y}" width="{sum(col_w)}" height="20" '
        f'fill="#e0e0e0" stroke="#000" stroke-width="0.5"/>'
    )
    for h, cw in zip(headers, col_w):
        svg.append(
            f'<text x="{hdr_x + 6}" y="{tbl_y + 14}" font-size="9" font-weight="700" '
            f'font-family="Arial" fill="#000">{h}</text>'
        )
        hdr_x += cw

    conduit_sys = '1"' if total_ac_amps * 1.25 > 30 else '3/4"'
    _inv_type_label = "Microinverter" if renderer._is_micro else "String Inverter"
    tbl_rows = [
        (f"PV Modules to {_inv_type_label} (DC {'quad cable' if renderer._is_micro else 'string wiring'})", "10 AWG", '1/2"', "~30 V DC", "N/A"),
        (
            f"Branch Circuit x{n_branches}: {_inv_type_label} to Combiner",
            f"#{branch_wire}",
            '3/4"',
            f"{inv_voltage} V AC",
            "15A 2P",
        ),
        (
            "AC Combiner to Main Service Panel",
            f"#{system_wire}",
            conduit_sys,
            f"{inv_voltage} V AC",
            f"{system_ocpd}A 2P",
        ),
    ]
    for ri, row in enumerate(tbl_rows):
        ry = tbl_y + 20 + ri * 20
        bg = "#f5f5f5" if ri % 2 == 0 else "#ffffff"
        svg.append(
            f'<rect x="{tbl_x}" y="{ry}" width="{sum(col_w)}" height="20" '
            f'fill="{bg}" stroke="#ccc" stroke-width="0.5"/>'
        )
        cx4 = tbl_x
        for cell, cw in zip(row, col_w):
            svg.append(
                f'<text x="{cx4 + 6}" y="{ry + 14}" font-size="8" font-family="Arial" fill="#000">{cell}</text>'
            )
            cx4 += cw

    # Notes
    note_y = tbl_y + 20 + len(tbl_rows) * 20 + 22
    svg.append(
        f'<text x="{tbl_x}" y="{note_y}" font-size="10" font-weight="700" '
        f'font-family="Arial" fill="#000">NOTES</text>'
    )
    notes = [
        "1.  All AC conductors are copper, 75 C rated, THWN-2 in EMT conduit unless noted otherwise.",
        f"2.  Branch circuits protected by {n_branches}x 15A 2-pole breakers in AC Combiner.",
        f"3.  System OCPD: {system_ocpd}A 2-pole breaker backfed at Main Service Panel.",
        f"4.  {_inv_type_label + 's' if renderer._is_micro else _inv_type_label}: {total_panels if renderer._is_micro else 1}x {inv_mfr} {inv_model}, {inv_voltage} V AC, {inv_amps} A each.",
        f"5.  PV modules: {total_panels}x {panel_mfr} {panel_model}, {panel_w} W STC.",
        "6.  All equipment shall be installed per manufacturer instructions and applicable electrical codes.",
    ]
    for ni, note in enumerate(notes):
        svg.append(
            f'<text x="{tbl_x}" y="{note_y + 16 + ni * 16}" font-size="8" '
            f'font-family="Arial" fill="#000">{note}</text>'
        )

    # Title block
    _addr = project.address if project else ""
    _today = date.today().strftime("%Y-%m-%d")
    svg.append(
        renderer._svg_title_block(
            VW,
            VH,
            "A-200",
            "ELECTRICAL SINGLE LINE DIAGRAM",
            f"AC {'Microinverter' if renderer._is_micro else 'String Inverter'} Single-Line",
            "14 of 14",
            _addr,
            _today,
        )
    )

    content = "\n".join(svg)
    return (
        f'<div class="page">'
        f'<svg width="100%" height="100%" viewBox="0 0 {VW} {VH}" '
        f'xmlns="http://www.w3.org/2000/svg" style="background:#fff;">'
        f"{content}</svg></div>"
    )
