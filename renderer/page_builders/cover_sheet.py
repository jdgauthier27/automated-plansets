"""Page builder: Cover Sheet (A-100)
=====================================
Extracted from HtmlRenderer._build_cover_sheet_page.
"""


def build_cover_sheet_page(renderer, address: str, today: str,
                           total_panels: int, total_kw: float) -> str:
    """A-100: Cover Sheet — project summary, sheet index, code references.

    Layout (1280×960px landscape):
      - Header band: company name + project title
      - Info strip: address, system size, date
      - Left column: sheet index table + governing codes
      - Right column: project summary + revision history + stamp area
      - Bottom-right: standard title block (A-100 | COVER SHEET)
    """
    VW, VH = 1280, 960
    svg = []

    # Background
    svg.append('<rect width="1280" height="960" fill="#ffffff"/>')

    # Outer border
    svg.append('<rect x="20" y="20" width="1240" height="820" fill="none" stroke="#000" stroke-width="2"/>')

    # ── Header band ────────────────────────────────────────────────
    company = "Solar Contractor"
    if renderer._project and renderer._project.company_name:
        company = renderer._project.company_name
    svg.append('<rect x="20" y="20" width="1240" height="80" fill="#1a3a5c" stroke="#000" stroke-width="1"/>')
    svg.append(
        f'<text x="640" y="56" text-anchor="middle" font-size="22" font-weight="700" '
        f'font-family="Arial" fill="#ffffff">{company.upper()}</text>'
    )
    svg.append(
        '<text x="640" y="83" text-anchor="middle" font-size="13" font-family="Arial" '
        'fill="#cce0ff">SOLAR PV SYSTEM INSTALLATION PLANSET</text>'
    )

    # ── Project info strip ─────────────────────────────────────────
    svg.append('<rect x="20" y="100" width="1240" height="58" fill="#f0f4f8" stroke="#000" stroke-width="0.5"/>')

    # Address
    svg.append(
        '<text x="36" y="118" font-size="8.5" font-weight="700" font-family="Arial" fill="#555">PROJECT ADDRESS</text>'
    )
    svg.append(
        f'<text x="36" y="134" font-size="11" font-weight="700" font-family="Arial" fill="#000">{address}</text>'
    )
    svg.append('<text x="36" y="150" font-size="8" font-family="Arial" fill="#777">Site of Installation</text>')

    # System size
    if renderer._project:
        sys_kw_str = f"{renderer._project.system_dc_kw:.2f}"
    else:
        sys_kw_str = f"{total_kw:.2f}"
    svg.append(
        '<text x="510" y="118" font-size="8.5" font-weight="700" font-family="Arial" fill="#555">SYSTEM SIZE</text>'
    )
    svg.append(
        f'<text x="510" y="134" font-size="12" font-weight="700" font-family="Arial" fill="#000">'
        f"{sys_kw_str} kW DC / {total_panels} Panels</text>"
    )

    # Date
    svg.append(
        '<text x="920" y="118" font-size="8.5" font-weight="700" font-family="Arial" fill="#555">DATE OF ISSUE</text>'
    )
    svg.append(
        f'<text x="920" y="134" font-size="11" font-weight="700" font-family="Arial" fill="#000">{today}</text>'
    )

    # ── Sheet index table (left column) ────────────────────────────
    si_x = 36
    si_y = 178
    svg.append(
        f'<text x="{si_x}" y="{si_y}" font-size="12" font-weight="700" font-family="Arial" fill="#000">SHEET INDEX</text>'
    )
    si_y += 18

    sheet_index = [
        ("A-100", "Cover Sheet"),
        ("A-101", "Site Plan"),
        ("A-102", "Racking and Framing Plan"),
        ("A-103", "String Plan"),
        ("A-200", "Electrical Single Line Diagram"),
        ("A-300", "Structural / Mounting Details"),
        ("A-400", "Bill of Materials (BOM)"),
    ]
    col_w0, col_w1 = 100, 330
    tbl_w = col_w0 + col_w1

    # Header row
    svg.append(
        f'<rect x="{si_x}" y="{si_y}" width="{tbl_w}" height="20" fill="#1a3a5c" stroke="#000" stroke-width="0.5"/>'
    )
    svg.append(
        f'<text x="{si_x + 6}" y="{si_y + 14}" font-size="9" font-weight="700" font-family="Arial" fill="#fff">SHEET NO.</text>'
    )
    svg.append(
        f'<text x="{si_x + col_w0 + 6}" y="{si_y + 14}" font-size="9" font-weight="700" font-family="Arial" fill="#fff">TITLE</text>'
    )
    si_y += 20

    for ri, (sheet_id, title) in enumerate(sheet_index):
        row_bg = "#e8f0fe" if sheet_id == "A-100" else ("#f5f5f5" if ri % 2 == 0 else "#ffffff")
        svg.append(
            f'<rect x="{si_x}" y="{si_y}" width="{tbl_w}" height="22" fill="{row_bg}" stroke="#ccc" stroke-width="0.5"/>'
        )
        svg.append(
            f'<line x1="{si_x + col_w0}" y1="{si_y}" x2="{si_x + col_w0}" y2="{si_y + 22}" stroke="#ccc" stroke-width="0.5"/>'
        )
        svg.append(
            f'<text x="{si_x + 6}" y="{si_y + 15}" font-size="10" font-weight="700" font-family="Arial" fill="#1a3a5c">{sheet_id}</text>'
        )
        svg.append(
            f'<text x="{si_x + col_w0 + 6}" y="{si_y + 15}" font-size="10" font-family="Arial" fill="#000">{title}</text>'
        )
        si_y += 22

    # ── Governing codes (left column, below sheet index) ──────────
    codes_y = si_y + 28
    svg.append(
        f'<text x="{si_x}" y="{codes_y}" font-size="12" font-weight="700" font-family="Arial" fill="#000">GOVERNING CODES</text>'
    )
    codes_y += 18

    # Use jurisdiction engine for governing codes (same pattern as PV-1 at line 1031)
    gov_codes = renderer._jurisdiction.get_governing_codes()
    codes = [f"{c['title']} ({c['edition']})" for c in gov_codes]

    for code in codes:
        svg.append(
            f'<text x="{si_x + 10}" y="{codes_y}" font-size="9" font-family="Arial" fill="#000">• {code}</text>'
        )
        codes_y += 15

    # ── Right column ───────────────────────────────────────────────
    rx = 580
    ry = 178
    r_width = 670

    # Project summary box
    svg.append(
        f'<rect x="{rx}" y="{ry}" width="{r_width}" height="185" fill="#f8f8f8" stroke="#000" stroke-width="1"/>'
    )
    svg.append(
        f'<rect x="{rx}" y="{ry}" width="{r_width}" height="24" fill="#1a3a5c" stroke="#000" stroke-width="0.5"/>'
    )
    svg.append(
        f'<text x="{rx + r_width // 2}" y="{ry + 16}" text-anchor="middle" font-size="10" font-weight="700" '
        f'font-family="Arial" fill="#ffffff">PROJECT SUMMARY</text>'
    )

    if renderer._project:
        p = renderer._project
        panel_str = f"{p.panel.manufacturer} {p.panel.model} ({p.panel.wattage_w}W)"
        inv_str = f"{p.inverter.manufacturer} {p.inverter.model}"
        rack_str = f"{p.racking.manufacturer} {p.racking.model}"
        dc_kw_str = f"{p.system_dc_kw:.2f} kW DC"
        ac_kw_str = f"{p.system_ac_kw:.2f} kW AC"
        prod_kwh = (
            f"{int(p.target_production_kwh):,} kWh/yr"
            if p.target_production_kwh > 0
            else f"{int(p.estimated_annual_kwh):,} kWh/yr"
        )
    else:
        panel_str = renderer._panel_model_full
        inv_str = renderer.INV_MODEL_SHORT
        rack_str = renderer._racking_full
        dc_kw_str = f"{total_kw:.2f} kW DC"
        ac_kw_str = "—"
        prod_kwh = "—"

    summary_rows = [
        ("Solar Modules", f"{total_panels}× {panel_str}"),
        ("Inverters", f"{total_panels}× {inv_str}"),
        ("Racking System", rack_str),
        ("DC System Size", dc_kw_str),
        ("AC System Size", ac_kw_str),
        ("Est. Annual Production", prod_kwh),
    ]
    sy = ry + 34
    for label, value in summary_rows:
        svg.append(
            f'<text x="{rx + 12}" y="{sy}" font-size="9" font-weight="700" font-family="Arial" fill="#555">{label}:</text>'
        )
        svg.append(f'<text x="{rx + 200}" y="{sy}" font-size="9" font-family="Arial" fill="#000">{value}</text>')
        sy += 22

    # ── Revision history box ───────────────────────────────────────
    rev_y = ry + 200
    rev_h = 110
    svg.append(
        f'<rect x="{rx}" y="{rev_y}" width="{r_width}" height="{rev_h}" fill="#ffffff" stroke="#000" stroke-width="1"/>'
    )
    svg.append(
        f'<rect x="{rx}" y="{rev_y}" width="{r_width}" height="24" fill="#1a3a5c" stroke="#000" stroke-width="0.5"/>'
    )
    svg.append(
        f'<text x="{rx + r_width // 2}" y="{rev_y + 16}" text-anchor="middle" font-size="10" font-weight="700" '
        f'font-family="Arial" fill="#ffffff">REVISION HISTORY</text>'
    )

    rev_cols = [60, 150, 380, 80]
    rh_y = rev_y + 24
    svg.append(
        f'<rect x="{rx}" y="{rh_y}" width="{r_width}" height="18" fill="#e0e0e0" stroke="#ccc" stroke-width="0.5"/>'
    )
    rcx = rx
    for hdr, cw in zip(["REV", "DATE", "DESCRIPTION", "BY"], rev_cols):
        svg.append(
            f'<text x="{rcx + 5}" y="{rh_y + 13}" font-size="8.5" font-weight="700" font-family="Arial" fill="#000">{hdr}</text>'
        )
        rcx += cw

    row0_y = rh_y + 18
    svg.append(
        f'<rect x="{rx}" y="{row0_y}" width="{r_width}" height="22" fill="#f9f9f9" stroke="#ccc" stroke-width="0.5"/>'
    )
    rcx = rx
    for val, cw in zip(["0", today, "Initial Issue — Permit Submittal", "AI"], rev_cols):
        svg.append(
            f'<text x="{rcx + 5}" y="{row0_y + 15}" font-size="9" font-family="Arial" fill="#000">{val}</text>'
        )
        rcx += cw

    # ── Designer / engineer stamp placeholder ──────────────────────
    stamp_y = rev_y + rev_h + 18
    svg.append(
        f'<rect x="{rx}" y="{stamp_y}" width="{r_width}" height="75" fill="#fafafa" stroke="#aaa" stroke-width="0.8" stroke-dasharray="5,3"/>'
    )
    svg.append(
        f'<text x="{rx + r_width // 2}" y="{stamp_y + 22}" text-anchor="middle" font-size="10" font-weight="700" font-family="Arial" fill="#999">ENGINEER / DESIGNER STAMP</text>'
    )
    svg.append(
        f'<text x="{rx + r_width // 2}" y="{stamp_y + 42}" text-anchor="middle" font-size="9" font-family="Arial" fill="#bbb">[ Reserved for Official Stamp ]</text>'
    )
    designer = (
        renderer._project.designer_name if renderer._project and renderer._project.designer_name else "AI Solar Design Engine"
    )
    svg.append(
        f'<text x="{rx + r_width // 2}" y="{stamp_y + 62}" text-anchor="middle" font-size="9" font-family="Arial" fill="#777">Prepared by: {designer}</text>'
    )

    # ── Standard title block ───────────────────────────────────────
    svg.append(
        renderer._svg_title_block(
            VW, VH, "A-100", "COVER SHEET", "Solar PV System Installation Planset", "1 of 14", address, today
        )
    )

    content = "\n".join(svg)
    return (
        f'<div class="page">'
        f'<svg width="100%" height="100%" viewBox="0 0 {VW} {VH}" '
        f'xmlns="http://www.w3.org/2000/svg" style="background:#fff;">'
        f"{content}</svg></div>"
    )
