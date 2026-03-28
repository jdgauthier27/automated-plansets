"""Page builder: Inverter Datasheet (R-002)
============================================
Equipment specification sheet for the inverter / microinverter.
"""


def build_inverter_datasheet_page(renderer, address: str, today: str) -> str:
    """R-002: Equipment Spec — Inverter datasheet page.

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
    if renderer._project and renderer._project.inverter:
        inv = renderer._project.inverter
        mfr = inv.manufacturer
        model = inv.model
        is_micro = inv.is_micro
        ac_voltage = inv.ac_voltage_v
        max_ac_power = inv.max_ac_power_va
        max_ac_amps = inv.max_ac_amps
        efficiency = getattr(inv, 'peak_efficiency_pct', 97.5)
        weight_kg = getattr(inv, 'weight_kg', 1.08)
    else:
        mfr = "Enphase Energy"
        model = "IQ8PLUS-72-2-US"
        is_micro = True
        ac_voltage = 240
        max_ac_power = 290
        max_ac_amps = 1.21
        efficiency = 97.5
        weight_kg = 1.08

    inv_type = "Microinverter" if is_micro else "String Inverter"

    # Background + border
    svg.append('<rect width="1280" height="960" fill="#ffffff"/>')
    svg.append('<rect x="20" y="20" width="1240" height="820" fill="none" stroke="#000" stroke-width="2"/>')

    # Header band
    svg.append('<rect x="20" y="20" width="1240" height="42" fill="#f5f5f5" stroke="#000" stroke-width="1"/>')
    svg.append(
        f'<text x="640" y="38" text-anchor="middle" font-size="14" font-weight="700" '
        f'font-family="Arial" fill="#000000">EQUIPMENT SPECIFICATION — INVERTER</text>'
    )
    svg.append(
        f'<text x="640" y="54" text-anchor="middle" font-size="11" font-family="Arial" '
        f'fill="#444444">{mfr} {model}</text>'
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
        ("Type", inv_type),
        ("Nominal AC Voltage", f"{ac_voltage} VAC"),
        ("Max Continuous Output Power", f"{max_ac_power} VA ({max_ac_power} W)"),
        ("Max Continuous Output Current", f"{max_ac_amps} A"),
        ("Peak Efficiency", f"{efficiency}%"),
        ("Weight", f"{weight_kg} kg"),
    ]

    # Draw specs table
    tbl_y = info_y + 20
    col_w = [280, 300]
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

    # Certifications placeholder
    cert_y = tbl_y + len(specs) * 26 + 40
    svg.append(
        f'<text x="{info_x}" y="{cert_y}" font-size="12" font-weight="700" '
        f'font-family="Arial" fill="#000">CERTIFICATIONS &amp; LISTINGS</text>'
    )
    certs = [
        "UL 1741 / UL 1741 SA — Inverter Safety & Grid Support",
        "IEEE 1547 / IEEE 1547.1 — Interconnection Standard",
        "FCC Part 15 Class B — EMC Compliance",
        "CEC Listed — California Energy Commission",
        "CSA C22.2 No. 107.1 — Canadian Standards",
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
            VW, VH, "R-002", "EQUIPMENT SPEC (INVERTER)",
            f"{mfr} {model}", "12 of 15", address, today
        )
    )

    content = "\n".join(svg)
    return (
        f'<div class="page">'
        f'<svg width="100%" height="100%" viewBox="0 0 {VW} {VH}" '
        f'xmlns="http://www.w3.org/2000/svg" style="background:#fff;">'
        f"{content}</svg></div>"
    )
