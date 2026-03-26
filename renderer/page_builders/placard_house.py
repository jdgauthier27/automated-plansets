"""Page builder: Placard House (PV-6.1 / E-604)
=================================================
Extracted from HtmlRenderer._build_placard_house_page.
"""


def build_placard_house_page(renderer, address: str, today: str) -> str:
    """PV-6.1: Placard house — MICROINVERTER topology disconnect locations.

    Matches Cubillas PV-9 style: CAUTION header, building elevation with all
    equipment labelled, for first responders and building inspectors.

    MICROINVERTER SYSTEM (Enphase IQ8A) topology — NO DC conduit, NO central inverter:
      Roof panels (microinverters under each) → AC trunk cable
      → Junction Box (NEMA 3R, exterior) → PV Load Center (125A/240V)
      → Main Service Panel → Main Billing Meter
    All conduit on this diagram is AC (red). There is no DC conduit or DC disconnect.
    """
    svg_parts = []

    svg_parts.append('<rect width="1280" height="960" fill="#ffffff"/>')
    svg_parts.append('<rect x="20" y="20" width="1240" height="820" fill="none" stroke="#000" stroke-width="2"/>')

    # ── CAUTION header bar (matches Cubillas PV-9 style) ─────────────
    svg_parts.append('<rect x="20" y="20" width="1240" height="38" fill="#FFD700" stroke="#000" stroke-width="2"/>')
    svg_parts.append(
        '<text x="640" y="34" text-anchor="middle" font-size="14" font-weight="700" font-family="Arial" fill="#000">! CAUTION !</text>'
    )

    # ── "Power supplied from following sources" notice ────────────────
    svg_parts.append('<rect x="20" y="58" width="1240" height="30" fill="#f5f5f5" stroke="#000" stroke-width="1"/>')
    svg_parts.append(
        '<text x="640" y="71" text-anchor="middle" font-size="9" font-weight="700" font-family="Arial" fill="#000">'
        "POWER TO THIS BUILDING IS SUPPLIED FROM THE FOLLOWING SOURCES WITH DISCONNECTS LOCATED AS SHOWN"
        "</text>"
    )
    svg_parts.append(
        '<text x="640" y="82" text-anchor="middle" font-size="8" font-family="Arial" fill="#333">'
        "SERVICE 1 OF 1 — NEW ROOF MOUNT SOLAR PV ARRAY (MICROINVERTER SYSTEM — ALL AC OUTPUT)"
        "</text>"
    )

    # ── House geometry ────────────────────────────────────────────────
    # Centered house elevation with equipment on sides
    house_x = 370  # left wall x
    roof_peak_y = 150  # top of roof
    roof_base_y = 255  # eave line (roof meets walls)
    wall_bottom_y = 490  # ground line
    house_w = 290
    roof_overhang = 22  # eaves extend past walls

    # ── Ground line ───────────────────────────────────────────────────
    svg_parts.append(
        f'<line x1="80" y1="{wall_bottom_y}" x2="950" y2="{wall_bottom_y}" '
        f'stroke="#000" stroke-width="1.5" stroke-dasharray="8,4"/>'
    )
    svg_parts.append(
        f'<text x="960" y="{wall_bottom_y + 4}" font-size="8" font-family="Arial" fill="#666">GRADE</text>'
    )

    # ── Roof (gable) ──────────────────────────────────────────────────
    roof_left = house_x - roof_overhang
    roof_right = house_x + house_w + roof_overhang
    roof_cx = house_x + house_w / 2
    svg_parts.append(
        f'<polygon points="{roof_left},{roof_base_y} {roof_cx:.0f},{roof_peak_y} '
        f'{roof_right},{roof_base_y}" '
        f'fill="#e8e0d8" stroke="#000" stroke-width="2"/>'
    )

    # ── Solar panels on roof (right slope, south-facing) ─────────────
    # 4 representative panels with microinverter dots beneath each
    panel_count = 4
    panel_w, panel_h = 38, 15
    for pi in range(panel_count):
        t = 0.20 + pi * 0.16
        px = roof_cx + t * (roof_right - roof_cx)
        py = roof_peak_y + t * (roof_base_y - roof_peak_y)
        angle = 27  # roof pitch angle
        svg_parts.append(
            f'<rect x="{px - panel_w / 2:.0f}" y="{py - panel_h:.0f}" '
            f'width="{panel_w}" height="{panel_h}" '
            f'fill="#ffffff" stroke="#000000" stroke-width="0.9" '
            f'transform="rotate({angle},{px:.0f},{py - panel_h / 2:.0f})"/>'
        )
        # Microinverter dot below panel
        svg_parts.append(
            f'<circle cx="{px:.0f}" cy="{py - 3:.0f}" r="3" '
            f'fill="#cc0000" stroke="#fff" stroke-width="0.5" '
            f'transform="rotate({angle},{px:.0f},{py:.0f})"/>'
        )

    # ── Walls ─────────────────────────────────────────────────────────
    wall_h = wall_bottom_y - roof_base_y
    svg_parts.append(
        f'<rect x="{house_x}" y="{roof_base_y}" width="{house_w}" height="{wall_h}" '
        f'fill="#ffffff" stroke="#000" stroke-width="2"/>'
    )

    # ── Door (centered) ───────────────────────────────────────────────
    door_w, door_h = 42, 84
    door_x = house_x + house_w / 2 - door_w / 2
    door_y = wall_bottom_y - door_h
    svg_parts.append(
        f'<rect x="{door_x:.0f}" y="{door_y}" width="{door_w}" height="{door_h}" '
        f'fill="#c4a882" stroke="#000" stroke-width="1"/>'
    )
    svg_parts.append(
        f'<circle cx="{door_x + door_w - 9:.0f}" cy="{door_y + door_h / 2:.0f}" r="3" '
        f'fill="#888" stroke="#555" stroke-width="0.5"/>'
    )

    # ── Windows ───────────────────────────────────────────────────────
    win_w, win_h = 46, 46
    for wx in [house_x + 32, house_x + house_w - 32 - win_w]:
        wy = roof_base_y + 38
        svg_parts.append(
            f'<rect x="{wx:.0f}" y="{wy}" width="{win_w}" height="{win_h}" '
            f'fill="#f0f0f0" stroke="#000" stroke-width="1"/>'
        )
        svg_parts.append(
            f'<line x1="{wx + win_w / 2:.0f}" y1="{wy}" x2="{wx + win_w / 2:.0f}" '
            f'y2="{wy + win_h}" stroke="#000" stroke-width="0.5"/>'
        )
        svg_parts.append(
            f'<line x1="{wx:.0f}" y1="{wy + win_h / 2:.0f}" x2="{wx + win_w:.0f}" '
            f'y2="{wy + win_h / 2:.0f}" stroke="#000" stroke-width="0.5"/>'
        )

    # ── RIGHT SIDE equipment: JUNC. BOX + PV LOAD CTR ────────────────
    eq_x = house_x + house_w + 35  # right of house

    # Junction Box (NEMA 3R)
    jb_y = roof_base_y + 18
    svg_parts.append(
        f'<rect x="{eq_x}" y="{jb_y}" width="90" height="52" fill="#ffffff" stroke="#000" stroke-width="1.8"/>'
    )
    svg_parts.append(
        f'<text x="{eq_x + 45}" y="{jb_y + 18}" text-anchor="middle" '
        f'font-size="8" font-weight="700" font-family="Arial" fill="#000">JUNC. BOX</text>'
    )
    svg_parts.append(
        f'<text x="{eq_x + 45}" y="{jb_y + 30}" text-anchor="middle" '
        f'font-size="7" font-family="Arial" fill="#444">NEMA 3R</text>'
    )
    svg_parts.append(
        f'<text x="{eq_x + 45}" y="{jb_y + 42}" text-anchor="middle" '
        f'font-size="7" font-family="Arial" fill="#444">AC BRANCH MERGE</text>'
    )

    # PV Load Center (125A/240V)
    pvlc_y = jb_y + 80
    svg_parts.append(
        f'<rect x="{eq_x}" y="{pvlc_y}" width="90" height="60" fill="#ffffff" stroke="#000" stroke-width="1.8"/>'
    )
    svg_parts.append(
        f'<text x="{eq_x + 45}" y="{pvlc_y + 18}" text-anchor="middle" '
        f'font-size="8" font-weight="700" font-family="Arial" fill="#000">PV LOAD CTR</text>'
    )
    svg_parts.append(
        f'<text x="{eq_x + 45}" y="{pvlc_y + 30}" text-anchor="middle" '
        f'font-size="7" font-family="Arial" fill="#444">125A / 240V 1&#x3C6;</text>'
    )
    svg_parts.append(
        f'<text x="{eq_x + 45}" y="{pvlc_y + 42}" text-anchor="middle" '
        f'font-size="7" font-family="Arial" fill="#444">30A 2P BACKFED</text>'
    )
    svg_parts.append(
        f'<text x="{eq_x + 45}" y="{pvlc_y + 53}" text-anchor="middle" '
        f'font-size="7" font-family="Arial" fill="#cc0000">RAPID SHUTDOWN</text>'
    )

    # ── LEFT SIDE equipment: MAIN SERVICE PANEL + METER ──────────────
    mp_x = house_x - 100
    mp_y = roof_base_y + 40
    svg_parts.append(
        f'<rect x="{mp_x}" y="{mp_y}" width="72" height="88" fill="#f0f0f0" stroke="#000" stroke-width="1.8"/>'
    )
    svg_parts.append(
        f'<text x="{mp_x + 36}" y="{mp_y + 25}" text-anchor="middle" '
        f'font-size="8" font-weight="700" font-family="Arial" fill="#000">MAIN</text>'
    )
    svg_parts.append(
        f'<text x="{mp_x + 36}" y="{mp_y + 38}" text-anchor="middle" '
        f'font-size="8" font-weight="700" font-family="Arial" fill="#000">SERVICE</text>'
    )
    svg_parts.append(
        f'<text x="{mp_x + 36}" y="{mp_y + 51}" text-anchor="middle" '
        f'font-size="8" font-weight="700" font-family="Arial" fill="#000">PANEL</text>'
    )
    svg_parts.append(
        f'<text x="{mp_x + 36}" y="{mp_y + 65}" text-anchor="middle" '
        f'font-size="7" font-family="Arial" fill="#444">200A / 240V</text>'
    )
    svg_parts.append(
        f'<text x="{mp_x + 36}" y="{mp_y + 77}" text-anchor="middle" '
        f'font-size="7" font-family="Arial" fill="#cc0000">DUAL SOURCE</text>'
    )

    # Meter (exterior left wall, near grade)
    meter_x = mp_x
    meter_y = wall_bottom_y - 80
    svg_parts.append(
        f'<circle cx="{meter_x + 36}" cy="{meter_y + 28}" r="26" fill="#f8f8f8" stroke="#000" stroke-width="1.8"/>'
    )
    svg_parts.append(
        f'<text x="{meter_x + 36}" y="{meter_y + 24}" text-anchor="middle" '
        f'font-size="8" font-weight="700" font-family="Arial" fill="#000">MAIN</text>'
    )
    svg_parts.append(
        f'<text x="{meter_x + 36}" y="{meter_y + 35}" text-anchor="middle" '
        f'font-size="8" font-weight="700" font-family="Arial" fill="#000">BILLING</text>'
    )
    svg_parts.append(
        f'<text x="{meter_x + 36}" y="{meter_y + 46}" text-anchor="middle" '
        f'font-size="7" font-family="Arial" fill="#444">METER</text>'
    )
    svg_parts.append(
        f'<text x="{meter_x + 36}" y="{meter_y + 65}" text-anchor="middle" '
        f'font-size="7" font-family="Arial" fill="#000000">BI-DIRECTIONAL</text>'
    )

    # Monitoring system (right side, below PV Load Center)
    mon_y = pvlc_y + 80
    svg_parts.append(
        f'<rect x="{eq_x}" y="{mon_y}" width="90" height="42" '
        f'fill="#ffffff" stroke="#888" stroke-width="1" stroke-dasharray="4,2"/>'
    )
    svg_parts.append(
        f'<text x="{eq_x + 45}" y="{mon_y + 16}" text-anchor="middle" '
        f'font-size="8" font-weight="700" font-family="Arial" fill="#000">MONITORING</text>'
    )
    svg_parts.append(
        f'<text x="{eq_x + 45}" y="{mon_y + 28}" text-anchor="middle" '
        f'font-size="7" font-family="Arial" fill="#444">ENPHASE ENVOY</text>'
    )
    svg_parts.append(
        f'<text x="{eq_x + 45}" y="{mon_y + 38}" text-anchor="middle" '
        f'font-size="6" font-family="Arial" fill="#888">(IF INSTALLED)</text>'
    )

    # ── ALL-AC conduit runs (microinverter system) ────────────────────
    # AC trunk cable: Roof eave → Junction Box (RED — all AC)
    svg_parts.append(
        f'<line x1="{house_x + house_w}" y1="{roof_base_y}" '
        f'x2="{eq_x}" y2="{jb_y + 26}" '
        f'stroke="#cc0000" stroke-width="2" stroke-dasharray="5,3"/>'
    )
    # Junction Box → PV Load Center
    svg_parts.append(
        f'<line x1="{eq_x + 45}" y1="{jb_y + 52}" '
        f'x2="{eq_x + 45}" y2="{pvlc_y}" '
        f'stroke="#cc0000" stroke-width="2" stroke-dasharray="5,3"/>'
    )
    # PV Load Center → Main Service Panel (run across bottom of house)
    svg_parts.append(
        f'<polyline points="{eq_x + 45},{pvlc_y + 60} '
        f"{eq_x + 45},{wall_bottom_y - 12} "
        f"{mp_x + 72},{wall_bottom_y - 12} "
        f'{mp_x + 72},{mp_y + 88}" '
        f'fill="none" stroke="#cc0000" stroke-width="2" stroke-dasharray="5,3"/>'
    )
    # Main Service Panel → Meter
    svg_parts.append(
        f'<line x1="{mp_x + 36}" y1="{mp_y + 88}" '
        f'x2="{mp_x + 36}" y2="{meter_y}" '
        f'stroke="#cc0000" stroke-width="2" stroke-dasharray="5,3"/>'
    )

    # ── Callout annotations ───────────────────────────────────────────
    callouts = [
        {
            "num": "1",
            "label": "ROOF ARRAY (13 MODULES)",
            "sublabel": "13x ENPHASE IQ8A MICROINVERTERS",
            "dot_x": roof_cx + 0.45 * (roof_right - roof_cx),
            "dot_y": roof_peak_y + 0.45 * (roof_base_y - roof_peak_y),
            "box_x": 710,
            "box_y": 100,
        },
        {
            "num": "2",
            "label": "JUNCTION BOX (NEMA 3R)",
            "sublabel": "AC BRANCH CIRCUIT MERGE POINT",
            "dot_x": eq_x + 45,
            "dot_y": jb_y + 26,
            "box_x": 760,
            "box_y": 205,
        },
        {
            "num": "3",
            "label": "PV LOAD CENTER",
            "sublabel": "125A/240V — 30A 2P RAPID SHUTDOWN",
            "dot_x": eq_x + 45,
            "dot_y": pvlc_y + 30,
            "box_x": 760,
            "box_y": 310,
        },
        {
            "num": "4",
            "label": "MAIN SERVICE PANEL",
            "sublabel": "200A/240V — DUAL POWER SOURCE",
            "dot_x": mp_x + 36,
            "dot_y": mp_y + 44,
            "box_x": 55,
            "box_y": 205,
        },
        {
            "num": "5",
            "label": "MAIN BILLING METER",
            "sublabel": "BI-DIRECTIONAL (NET METERING)",
            "dot_x": meter_x + 36,
            "dot_y": meter_y + 28,
            "box_x": 55,
            "box_y": 380,
        },
    ]

    for c in callouts:
        # Filled circle at equipment location
        svg_parts.append(
            f'<circle cx="{c["dot_x"]:.0f}" cy="{c["dot_y"]:.0f}" r="11" '
            f'fill="#000000" stroke="#fff" stroke-width="1.5"/>'
        )
        svg_parts.append(
            f'<text x="{c["dot_x"]:.0f}" y="{c["dot_y"] + 4:.0f}" text-anchor="middle" '
            f'font-size="10" font-weight="700" font-family="Arial" fill="#fff">{c["num"]}</text>'
        )
        # Leader line to callout box
        svg_parts.append(
            f'<line x1="{c["dot_x"]:.0f}" y1="{c["dot_y"]:.0f}" '
            f'x2="{c["box_x"] + 110:.0f}" y2="{c["box_y"] + 24:.0f}" '
            f'stroke="#555" stroke-width="0.8" stroke-dasharray="4,2"/>'
        )
        # Callout box
        svg_parts.append(
            f'<rect x="{c["box_x"]}" y="{c["box_y"]}" width="220" height="48" '
            f'rx="2" fill="#ffffff" stroke="#000000" stroke-width="1.3"/>'
        )
        # Number badge inside box
        svg_parts.append(f'<circle cx="{c["box_x"] + 18}" cy="{c["box_y"] + 24}" r="11" fill="#000000"/>')
        svg_parts.append(
            f'<text x="{c["box_x"] + 18}" y="{c["box_y"] + 28}" text-anchor="middle" '
            f'font-size="10" font-weight="700" font-family="Arial" fill="#fff">{c["num"]}</text>'
        )
        # Label lines
        svg_parts.append(
            f'<text x="{c["box_x"] + 36}" y="{c["box_y"] + 18}" '
            f'font-size="8.5" font-weight="700" font-family="Arial" fill="#000">{c["label"]}</text>'
        )
        svg_parts.append(
            f'<text x="{c["box_x"] + 36}" y="{c["box_y"] + 34}" '
            f'font-size="7.5" font-family="Arial" fill="#444">{c["sublabel"]}</text>'
        )

    # ── Legend ────────────────────────────────────────────────────────
    leg_y = wall_bottom_y + 20
    svg_parts.append(
        f'<text x="50" y="{leg_y}" font-size="9" font-weight="700" font-family="Arial" fill="#000">SYSTEM LEGEND</text>'
    )
    legend_items = [
        ("#cc0000", "——", "AC conduit / trunk cable (Microinverters → Junc. Box → PV Load Center → Panel)"),
        ("#cc0000", "●", "Enphase IQ8A microinverter (one under each panel, AC output only)"),
        ("#000000", "①", "Callout number — matches equipment location on building"),
    ]
    for li, (lc, sym, txt) in enumerate(legend_items):
        ly2 = leg_y + 18 + li * 16
        svg_parts.append(f'<text x="60" y="{ly2}" font-size="9" font-family="Arial" fill="{lc}">{sym}</text>')
        svg_parts.append(f'<text x="80" y="{ly2}" font-size="8" font-family="Arial" fill="#333">{txt}</text>')

    # ── Notes ─────────────────────────────────────────────────────────
    notes_y = leg_y + 80
    svg_parts.append(
        f'<text x="50" y="{notes_y}" font-size="9" font-weight="700" font-family="Arial" fill="#000">NOTES</text>'
    )
    notes = [
        "This system uses MICROINVERTERS — there is NO DC conduit and NO central inverter on this property.",
        "All conductors from the PV array to the load center are AC. Rapid shutdown is at the PV Load Center.",
        f'All labels must be permanently attached, weather/UV-resistant, min. 3/8" letter height ({renderer._code_prefix} {"690.31(G)" if renderer._code_prefix == "NEC" else "64-060"}).',
        "Labels on roof and equipment must remain visible during inspection walk-through.",
        f"Bi-directional meter required for {renderer._utility_name} net metering (max {int(renderer._utility_info.get('net_metering_max_kw', 25))} kW single-phase).",
    ]
    for ni, note in enumerate(notes):
        svg_parts.append(
            f'<text x="60" y="{notes_y + 15 + ni * 15}" font-size="7.5" font-family="Arial" fill="#333">{ni + 1}. {note}</text>'
        )

    # ── Title block ───────────────────────────────────────────────────
    svg_parts.append(
        renderer._svg_title_block(
            1280,
            960,
            "PV-6.1",
            "Placard House",
            "Disconnect Locations — Microinverter System",
            "9 of 13",
            address,
            today,
        )
    )

    svg_content = "\n".join(svg_parts)
    return f'<div class="page"><svg width="100%" height="100%" viewBox="0 0 1280 960" xmlns="http://www.w3.org/2000/svg" style="background:#fff;">{svg_content}</svg></div>'
