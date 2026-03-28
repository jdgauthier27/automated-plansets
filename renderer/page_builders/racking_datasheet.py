"""Page builder: Racking Datasheet (PV-8.2)
========================================
Extracted from HtmlRenderer._build_racking_datasheet_page.
"""


def build_racking_datasheet_page(renderer, address: str, today: str) -> str:
    """PV-8.2: IronRidge XR10 rail + bonded splice specification sheet (two-column cut sheet)."""
    VW, VH = 1280, 960
    svg = []

    # ── Arrow-head marker defs for dimension lines ─────────────────────
    svg.append(
        "<defs>"
        '<marker id="arr-l" markerWidth="6" markerHeight="6" refX="6" refY="3" orient="auto">'
        '<polygon points="0,1 6,3 0,5" fill="#000"/></marker>'
        '<marker id="arr-r" markerWidth="6" markerHeight="6" refX="0" refY="3" orient="auto">'
        '<polygon points="6,1 0,3 6,5" fill="#000"/></marker>'
        "</defs>"
    )

    svg.append('<rect width="1280" height="960" fill="#ffffff"/>')
    svg.append('<rect x="20" y="20" width="1240" height="820" fill="none" stroke="#000" stroke-width="2"/>')

    # ── Two-section header: LEFT = XR10 Rail, RIGHT = XR10 Bonded Splice ──
    # Left section header (x=20–632)
    svg.append('<rect x="20" y="20" width="612" height="42" fill="#f5f5f5" stroke="#000" stroke-width="1"/>')
    svg.append('<rect x="519" y="23" width="60" height="16" fill="#e87722" rx="2"/>')
    svg.append(
        '<text x="549" y="35" text-anchor="middle" font-size="8" font-weight="700" '
        'font-family="Arial" fill="#ffffff">Cut Sheet</text>'
    )
    svg.append(
        '<text x="35" y="38" font-size="14" font-weight="700" font-family="Arial" fill="#000">// IRONRIDGE</text>'
    )
    svg.append(
        '<text x="200" y="38" font-size="13" font-weight="700" font-family="Arial" fill="#000">  XR10 Rail</text>'
    )
    svg.append(
        '<text x="35" y="54" font-size="9" font-family="Arial" fill="#444">'
        "6005-T5 Extruded Aluminum  |  Clear Anodized  |  For Flush-Mount PV Arrays</text>"
    )

    # Right section header (x=633–1260)
    svg.append('<rect x="633" y="20" width="627" height="42" fill="#f5f5f5" stroke="#000" stroke-width="1"/>')
    svg.append('<rect x="1133" y="23" width="60" height="16" fill="#e87722" rx="2"/>')
    svg.append(
        '<text x="1163" y="35" text-anchor="middle" font-size="8" font-weight="700" '
        'font-family="Arial" fill="#ffffff">Cut Sheet</text>'
    )
    svg.append(
        '<text x="648" y="38" font-size="14" font-weight="700" font-family="Arial" fill="#000">// IRONRIDGE</text>'
    )
    svg.append(
        '<text x="813" y="38" font-size="13" font-weight="700" '
        'font-family="Arial" fill="#000">  XR10 Bonded Splice</text>'
    )
    svg.append(
        '<text x="648" y="54" font-size="9" font-family="Arial" fill="#444">'
        "For Splicing and Bonding IronRidge XR10 Rail Sections  |  Includes Self-Tapping Screws</text>"
    )

    # Vertical divider between two cut-sheet sections
    svg.append('<line x1="633" y1="62" x2="633" y2="840" stroke="#000" stroke-width="1.5"/>')

    # ── Left column: cross-section diagram ───────────────────────────
    svg.append(
        '<text x="35" y="82" font-size="11" font-weight="700" '
        'font-family="Arial" fill="#000">XR10 RAIL CROSS-SECTION PROFILE</text>'
    )
    svg.append(
        '<text x="180" y="95" text-anchor="middle" font-size="9" font-family="Arial" fill="#555">(N.T.S.)</text>'
    )

    # C-channel cross section drawing
    cs_x, cs_y = 55, 110
    cs_w, cs_h = 250, 170  # scaled representation

    # Overall rail outer profile (C-channel shape)
    # Dimensions: 1.72" H x 2.22" W, wall ~0.099" (2.5mm)
    t = 14  # wall thickness in drawing units
    # Draw C-channel: top flange, web left, bottom flange
    rail_pts = (
        f"{cs_x},{cs_y} "  # top-left outer
        f"{cs_x + cs_w},{cs_y} "  # top-right outer
        f"{cs_x + cs_w},{cs_y + t} "  # top-right inner (top flange bottom)
        f"{cs_x + t},{cs_y + t} "  # top-left inner (web starts)
        f"{cs_x + t},{cs_y + cs_h - t} "  # bottom-left inner (web ends)
        f"{cs_x + cs_w},{cs_y + cs_h - t} "  # bottom-right inner (bottom flange top)
        f"{cs_x + cs_w},{cs_y + cs_h} "  # bottom-right outer
        f"{cs_x},{cs_y + cs_h} "  # bottom-left outer
    )
    svg.append(f'<polygon points="{rail_pts}" fill="#b8c8d8" stroke="#000" stroke-width="2"/>')

    # T-slot channel in web (simplified)
    tslot_x = cs_x + t + 10
    tslot_w = 18
    tslot_inner_y = cs_y + t
    tslot_inner_h = cs_h - 2 * t
    svg.append(
        f'<rect x="{tslot_x}" y="{tslot_inner_y}" width="{tslot_w}" height="{tslot_inner_h}" '
        f'fill="#e8f0f8" stroke="#555" stroke-width="0.8"/>'
    )
    svg.append(
        f'<text x="{tslot_x + tslot_w // 2}" y="{tslot_inner_y + tslot_inner_h // 2 + 3}" '
        f'text-anchor="middle" font-size="7" font-family="Arial" fill="#333">T-SLOT</text>'
    )

    # Dimension lines on cross-section
    # Width (top)
    dim_y_top = cs_y - 20
    svg.append(f'<line x1="{cs_x}" y1="{cs_y}" x2="{cs_x}" y2="{dim_y_top - 3}" stroke="#000" stroke-width="0.5"/>')
    svg.append(
        f'<line x1="{cs_x + cs_w}" y1="{cs_y}" x2="{cs_x + cs_w}" y2="{dim_y_top - 3}" stroke="#000" stroke-width="0.5"/>'
    )
    svg.append(
        f'<line x1="{cs_x}" y1="{dim_y_top}" x2="{cs_x + cs_w}" y2="{dim_y_top}" '
        f'stroke="#000" stroke-width="0.8" marker-start="url(#arr-l)" marker-end="url(#arr-r)"/>'
    )
    svg.append(
        f'<text x="{cs_x + cs_w // 2}" y="{dim_y_top - 5}" text-anchor="middle" '
        f'font-size="9" font-family="Arial" fill="#000">2.22" (56.4mm)</text>'
    )
    # Height (right)
    dim_x_right = cs_x + cs_w + 18
    svg.append(
        f'<line x1="{cs_x + cs_w}" y1="{cs_y}" x2="{dim_x_right + 3}" y2="{cs_y}" stroke="#000" stroke-width="0.5"/>'
    )
    svg.append(
        f'<line x1="{cs_x + cs_w}" y1="{cs_y + cs_h}" x2="{dim_x_right + 3}" y2="{cs_y + cs_h}" stroke="#000" stroke-width="0.5"/>'
    )
    svg.append(
        f'<line x1="{dim_x_right}" y1="{cs_y}" x2="{dim_x_right}" y2="{cs_y + cs_h}" '
        f'stroke="#000" stroke-width="0.8" marker-start="url(#arr-l)" marker-end="url(#arr-r)"/>'
    )
    svg.append(
        f'<text x="{dim_x_right + 10}" y="{cs_y + cs_h // 2 + 4}" font-size="9" '
        f'font-family="Arial" fill="#000">1.72"</text>'
    )
    # Wall thickness
    svg.append(
        f'<text x="{cs_x + t // 2}" y="{cs_y + cs_h + 20}" text-anchor="middle" '
        f'font-size="8" font-family="Arial" fill="#555">t = 0.099"</text>'
    )

    # Isometric perspective of a rail section (right of cross-section)
    rp_x, rp_y = cs_x + cs_w + 80, cs_y + 10
    rp_len = 130  # length of the perspective view
    rp_d = 35  # depth foreshortening
    rp_h_s = cs_h * 0.6  # scaled height
    rp_w_s = cs_w * 0.4  # scaled width

    # Draw 3D extruded C-channel (simplified perspective)
    # Front face (same C-channel but smaller)
    def rail3d(x, y):
        # Isometric projection offset
        return x + rp_x, y + rp_y

    # Top plane
    svg.append(
        f'<polygon points="'
        f"{rp_x},{rp_y} {rp_x + rp_len},{rp_y - rp_d} "
        f'{rp_x + rp_len + rp_w_s},{rp_y - rp_d} {rp_x + rp_w_s},{rp_y}" '
        f'fill="#d0dce8" stroke="#000" stroke-width="1"/>'
    )
    # Front face (C-channel)
    svg.append(
        f'<polygon points="'
        f"{rp_x},{rp_y} {rp_x + rp_w_s},{rp_y} "
        f'{rp_x + rp_w_s},{rp_y + rp_h_s} {rp_x},{rp_y + rp_h_s}" '
        f'fill="#b8c8d8" stroke="#000" stroke-width="1"/>'
    )
    # Bottom plane
    svg.append(
        f'<polygon points="'
        f"{rp_x},{rp_y + rp_h_s} {rp_x + rp_w_s},{rp_y + rp_h_s} "
        f'{rp_x + rp_len + rp_w_s},{rp_y + rp_h_s - rp_d} {rp_x + rp_len},{rp_y + rp_h_s - rp_d}" '
        f'fill="#a0b0c0" stroke="#000" stroke-width="1"/>'
    )
    svg.append(
        f'<text x="{rp_x + rp_len // 2}" y="{rp_y + rp_h_s + 22}" text-anchor="middle" '
        f'font-size="9" font-family="Arial" fill="#333">ISOMETRIC VIEW (N.T.S.)</text>'
    )
    # Length annotation
    svg.append(
        f'<text x="{rp_x + rp_len // 2}" y="{rp_y - rp_d - 10}" text-anchor="middle" '
        f'font-size="8" font-family="Arial" fill="#555">Available: 168" or 204"</text>'
    )

    # ── Structural Properties table (left column) ─────────────────────
    sp_y = cs_y + cs_h + 60
    svg.append(
        f'<text x="35" y="{sp_y}" font-size="10" font-weight="700" '
        f'font-family="Arial" fill="#000">STRUCTURAL PROPERTIES</text>'
    )
    sp_rows = [
        ("Extrusion Alloy", "6005-T5 Aluminum"),
        ("Surface Finish", "Clear Anodized (Class I)"),
        ("Yield Strength (Fty)", "35 ksi (241 MPa)"),
        ("Ultimate Tensile Strength (Ftu)", "38 ksi (262 MPa)"),
        ("Modulus of Elasticity", "10,100 ksi (69.6 GPa)"),
        ("Moment of Inertia (Ix)", "0.425 in\u2074"),
        ("Section Modulus (Sx)", "0.293 in\u00b3"),
        ("Weight", "0.88 lb/ft  (1.31 kg/m)"),
    ]
    row_h = 24
    for ri, (label, val) in enumerate(sp_rows):
        ry = sp_y + 14 + ri * row_h
        bg = "#f5f5f5" if ri % 2 == 0 else "#ffffff"
        svg.append(
            f'<rect x="30" y="{ry}" width="560" height="{row_h}" fill="{bg}" stroke="#ccc" stroke-width="0.5"/>'
        )
        svg.append(f'<text x="38" y="{ry + 16}" font-size="9" font-family="Arial" fill="#000">{label}</text>')
        svg.append(
            f'<text x="582" y="{ry + 16}" text-anchor="end" font-size="9" font-weight="600" '
            f'font-family="Arial" fill="#000000">{val}</text>'
        )

    # ── Span / Load Table ──────────────────────────────────────────────
    sl_y = sp_y + 14 + len(sp_rows) * row_h + 22
    svg.append(
        f'<text x="35" y="{sl_y}" font-size="10" font-weight="700" '
        f'font-family="Arial" fill="#000">ALLOWABLE LOAD vs. SPAN (UDL)</text>'
    )
    svg.append(
        f'<text x="35" y="{sl_y + 14}" font-size="8" font-family="Arial" fill="#555">'
        f"Maximum uniformly distributed load (lb/ft) per IBC 2021 \u2014 Single span, L/180 deflection limit</text>"
    )
    # Table header
    th_y = sl_y + 26
    headers = ["Span", '24"', '36"', '48"', '60"', '72"', '84"', '96"']
    col_w = 72
    svg.append(
        f'<rect x="30" y="{th_y}" width="{len(headers) * col_w + 10}" height="22" '
        f'fill="#e8e8e8" stroke="#000" stroke-width="0.5"/>'
    )
    for ci, hdr in enumerate(headers):
        svg.append(
            f'<text x="{30 + ci * col_w + col_w // 2 + 5}" y="{th_y + 15}" text-anchor="middle" '
            f'font-size="9" font-weight="700" font-family="Arial" fill="#000">{hdr}</text>'
        )
    # Data rows (Allowable UDL for XR10)
    load_data = [
        ("XR10", "820", "364", "205", "131", "91", "67", "51"),
    ]
    for ri, row_data in enumerate(load_data):
        ry2 = th_y + 22 + ri * row_h
        svg.append(
            f'<rect x="30" y="{ry2}" width="{len(headers) * col_w + 10}" height="{row_h}" '
            f'fill="#f5f5f5" stroke="#ccc" stroke-width="0.5"/>'
        )
        for ci, cell in enumerate(row_data):
            svg.append(
                f'<text x="{30 + ci * col_w + col_w // 2 + 5}" y="{ry2 + 16}" text-anchor="middle" '
                f'font-size="9" font-weight="600" font-family="Arial" fill="#000">{cell}</text>'
            )
    svg.append(
        f'<text x="35" y="{th_y + 22 + len(load_data) * row_h + 14}" font-size="7" '
        f'font-family="Arial" fill="#666" font-style="italic">'
        f"Values in lb/ft. Consult IronRidge engineering specs for complete loading tables.</text>"
    )

    # ── Left column: Part Numbers table (Cubillas 5-col format) ───────
    pnl_y = th_y + 22 + len(load_data) * row_h + 34
    svg.append(
        f'<text x="35" y="{pnl_y}" font-size="10" font-weight="700" '
        f'font-family="Arial" fill="#000">PART NUMBERS</text>'
    )
    pnl_col_widths = [95, 95, 185, 145, 70]  # total = 590 (x=30 to x=620)
    pnl_col_labels = ["Clear Part #", "Black Part #", "Description / Length", "Material", "Weight"]
    pnl_hdr_y = pnl_y + 14
    pnl_x_starts = [30]
    for cw in pnl_col_widths[:-1]:
        pnl_x_starts.append(pnl_x_starts[-1] + cw)
    svg.append(
        f'<rect x="30" y="{pnl_hdr_y}" width="590" height="22" fill="#e8e8e8" stroke="#000" stroke-width="0.5"/>'
    )
    for ci, (hdr, xs) in enumerate(zip(pnl_col_labels, pnl_x_starts)):
        svg.append(
            f'<text x="{xs + 6}" y="{pnl_hdr_y + 15}" font-size="8" font-weight="700" '
            f'font-family="Arial" fill="#000">{hdr}</text>'
        )
    pnl_rows = [
        ("XR-10-168A", "XR-10-168B", 'XR10 Rail, 168" (14 ft)', "6005-T5 Alum., Clear Anodized", "12.3 lb"),
        ("XR-10-204A", "XR-10-204B", 'XR10 Rail, 204" (17 ft)', "6005-T5 Alum., Clear Anodized", "14.9 lb"),
    ]
    for ri, row_cells in enumerate(pnl_rows):
        pnl_ry = pnl_hdr_y + 22 + ri * 22
        bg = "#f5f5f5" if ri % 2 == 0 else "#ffffff"
        svg.append(
            f'<rect x="30" y="{pnl_ry}" width="590" height="22" fill="{bg}" stroke="#ccc" stroke-width="0.5"/>'
        )
        for ci, (cell, xs) in enumerate(zip(row_cells, pnl_x_starts)):
            fw = "700" if ci == 0 else "400"
            svg.append(
                f'<text x="{xs + 6}" y="{pnl_ry + 15}" font-size="8" font-weight="{fw}" '
                f'font-family="Arial" fill="#000">{cell}</text>'
            )

    # ── Right column: XR10 Bonded Splice Cut Sheet ────────────────────
    rx2 = 648  # right col left edge (inside divider at 633)
    rc_cx = 946  # right col centre x

    # ── Assembly overview diagram ──────────────────────────────────────
    svg.append(
        f'<text x="{rx2}" y="73" font-size="11" font-weight="700" '
        f'font-family="Arial" fill="#000">XR10 BONDED SPLICE \u2014 ASSEMBLY OVERVIEW</text>'
    )
    svg.append(f'<text x="{rx2 + 430}" y="73" font-size="8" font-family="Arial" fill="#555">(N.T.S.)</text>')

    ov_y = 88
    ov_h = 48  # rail cross-section height in diagram
    ov_rail_w = 155  # length of each rail section
    ov_gap = 32  # gap between the two rail ends
    ov_splice_w = ov_gap + 44  # splice overlaps 22px into each rail

    # Left rail section (solid rect representing C-channel end)
    lr_x = rc_cx - ov_gap // 2 - ov_rail_w
    svg.append(
        f'<rect x="{lr_x}" y="{ov_y}" width="{ov_rail_w}" height="{ov_h}" '
        f'fill="#b8c8d8" stroke="#000" stroke-width="1.5"/>'
    )
    # Hatching to suggest open channel end
    for hi in range(0, ov_h, 8):
        svg.append(
            f'<line x1="{lr_x + ov_rail_w - 10}" y1="{ov_y + hi}" '
            f'x2="{lr_x + ov_rail_w}" y2="{ov_y + min(hi + 10, ov_h)}" '
            f'stroke="#6090b0" stroke-width="0.7"/>'
        )
    svg.append(
        f'<text x="{lr_x + ov_rail_w // 2}" y="{ov_y + ov_h + 14}" '
        f'text-anchor="middle" font-size="8" font-family="Arial" fill="#444">XR10 Rail A</text>'
    )

    # Right rail section
    rr_x = rc_cx + ov_gap // 2
    svg.append(
        f'<rect x="{rr_x}" y="{ov_y}" width="{ov_rail_w}" height="{ov_h}" '
        f'fill="#b8c8d8" stroke="#000" stroke-width="1.5"/>'
    )
    for hi in range(0, ov_h, 8):
        svg.append(
            f'<line x1="{rr_x}" y1="{ov_y + hi}" '
            f'x2="{rr_x + 10}" y2="{ov_y + min(hi + 10, ov_h)}" '
            f'stroke="#6090b0" stroke-width="0.7"/>'
        )
    svg.append(
        f'<text x="{rr_x + ov_rail_w // 2}" y="{ov_y + ov_h + 14}" '
        f'text-anchor="middle" font-size="8" font-family="Arial" fill="#444">XR10 Rail B</text>'
    )

    # Bonded splice (shown inset inside both rails)
    sp_ov_x = rc_cx - ov_splice_w // 2
    sp_inset = 5
    svg.append(
        f'<rect x="{sp_ov_x}" y="{ov_y + sp_inset}" '
        f'width="{ov_splice_w}" height="{ov_h - 2 * sp_inset}" '
        f'fill="#e8c46a" stroke="#8b6914" stroke-width="2" rx="2"/>'
    )
    svg.append(
        f'<text x="{rc_cx}" y="{ov_y + ov_h // 2 + 4}" '
        f'text-anchor="middle" font-size="8" font-weight="700" '
        f'font-family="Arial" fill="#5a4010">SPLICE</text>'
    )

    # Self-tapping screws on splice (×2 visible from side)
    for sc_off in [-14, 14]:
        scx = rc_cx + sc_off
        scy = ov_y + sp_inset
        svg.append(f'<circle cx="{scx}" cy="{scy}" r="5" fill="#c0c8d0" stroke="#333" stroke-width="1"/>')
        svg.append(f'<line x1="{scx - 4}" y1="{scy}" x2="{scx + 4}" y2="{scy}" stroke="#555" stroke-width="0.8"/>')
        svg.append(f'<line x1="{scx}" y1="{scy - 4}" x2="{scx}" y2="{scy + 4}" stroke="#555" stroke-width="0.8"/>')

    # Callout: screws
    svg.append(
        f'<text x="{rc_cx}" y="{ov_y - 10}" text-anchor="middle" '
        f'font-size="8" font-family="Arial" fill="#000">Self-Tapping Screws (\u00d74 per splice)</text>'
    )
    svg.append(
        f'<line x1="{rc_cx - 14}" y1="{ov_y - 4}" x2="{rc_cx - 14}" y2="{ov_y + sp_inset}" '
        f'stroke="#000" stroke-width="0.7" stroke-dasharray="3,2"/>'
    )

    svg.append(f'<line x1="{rx2 + 10}" y1="162" x2="1248" y2="162" stroke="#ccc" stroke-width="0.8"/>')

    # ── Section 1: Splice dimensional drawing ─────────────────────────
    svg.append(
        f'<text x="{rx2}" y="178" font-size="10" font-weight="700" '
        f'font-family="Arial" fill="#000">1)  Splice, XR10, Mill  \u2014  12" long</text>'
    )

    # Splice front view rectangle (12" length, .88" height)
    spl_x = rx2 + 35
    spl_y = 195
    spl_draw_w = 280  # represents 12" (23.3 px/inch)
    spl_draw_h = 24  # represents .88" (approx 27 px/inch — not to same scale)
    svg.append(
        f'<rect x="{spl_x}" y="{spl_y}" width="{spl_draw_w}" height="{spl_draw_h}" '
        f'fill="#d8e8f4" stroke="#000" stroke-width="1.5" rx="1"/>'
    )

    # Diagonal hatching on splice (material symbol)
    for hxi in range(8, spl_draw_w - 4, 12):
        hx = spl_x + hxi
        svg.append(
            f'<line x1="{hx}" y1="{spl_y}" '
            f'x2="{min(hx + spl_draw_h, spl_x + spl_draw_w)}" y2="{min(spl_y + spl_draw_h, spl_y + spl_draw_h)}" '
            f'stroke="#8aaac8" stroke-width="0.5"/>'
        )

    # Length dimension (below splice)
    dim_spl_bot = spl_y + spl_draw_h + 14
    svg.append(
        f'<line x1="{spl_x}" y1="{spl_y + spl_draw_h}" x2="{spl_x}" y2="{dim_spl_bot - 2}" '
        f'stroke="#000" stroke-width="0.5"/>'
    )
    svg.append(
        f'<line x1="{spl_x + spl_draw_w}" y1="{spl_y + spl_draw_h}" '
        f'x2="{spl_x + spl_draw_w}" y2="{dim_spl_bot - 2}" stroke="#000" stroke-width="0.5"/>'
    )
    svg.append(
        f'<line x1="{spl_x}" y1="{dim_spl_bot}" x2="{spl_x + spl_draw_w}" y2="{dim_spl_bot}" '
        f'stroke="#000" stroke-width="0.8" marker-start="url(#arr-l)" marker-end="url(#arr-r)"/>'
    )
    svg.append(
        f'<text x="{spl_x + spl_draw_w // 2}" y="{dim_spl_bot + 12}" text-anchor="middle" '
        f'font-size="9" font-family="Arial" fill="#000">12.0"</text>'
    )

    # Width (.88") and depth (.60") annotations to the right
    dim_spl_rx = spl_x + spl_draw_w + 18
    svg.append(
        f'<line x1="{spl_x + spl_draw_w}" y1="{spl_y}" x2="{dim_spl_rx - 2}" y2="{spl_y}" '
        f'stroke="#000" stroke-width="0.5"/>'
    )
    svg.append(
        f'<line x1="{spl_x + spl_draw_w}" y1="{spl_y + spl_draw_h}" x2="{dim_spl_rx - 2}" y2="{spl_y + spl_draw_h}" '
        f'stroke="#000" stroke-width="0.5"/>'
    )
    svg.append(
        f'<line x1="{dim_spl_rx}" y1="{spl_y}" x2="{dim_spl_rx}" y2="{spl_y + spl_draw_h}" '
        f'stroke="#000" stroke-width="0.8" marker-start="url(#arr-l)" marker-end="url(#arr-r)"/>'
    )
    svg.append(
        f'<text x="{dim_spl_rx + 8}" y="{spl_y + spl_draw_h // 2 + 4}" '
        f'font-size="9" font-family="Arial" fill="#000">.88" W \u00d7 .60" D</text>'
    )

    # ── Splice material property table ────────────────────────────────
    spt_y = dim_spl_bot + 26
    svg.append(
        f'<rect x="{rx2 + 10}" y="{spt_y}" width="580" height="22" '
        f'fill="#e8e8e8" stroke="#000" stroke-width="0.5"/>'
    )
    svg.append(
        f'<text x="{rx2 + 18}" y="{spt_y + 15}" font-size="8" font-weight="700" '
        f'font-family="Arial" fill="#000">Property</text>'
    )
    svg.append(
        f'<text x="{rx2 + 220}" y="{spt_y + 15}" font-size="8" font-weight="700" '
        f'font-family="Arial" fill="#000">Value</text>'
    )
    splice_props = [
        ("Material", "6000 Series Aluminum"),
        ("Finish", "Mill"),
        ("Part Number", "XR-10-SPLC-M1"),
    ]
    for ri, (lbl, val) in enumerate(splice_props):
        ry_sp = spt_y + 22 + ri * 22
        bg = "#f5f5f5" if ri % 2 == 0 else "#ffffff"
        svg.append(
            f'<rect x="{rx2 + 10}" y="{ry_sp}" width="580" height="22" '
            f'fill="{bg}" stroke="#ccc" stroke-width="0.5"/>'
        )
        svg.append(
            f'<text x="{rx2 + 18}" y="{ry_sp + 15}" font-size="9" font-family="Arial" fill="#000">{lbl}</text>'
        )
        svg.append(
            f'<text x="{rx2 + 220}" y="{ry_sp + 15}" font-size="9" font-weight="600" '
            f'font-family="Arial" fill="#000">{val}</text>'
        )

    # ── Section 2: Screw dimensional drawing ──────────────────────────
    scr_sec_y = spt_y + 22 + len(splice_props) * 22 + 24
    svg.append(
        f'<text x="{rx2}" y="{scr_sec_y}" font-size="10" font-weight="700" '
        f'font-family="Arial" fill="#000">2)  Screw, Self Drilling  \u2014  #12-14 TYPE "B" THREAD</text>'
    )

    # Screw side-view: scale = 150 px per inch
    scr_sc = 150  # px per inch
    scr_tot = int(0.63 * scr_sc)  # 94px total length
    scr_hd = int(0.31 * scr_sc)  # 46px head length
    scr_shd = int(0.42 * scr_sc)  # 63px shank diameter
    scr_hdiam = scr_shd + 12  # head slightly taller (75px)
    scr_x = rx2 + 70
    scr_y = scr_sec_y + 36

    # Head (tapered trapezoid — hex drive representation)
    scr_hd_pts = (
        f"{scr_x},{scr_y + (scr_hdiam - scr_shd) // 2} "
        f"{scr_x + scr_hd},{scr_y} "
        f"{scr_x + scr_hd},{scr_y + scr_hdiam} "
        f"{scr_x},{scr_y + scr_hdiam - (scr_hdiam - scr_shd) // 2}"
    )
    svg.append(f'<polygon points="{scr_hd_pts}" fill="#c8d8e8" stroke="#000" stroke-width="1.5"/>')
    # Cross slot on head
    scr_hcx = scr_x + scr_hd // 3
    scr_hcy = scr_y + scr_hdiam // 2
    svg.append(
        f'<line x1="{scr_hcx - 7}" y1="{scr_hcy}" x2="{scr_hcx + 7}" y2="{scr_hcy}" '
        f'stroke="#555" stroke-width="1.5"/>'
    )
    svg.append(
        f'<line x1="{scr_hcx}" y1="{scr_hcy - 7}" x2="{scr_hcx}" y2="{scr_hcy + 7}" '
        f'stroke="#555" stroke-width="1.5"/>'
    )

    # Shank (threaded cylinder)
    shk_x = scr_x + scr_hd
    shk_y = scr_y + (scr_hdiam - scr_shd) // 2
    shk_len = scr_tot - scr_hd
    svg.append(
        f'<rect x="{shk_x}" y="{shk_y}" width="{shk_len}" height="{scr_shd}" '
        f'fill="#d8eaf8" stroke="#000" stroke-width="1.5"/>'
    )
    # Thread lines (diagonal)
    for ti in range(4, shk_len - 4, 7):
        svg.append(
            f'<line x1="{shk_x + ti}" y1="{shk_y}" x2="{shk_x + ti + 6}" y2="{shk_y + scr_shd}" '
            f'stroke="#7090b0" stroke-width="0.5"/>'
        )

    # Self-drill tip (triangle)
    tip_bx = shk_x + shk_len
    tip_pts = f"{tip_bx},{shk_y} {tip_bx + 14},{shk_y + scr_shd // 2} {tip_bx},{shk_y + scr_shd}"
    svg.append(f'<polygon points="{tip_pts}" fill="#b8c8d8" stroke="#000" stroke-width="1"/>')

    # Total length dimension (above screw)
    scr_dim_top = scr_y - 16
    svg.append(
        f'<line x1="{scr_x}" y1="{scr_y}" x2="{scr_x}" y2="{scr_dim_top - 2}" stroke="#000" stroke-width="0.5"/>'
    )
    tip_rx = tip_bx + 14
    svg.append(
        f'<line x1="{tip_rx}" y1="{shk_y + scr_shd // 2}" x2="{tip_rx}" y2="{scr_dim_top - 2}" '
        f'stroke="#000" stroke-width="0.5"/>'
    )
    svg.append(
        f'<line x1="{scr_x}" y1="{scr_dim_top}" x2="{tip_rx}" y2="{scr_dim_top}" '
        f'stroke="#000" stroke-width="0.8" marker-start="url(#arr-l)" marker-end="url(#arr-r)"/>'
    )
    svg.append(
        f'<text x="{scr_x + (tip_rx - scr_x) // 2}" y="{scr_dim_top - 4}" text-anchor="middle" '
        f'font-size="9" font-family="Arial" fill="#000">.63" Total</text>'
    )

    # Head length dimension (below, bracketing head only)
    scr_bot = scr_y + scr_hdiam
    scr_dim_bot = scr_bot + 16
    svg.append(
        f'<line x1="{scr_x}" y1="{scr_bot}" x2="{scr_x}" y2="{scr_dim_bot - 2}" stroke="#000" stroke-width="0.5"/>'
    )
    svg.append(
        f'<line x1="{scr_x + scr_hd}" y1="{scr_bot}" x2="{scr_x + scr_hd}" y2="{scr_dim_bot - 2}" '
        f'stroke="#000" stroke-width="0.5"/>'
    )
    svg.append(
        f'<line x1="{scr_x}" y1="{scr_dim_bot}" x2="{scr_x + scr_hd}" y2="{scr_dim_bot}" '
        f'stroke="#000" stroke-width="0.8" marker-start="url(#arr-l)" marker-end="url(#arr-r)"/>'
    )
    svg.append(
        f'<text x="{scr_x + scr_hd // 2}" y="{scr_dim_bot + 12}" text-anchor="middle" '
        f'font-size="9" font-family="Arial" fill="#000">.31" Head</text>'
    )

    # Shank diameter dimension (right side)
    scr_dim_rx = tip_rx + 22
    svg.append(
        f'<line x1="{shk_x + shk_len // 2}" y1="{shk_y}" x2="{scr_dim_rx - 2}" y2="{shk_y}" '
        f'stroke="#000" stroke-width="0.5"/>'
    )
    svg.append(
        f'<line x1="{shk_x + shk_len // 2}" y1="{shk_y + scr_shd}" x2="{scr_dim_rx - 2}" y2="{shk_y + scr_shd}" '
        f'stroke="#000" stroke-width="0.5"/>'
    )
    svg.append(
        f'<line x1="{scr_dim_rx}" y1="{shk_y}" x2="{scr_dim_rx}" y2="{shk_y + scr_shd}" '
        f'stroke="#000" stroke-width="0.8" marker-start="url(#arr-l)" marker-end="url(#arr-r)"/>'
    )
    svg.append(
        f'<text x="{scr_dim_rx + 8}" y="{shk_y + scr_shd // 2 + 4}" '
        f'font-size="9" font-family="Arial" fill="#000">\u00d8 .42"</text>'
    )

    # ── Screw material property table ─────────────────────────────────
    scrpt_y = scr_bot + 46
    svg.append(
        f'<rect x="{rx2 + 10}" y="{scrpt_y}" width="580" height="22" '
        f'fill="#e8e8e8" stroke="#000" stroke-width="0.5"/>'
    )
    svg.append(
        f'<text x="{rx2 + 18}" y="{scrpt_y + 15}" font-size="8" font-weight="700" '
        f'font-family="Arial" fill="#000">Property</text>'
    )
    svg.append(
        f'<text x="{rx2 + 220}" y="{scrpt_y + 15}" font-size="8" font-weight="700" '
        f'font-family="Arial" fill="#000">Value</text>'
    )
    screw_props = [
        ("Material", "300 Series Stainless Steel"),
        ("Finish", "Clear"),
        ("Thread", '#12-14 TYPE "B" SELF-DRILLING'),
    ]
    for ri, (lbl, val) in enumerate(screw_props):
        ry_sc = scrpt_y + 22 + ri * 22
        bg = "#f5f5f5" if ri % 2 == 0 else "#ffffff"
        svg.append(
            f'<rect x="{rx2 + 10}" y="{ry_sc}" width="580" height="22" '
            f'fill="{bg}" stroke="#ccc" stroke-width="0.5"/>'
        )
        svg.append(
            f'<text x="{rx2 + 18}" y="{ry_sc + 15}" font-size="9" font-family="Arial" fill="#000">{lbl}</text>'
        )
        svg.append(
            f'<text x="{rx2 + 220}" y="{ry_sc + 15}" font-size="9" font-weight="600" '
            f'font-family="Arial" fill="#000">{val}</text>'
        )

    # ── Title block ───────────────────────────────────────────────────
    svg.append(
        renderer._svg_title_block(
            VW,
            VH,
            "R-004",
            "EQUIPMENT SPEC (RACKING)",
            "IronRidge XR10 Flush Mount Rail System",
            "14 of 15",
            address,
            today,
        )
    )

    content = "\n".join(svg)
    return (
        f'<div class="page">'
        f'<svg width="100%" height="100%" viewBox="0 0 {VW} {VH}" '
        f'xmlns="http://www.w3.org/2000/svg" style="background:#fff;">'
        f"{content}</svg></div>"
    )
