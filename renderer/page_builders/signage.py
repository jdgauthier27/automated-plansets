"""Page builder: Signage / Electrical Labels (PV-6 / E-603)
============================================================
Extracted from HtmlRenderer._build_signage_page.
"""


def build_signage_page(renderer, address: str, today: str) -> str:
    """PV-6: Required warning labels and placards — 14 items, ANSI Z535."""
    VW, VH = 1280, 960
    svg_parts = []

    # Background & border
    svg_parts.append(f'<rect width="{VW}" height="{VH}" fill="#ffffff"/>')
    svg_parts.append(
        f'<rect x="20" y="20" width="{VW - 40}" height="{VH - 40}" fill="none" stroke="#000" stroke-width="1.5"/>'
    )

    # Page header
    svg_parts.append(
        '<text x="40" y="52" font-size="15" font-weight="700" '
        'font-family="Arial" fill="#000">E-603: SIGNAGE</text>'
    )
    _cp = renderer._code_prefix
    _is_nec = _cp == "NEC"
    _code_ref = f"{'NEC Article 690' if _is_nec else 'CEC Section 64 (CSA C22.1-21)'}"
    svg_parts.append(
        f'<text x="40" y="68" font-size="9" font-family="Arial" fill="#555">'
        f"Required warning labels per {_code_ref}, ANSI Z535.4 — "
        f"install at indicated locations prior to utility energization</text>"
    )
    svg_parts.append('<line x1="30" y1="76" x2="1250" y2="76" stroke="#ccc" stroke-width="0.7"/>')

    # ── ANSI Z535 colour constants ─────────────────────────────────
    ANSI_RED = "#C62828"  # DANGER
    ANSI_ORANGE = "#E65100"  # WARNING
    ANSI_YELLOW = "#F9A825"  # CAUTION
    ANSI_BLUE = "#1565C0"  # INFO / directive
    WHITE = "#FFFFFF"
    BLACK = "#000000"

    # ── 14 label definitions ───────────────────────────────────────
    _un = renderer._utility_name
    _safety_listing = f"{'UL 1741 LISTED' if _is_nec else 'CSA C22.2 No. 107.1 LISTED'}"

    def _lr(nec_ref, cec_ref):
        """Return the appropriate label code ref for the jurisdiction."""
        return f"NEC {nec_ref}" if _is_nec else f"CEC Rule {cec_ref}"

    labels = [
        # DANGER x 2
        (
            "L-01",
            "DANGER",
            ANSI_RED,
            WHITE,
            "ELECTRIC SHOCK HAZARD",
            [
                "TERMINALS ON BOTH LINE AND LOAD",
                "SIDES MAY BE ENERGIZED IN THE",
                "OPEN POSITION \u2014 DO NOT TOUCH.",
            ],
            _lr("690.17", "64-218"),
            "On or adjacent to each DC disconnect",
        ),
        (
            "L-02",
            "DANGER",
            ANSI_RED,
            WHITE,
            "HIGH DC VOLTAGE \u2014 DO NOT TOUCH",
            ["SOLAR PANELS PRODUCE LETHAL", "VOLTAGE WHEN EXPOSED TO LIGHT.", "RISK OF FATAL ELECTRICAL SHOCK."],
            _lr("690.5", "64-218"),
            "Roof surface near array / array combiner box",
        ),
        # WARNING x 5
        (
            "L-03",
            "WARNING",
            ANSI_ORANGE,
            WHITE,
            "DUAL POWER SOURCES",
            ["THIS EQUIPMENT IS FED FROM TWO", "SEPARATE SOURCES \u2014 DISCONNECT", "BOTH BEFORE SERVICING."],
            _lr("705.12", "64-218"),
            "Main electrical panel exterior",
        ),
        (
            "L-04",
            "WARNING",
            ANSI_ORANGE,
            WHITE,
            "BACKFED CIRCUIT \u2014 DO NOT RELOCATE",
            ["PHOTOVOLTAIC SYSTEM BACKFED", "BREAKER MUST REMAIN AT THIS", "LOCATION IN THE LOAD CENTER."],
            _lr("705.12(B)(4)", "64-218"),
            "Adjacent to PV backfed breaker in load center",
        ),
        (
            "L-05",
            "WARNING",
            ANSI_ORANGE,
            WHITE,
            "RAPID SHUTDOWN EQUIPPED",
            ["PHOTOVOLTAIC SYSTEM EQUIPPED", "WITH RAPID SHUTDOWN \u2014 PRESS", "SWITCH TO DE-ENERGIZE ARRAY."],
            _lr("690.12", "64-218"),
            "Service entrance / main panel exterior",
        ),
        (
            "L-06",
            "WARNING",
            ANSI_ORANGE,
            WHITE,
            "INVERTER OUTPUT \u2014 SHOCK RISK",
            [
                "INVERTER OUTPUT REMAINS ENERGIZED",
                "AFTER AC DISCONNECT IS OPENED.",
                "WAIT 5 MINUTES BEFORE SERVICING.",
            ],
            _lr("690.13", "64-218"),
            "On inverter housing / enclosure",
        ),
        (
            "L-07",
            "WARNING",
            ANSI_ORANGE,
            WHITE,
            "RAPID SHUTDOWN SWITCH",
            ["SOLAR PHOTOVOLTAIC SYSTEM \u2014", "PRESS TO DE-ENERGIZE ROOF", "CONDUCTORS WITHIN 30 SECONDS."],
            _lr("690.12(B)(1)", "64-218"),
            "At rapid shutdown initiator / RSM switch",
        ),
        # CAUTION x 4
        (
            "L-08",
            "CAUTION",
            ANSI_YELLOW,
            BLACK,
            "PHOTOVOLTAIC DC CIRCUITS",
            [
                "SOLAR CIRCUIT \u2014 DO NOT INTERRUPT",
                "UNDER LOAD. MAXIMUM 600 V DC.",
                "LABEL EVERY 3 m (10 ft) OF CONDUIT.",
            ],
            _lr("690.31(G)", "64-214"),
            "All DC conduit runs \u2014 every 3 m and at junctions",
        ),
        (
            "L-09",
            "CAUTION",
            ANSI_YELLOW,
            BLACK,
            "PHOTOVOLTAIC AC CIRCUITS",
            [
                "SOLAR CIRCUIT \u2014 MAXIMUM 240 V AC.",
                "ENERGIZED FROM INVERTER AND",
                "UTILITY GRID SIMULTANEOUSLY.",
            ],
            _lr("690.31", "64-214"),
            "All AC conduit between inverter and load center",
        ),
        (
            "L-10",
            "CAUTION",
            ANSI_YELLOW,
            BLACK,
            "DISCONNECT BEFORE SERVICING",
            ["OPEN BOTH DC DISCONNECT AND", "AC DISCONNECT BEFORE SERVICING", "ANY PART OF THIS SYSTEM."],
            _lr("690.13", "84-030"),
            "On each piece of electrical equipment",
        ),
        (
            "L-11",
            "CAUTION",
            ANSI_YELLOW,
            BLACK,
            "JUNCTION BOX \u2014 PV CIRCUIT INSIDE",
            [
                "ALL JUNCTION AND PULL BOXES ON",
                "THIS CIRCUIT SHALL BE LABELED AT",
                "EVERY POINT OF ACCESS PER CODE.",
            ],
            _lr("690.31(G)(3)", "64-214"),
            "At all PV junction boxes and pull boxes",
        ),
        # INFO x 3
        (
            "L-12",
            "INFO",
            ANSI_BLUE,
            WHITE,
            "PHOTOVOLTAIC SYSTEM DISCONNECT",
            ["DC DISCONNECTING MEANS.", "MAXIMUM SYSTEM VOLTAGE: 600 V DC.", f"{_safety_listing}."],
            _lr("690.17", "84-030"),
            "On DC disconnect switch or enclosure cover",
        ),
        (
            "L-13",
            "INFO",
            ANSI_BLUE,
            WHITE,
            "POINT OF INTERCONNECTION",
            ["PHOTOVOLTAIC SYSTEM INTERACTIVE", "WITH UTILITY GRID.", f"{_un} NET METERING."],
            _lr("705.10", "84-030"),
            "On load center at grid interconnection point",
        ),
        (
            "L-14",
            "INFO",
            ANSI_BLUE,
            WHITE,
            "BI-DIRECTIONAL UTILITY METER",
            [f"NET METERING \u2014 {_un}.", "RECORDS ENERGY EXPORTED TO AND", "IMPORTED FROM THE UTILITY GRID."],
            f"{_un} {'NEM 3.0' if _is_nec else 'Distribution Tariff D'}",
            "Adjacent to utility revenue meter",
        ),
    ]

    # ── Grid layout (3 cols × 5 rows; notes in right-column panel) ─
    col_count = 3
    label_w = 309
    col_gap = 16
    card_h = 120
    header_h = 26
    footer_h = 20
    row_gap = 12
    loc_h = 13
    row_h = card_h + loc_h + row_gap

    start_x = 33
    start_y = 85

    col_x = [start_x + i * (label_w + col_gap) for i in range(col_count)]
    row_y = [start_y + i * row_h for i in range(5)]

    for idx, (lnum, level, color, tcolor, title, lines, code, location) in enumerate(labels):
        col = idx % col_count
        row = idx // col_count
        x = col_x[col]
        y = row_y[row]

        # Card outline (white fill)
        svg_parts.append(
            f'<rect x="{x}" y="{y}" width="{label_w}" height="{card_h}" '
            f'fill="#ffffff" stroke="#444" stroke-width="1.2" rx="2"/>'
        )

        # ── Coloured header bar ──────────────────────────────────
        svg_parts.append(
            f'<rect x="{x}" y="{y}" width="{label_w}" height="{header_h}" fill="{color}" rx="2" stroke="none"/>'
        )
        svg_parts.append(
            f'<rect x="{x}" y="{y + header_h - 3}" width="{label_w}" height="3" fill="{color}" stroke="none"/>'
        )

        # Safety triangle icon (for DANGER/WARNING/CAUTION)
        if level in ("DANGER", "WARNING", "CAUTION"):
            tx = x + 16
            ty = y + header_h // 2
            ts = 8
            tri_pts = (
                f"{tx:.1f},{ty - ts:.1f} "
                f"{tx - ts * 0.866:.1f},{ty + ts * 0.5:.1f} "
                f"{tx + ts * 0.866:.1f},{ty + ts * 0.5:.1f}"
            )
            svg_parts.append(
                f'<polygon points="{tri_pts}" fill="white" stroke="{color}" stroke-width="0.5" opacity="0.92"/>'
            )
            svg_parts.append(
                f'<text x="{tx}" y="{ty + 4}" text-anchor="middle" '
                f'font-size="8" font-weight="900" font-family="Arial" '
                f'fill="{color}">!</text>'
            )
        else:
            svg_parts.append(f'<circle cx="{x + 14}" cy="{y + header_h // 2}" r="7" fill="white" opacity="0.9"/>')
            svg_parts.append(
                f'<text x="{x + 14}" y="{y + header_h // 2 + 4}" '
                f'text-anchor="middle" font-size="9" font-weight="900" '
                f'font-family="Arial" fill="{color}">i</text>'
            )

        # Level text
        mid_x = x + label_w // 2 + 10
        mid_y = y + header_h // 2 + 5
        svg_parts.append(
            f'<text x="{mid_x}" y="{mid_y}" text-anchor="middle" '
            f'font-size="11" font-weight="900" font-family="Arial" '
            f'fill="{tcolor}" letter-spacing="2">{level}</text>'
        )

        # Label number badge
        badge_w = 38
        badge_x = x + label_w - badge_w
        svg_parts.append(
            f'<rect x="{badge_x}" y="{y}" width="{badge_w}" height="{header_h}" '
            f'fill="rgba(0,0,0,0.22)" stroke="none" rx="2"/>'
        )
        svg_parts.append(
            f'<text x="{badge_x + badge_w // 2}" y="{y + header_h // 2 + 4}" '
            f'text-anchor="middle" font-size="8" font-weight="700" '
            f'font-family="Arial" fill="white">{lnum}</text>'
        )

        # ── White body ───────────────────────────────────────────
        body_top = y + header_h

        # Title line (bold)
        svg_parts.append(
            f'<text x="{x + label_w // 2}" y="{body_top + 18}" '
            f'text-anchor="middle" font-size="9.5" font-weight="900" '
            f'font-family="Arial" fill="#000">{title}</text>'
        )

        # Body lines
        line_y = body_top + 34
        for line in lines:
            svg_parts.append(
                f'<text x="{x + label_w // 2}" y="{line_y}" '
                f'text-anchor="middle" font-size="8.5" font-family="Arial" '
                f'fill="#222">{line}</text>'
            )
            line_y += 14

        # ── Footer: code reference ───────────────────────────────
        foot_y = y + card_h - footer_h
        svg_parts.append(
            f'<rect x="{x}" y="{foot_y}" width="{label_w}" height="{footer_h}" '
            f'fill="#f2f2f2" stroke="none" rx="0"/>'
        )
        svg_parts.append(
            f'<line x1="{x}" y1="{foot_y}" x2="{x + label_w}" y2="{foot_y}" stroke="#ccc" stroke-width="0.7"/>'
        )
        svg_parts.append(
            f'<text x="{x + label_w // 2}" y="{foot_y + 13}" '
            f'text-anchor="middle" font-size="7.5" font-family="Arial" '
            f'fill="#444">{code}</text>'
        )

        # ── Location note below card ─────────────────────────────
        svg_parts.append(
            f'<text x="{x + 5}" y="{y + card_h + 11}" '
            f'font-size="7.5" font-style="italic" font-family="Arial" '
            f'fill="#555">&#9658; {location}</text>'
        )

    # ── Right-column notes panel (Cubillas PV-6 standard) ────────────
    nc_x = 1007
    nc_y = 75
    nc_w = 243
    nc_h = 735

    # Column border
    svg_parts.append(
        f'<rect x="{nc_x}" y="{nc_y}" width="{nc_w}" height="{nc_h}" '
        f'fill="#ffffff" stroke="#000" stroke-width="1.2"/>'
    )
    # Header bar
    svg_parts.append(f'<rect x="{nc_x}" y="{nc_y}" width="{nc_w}" height="22" fill="#e8e8e8" stroke="none"/>')
    svg_parts.append(
        f'<line x1="{nc_x}" y1="{nc_y + 22}" x2="{nc_x + nc_w}" y2="{nc_y + 22}" stroke="#000" stroke-width="0.8"/>'
    )
    svg_parts.append(
        f'<text x="{nc_x + nc_w // 2}" y="{nc_y + 15}" text-anchor="middle" '
        f'font-size="9" font-weight="700" font-family="Arial" fill="#000">'
        f"LABELING NOTES</text>"
    )

    # Text rendering helpers
    _nc_ty = [nc_y + 34]  # mutable y cursor
    nc_lx = nc_x + 8

    def _nc(text, bold=False, fill="#000", size=7.0):
        fw = "700" if bold else "400"
        svg_parts.append(
            f'<text x="{nc_lx}" y="{_nc_ty[0]}" font-size="{size}" '
            f'font-weight="{fw}" font-family="Arial" fill="{fill}">'
            f"{text}</text>"
        )
        _nc_ty[0] += 12.0

    def _nc_gap(px=6):
        _nc_ty[0] += px

    def _nc_divider():
        svg_parts.append(
            f'<line x1="{nc_x + 5}" y1="{_nc_ty[0]}" '
            f'x2="{nc_x + nc_w - 5}" y2="{_nc_ty[0]}" '
            f'stroke="#ccc" stroke-width="0.6"/>'
        )
        _nc_ty[0] += 8

    # ── Block 1: Hand-written labels prohibited ────────────────────
    _pc = renderer._code_prefix
    _pn = _pc == "NEC"
    _nc("ALL SIGNAGE MUST BE")
    _nc("PERMANENTLY ATTACHED AND")
    _nc("WEATHER/SUNLIGHT RESISTANT")
    _nc("AND CANNOT BE HAND-WRITTEN")
    _nc(f"PER {_pc} {'110.21(B)' if _pn else '2-100'}.")
    _nc_gap(8)
    _nc_divider()

    # ── Block 2: Directory requirement ─────────────────────────────
    _nc("PERMANENT PLAQUE OR DIRECTORY")
    _nc("PROVIDING THE LOCATION OF")
    _nc("THE SERVICE DISCONNECTING")
    _nc("MEANS AND THE PV SYSTEM")
    _nc("DISCONNECTING MEANS IF NOT IN")
    _nc("THE SAME LOCATION.")
    _nc(f"[{_pc} {'690.56(B)' if _pn else '64-214'}]", fill="#555")
    _nc_gap(8)
    _nc_divider()

    # ── Block 3: Directory at disconnects ──────────────────────────
    _nc("WHERE PV SYSTEMS ARE REMOTELY")
    _nc("LOCATED FROM EACH OTHER, A")
    _nc(f"DIRECTORY PER {_pc} {'705.10' if _pn else '64-214'} SHALL")
    _nc("BE PROVIDED AT EACH DISCONNECT.")
    _nc("PV EQUIPMENT AND DISCONNECTING")
    _nc("MEANS SHALL NOT BE INSTALLED")
    _nc("IN BATHROOMS.")
    _nc(f"[{_pc} {'690.4(D),(E)' if _pn else '64-060'}]", fill="#555")
    _nc_gap(8)
    _nc_divider()

    # ── Labeling Requirements 1.1–1.5 (Cubillas numbered format) ───
    _nc("LABELING REQUIREMENTS:", bold=True)
    _nc_gap(4)
    _nc("1.1 REQUIREMENTS BASED ON CEC")
    _nc("     SECTION 64 / ANSI Z535.4.")
    _nc_gap(3)
    _nc("1.2 MATERIAL PER REQUIREMENTS")
    _nc("     OF THE AUTHORITY HAVING")
    _nc("     JURISDICTION.")
    _nc_gap(3)
    _nc("1.3 LABELS TO BE SUFFICIENTLY")
    _nc("     DURABLE FOR THE ENVIRONMENT.")
    _nc_gap(3)
    _nc('1.4 MIN LETTER HEIGHT: 3/8"')
    _nc("     (9.5 mm). PERMANENTLY")
    _nc("     AFFIXED.")
    _nc_gap(3)
    _nc("1.5 ALERTING WORDS COLOR CODED:")
    _nc("     DANGER = RED BACKGROUND;")
    _nc("     WARNING = ORANGE BG;")
    _nc("     CAUTION = YELLOW BG.")
    _nc("     [ANSI Z535]")
    _nc_gap(12)
    _nc_divider()

    # ── Footer ──────────────────────────────────────────────────────
    _nc("LABELS ARE NOT DRAWN TO SCALE", bold=True)

    # ── Bottom footer note (matches Cubillas PV-6 standard) ──────────
    _code_name = "NEC" if _is_nec else "CEC"
    svg_parts.append(
        f'<text x="30" y="848" font-size="8" font-style="italic" '
        f'font-family="Arial" fill="#333">'
        f"NOTE:- *ALL PLAQUES AND SIGNAGE WILL BE INSTALLED OR REFLECTIVE "
        f"ADHESIVE LABEL AS REQUIRED BY THE {_code_name}*"
        f"</text>"
    )

    # ── Title block ───────────────────────────────────────────────
    svg_parts.append(
        renderer._svg_title_block(
            VW,
            VH,
            sheet_id="E-603",
            sheet_title="SIGNAGE",
            subtitle=f"{_cp} {'690 / NEC' if _is_nec else 'Rule 64'} | ANSI Z535.4",
            page_of="9 of 15",
            address=address,
            today=today,
        )
    )

    svg_content = "\n".join(svg_parts)
    return (
        f'<div class="page"><svg width="100%" height="100%" '
        f'viewBox="0 0 {VW} {VH}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#fff;">{svg_content}</svg></div>'
    )
