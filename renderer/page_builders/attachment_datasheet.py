"""
Page builder: Attachment Datasheet (PV-8.3)
========================================
Extracted from HtmlRenderer._build_attachment_datasheet_page.
"""


def build_attachment_datasheet_page(renderer, address: str, today: str) -> str:
    """PV-8.3: IronRidge FlashFoot2 roof attachment specification sheet."""
    VW, VH = 1280, 960
    svg = []

    svg.append('<rect width="1280" height="960" fill="#ffffff"/>')
    svg.append('<rect x="20" y="20" width="1240" height="820" fill="none" stroke="#000" stroke-width="2"/>')

    # ── Header ────────────────────────────────────────────────────────
    svg.append('<rect x="20" y="20" width="1240" height="42" fill="#f5f5f5" stroke="#000" stroke-width="1"/>')
    svg.append(
        '<text x="640" y="37" text-anchor="middle" font-size="14" font-weight="700" '
        'font-family="Arial" fill="#000000">IRONRIDGE — FLASHFOOT2 ROOF ATTACHMENT</text>'
    )
    svg.append(
        '<text x="640" y="53" text-anchor="middle" font-size="11" font-family="Arial" '
        'fill="#444444">Flush-Mount Lag Bolt Attachment | EPDM Flashing | For Composite Shingle Roofs</text>'
    )

    row_h = 24

    # ── Left column: exploded view diagram ───────────────────────────
    svg.append(
        '<text x="35" y="82" font-size="11" font-weight="700" '
        'font-family="Arial" fill="#000">FLASHFOOT2 COMPONENT DIAGRAM (EXPLODED)</text>'
    )

    # Draw exploded view of FlashFoot2 components (side profile)
    exp_x, exp_y = 55, 100
    exp_cx = exp_x + 200  # center x for aligned components

    # Component 1: Cap (top)
    cap_y = exp_y
    svg.append(
        f'<rect x="{exp_cx - 30}" y="{cap_y}" width="60" height="18" rx="4" '
        f'fill="#d0d8e0" stroke="#000" stroke-width="1.5"/>'
    )
    svg.append(
        f'<text x="{exp_cx}" y="{cap_y + 13}" text-anchor="middle" '
        f'font-size="8" font-weight="600" font-family="Arial" fill="#000">CAP</text>'
    )
    svg.append(
        f'<text x="{exp_cx + 50}" y="{cap_y + 12}" font-size="8" '
        f'font-family="Arial" fill="#555">6063-T5 Aluminum</text>'
    )
    # leader line
    svg.append(
        f'<line x1="{exp_cx + 32}" y1="{cap_y + 9}" x2="{exp_cx + 46}" y2="{cap_y + 9}" '
        f'stroke="#666" stroke-width="0.7"/>'
    )
    svg.append(f'<circle cx="{exp_cx + 30}" cy="{cap_y + 9}" r="1.5" fill="#666"/>')

    # Component 2: Base (below cap)
    base_y = cap_y + 40
    svg.append(
        f'<rect x="{exp_cx - 38}" y="{base_y}" width="76" height="22" rx="3" '
        f'fill="#c0c8d0" stroke="#000" stroke-width="1.5"/>'
    )
    svg.append(
        f'<rect x="{exp_cx - 28}" y="{base_y + 2}" width="56" height="18" rx="2" '
        f'fill="#a8b8c8" stroke="#888" stroke-width="0.5"/>'
    )
    svg.append(
        f'<text x="{exp_cx}" y="{base_y + 14}" text-anchor="middle" '
        f'font-size="8" font-weight="600" font-family="Arial" fill="#000">BASE</text>'
    )
    svg.append(
        f'<text x="{exp_cx + 52}" y="{base_y + 14}" font-size="8" '
        f'font-family="Arial" fill="#555">6063-T5 Aluminum</text>'
    )
    svg.append(
        f'<line x1="{exp_cx + 38}" y1="{base_y + 11}" x2="{exp_cx + 50}" y2="{base_y + 11}" '
        f'stroke="#666" stroke-width="0.7"/>'
    )

    # Component 3: EPDM gasket / flashing
    gsk_y = base_y + 44
    svg.append(
        f'<ellipse cx="{exp_cx}" cy="{gsk_y + 15}" rx="55" ry="14" fill="#2a2a2a" stroke="#000" stroke-width="1"/>'
    )
    svg.append(
        f'<ellipse cx="{exp_cx}" cy="{gsk_y + 15}" rx="38" ry="9" fill="#444" stroke="#666" stroke-width="0.5"/>'
    )
    svg.append(
        f'<text x="{exp_cx}" y="{gsk_y + 19}" text-anchor="middle" '
        f'font-size="7" font-weight="600" font-family="Arial" fill="#fff">EPDM</text>'
    )
    svg.append(
        f'<text x="{exp_cx + 70}" y="{gsk_y + 18}" font-size="8" '
        f'font-family="Arial" fill="#555">EPDM Rubber Gasket</text>'
    )
    svg.append(
        f'<text x="{exp_cx + 70}" y="{gsk_y + 30}" font-size="8" '
        f'font-family="Arial" fill="#555">12" Round Aluminum Flash</text>'
    )
    svg.append(
        f'<line x1="{exp_cx + 56}" y1="{gsk_y + 15}" x2="{exp_cx + 68}" y2="{gsk_y + 15}" '
        f'stroke="#666" stroke-width="0.7"/>'
    )

    # Component 4: Lag bolt
    bolt_y = gsk_y + 50
    bolt_head_y = bolt_y + 5
    svg.append(
        f'<polygon points="{exp_cx - 8},{bolt_head_y} {exp_cx + 8},{bolt_head_y} '
        f'{exp_cx + 8},{bolt_head_y + 12} {exp_cx - 8},{bolt_head_y + 12}" '
        f'fill="#888" stroke="#000" stroke-width="1"/>'
    )
    svg.append(
        f'<rect x="{exp_cx - 3}" y="{bolt_head_y + 12}" width="6" height="50" '
        f'fill="#999" stroke="#555" stroke-width="0.8"/>'
    )
    # Thread lines
    for ti in range(0, 45, 5):
        ty = bolt_head_y + 12 + ti
        svg.append(
            f'<line x1="{exp_cx - 5}" y1="{ty}" x2="{exp_cx + 5}" y2="{ty + 3}" stroke="#666" stroke-width="0.5"/>'
        )
    svg.append(
        f'<text x="{exp_cx + 22}" y="{bolt_head_y + 30}" font-size="8" '
        f'font-family="Arial" fill="#555">5/16" × 2.5" Lag Bolt</text>'
    )
    svg.append(
        f'<text x="{exp_cx + 22}" y="{bolt_head_y + 42}" font-size="8" '
        f'font-family="Arial" fill="#555">304 Stainless Steel</text>'
    )
    svg.append(
        f'<line x1="{exp_cx + 8}" y1="{bolt_head_y + 20}" x2="{exp_cx + 20}" y2="{bolt_head_y + 20}" '
        f'stroke="#666" stroke-width="0.7"/>'
    )

    # Dimension annotations
    total_h_px = (bolt_head_y + 62) - cap_y
    dim_x_left = exp_cx - 80
    svg.append(
        f'<line x1="{dim_x_left}" y1="{cap_y}" x2="{exp_cx - 42}" y2="{cap_y}" stroke="#000" stroke-width="0.5"/>'
    )
    svg.append(
        f'<line x1="{dim_x_left}" y1="{bolt_head_y + 62}" x2="{exp_cx - 42}" y2="{bolt_head_y + 62}" '
        f'stroke="#000" stroke-width="0.5"/>'
    )
    svg.append(
        f'<line x1="{dim_x_left}" y1="{cap_y}" x2="{dim_x_left}" y2="{bolt_head_y + 62}" '
        f'stroke="#000" stroke-width="0.8"/>'
    )
    svg.append(
        f'<text x="{dim_x_left - 5}" y="{cap_y + total_h_px // 2 + 3}" text-anchor="end" '
        f'font-size="8" font-family="Arial" fill="#333" '
        f'transform="rotate(-90,{dim_x_left - 5},{cap_y + total_h_px // 2})">Total Height</text>'
    )

    # Assembly note
    asm_note_y = bolt_head_y + 80
    svg.append(
        f'<text x="{exp_cx}" y="{asm_note_y}" text-anchor="middle" font-size="8" '
        f'font-weight="600" font-family="Arial" fill="#000000">ASSEMBLED PROFILE (N.T.S.)</text>'
    )

    # Assembled cross-section (side view installed on roof)
    asm_x = exp_x + 20
    asm_y = asm_note_y + 14
    asm_w = 340

    # Rafter (wood)
    svg.append(
        f'<rect x="{asm_x + 80}" y="{asm_y + 100}" width="180" height="35" '
        f'fill="#d4b896" stroke="#000" stroke-width="1"/>'
    )
    for xi in range(asm_x + 90, asm_x + 260, 20):
        svg.append(
            f'<line x1="{xi}" y1="{asm_y + 102}" x2="{xi}" y2="{asm_y + 133}" stroke="#b8936a" stroke-width="0.5"/>'
        )
    svg.append(
        f'<text x="{asm_x + 170}" y="{asm_y + 120}" text-anchor="middle" '
        f'font-size="8" font-family="Arial" fill="#000">RAFTER @ 24" O.C.</text>'
    )

    # Decking
    svg.append(
        f'<rect x="{asm_x + 60}" y="{asm_y + 80}" width="220" height="20" '
        f'fill="#c8b070" stroke="#000" stroke-width="1"/>'
    )
    svg.append(
        f'<text x="{asm_x + 170}" y="{asm_y + 93}" text-anchor="middle" '
        f'font-size="7" font-family="Arial" fill="#000">ROOF DECKING (OSB/PLYWOOD)</text>'
    )

    # Shingles
    for shi in range(6):
        sx = asm_x + 62 + shi * 35
        svg.append(
            f'<rect x="{sx}" y="{asm_y + 60}" width="38" height="22" fill="#888" stroke="#555" stroke-width="0.5"/>'
        )
    svg.append(
        f'<text x="{asm_x + 170}" y="{asm_y + 75}" text-anchor="middle" '
        f'font-size="7" font-family="Arial" fill="#fff">COMP. SHINGLES</text>'
    )

    # FlashFoot2 flashing (round, sitting on shingles)
    svg.append(
        f'<ellipse cx="{asm_x + 170}" cy="{asm_y + 60}" rx="40" ry="8" '
        f'fill="#2a2a2a" stroke="#000" stroke-width="1"/>'
    )

    # Base block
    svg.append(
        f'<rect x="{asm_x + 145}" y="{asm_y + 38}" width="50" height="22" '
        f'fill="#b0b8c0" stroke="#000" stroke-width="1.5"/>'
    )
    svg.append(
        f'<text x="{asm_x + 170}" y="{asm_y + 52}" text-anchor="middle" '
        f'font-size="7" font-weight="600" font-family="Arial" fill="#000">BASE</text>'
    )

    # Cap
    svg.append(
        f'<rect x="{asm_x + 152}" y="{asm_y + 22}" width="36" height="16" rx="3" '
        f'fill="#c8d0d8" stroke="#000" stroke-width="1.5"/>'
    )
    svg.append(
        f'<text x="{asm_x + 170}" y="{asm_y + 33}" text-anchor="middle" '
        f'font-size="7" font-weight="600" font-family="Arial" fill="#000">CAP</text>'
    )

    # Lag bolt shaft
    svg.append(
        f'<rect x="{asm_x + 167}" y="{asm_y + 38}" width="6" height="97" '
        f'fill="#888" stroke="#555" stroke-width="0.5"/>'
    )
    svg.append(
        f'<line x1="{asm_x + 170}" y1="{asm_y + 60}" x2="{asm_x + 170}" y2="{asm_y + 135}" '
        f'stroke="#999" stroke-width="4"/>'
    )

    # Rail sitting on cap
    svg.append(
        f'<rect x="{asm_x + 100}" y="{asm_y + 8}" width="140" height="16" '
        f'fill="#b8c4d0" stroke="#000" stroke-width="1.5"/>'
    )
    svg.append(
        f'<text x="{asm_x + 170}" y="{asm_y + 20}" text-anchor="middle" '
        f'font-size="7" font-weight="600" font-family="Arial" fill="#000">XR10 RAIL</text>'
    )

    # Module on rail
    svg.append(
        f'<rect x="{asm_x + 85}" y="{asm_y - 18}" width="170" height="28" '
        f'fill="#ffffff" stroke="#000" stroke-width="1.5"/>'
    )
    svg.append(
        f'<text x="{asm_x + 170}" y="{asm_y - 1}" text-anchor="middle" '
        f'font-size="8" font-weight="600" font-family="Arial" fill="#000000">PV MODULE</text>'
    )

    # Annotation leaders
    svg.append(
        f'<line x1="{asm_x + 215}" y1="{asm_y - 4}" x2="{asm_x + 265}" y2="{asm_y - 20}" '
        f'stroke="#444" stroke-width="0.7"/>'
    )
    svg.append(
        f'<text x="{asm_x + 268}" y="{asm_y - 16}" font-size="7" font-family="Arial" fill="#333">{renderer._panel_model_short} {renderer._panel_wattage}W</text>'
    )
    svg.append(
        f'<line x1="{asm_x + 215}" y1="{asm_y + 16}" x2="{asm_x + 265}" y2="{asm_y + 16}" '
        f'stroke="#444" stroke-width="0.7"/>'
    )
    svg.append(
        f'<text x="{asm_x + 268}" y="{asm_y + 20}" font-size="7" font-family="Arial" fill="#333">XR10 Rail</text>'
    )
    svg.append(
        f'<line x1="{asm_x + 195}" y1="{asm_y + 38}" x2="{asm_x + 265}" y2="{asm_y + 42}" '
        f'stroke="#444" stroke-width="0.7"/>'
    )
    svg.append(
        f'<text x="{asm_x + 268}" y="{asm_y + 45}" font-size="7" font-family="Arial" fill="#333">FlashFoot2 Cap</text>'
    )
    svg.append(
        f'<line x1="{asm_x + 195}" y1="{asm_y + 58}" x2="{asm_x + 265}" y2="{asm_y + 65}" '
        f'stroke="#444" stroke-width="0.7"/>'
    )
    svg.append(
        f'<text x="{asm_x + 268}" y="{asm_y + 69}" font-size="7" font-family="Arial" fill="#333">FlashFoot2 Base</text>'
    )
    svg.append(
        f'<line x1="{asm_x + 210}" y1="{asm_y + 66}" x2="{asm_x + 265}" y2="{asm_y + 82}" '
        f'stroke="#444" stroke-width="0.7"/>'
    )
    svg.append(
        f'<text x="{asm_x + 268}" y="{asm_y + 86}" font-size="7" font-family="Arial" fill="#333">EPDM Flash</text>'
    )
    svg.append(
        f'<line x1="{asm_x + 195}" y1="{asm_y + 90}" x2="{asm_x + 265}" y2="{asm_y + 100}" '
        f'stroke="#444" stroke-width="0.7"/>'
    )
    svg.append(
        f'<text x="{asm_x + 268}" y="{asm_y + 104}" font-size="7" font-family="Arial" fill="#333">Comp. Shingles</text>'
    )

    # ── Right column: Specifications ──────────────────────────────────
    rx3 = 640
    spec_y = 72
    svg.append(
        f'<text x="{rx3}" y="{spec_y}" font-size="10" font-weight="700" '
        f'font-family="Arial" fill="#000">PRODUCT SPECIFICATIONS</text>'
    )
    spec_rows = [
        ("Product Name", "FlashFoot2"),
        ("Manufacturer", "IronRidge Inc."),
        ("Part Number (Cap)", "FF2-CAP"),
        ("Part Number (Base)", "FF2-BASE"),
        ("Cap Material", "6063-T5 Aluminum, clear anodized"),
        ("Base Material", "6063-T5 Aluminum, clear anodized"),
        ("Flashing", '12" round aluminum, EPDM rubber gasket'),
        ("Lag Bolt Spec.", '5/16" × 2.5" min. — 304 SS or hot-dip galv.'),
        ("Lag Bolt Torque", "15–25 ft-lbs  (must use torque wrench)"),
        ("Min. Embedment Depth", '2.5" into rafter (63.5mm)'),
        ("Working Load (per foot)", "1,000 lbs (4,448 N)"),
        ("Assembly Weight", "0.65 lbs (0.29 kg) per foot"),
        ("Compatible Roof Types", "Comp. shingles, concrete/clay tile, metal"),
    ]
    for ri, (label, val) in enumerate(spec_rows):
        ry4 = spec_y + 14 + ri * row_h
        bg = "#f5f5f5" if ri % 2 == 0 else "#ffffff"
        svg.append(
            f'<rect x="{rx3}" y="{ry4}" width="610" height="{row_h}" fill="{bg}" stroke="#ccc" stroke-width="0.5"/>'
        )
        svg.append(
            f'<text x="{rx3 + 8}" y="{ry4 + 16}" font-size="9" font-family="Arial" fill="#000">{label}</text>'
        )
        svg.append(
            f'<text x="{rx3 + 230}" y="{ry4 + 16}" font-size="9" font-weight="600" '
            f'font-family="Arial" fill="#000000">{val}</text>'
        )

    # Installation Requirements
    ir_y = spec_y + 14 + len(spec_rows) * row_h + 22
    svg.append(
        f'<text x="{rx3}" y="{ir_y}" font-size="10" font-weight="700" '
        f'font-family="Arial" fill="#000">INSTALLATION REQUIREMENTS</text>'
    )
    ir_notes = [
        "1.  Locate and mark all rafters. Attachment points must hit rafter centers.",
        '2.  Pre-drill pilot hole: 17/64" diameter through all layers into rafter.',
        "3.  Apply sealant to pilot hole before inserting lag bolt.",
        "4.  Thread lag bolt through FlashFoot2 base, flashing, and pre-drilled hole.",
        "5.  Torque to 15–25 ft-lbs using calibrated torque wrench. DO NOT over-torque.",
        "6.  Apply roofing sealant (e.g., NP1) around base perimeter.",
        "7.  Slide XR10 rail T-bolt into channel; position base on T-bolt.",
        "8.  Verify level and alignment of rail before final tightening.",
        '9.  Maintain minimum 18" from ridge and eave per local fire code.',
    ]
    for ni, note in enumerate(ir_notes):
        ny2 = ir_y + 16 + ni * 20
        svg.append(f'<text x="{rx3}" y="{ny2}" font-size="9" font-family="Arial" fill="#000">{note}</text>')

    # Code compliance box
    cc_y = ir_y + 16 + len(ir_notes) * 20 + 20
    svg.append(
        f'<rect x="{rx3}" y="{cc_y}" width="610" height="80" '
        f'fill="#ffffff" stroke="#000000" stroke-width="1.5" rx="3"/>'
    )
    svg.append(
        f'<text x="{rx3 + 8}" y="{cc_y + 18}" font-size="10" font-weight="700" '
        f'font-family="Arial" fill="#000000">CODE COMPLIANCE &amp; CERTIFICATIONS</text>'
    )
    certs2 = [
        "ICC-ES ESR-3164  |  UL 2703 Listed Attachment System",
        f"IBC 2021 / {renderer._building_code} 2020  |  ASCE 7-22 Wind/Snow Loading",
        f"{'NEC Article 690' if renderer._code_prefix == 'NEC' else 'CEC Section 64 (CSA C22.1-2021)'}  |  {renderer._building_code} Compliant",
    ]
    for ci3, cert in enumerate(certs2):
        svg.append(
            f'<text x="{rx3 + 12}" y="{cc_y + 36 + ci3 * 18}" font-size="9" '
            f'font-family="Arial" fill="#333">{cert}</text>'
        )

    # ── Title block ───────────────────────────────────────────────────
    svg.append(
        renderer._svg_title_block(
            VW,
            VH,
            "R-005",
            "EQUIPMENT SPEC (ATTACHMENT)",
            "IronRidge FlashFoot2 Roof Attachment",
            "15 of 15",
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
