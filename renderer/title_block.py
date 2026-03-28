"""
SVG title block generator for planset sheets.
===============================================

Extracted from ``HtmlRenderer._svg_title_block``.

Generates a reusable 520 x 130 px SVG title block matching the
Cubillas / All Valley Solar standard, positioned
in the bottom-right corner of the sheet.

Layout (520 x 130 px):
  Row 1 (28px):  Owner name (bold) + address
  Row 2 (17px):  AHJ
  Row 3 (38px):  Contractor info (left) | Contractor signature (right)
  Row 4 (16px):  Sheet title (centered)
  Row 5 (31px):  Date / Drawn By | REV #1 | REV #2 | REV #3
  Right col:     Sheet ID (large bold) spanning full height
"""

from renderer.svg_helpers import make_ahj_label


def svg_title_block(
    vw: int,
    vh: int,
    sheet_id: str,
    sheet_title: str,
    subtitle: str,
    page_of: str,
    address: str,
    today: str,
    *,
    company: str = "Solar Contractor",
    designer: str = "AI Solar Design Engine",
    company_license: str = "",
    company_email: str = "",
    transparent: bool = False,
) -> str:
    """Generate a reusable SVG title block.

    Args:
        vw, vh:           SVG viewport width and height.
        sheet_id:         Sheet identifier (e.g. "PV-3").
        sheet_title:      Sheet title (e.g. "Site Plan").
        subtitle:         Secondary description line.
        page_of:          Page numbering string (e.g. "3 of 13").
        address:          Full project address.
        today:            Date string for the DATE field.
        company:          Contractor / company name.
        designer:         Drawn-by name (truncated to 8 chars in display).
        company_license:  License line shown under company name.
        company_email:    Email line shown under license.
        transparent:      If True, uses semi-transparent dark background
                          (for satellite overlay pages).

    Returns:
        An SVG ``<g>`` element string containing the complete title block.
    """
    tb_w, tb_h = 520, 130
    tb_x = vw - tb_w - 15
    tb_y = vh - tb_h - 15

    # ── Color scheme ────────────────────────────────────────────────────
    fill = "rgba(0,0,0,0.75)" if transparent else "#ffffff"
    text_fill = "#ffffff" if transparent else "#000000"
    sub_fill = "rgba(255,255,255,0.65)" if transparent else "#444444"
    border = "rgba(255,255,255,0.35)" if transparent else "#000000"
    div_c = "rgba(255,255,255,0.25)" if transparent else "#aaaaaa"

    # Derive owner name from address (street address before first comma)
    owner_name = address.split(",")[0].strip().upper() + " RESIDENCE"

    # ── Key x positions ─────────────────────────────────────────────────
    DIV_X = tb_x + 350  # left/right column divider
    SIG_DIV = tb_x + 192  # divider within row 3 (contractor vs signature)

    # ── Key row y-positions (from tb_y) ─────────────────────────────────
    y1 = tb_y + 28  # end of row 1 (owner/addr)
    y2 = tb_y + 45  # end of row 2 (AHJ)
    y3 = tb_y + 83  # end of row 3 (contractor/sig)
    y4 = tb_y + 99  # end of row 4 (sheet title)
    # row 5: y4 -> tb_y+130

    parts: list[str] = []

    # ── Outer border ────────────────────────────────────────────────────
    parts.append(
        f'<rect x="{tb_x}" y="{tb_y}" width="{tb_w}" height="{tb_h}" '
        f'fill="{fill}" stroke="{border}" stroke-width="1.5"/>'
    )

    # ── Vertical divider (left col / right col) ────────────────────────
    parts.append(
        f'<line x1="{DIV_X}" y1="{tb_y}" x2="{DIV_X}" y2="{tb_y + tb_h}" stroke="{border}" stroke-width="0.8"/>'
    )

    # ── Horizontal row dividers (left column only) ─────────────────────
    for yd in [y1, y2, y3, y4]:
        parts.append(f'<line x1="{tb_x}" y1="{yd}" x2="{DIV_X}" y2="{yd}" stroke="{div_c}" stroke-width="0.5"/>')

    lx = tb_x + 6  # left text margin

    # ── Row 1: Owner name + address ────────────────────────────────────
    parts.append(
        f'<text x="{lx}" y="{tb_y + 14}" font-size="11" font-weight="700" '
        f'font-family="Arial" fill="{text_fill}">{owner_name}</text>'
    )
    parts.append(
        f'<text x="{lx}" y="{tb_y + 26}" font-size="7.5" font-family="Arial" fill="{sub_fill}">{address}</text>'
    )

    # ── Row 2: AHJ ─────────────────────────────────────────────────────
    parts.append(
        f'<text x="{lx}" y="{y1 + 12}" font-size="8.5" '
        f'font-family="Arial" fill="{text_fill}">AHJ: {make_ahj_label(address)}</text>'
    )

    # ── Row 3: Contractor info (left) + Signature (right) ──────────────
    # Inner vertical divider separating contractor and signature sub-columns
    parts.append(f'<line x1="{SIG_DIV}" y1="{y2}" x2="{SIG_DIV}" y2="{y3}" stroke="{div_c}" stroke-width="0.5"/>')
    # Contractor info
    parts.append(
        f'<text x="{lx}" y="{y2 + 12}" font-size="8.5" font-weight="700" '
        f'font-family="Arial" fill="{text_fill}">{company}</text>'
    )
    parts.append(
        f'<text x="{lx}" y="{y2 + 23}" font-size="7" font-family="Arial" fill="{sub_fill}">{company_license}</text>'
    )
    parts.append(
        f'<text x="{lx}" y="{y2 + 33}" font-size="7" font-family="Arial" fill="{sub_fill}">{company_email}</text>'
    )
    # Contractor signature area
    parts.append(
        f'<text x="{SIG_DIV + 5}" y="{y2 + 11}" font-size="6.5" '
        f'font-family="Arial" fill="{sub_fill}">CONTRACTOR SIGNATURE</text>'
    )
    parts.append(
        f'<line x1="{SIG_DIV + 5}" y1="{y3 - 9}" x2="{DIV_X - 5}" y2="{y3 - 9}" stroke="{div_c}" stroke-width="0.8"/>'
    )

    # ── Row 4: Sheet title ─────────────────────────────────────────────
    cx_left = tb_x + 175  # center of left column
    parts.append(
        f'<text x="{cx_left}" y="{y3 + 11}" text-anchor="middle" font-size="9" '
        f'font-weight="700" font-family="Arial" fill="{text_fill}">{sheet_title.upper()}</text>'
    )

    # ── Row 5: Date / Drawn By + REV boxes ─────────────────────────────
    parts.append(
        f'<text x="{lx}" y="{y4 + 11}" font-size="7.5" font-family="Arial" fill="{text_fill}">DATE: {today}</text>'
    )
    drawn_label = (designer[:8] if len(designer) > 8 else designer).upper()
    parts.append(
        f'<text x="{lx}" y="{y4 + 22}" font-size="7.5" '
        f'font-family="Arial" fill="{text_fill}">DRAWN BY: {drawn_label}</text>'
    )
    # Three revision boxes
    rev_start = tb_x + 105
    rev_bw = 81  # box width for each REV column
    rev_bh = tb_h - (y4 - tb_y) - 2  # ~29px
    for i, rev_lbl in enumerate(["REV #1:", "REV #2:", "REV #3:"]):
        rx = rev_start + i * rev_bw
        parts.append(
            f'<rect x="{rx}" y="{y4 + 1}" width="{rev_bw - 1}" height="{rev_bh}" '
            f'fill="none" stroke="{div_c}" stroke-width="0.5"/>'
        )
        parts.append(
            f'<text x="{rx + 3}" y="{y4 + 10}" font-size="6.5" font-family="Arial" fill="{sub_fill}">{rev_lbl}</text>'
        )

    # ── Right column: Sheet ID (large) + labels + page # ──────────────
    cx_right = (DIV_X + tb_x + tb_w) // 2  # center of right column

    parts.append(
        f'<text x="{cx_right}" y="{tb_y + 62}" text-anchor="middle" font-size="28" '
        f'font-weight="700" font-family="Arial" fill="{text_fill}">{sheet_id}</text>'
    )
    parts.append(
        f'<text x="{cx_right}" y="{tb_y + 84}" text-anchor="middle" font-size="8.5" '
        f'font-family="Arial" fill="{sub_fill}">{sheet_title.upper()}</text>'
    )
    if subtitle:
        parts.append(
            f'<text x="{cx_right}" y="{tb_y + 97}" text-anchor="middle" font-size="6.5" '
            f'font-family="Arial" fill="{sub_fill}">{subtitle}</text>'
        )
    parts.append(
        f'<text x="{cx_right}" y="{tb_y + 118}" text-anchor="middle" font-size="7.5" '
        f'font-family="Arial" fill="{sub_fill}">Sheet {page_of}</text>'
    )

    return f"<g>{''.join(parts)}</g>"
