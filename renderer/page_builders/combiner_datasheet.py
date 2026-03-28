"""Page builder: Combiner Box Datasheet (R-003)
=================================================
Equipment specification sheet for the combiner box / IQ Combiner.
"""


def build_combiner_datasheet_page(renderer, address: str, today: str) -> str:
    """R-003: Equipment Spec — Combiner box datasheet page.

    Args:
        renderer: HtmlRenderer instance (provides project, equipment properties)
        address: Project address string
        today: Date string for title block

    Returns:
        HTML string containing the page div with SVG content.
    """
    VW, VH = 1280, 960
    svg = []

    # Pull specs from ProjectSpec or fall back to defaults
    if renderer._project and hasattr(renderer._project, 'combiner') and renderer._project.combiner:
        cb = renderer._project.combiner
        mfr = getattr(cb, 'manufacturer', 'Enphase Energy')
        model = getattr(cb, 'model', 'IQ Combiner 5C')
        model_full = getattr(cb, 'model_number', 'X-IQ-AM1-240-5C')
    else:
        mfr = "Enphase Energy"
        model = "IQ Combiner 5C"
        model_full = "X-IQ-AM1-240-5C"

    # Background + border
    svg.append('<rect width="1280" height="960" fill="#ffffff"/>')
    svg.append('<rect x="20" y="20" width="1240" height="820" fill="none" stroke="#000" stroke-width="2"/>')

    # Header band
    svg.append('<rect x="20" y="20" width="1240" height="42" fill="#f5f5f5" stroke="#000" stroke-width="1"/>')
    svg.append(
        f'<text x="640" y="38" text-anchor="middle" font-size="14" font-weight="700" '
        f'font-family="Arial" fill="#000000">EQUIPMENT SPECIFICATION — COMBINER BOX</text>'
    )
    svg.append(
        f'<text x="640" y="54" text-anchor="middle" font-size="11" font-family="Arial" '
        f'fill="#444444">{mfr} {model} ({model_full})</text>'
    )

    # Product info section
    info_x, info_y = 50, 90
    svg.append(
        f'<text x="{info_x}" y="{info_y}" font-size="12" font-weight="700" '
        f'font-family="Arial" fill="#000">PRODUCT INFORMATION</text>'
    )

    specs = [
        ("Manufacturer", mfr),
        ("Model", model),
        ("Part Number", model_full),
        ("Type", "AC Combiner with IQ Gateway"),
        ("Max Branch Circuits", "4 (expandable)"),
        ("Branch Breaker Rating", "20A / 2-Pole"),
        ("Max System Voltage", "240 VAC"),
        ("Enclosure Rating", "NEMA 3R"),
        ("Integrated Gateway", "Yes — IQ Gateway (production + consumption CTs)"),
    ]

    # Draw specs table
    tbl_y = info_y + 20
    col_w = [280, 380]
    for i, (label, value) in enumerate(specs):
        ry = tbl_y + i * 26
        bg = "#f0f4ff" if i % 2 == 0 else "#ffffff"
        svg.append(
            f'<rect x="{info_x}" y="{ry}" width="{sum(col_w)}" height="26" '
            f'fill="{bg}" stroke="#ddd" stroke-width="0.5"/>'
        )
        svg.append(
            f'<text x="{info_x + 10}" y="{ry + 18}" font-size="10" font-weight="600" '
            f'font-family="Arial" fill="#333">{label}</text>'
        )
        svg.append(
            f'<text x="{info_x + col_w[0] + 10}" y="{ry + 18}" font-size="10" '
            f'font-family="Arial" fill="#000">{value}</text>'
        )

    # Certifications
    cert_y = tbl_y + len(specs) * 26 + 40
    svg.append(
        f'<text x="{info_x}" y="{cert_y}" font-size="12" font-weight="700" '
        f'font-family="Arial" fill="#000">CERTIFICATIONS &amp; LISTINGS</text>'
    )
    certs = [
        "UL 1741 — Inverter/Combiner Safety",
        "UL 50 / UL 50E — Enclosures",
        "IEEE 1547 — Interconnection Standard",
        "FCC Part 15 Class B — EMC Compliance",
        "CEC Listed — California Energy Commission",
    ]
    for i, cert in enumerate(certs):
        y = cert_y + 20 + i * 18
        svg.append(
            f'<text x="{info_x + 10}" y="{y}" font-size="9" font-family="Arial" '
            f'fill="#333">• {cert}</text>'
        )

    # Note about real datasheet
    note_y = cert_y + 20 + len(certs) * 18 + 30
    svg.append(
        f'<text x="{info_x}" y="{note_y}" font-size="9" font-style="italic" '
        f'font-family="Arial" fill="#666">Note: For complete specifications, '
        f'refer to the manufacturer datasheet. This page will be replaced with</text>'
    )
    svg.append(
        f'<text x="{info_x}" y="{note_y + 14}" font-size="9" font-style="italic" '
        f'font-family="Arial" fill="#666">the official manufacturer PDF in the final permit submission.</text>'
    )

    # Title block
    svg.append(
        renderer._svg_title_block(
            VW, VH, "R-003", "EQUIPMENT SPEC (COMBINER)",
            f"{mfr} {model}", "13 of 15", address, today
        )
    )

    content = "\n".join(svg)
    return (
        f'<div class="page">'
        f'<svg width="100%" height="100%" viewBox="0 0 {VW} {VH}" '
        f'xmlns="http://www.w3.org/2000/svg" style="background:#fff;">'
        f"{content}</svg></div>"
    )
