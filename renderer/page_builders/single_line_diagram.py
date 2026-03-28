"""Page builder: Single-Line Diagram (PV-4 / E-601)
=====================================================
Extracted from HtmlRenderer._build_single_line_diagram.

Largest page builder. Contains:
  - Circuit diagram SVG (PV array → JB → Load Center → OCPD → Main → Meter → Grid)
  - Conductor & Conduit Schedule
  - PV Module Electrical Specifications table
  - Inverter Electrical Specifications table
  - Branch Circuit Data
  - OCPD Calculations
  - Busbar Calculations / 120% Rule
  - Electrical Notes
"""

import math

from renderer.svg_helpers import wire_gauge


def build_single_line_diagram(
    renderer, total_panels: int, total_kw: float, address: str, today: str
) -> str:
    """PV-4: Single-line diagram — full permit-ready layout.

    Layout (1280×960 SVG):
      Top (y=60-300):   Circuit flow + String Data / 120% Rule
      Middle (y=308-498): Conductor Schedule + PV Module Spec
      Lower (y=506-660):  Inverter Spec + OCPD Calculations
      Bottom (y=668-830): Electrical notes
    """
    svg_parts = []

    # Jurisdiction-aware code references
    _cp = renderer._code_prefix
    _is_nec = _cp == "NEC"

    # ── Electrical calculations ──────────────────────────────────────
    # Panel electrical specs — from ProjectSpec/catalog or legacy defaults
    voc_per_panel = renderer._panel_voc
    vmp_per_panel = renderer._panel_vmp
    isc_per_panel = renderer._panel_isc
    imp_per_panel = renderer._panel_imp
    temp_coeff_voc = renderer._panel_temp_coeff_voc
    panel_efficiency = renderer._project.panel.efficiency_pct if renderer._project else 22.5

    is_micro = renderer._is_micro

    if is_micro:
        # ── Microinverter branch circuit calculations ──────────────────
        MAX_PER_BRANCH = renderer._max_per_branch
        BRANCH_BREAKER_A = 15  # 2P-15A branch breaker

        n_branches = max(1, math.ceil(total_panels / MAX_PER_BRANCH))
        branch_sizes: list = []
        _remaining = total_panels
        for _bi in range(n_branches):
            _sz = math.ceil(_remaining / (n_branches - _bi))
            branch_sizes.append(_sz)
            _remaining -= _sz

        max_branch_current = max(branch_sizes) * renderer.INV_AC_AMPS_PER_UNIT
        total_ac_current = total_panels * renderer.INV_AC_AMPS_PER_UNIT
    else:
        # ── String inverter: single inverter handles all panels ────────
        MAX_PER_BRANCH = total_panels
        BRANCH_BREAKER_A = 0  # no branch breakers

        n_branches = 1
        branch_sizes = [total_panels]

        inv = renderer._project.inverter
        total_ac_current = inv.rated_ac_output_w / inv.ac_voltage_v
        max_branch_current = total_ac_current

    # Wire sizing helpers


    def _conduit_size(amps):
        if amps <= 30:
            return '3/4"'
        if amps <= 55:
            return '1"'
        return '1-1/4"'

    def _egc_gauge(ocpd_a):
        """Minimum EGC copper wire size per jurisdiction EGC table"""
        if ocpd_a <= 15:
            return "#14 AWG"
        if ocpd_a <= 20:
            return "#12 AWG"
        if ocpd_a <= 60:
            return "#10 AWG"
        if ocpd_a <= 100:
            return "#8 AWG"
        if ocpd_a <= 200:
            return "#6 AWG"
        return "#4 AWG"

    branch_ac_wire = wire_gauge(max_branch_current * 1.25)  # branch circuit
    branch_ac_conduit = _conduit_size(max_branch_current * 1.25)
    sys_ac_wire = wire_gauge(total_ac_current * 1.25)  # load-center output
    sys_ac_conduit = _conduit_size(total_ac_current * 1.25)
    egc_wire = sys_ac_wire  # EGC follows system wire
    # Per-segment EGC wire: branch_egc computed now; sys_egc computed after system_ocpd
    branch_egc_wire = _egc_gauge(BRANCH_BREAKER_A)  # 15A branch → #14 AWG

    # System OCPD: 125% × total AC continuous output (NEC 690.8 / CEC Rule 4-004)
    system_ocpd = math.ceil(total_ac_current * 1.25 / 5) * 5  # 26 A → 30 A
    sys_egc_wire = _egc_gauge(system_ocpd)  # 30A system → #10 AWG

    # 120% rule (NEC 705.12 / CEC 64-056)
    # North American 200A residential panels (Square D QO, Eaton, etc.) have a
    # 225A rated bus bar — the bus rating is higher than the main breaker rating.
    # Cubillas PV-4 shows MAIN BUS RATING: 225A / MAIN DISCONNECT: 200A.
    # Using 225A for the bus (per panel label) is more technically accurate.
    main_breaker = renderer._main_breaker_a
    bus_rating = renderer._bus_rating_a
    total_ocpd = system_ocpd + main_breaker  # 30 + 200 = 230
    rule_120_lim = int(bus_rating * 1.2)  # 270
    rule_120_pass = total_ocpd <= rule_120_lim  # 230 ≤ 270 ✓

    # Keep legacy names so downstream code (120% rule box) still works
    ac_breaker = system_ocpd
    ac_wire = sys_ac_wire
    ac_conduit = sys_ac_conduit
    inv_amps_ac = total_ac_current

    inv_kw = renderer._calc_ac_kw(total_panels)  # total_panels × 384VA

    # ── SVG canvas & border ──────────────────────────────────────────
    svg_parts.append('<rect width="1280" height="960" fill="#ffffff"/>')
    svg_parts.append('<rect x="20" y="20" width="1240" height="820" fill="none" stroke="#000" stroke-width="2"/>')

    # Page title strip
    svg_parts.append('<rect x="20" y="20" width="1240" height="26" fill="#e8e8e8" stroke="#000" stroke-width="1"/>')
    svg_parts.append(
        '<text x="640" y="37" text-anchor="middle" font-size="12" font-weight="700" font-family="Arial" fill="#000">SINGLE-LINE DIAGRAM — E-601</text>'
    )

    # ── SVG defs ─────────────────────────────────────────────────────
    svg_parts.append("""<defs>
      <marker id="arr-dc" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
    <polygon points="0,0 8,3 0,6" fill="#0066cc"/>
      </marker>
      <marker id="arr-ac" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
    <polygon points="0,0 8,3 0,6" fill="#cc0000"/>
      </marker>
    </defs>""")

    # ── NOTES box  (top-left, y=47–128 — matches Cubillas PV-4 standard) ──
    # In Cubillas, a prominent NOTES box occupies the top-left of the SLD,
    # providing key safety and code-compliance notes visible to permit reviewers
    # before they trace the circuit.  Our microinverter-specific notes replace
    # the Cubillas DC-connector warning with equivalent IQ8A system notes.
    nb_x, nb_y, nb_w, nb_h = 28, 47, 426, 106
    svg_parts.append(
        f'<rect x="{nb_x}" y="{nb_y}" width="{nb_w}" height="{nb_h}" '
        f'fill="#ffffff" stroke="#000" stroke-width="1.2"/>'
    )
    # Header bar
    svg_parts.append(
        f'<rect x="{nb_x}" y="{nb_y}" width="{nb_w}" height="13" fill="#e8e8e8" stroke="#000" stroke-width="1"/>'
    )
    svg_parts.append(
        f'<text x="{nb_x + 8}" y="{nb_y + 9}" '
        f'font-size="8" font-weight="700" font-family="Arial" fill="#000">NOTES:</text>'
    )
    svg_parts.append(
        f'<line x1="{nb_x}" y1="{nb_y + 13}" x2="{nb_x + nb_w}" y2="{nb_y + 13}" stroke="#000" stroke-width="0.8"/>'
    )
    _cp = renderer._code_prefix
    _is_nec = _cp == "NEC"
    if is_micro:
        _sld_notes = [
            f"All microinverters: same manufacturer and model — do not mix brands. [{_cp} {'690.4' if _is_nec else '64-102'}]",
            "DC circuit fully isolated in each module — no field-accessible DC wiring.",
            f"Array grounding electrode system required. [{_cp} {'250.94' if _is_nec else 'Rule 10'}]",
            f"AC conductors: 125% of max continuous output current. [{_cp} {'690.8' if _is_nec else 'Rule 4-004'}]",
            f"Backfed PV breaker at opposite end of bus bar from main breaker. [{_cp} {'705.12' if _is_nec else '64-056'}]",
            f"Exterior conduit/boxes: rain-tight and wet-location approved. [{_cp} {'314.15' if _is_nec else '12-1412'}]",
            f"All metallic raceways bonded and grounded. [{_cp} {'250.96' if _is_nec else 'Rule 10-900'}]",
            f"Rapid shutdown: array \u226430 V within 30 s of initiating signal. [{_cp} {'690.12' if _is_nec else '64-218'}]",
            "Conductor/conduit specs are minimums; field may require upsizing.",
            f"Supplemental ground rod at array required. [{_cp} {'690.47' if _is_nec else '64-104'}]",
        ]
    else:
        _sld_notes = [
            f"String inverter: verify string Voc (cold) ≤ inverter max DC input voltage. [{_cp} {'690.7' if _is_nec else '64-056'}]",
            f"DC conductors: Isc × 1.56 minimum ampacity. [{_cp} {'690.8' if _is_nec else 'Rule 14-100'}]",
            f"Array grounding electrode system required. [{_cp} {'250.94' if _is_nec else 'Rule 10'}]",
            f"AC conductors: 125% of max continuous output current. [{_cp} {'690.8' if _is_nec else 'Rule 4-004'}]",
            f"Backfed PV breaker at opposite end of bus bar from main breaker. [{_cp} {'705.12' if _is_nec else '64-056'}]",
            f"Exterior conduit/boxes: rain-tight and wet-location approved. [{_cp} {'314.15' if _is_nec else '12-1412'}]",
            f"All metallic raceways bonded and grounded. [{_cp} {'250.96' if _is_nec else 'Rule 10-900'}]",
            f"Rapid shutdown: comply with {_cp} {'690.12' if _is_nec else '64-218'} (or supply-side tap).",
            "Conductor/conduit specs are minimums; field may require upsizing.",
            f"Supplemental ground rod at array required. [{_cp} {'690.47' if _is_nec else '64-104'}]",
        ]
    _col2_start = nb_x + nb_w // 2 + 4
    _half = (len(_sld_notes) + 1) // 2  # 5 notes left, 4 right
    for _ni, _note in enumerate(_sld_notes):
        _col = _ni // _half
        _row = _ni % _half
        _nx = _col2_start if _col else nb_x + 8
        _ny = nb_y + 17 + _row * 12
        svg_parts.append(
            f'<text x="{_nx}" y="{_ny}" font-size="5" font-family="Arial" fill="#222">{_ni + 1}. {_note}</text>'
        )


    # ── TOP: CONDUCTOR AND CONDUIT SCHEDULE — delegated to single_line_tables ──
    from renderer.page_builders.single_line_tables import (
        build_conductor_schedule, build_pv_system_summary, build_sld_lower_tables
    )
    _calc = {
        'n_branches': n_branches, 'sys_ac_wire': sys_ac_wire,
        'sys_ac_conduit': sys_ac_conduit, 'sys_egc_wire': sys_egc_wire,
        'total_panels': total_panels, 'total_kw': total_kw, 'inv_kw': inv_kw,
        'total_ac_current': total_ac_current, 'max_branch_current': max_branch_current,
        'branch_sizes': branch_sizes, 'MAX_PER_BRANCH': MAX_PER_BRANCH,
        'BRANCH_BREAKER_A': BRANCH_BREAKER_A, 'system_ocpd': system_ocpd,
        'main_breaker': main_breaker, 'bus_rating': bus_rating,
        'rule_120_pass': rule_120_pass, 'rule_120_lim': rule_120_lim,
        'voc_per_panel': voc_per_panel, 'vmp_per_panel': vmp_per_panel,
        'isc_per_panel': isc_per_panel, 'imp_per_panel': imp_per_panel,
        'temp_coeff_voc': temp_coeff_voc, 'panel_efficiency': panel_efficiency,
        'branch_ac_wire': branch_ac_wire, 'branch_ac_conduit': branch_ac_conduit,
        'branch_egc_wire': branch_egc_wire, 'ac_breaker': ac_breaker,
        '_cp': _cp, '_is_nec': _is_nec,
    }
    build_conductor_schedule(svg_parts, renderer, _calc)

    # ── TOP-RIGHT: PHOTOVOLTAIC SYSTEM SUMMARY — delegated to single_line_tables ──
    build_pv_system_summary(svg_parts, renderer, _calc)

    # ── Compressed circuit layout (x=28..875, y=55..295) ─────────────
    bus_y = 205
    cx_pv = 75
    cx_dc_disc = 200
    cx_inv = 345
    cx_ac_ocpd = 478
    cx_main = 620
    cx_meter = 745
    cx_grid = 855

    # ── Helpers ──────────────────────────────────────────────────────
    def _ground(gx, gy):
        p = [f'<line x1="{gx}" y1="{gy}" x2="{gx}" y2="{gy + 13}" stroke="#00aa00" stroke-width="1.5"/>']
        for j in range(3):
            hw = 7 - j * 2
            yy = gy + 13 + j * 4
            p.append(
                f'<line x1="{gx - hw}" y1="{yy}" x2="{gx + hw}" y2="{yy}" stroke="#00aa00" stroke-width="1.5"/>'
            )
        return "\n".join(p)

    def _switch(sx, sy, label):
        sw = 25
        p = [
            f'<circle cx="{sx}" cy="{sy}" r="3" fill="#000"/>',
            f'<line x1="{sx}" y1="{sy}" x2="{sx + sw}" y2="{sy - 11}" stroke="#000" stroke-width="2"/>',
            f'<circle cx="{sx + sw + 2}" cy="{sy}" r="3" fill="none" stroke="#000" stroke-width="1.5"/>',
        ]
        if label:
            p.append(
                f'<text x="{sx + sw // 2}" y="{sy + 17}" text-anchor="middle" '
                f'font-size="7" font-weight="700" font-family="Arial" fill="#000">{label}</text>'
            )
        return "\n".join(p)

    # ── 1. PV ARRAY — per-string circuit detail ───────────────────────
    # Layout: expanded box showing each string as a series chain of
    # panel icons, with a combiner bus bar on the right side for
    # multi-string systems. Output exits at bus_y (horizontal centre).
    max_icons_per_str = 6  # compact panel icons rendered per row
    icon_w = 10  # panel icon width  (px)
    icon_h = 8  # panel icon height (px)
    icon_gap = 1  # gap between consecutive icons
    str_row_h = 24  # total height per string row (label + icons)

    pv_box_x = 28
    pv_box_w = 116
    # Height: 14 (header) + n_branches*(str_row_h+3) + 10 (footer pad)
    pv_box_inner_h = 14 + n_branches * (str_row_h + 3) + 10
    pv_box_h = max(68, pv_box_inner_h)
    pv_box_y = bus_y - pv_box_h // 2

    # Outer box
    svg_parts.append(
        f'<rect x="{pv_box_x}" y="{pv_box_y}" width="{pv_box_w}" height="{pv_box_h}" '
        f'fill="#ffffff" stroke="#000" stroke-width="2"/>'
    )
    # Header bar
    svg_parts.append(
        f'<rect x="{pv_box_x}" y="{pv_box_y}" width="{pv_box_w}" height="14" '
        f'fill="#e8e8e8" stroke="#000" stroke-width="1"/>'
    )
    svg_parts.append(
        f'<text x="{pv_box_x + pv_box_w // 2}" y="{pv_box_y + 10}" text-anchor="middle" '
        f'font-size="7.5" font-weight="700" font-family="Arial" fill="#000">PV ARRAY</text>'
    )

    # Sun-ray icon in header (decorative, shows it is a PV source)
    sx0 = pv_box_x + 8
    sy0 = pv_box_y + 7
    for _ang in [0, 45, 90, 135]:
        import math as _m

        dx, dy = _m.cos(_m.radians(_ang)) * 5, _m.sin(_m.radians(_ang)) * 5
        svg_parts.append(
            f'<line x1="{sx0 + dx:.0f}" y1="{sy0 + dy:.0f}" x2="{sx0 + dx * 1.9:.0f}" y2="{sy0 + dy * 1.9:.0f}" '
            f'stroke="#ffaa00" stroke-width="1"/>'
        )
    svg_parts.append(f'<circle cx="{sx0}" cy="{sy0}" r="2.5" fill="#ffcc00" stroke="none"/>')

    # Per-circuit rows (AC branch circuits for microinverter system)
    str_mid_ys = []  # y-centre of each circuit's icon row (used for wiring)
    collect_x = pv_box_x + pv_box_w - 14  # x of internal collection bar

    for si in range(n_branches):
        str_panels_i = branch_sizes[si]
        row_top = pv_box_y + 16 + si * (str_row_h + 3)
        label_y = row_top + 9
        icons_y = row_top + 12  # top of icon row
        mid_y = icons_y + icon_h // 2  # vertical centre of icon row
        str_mid_ys.append(mid_y)

        show_count = min(max_icons_per_str, str_panels_i)
        icons_start_x = pv_box_x + 6

        # Circuit label (AC branch circuit — not a DC string)
        svg_parts.append(
            f'<text x="{icons_start_x}" y="{label_y}" '
            f'font-size="6.5" font-weight="700" font-family="Arial" fill="#333">'
            f"CIRCUIT-{si + 1}  ({str_panels_i} MODULES)</text>"
        )

        # Wire behind icons (AC wire — black/dark)
        wire_end_x = (
            icons_start_x + show_count * (icon_w + icon_gap) + (10 if str_panels_i > max_icons_per_str else 0)
        )
        svg_parts.append(
            f'<line x1="{icons_start_x}" y1="{mid_y}" '
            f'x2="{collect_x}" y2="{mid_y}" '
            f'stroke="#cc0000" stroke-width="0.8"/>'
        )

        # Panel icons — white fill with black outline (AC module / microinverter style)
        for pi in range(show_count):
            px = icons_start_x + pi * (icon_w + icon_gap)
            svg_parts.append(
                f'<rect x="{px}" y="{icons_y}" width="{icon_w}" height="{icon_h}" '
                f'fill="#fff" stroke="#000" stroke-width="0.8"/>'
            )
            # Horizontal cell divider (light gray)
            svg_parts.append(
                f'<line x1="{px + 1}" y1="{icons_y + icon_h // 2}" '
                f'x2="{px + icon_w - 1}" y2="{icons_y + icon_h // 2}" '
                f'stroke="#aaa" stroke-width="0.4"/>'
            )
            # Microinverter dot below each panel (shows module-level electronics)
            svg_parts.append(
                f'<circle cx="{px + icon_w // 2}" cy="{icons_y + icon_h + 2}" '
                f'r="1.5" fill="#cc0000" stroke="none"/>'
            )

        # Truncation label "+N more" when panels exceed max icons
        if str_panels_i > max_icons_per_str:
            px_extra = icons_start_x + max_icons_per_str * (icon_w + icon_gap)
            svg_parts.append(
                f'<text x="{px_extra + 1}" y="{icons_y + icon_h - 1}" '
                f'font-size="5.5" font-weight="700" font-family="Arial" '
                f'fill="#555">+{str_panels_i - max_icons_per_str}</text>'
            )

        # AC output marker (no +/− polarity — microinverter outputs are AC)
        svg_parts.append(
            f'<text x="{wire_end_x - 1}" y="{mid_y + 3}" '
            f'font-size="7" font-weight="700" font-family="Arial" fill="#cc0000">~</text>'
        )

    # ── Combiner bus / collection bar (right side of PV box) ─────────
    # For all systems: a vertical bar at collect_x collects string outputs.
    # Multi-string: vertical bar is labelled "CB" (DC Combiner Box).
    # Single-string: acts as a simple output terminal.
    bar_top = str_mid_ys[0]
    bar_bot = str_mid_ys[-1]
    svg_parts.append(
        f'<line x1="{collect_x}" y1="{bar_top}" x2="{collect_x}" y2="{bar_bot}" stroke="#000" stroke-width="1.8"/>'
    )
    # Output stub to box right edge at bus_y
    svg_parts.append(
        f'<line x1="{collect_x}" y1="{bus_y}" '
        f'x2="{pv_box_x + pv_box_w}" y2="{bus_y}" '
        f'stroke="#000" stroke-width="1.8"/>'
    )

    if n_branches > 1:
        # Branch collection bar label — "LC" (load-center input bus)
        cb_label_y = (bar_top + bar_bot) // 2
        svg_parts.append(
            f'<rect x="{collect_x - 9}" y="{cb_label_y - 8}" width="18" height="16" '
            f'fill="#fff" stroke="#555" stroke-width="0.8" rx="2"/>'
        )
        svg_parts.append(
            f'<text x="{collect_x}" y="{cb_label_y + 2}" text-anchor="middle" '
            f'font-size="6" font-weight="700" font-family="Arial" fill="#cc0000">AC</text>'
        )
        # Small AC node dots where branches join collection bar
        for sy in str_mid_ys:
            svg_parts.append(f'<circle cx="{collect_x}" cy="{sy}" r="2" fill="#cc0000" stroke="none"/>')

    # System summary below box
    pv_cx_new = pv_box_x + pv_box_w // 2
    svg_parts.append(
        f'<text x="{pv_cx_new}" y="{pv_box_y + pv_box_h + 9}" text-anchor="middle" '
        f'font-size="6" font-family="Arial" fill="#333">'
        f"{total_panels}× {renderer.panel.wattage}W = {total_kw:.2f} kW DC</text>"
    )

    # ── Supplemental ground rod at PV array (NEC 690.47 / CEC 64-104) ──
    # A supplemental grounding electrode (driven rod) is required adjacent to the
    # PV array and connected via GEC to the system grounding electrode conductor.
    # Symbol is drawn so its bottom aligns with the EGC bus at egc_y (bus_y+82).
    # The EGC bus is extended leftward to connect at this point (see Change 3).
    # Only rendered when there is sufficient vertical space between the PV array
    # box bottom and the EGC bus level (i.e., for typical 1–3 branch systems).
    _gec_rod_y = (bus_y + 82) - 25  # ground symbol occupies y → y+25; bottom = egc_y
    if _gec_rod_y >= pv_box_y + pv_box_h + 10:
        svg_parts.append(_ground(pv_cx_new, _gec_rod_y))
        svg_parts.append(
            f'<text x="{pv_cx_new + 11}" y="{_gec_rod_y + 8}" '
            f'font-size="6" font-weight="700" font-family="Arial" fill="#00aa00">'
            f"SUPP. GND ROD</text>"
        )
        svg_parts.append(
            f'<text x="{pv_cx_new + 11}" y="{_gec_rod_y + 17}" '
            f'font-size="5.5" font-family="Arial" fill="#00aa00">'
            f"GEC \u2014 #6 AWG CU</text>"
        )
        svg_parts.append(
            f'<text x="{pv_cx_new + 11}" y="{_gec_rod_y + 25}" '
            f'font-size="5.5" font-family="Arial" fill="#00aa00">'
            f"[{_cp} {'690.47' if _is_nec else '64-104'}]</text>"
        )

    pv_right_edge = pv_box_x + pv_box_w  # = 144

    # Tag circle 1 (matches Conductor & Conduit Schedule Tag 1: TRUNK CABLE, FREE AIR)
    tag_ax = (pv_right_edge + cx_dc_disc - 13) // 2  # ≈ midpoint
    svg_parts.append(f'<circle cx="{tag_ax}" cy="{bus_y - 28}" r="8" fill="#fff" stroke="#000" stroke-width="1"/>')
    svg_parts.append(
        f'<text x="{tag_ax}" y="{bus_y - 24}" text-anchor="middle" font-size="8" font-weight="700" font-family="Arial" fill="#000">1</text>'
    )

    # PV array → junction box (AC output from microinverters — all red/AC)
    svg_parts.append(
        f'<line x1="{pv_right_edge}" y1="{bus_y}" x2="{cx_dc_disc - 15}" y2="{bus_y}" stroke="#cc0000" stroke-width="2.5" marker-end="url(#arr-ac)"/>'
    )
    svg_parts.append(
        f'<text x="{tag_ax}" y="{bus_y - 12}" text-anchor="middle" font-size="6" font-family="Arial" fill="#cc0000">TRUNK CABLE (FREE AIR)</text>'
    )

    # ── 2. AC JUNCTION BOX (branch circuits combine here → PV load center) ──
    # Small box symbol for NEMA 3R junction box
    jb_sz = 22
    jb_x, jb_y = cx_dc_disc - jb_sz // 2, bus_y - jb_sz // 2
    svg_parts.append(
        f'<rect x="{jb_x}" y="{jb_y}" width="{jb_sz}" height="{jb_sz}" '
        f'fill="#fff" stroke="#000" stroke-width="1.5"/>'
    )
    svg_parts.append(
        f'<text x="{cx_dc_disc}" y="{bus_y - 1}" text-anchor="middle" '
        f'font-size="5.5" font-weight="700" font-family="Arial" fill="#000">JB</text>'
    )
    svg_parts.append(
        f'<text x="{cx_dc_disc}" y="{bus_y + 8}" text-anchor="middle" '
        f'font-size="5" font-family="Arial" fill="#555">NEMA 3R</text>'
    )
    svg_parts.append(
        f'<text x="{cx_dc_disc}" y="{bus_y + 28}" text-anchor="middle" font-size="6" font-family="Arial" fill="#333">JUNC. BOX</text>'
    )

    # Junction box → PV load center  (AC wire)
    svg_parts.append(
        f'<line x1="{cx_dc_disc + jb_sz // 2}" y1="{bus_y}" x2="{cx_inv - 33}" y2="{bus_y}" stroke="#cc0000" stroke-width="2.5" marker-end="url(#arr-ac)"/>'
    )

    # ── 3. PV LOAD CENTER (125A — combines AC branch circuits) ────────────
    inv_w, inv_h = 60, 44
    inv_x, inv_y = cx_inv - inv_w // 2, bus_y - inv_h // 2
    svg_parts.append(
        f'<rect x="{inv_x}" y="{inv_y}" width="{inv_w}" height="{inv_h}" fill="#f5f5f5" stroke="#000" stroke-width="2"/>'
    )
    # "LC" symbol — two vertical bus bars inside box
    for _bi in range(2):
        _bx = inv_x + 16 + _bi * 22
        svg_parts.append(
            f'<line x1="{_bx}" y1="{inv_y + 6}" x2="{_bx}" y2="{inv_y + inv_h - 6}" stroke="#000" stroke-width="2"/>'
        )
        for _ti in range(3):
            _ty = inv_y + 12 + _ti * 8
            svg_parts.append(
                f'<line x1="{_bx - 4}" y1="{_ty}" x2="{_bx + 4}" y2="{_ty}" stroke="#000" stroke-width="1"/>'
            )
    svg_parts.append(
        f'<text x="{cx_inv}" y="{bus_y + inv_h // 2 + 12}" text-anchor="middle" font-size="7" font-weight="700" font-family="Arial" fill="#000">PV LOAD CTR</text>'
    )
    svg_parts.append(
        f'<text x="{cx_inv}" y="{bus_y + inv_h // 2 + 21}" text-anchor="middle" font-size="6" font-family="Arial" fill="#333">125A / 240V 1φ</text>'
    )
    svg_parts.append(_ground(cx_inv, inv_y + inv_h))

    # Tag circle 2 (matches Conductor & Conduit Schedule Tag 2: J-BOX → PV Load Center)
    tag_2x = (cx_dc_disc + jb_sz // 2 + cx_inv - inv_w // 2) // 2
    svg_parts.append(f'<circle cx="{tag_2x}" cy="{bus_y - 28}" r="8" fill="#fff" stroke="#000" stroke-width="1"/>')
    svg_parts.append(
        f'<text x="{tag_2x}" y="{bus_y - 24}" text-anchor="middle" font-size="8" font-weight="700" font-family="Arial" fill="#000">2</text>'
    )
    svg_parts.append(
        f'<text x="{tag_2x}" y="{bus_y - 12}" text-anchor="middle" font-size="6" font-family="Arial" fill="#cc0000">{sys_ac_wire} {renderer._wire_type}</text>'
    )

    # Tag circle 3 (matches Conductor & Conduit Schedule Tag 3: Load Center → AC OCPD)
    tag_bx = (cx_inv + inv_w // 2 + cx_ac_ocpd - 14) // 2
    svg_parts.append(f'<circle cx="{tag_bx}" cy="{bus_y - 26}" r="8" fill="#fff" stroke="#000" stroke-width="1"/>')
    svg_parts.append(
        f'<text x="{tag_bx}" y="{bus_y - 22}" text-anchor="middle" font-size="8" font-weight="700" font-family="Arial" fill="#000">3</text>'
    )

    # Load center → AC OCPD
    svg_parts.append(
        f'<line x1="{cx_inv + inv_w // 2}" y1="{bus_y}" x2="{cx_ac_ocpd - 15}" y2="{bus_y}" stroke="#cc0000" stroke-width="2.5" marker-end="url(#arr-ac)"/>'
    )
    svg_parts.append(
        f'<text x="{tag_bx}" y="{bus_y - 11}" text-anchor="middle" font-size="6" font-family="Arial" fill="#cc0000">{sys_ac_wire} {renderer._wire_type}</text>'
    )

    # ── 4. AC OCPD ───────────────────────────────────────────────────
    osz = 24
    ox, oy = cx_ac_ocpd - osz // 2, bus_y - osz // 2
    svg_parts.append(
        f'<rect x="{ox}" y="{oy}" width="{osz}" height="{osz}" fill="#fff" stroke="#000" stroke-width="2"/>'
    )
    svg_parts.append(
        f'<line x1="{ox}" y1="{oy}" x2="{ox + osz}" y2="{oy + osz}" stroke="#000" stroke-width="1.5"/>'
    )
    svg_parts.append(
        f'<line x1="{ox + osz}" y1="{oy}" x2="{ox}" y2="{oy + osz}" stroke="#000" stroke-width="1.5"/>'
    )
    svg_parts.append(
        f'<text x="{cx_ac_ocpd}" y="{bus_y + osz // 2 + 11}" text-anchor="middle" font-size="7" font-weight="700" font-family="Arial" fill="#000">AC OCPD</text>'
    )
    svg_parts.append(
        f'<text x="{cx_ac_ocpd}" y="{bus_y + osz // 2 + 21}" text-anchor="middle" font-size="6" font-family="Arial" fill="#333">{ac_breaker}A 2P</text>'
    )

    # AC OCPD → main panel
    svg_parts.append(
        f'<line x1="{cx_ac_ocpd + osz // 2}" y1="{bus_y}" x2="{cx_main - 33}" y2="{bus_y}" stroke="#cc0000" stroke-width="2.5" marker-end="url(#arr-ac)"/>'
    )

    # ── 5. MAIN PANEL ────────────────────────────────────────────────
    mp_w, mp_h = 58, 66
    mp_x, mp_y = cx_main - mp_w // 2, bus_y - mp_h // 2
    svg_parts.append(
        f'<rect x="{mp_x}" y="{mp_y}" width="{mp_w}" height="{mp_h}" fill="#f5f5f5" stroke="#000" stroke-width="2"/>'
    )
    for bi in range(2):
        bx = mp_x + 16 + bi * 24
        svg_parts.append(
            f'<line x1="{bx}" y1="{mp_y + 6}" x2="{bx}" y2="{mp_y + mp_h - 6}" stroke="#000" stroke-width="2"/>'
        )
        for ti in range(4):
            ty = mp_y + 14 + ti * 11
            svg_parts.append(
                f'<line x1="{bx - 5}" y1="{ty}" x2="{bx + 5}" y2="{ty}" stroke="#000" stroke-width="1"/>'
            )
    svg_parts.append(
        f'<text x="{cx_main}" y="{bus_y + mp_h // 2 + 12}" text-anchor="middle" font-size="7" font-weight="700" font-family="Arial" fill="#000">MAIN PANEL</text>'
    )
    svg_parts.append(
        f'<text x="{cx_main}" y="{bus_y + mp_h // 2 + 21}" text-anchor="middle" font-size="6" font-family="Arial" fill="#333">{main_breaker}A / {bus_rating}A BUS</text>'
    )
    svg_parts.append(_ground(cx_main, mp_y + mp_h))

    # Tag circle 4 (matches Conductor & Conduit Schedule Tag 4: AC OCPD → Main Service Panel)
    tag_4x = (cx_ac_ocpd + osz // 2 + cx_main - mp_w // 2) // 2
    svg_parts.append(f'<circle cx="{tag_4x}" cy="{bus_y - 28}" r="8" fill="#fff" stroke="#000" stroke-width="1"/>')
    svg_parts.append(
        f'<text x="{tag_4x}" y="{bus_y - 24}" text-anchor="middle" font-size="8" font-weight="700" font-family="Arial" fill="#000">4</text>'
    )
    svg_parts.append(
        f'<text x="{tag_4x}" y="{bus_y - 12}" text-anchor="middle" font-size="6" font-family="Arial" fill="#cc0000">{sys_ac_wire} {renderer._wire_type}</text>'
    )

    # Main panel → meter
    svg_parts.append(
        f'<line x1="{cx_main + mp_w // 2}" y1="{bus_y}" x2="{cx_meter - 21}" y2="{bus_y}" stroke="#cc0000" stroke-width="2.5" marker-end="url(#arr-ac)"/>'
    )

    # ── 6. METER ─────────────────────────────────────────────────────
    mr = 19
    svg_parts.append(f'<circle cx="{cx_meter}" cy="{bus_y}" r="{mr}" fill="#fff" stroke="#000" stroke-width="2"/>')
    svg_parts.append(
        f'<text x="{cx_meter}" y="{bus_y + 4}" text-anchor="middle" font-size="8" font-weight="700" font-family="Arial" fill="#000">Wh</text>'
    )
    svg_parts.append(
        f'<text x="{cx_meter}" y="{bus_y + mr + 12}" text-anchor="middle" font-size="7" font-weight="700" font-family="Arial" fill="#000">METER</text>'
    )
    svg_parts.append(
        f'<text x="{cx_meter}" y="{bus_y + mr + 21}" text-anchor="middle" font-size="6" font-family="Arial" fill="#333">BI-DIR.</text>'
    )

    # Tag circle 5 (matches Conductor & Conduit Schedule Tag 5: Main Panel → Utility Meter)
    tag_5x = (cx_main + mp_w // 2 + cx_meter - mr) // 2
    svg_parts.append(f'<circle cx="{tag_5x}" cy="{bus_y - 28}" r="8" fill="#fff" stroke="#000" stroke-width="1"/>')
    svg_parts.append(
        f'<text x="{tag_5x}" y="{bus_y - 24}" text-anchor="middle" font-size="8" font-weight="700" font-family="Arial" fill="#000">5</text>'
    )
    svg_parts.append(
        f'<text x="{tag_5x}" y="{bus_y - 12}" text-anchor="middle" font-size="6" font-family="Arial" fill="#cc0000">{sys_ac_wire} {renderer._wire_type}</text>'
    )

    # Meter → grid
    svg_parts.append(
        f'<line x1="{cx_meter + mr}" y1="{bus_y}" x2="{cx_grid - 18}" y2="{bus_y}" stroke="#cc0000" stroke-width="2.5" marker-end="url(#arr-ac)"/>'
    )

    # ── 7. GRID ──────────────────────────────────────────────────────
    gw = 34
    for gi in range(5):
        gwi = gw - gi * 5
        gxi = cx_grid - gwi // 2
        svg_parts.append(
            f'<line x1="{gxi}" y1="{bus_y - 11 + gi * 5}" x2="{gxi + gwi}" y2="{bus_y - 11 + gi * 5}" stroke="#000" stroke-width="1.8"/>'
        )
    svg_parts.append(
        f'<text x="{cx_grid}" y="{bus_y + 22}" text-anchor="middle" font-size="7" font-weight="700" font-family="Arial" fill="#000">GRID</text>'
    )
    svg_parts.append(
        f'<text x="{cx_grid}" y="{bus_y + 31}" text-anchor="middle" font-size="6" font-family="Arial" fill="#333">UTILITY 240V 1φ</text>'
    )

    # ── EGC bus ──────────────────────────────────────────────────────
    # Bus extended left to pv_cx_new (= PV array center = 86) so it connects
    # to the supplemental ground rod symbol rendered below the PV array box.
    # This shows that the PV array equipment ground ties into the same EGC
    # that runs to the main panel — matching the Cubillas SLD grounding path.
    egc_y = bus_y + 82
    egc_x_left = pv_cx_new  # = pv_box_x + pv_box_w // 2 = 86
    svg_parts.append(
        f'<line x1="{egc_x_left}" y1="{egc_y}" x2="{cx_main}" y2="{egc_y}" stroke="#00aa00" stroke-width="1.5" stroke-dasharray="5,3"/>'
    )
    svg_parts.append(
        f'<text x="{(egc_x_left + cx_main) // 2}" y="{egc_y + 11}" text-anchor="middle" font-size="6.5" font-family="Arial" fill="#00aa00">EGC — {egc_wire} CU BARE</text>'
    )

    # ── Conductor legend (inline, bottom of circuit area) ─────────────
    lg_x = 30
    lg_y = 266
    svg_parts.append(
        f'<line x1="{lg_x}" y1="{lg_y}" x2="{lg_x + 32}" y2="{lg_y}" stroke="#cc0000" stroke-width="2.5"/>'
    )
    svg_parts.append(
        f'<text x="{lg_x + 37}" y="{lg_y + 4}" font-size="6.5" font-family="Arial" fill="#333">AC ({"MICROINVERTER" if renderer._is_micro else "INVERTER"} OUTPUT)</text>'
    )
    svg_parts.append(
        f'<line x1="{lg_x + 185}" y1="{lg_y}" x2="{lg_x + 217}" y2="{lg_y}" stroke="#00aa00" stroke-width="1.5" stroke-dasharray="4,2"/>'
    )
    svg_parts.append(
        f'<text x="{lg_x + 222}" y="{lg_y + 4}" font-size="6.5" font-family="Arial" fill="#333">EGC</text>'
    )

    # ── RIGHT COLUMN: ELECTRICAL NOTES ──────────────────────────────
    # In Cubillas PV-4, the right column below the PHOTOVOLTAIC SYSTEM
    # summary contains the numbered ELECTRICAL NOTES — not BRANCH CIRCUIT
    # DATA.  Moving notes here matches the Cubillas reference exactly.
    # BRANCH CIRCUIT DATA has moved to the bottom-left (alongside OCPD).
    en_x, en_y, en_w = 884, 158, 376
    _elec_notes_col = [
        f"All conductors shall be copper, 90\u00b0C rated min. [{_cp} {'310.16' if _is_nec else 'Rule 12-100'}]",
        f"PV output conductors: {renderer._wire_type} or USE-2, sunlight-resistant. [{_cp} {'690.31' if _is_nec else '64-058'}]",
        f"All DC conductors enclosed in conduit unless listed as PV wire. [{_cp} {'690.31' if _is_nec else '12-1010'}]",
        f"Conductors identified at every junction, pull box, termination. [{_cp} {'690.31(G)' if _is_nec else '64-214'}]",
        f"All metallic raceways bonded to grounding electrode system. [{_cp} {'250.96' if _is_nec else 'Rule 10-900'}]",
        f"AC OCPD rated \u2265125% of inverter max continuous output current. [{_cp} {'690.8' if _is_nec else '64-100'}]",
        f"Backfed PV breaker at opposite end of bus from main breaker. [{_cp} {'705.12' if _is_nec else '64-056'}]",
        f"Rapid shutdown: array \u226430 V within 30 s of initiating signal. [{_cp} {'690.12' if _is_nec else '64-218'}]",
        f"Disconnect locations marked with lamacoid labels. [{_cp} {'690.13' if _is_nec else '2-308'}]",
    ]
    _ln_h = 15  # line height per note
    en_h = 16 + len(_elec_notes_col) * _ln_h + 6
    svg_parts.append(
        f'<rect x="{en_x}" y="{en_y}" width="{en_w}" height="{en_h}" fill="#ffffff" stroke="#000" stroke-width="1.2"/>'
    )
    svg_parts.append(
        f'<rect x="{en_x}" y="{en_y}" width="{en_w}" height="13" fill="#e8e8e8" stroke="#000" stroke-width="1"/>'
    )
    svg_parts.append(
        f'<text x="{en_x + 8}" y="{en_y + 9}" font-size="8" font-weight="700" font-family="Arial" fill="#000">ELECTRICAL NOTES:</text>'
    )
    for _ei, _en in enumerate(_elec_notes_col):
        _eny = en_y + 16 + (_ei + 1) * _ln_h - 3
        svg_parts.append(
            f'<text x="{en_x + 8}" y="{_eny}" font-size="6.5" font-family="Arial" fill="#333">{_ei + 1}. {_en}</text>'
        )


    # ── LOWER TABLES: Module/Inverter specs, Branch Circuit, OCPD, Busbar — delegated ──
    build_sld_lower_tables(svg_parts, renderer, _calc)

    # ── Title block ──────────────────────────────────────────────────
    svg_parts.append(
        renderer._svg_title_block(
            1280,
            960,
            "E-601",
            "Single-Line Diagram",
            f"{total_kw:.2f} kW DC / {inv_kw:.2f} kW AC",
            "7 of 15",
            address,
            today,
        )
    )

    svg_content = "\n".join(svg_parts)
    return f'<div class="page"><svg width="100%" height="100%" viewBox="0 0 1280 960" xmlns="http://www.w3.org/2000/svg" style="background:#fff;">{svg_content}</svg></div>'

