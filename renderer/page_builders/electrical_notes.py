"""Page builder: Electrical Notes (G-01)
========================================
General electrical notes, code references, and design criteria
for the solar PV installation.
"""

from datetime import date


def build_electrical_notes_page(renderer, address: str, today: str) -> str:
    """G-01: Electrical Notes — general notes, code references, design criteria.

    Args:
        renderer: HtmlRenderer instance (provides project, equipment properties)
        address: Project address string
        today: Date string for title block

    Returns:
        HTML string containing the page div with SVG content.
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
        'font-family="Arial" fill="#000000">ELECTRICAL NOTES</text>'
    )
    svg.append(
        '<text x="640" y="54" text-anchor="middle" font-size="11" font-family="Arial" '
        'fill="#444444">General Notes &amp; Code References</text>'
    )

    # Jurisdiction-aware code references
    _cp = getattr(renderer, '_code_prefix', 'NEC')
    _is_nec = _cp == "NEC"

    # General notes
    notes_x, notes_y = 40, 90
    notes = [
        "GENERAL ELECTRICAL NOTES",
        "",
        "1.  All work shall comply with the latest edition of the National Electrical Code (NEC/NFPA 70),",
        "    local amendments, and the Authority Having Jurisdiction (AHJ) requirements.",
        "",
        "2.  All conductors shall be copper, rated 75°C minimum (THWN-2 or equivalent) unless noted.",
        "",
        "3.  All conduit shall be Electrical Metallic Tubing (EMT) unless otherwise noted.",
        "",
        "4.  Equipment Grounding Conductor (EGC) shall be installed per NEC 250.122 and sized per OCPD rating.",
        "",
        "5.  All PV module frames, racking, and metallic enclosures shall be bonded per NEC 690.43.",
        "",
        "6.  Grounding electrode system shall comply with NEC 690.47 and 250.50.",
        "",
        "7.  All electrical connections and terminations shall be torqued to manufacturer specifications.",
        "",
        "8.  AC disconnect shall be lockable, rated for system voltage and current, and installed per NEC 690.15.",
        "",
        "9.  Rapid shutdown system shall comply with NEC 690.12 (2017 or later).",
        "",
        "10. All labels and placards per NEC 690.56 shall be installed before system energization.",
        "",
        "11. PV system output circuit conductors shall be sized at 125% of continuous current per NEC 690.8.",
        "",
        "12. Overcurrent protection devices (OCPD) shall be rated per NEC 240.4 and 690.9.",
        "",
        "13. Interconnection shall comply with NEC 705.12 (120% rule for supply-side connection).",
        "",
        "14. All outdoor equipment shall be rated NEMA 3R minimum.",
        "",
        "15. Contractor shall verify all existing electrical service conditions before installation.",
    ]

    if not _is_nec:
        # Adjust for Canadian Electrical Code (placeholder)
        notes[0] = "GENERAL ELECTRICAL NOTES (CEC)"
        notes[3] = "    local amendments, and the Authority Having Jurisdiction (AHJ) requirements."

    for i, note in enumerate(notes):
        y = notes_y + i * 16
        weight = "700" if note and not note.startswith(" ") and not note[0:1].isdigit() else "400"
        size = "11" if weight == "700" else "9"
        svg.append(
            f'<text x="{notes_x}" y="{y}" font-size="{size}" font-weight="{weight}" '
            f'font-family="Arial" fill="#000">{note}</text>'
        )

    # Governing codes section (right column)
    codes_x = 680
    codes_y = 90
    svg.append(
        f'<text x="{codes_x}" y="{codes_y}" font-size="11" font-weight="700" '
        f'font-family="Arial" fill="#000">GOVERNING CODES &amp; STANDARDS</text>'
    )

    codes = [
        "2022 National Electrical Code (NEC / NFPA 70)",
        "2022 California Electrical Code (Title 24, Part 3)",
        "2022 California Building Code (Title 24, Part 2)",
        "2022 California Fire Code (Title 24, Part 9)",
        "2022 California Energy Code (Title 24, Part 6)",
        "2022 California Residential Code (Title 24, Part 2.5)",
        "2022 California Plumbing Code (Title 24, Part 5)",
        "2022 California Mechanical Code (Title 24, Part 4)",
        "UL 1741 — Inverters, Converters, Controllers",
        "UL 2703 — Mounting Systems, Racking",
        "UL 61730 — PV Module Safety",
        "IEEE 1547 — Interconnection Standard",
        "IEC 61215 — PV Module Design Qualification",
    ]
    for i, code in enumerate(codes):
        y = codes_y + 24 + i * 18
        svg.append(
            f'<text x="{codes_x}" y="{y}" font-size="9" font-family="Arial" fill="#333">'
            f'• {code}</text>'
        )

    # Design criteria section
    dc_y = codes_y + 24 + len(codes) * 18 + 30
    svg.append(
        f'<text x="{codes_x}" y="{dc_y}" font-size="11" font-weight="700" '
        f'font-family="Arial" fill="#000">DESIGN CRITERIA</text>'
    )

    criteria = [
        "Ambient Temperature (High, 2%): 35°C",
        "Ambient Temperature (Record Low): 1°C",
        "Roof Temperature Adder: +22°C (conduit on roof)",
        "Wind Speed (Design): 110 mph (ASCE 7-16)",
        "Snow Load: 0 psf (Southern California)",
        "Seismic Design Category: D",
    ]
    for i, item in enumerate(criteria):
        y = dc_y + 24 + i * 18
        svg.append(
            f'<text x="{codes_x}" y="{y}" font-size="9" font-family="Arial" fill="#333">'
            f'• {item}</text>'
        )

    # Title block
    svg.append(
        renderer._svg_title_block(
            VW, VH, "G-01", "ELECTRICAL NOTES",
            "General Notes & Code References", "2 of 15", address, today
        )
    )

    content = "\n".join(svg)
    return (
        f'<div class="page">'
        f'<svg width="100%" height="100%" viewBox="0 0 {VW} {VH}" '
        f'xmlns="http://www.w3.org/2000/svg" style="background:#fff;">'
        f"{content}</svg></div>"
    )
