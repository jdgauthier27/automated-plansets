"""
Page builder: Module Datasheet (PV-8.1)
========================================
Extracted from HtmlRenderer._build_module_datasheet_page.
"""


def build_module_datasheet_page(renderer, address: str, today: str) -> str:
    """Build the Module Datasheet sheet (PV-8.1).

    Args:
        renderer: HtmlRenderer instance (provides project, equipment properties)
        address: Project address string
        today: Date string for title block

    Returns:
        HTML string containing the page div with SVG content.
    """
    VW, VH = 1280, 960
    svg = []

    # ── Pull ALL specs from ProjectSpec (or fall back to legacy defaults) ──
    if renderer._project:
        p = renderer._project.panel
        mfr = p.manufacturer
        model = p.model
        model_short = p.model_short
        series = p.series or model_short
        technology = p.technology
        wattage = p.wattage_w
        voc = p.voc_v
        vmp = p.vmp_v
        isc = p.isc_a
        imp = p.imp_a
        efficiency = p.efficiency_pct
        max_sys_v = p.max_system_voltage_v
        max_fuse = p.max_series_fuse_a
        tc_pmax = p.temp_coeff_pmax_pct_per_c
        tc_voc = p.temp_coeff_voc_pct_per_c
        tc_isc = p.temp_coeff_isc_pct_per_c
        noct = p.noct_c
        length_mm = p.dimensions.length_mm
        width_mm = p.dimensions.width_mm
        depth_mm = p.dimensions.depth_mm
        weight_kg = p.weight_kg
        weight_lbs = p.weight_lbs
        cell_count = p.cell_count
        cell_type = p.cell_type
        bifacial = p.bifacial
        bifacial_gain = p.bifacial_gain_pct
        certs = p.certifications
        warranty_prod = p.warranty_product_years
        warranty_perf = p.warranty_performance_years
        cell_grid = p.datasheet_drawing.cell_grid
        power_tol = p.power_tolerance
    else:
        mfr, model, model_short, series = "LONGi Solar", "Hi-MO 7 LR7-54HGBB-455M", "LONGi Hi-MO 7", "Hi-MO 7"
        technology, wattage = "HPBC Bifacial", 455
        voc, vmp, isc, imp = 37.5, 31.7, 14.19, 13.56
        efficiency, max_sys_v, max_fuse = 22.8, 1500, 25
        tc_pmax, tc_voc, tc_isc, noct = -0.29, -0.24, 0.05, 45.0
        length_mm, width_mm, depth_mm = 1800, 1134, 30
        weight_kg, weight_lbs = 26.5, 58.4
        cell_count, cell_type = 132, "n-type TOPCon"
        bifacial, bifacial_gain = True, 10.0
        certs = ["IEC 61215", "IEC 61730", "UL 1703"]
        warranty_prod, warranty_perf = 25, 30
        cell_grid = [12, 11]
        power_tol = "+3/-0 %"

    length_in = length_mm / 25.4
    width_in = width_mm / 25.4
    depth_in = depth_mm / 25.4

    # ── Background & engineering border ──────────────────────────────
    svg.append('<rect width="1280" height="960" fill="#ffffff"/>')
    svg.append('<rect x="20" y="20" width="1240" height="820" fill="none" stroke="#000" stroke-width="2"/>')

    # ── Page header ──────────────────────────────────────────────────
    svg.append('<rect x="20" y="20" width="1240" height="42" fill="#f5f5f5" stroke="#000" stroke-width="1"/>')
    svg.append(
        f'<text x="640" y="37" text-anchor="middle" font-size="14" font-weight="700" '
        f'font-family="Arial" fill="#000000">{mfr.upper()} — {series.upper()}</text>'
    )
    svg.append(
        f'<text x="640" y="53" text-anchor="middle" font-size="11" font-weight="400" '
        f'font-family="Arial" fill="#444444">{model} | {technology} | {wattage} Wp</text>'
    )

    # ── Manufacturer logo area (text-based) ──────────────────────────
    svg.append('<rect x="30" y="72" width="320" height="340" fill="#ffffff" stroke="#ccc" stroke-width="0.5"/>')
    svg.append(
        f'<text x="190" y="105" text-anchor="middle" font-size="13" font-weight="700" '
        f'font-family="Arial" fill="#000000">{mfr}</text>'
    )
    svg.append(
        f'<text x="190" y="120" text-anchor="middle" font-size="9" '
        f'font-family="Arial" fill="#555">{model_short}</text>'
    )

    # ── Module diagram (front view schematic) ─────────────────────────
    # Draw a simplified front view of the 132-cell panel (12×11 layout)
    mod_x, mod_y = 50, 130
    mod_w, mod_h = 140, 230  # proportional to 1134×1800mm
    svg.append(
        f'<rect x="{mod_x}" y="{mod_y}" width="{mod_w}" height="{mod_h}" '
        f'fill="#1a2a3a" stroke="#000" stroke-width="1.5"/>'
    )
    # Junction box (center bottom)
    svg.append(
        f'<rect x="{mod_x + mod_w // 2 - 10}" y="{mod_y + mod_h - 16}" '
        f'width="20" height="10" fill="#333" stroke="#666" stroke-width="0.5"/>'
    )
    # Cell grid from catalog datasheet drawing hints
    cell_cols, cell_rows = cell_grid[0], cell_grid[1]
    margin_x, margin_y = 6, 6
    cw = (mod_w - 2 * margin_x) / cell_cols
    ch = (mod_h - 2 * margin_y - 20) / cell_rows
    for row in range(cell_rows):
        for col in range(cell_cols):
            cx = mod_x + margin_x + col * cw
            cy = mod_y + margin_y + row * ch
            svg.append(
                f'<rect x="{cx:.1f}" y="{cy:.1f}" width="{cw - 0.5:.1f}" height="{ch - 0.5:.1f}" '
                f'fill="#1a3060" stroke="#0a1a40" stroke-width="0.3"/>'
            )
            # Busbars (horizontal lines through each cell)
            for bi in range(1, 10):
                bx = cx + (cw - 0.5) * bi / 10
                svg.append(
                    f'<line x1="{bx:.1f}" y1="{cy:.1f}" x2="{bx:.1f}" y2="{cy + ch - 0.5:.1f}" '
                    f'stroke="rgba(120,160,220,0.3)" stroke-width="0.1"/>'
                )
    # Cable leads
    svg.append(
        f'<line x1="{mod_x + mod_w // 2 - 6}" y1="{mod_y + mod_h}" '
        f'x2="{mod_x + mod_w // 2 - 6}" y2="{mod_y + mod_h + 14}" stroke="#c00" stroke-width="1.5"/>'
    )
    svg.append(
        f'<line x1="{mod_x + mod_w // 2 + 6}" y1="{mod_y + mod_h}" '
        f'x2="{mod_x + mod_w // 2 + 6}" y2="{mod_y + mod_h + 14}" stroke="#000" stroke-width="1.5"/>'
    )
    svg.append(
        f'<text x="{mod_x + mod_w // 2 - 6}" y="{mod_y + mod_h + 24}" '
        f'text-anchor="middle" font-size="7" font-family="Arial" fill="#c00">+</text>'
    )
    svg.append(
        f'<text x="{mod_x + mod_w // 2 + 6}" y="{mod_y + mod_h + 24}" '
        f'text-anchor="middle" font-size="7" font-family="Arial" fill="#000">−</text>'
    )
    # Module dimension labels
    svg.append(
        f'<text x="{mod_x + mod_w + 6}" y="{mod_y + mod_h // 2}" '
        f'font-size="7" font-family="Arial" fill="#333" '
        f'transform="rotate(90,{mod_x + mod_w + 6},{mod_y + mod_h // 2})">{length_mm:.0f} mm ({length_in:.1f}")</text>'
    )
    svg.append(
        f'<text x="{mod_x + mod_w // 2}" y="{mod_y - 5}" '
        f'text-anchor="middle" font-size="7" font-family="Arial" fill="#333">{width_mm:.0f} mm ({width_in:.1f}")</text>'
    )
    svg.append(
        f'<text x="195" y="{mod_y + mod_h + 38}" text-anchor="middle" font-size="8" '
        f'font-weight="600" font-family="Arial" fill="#000000">FRONT VIEW (N.T.S.)</text>'
    )

    # ── Certifications row (from catalog) ────────────────────────────
    for i, cert in enumerate(certs[:6]):
        cx2 = 35 + i * 53
        svg.append(
            f'<rect x="{cx2}" y="408" width="48" height="18" fill="none" stroke="#000000" stroke-width="1" rx="3"/>'
        )
        svg.append(
            f'<text x="{cx2 + 24}" y="420" text-anchor="middle" font-size="7" '
            f'font-weight="600" font-family="Arial" fill="#000000">{cert}</text>'
        )

    # ── Electrical Characteristics table (left column, below cert) ────
    elec_y = 438
    svg.append(
        f'<text x="35" y="{elec_y}" font-size="10" font-weight="700" '
        f'font-family="Arial" fill="#000">ELECTRICAL CHARACTERISTICS (STC*)</text>'
    )
    elec_rows = [
        ("Peak Power (Pmax)", f"{wattage} W"),
        ("Open Circuit Voltage (Voc)", f"{voc} V"),
        ("Max Power Voltage (Vmp)", f"{vmp} V"),
        ("Short Circuit Current (Isc)", f"{isc} A"),
        ("Max Power Current (Imp)", f"{imp} A"),
        ("Module Efficiency", f"{efficiency} %"),
        ("Max System Voltage", f"{max_sys_v} V DC"),
        ("Max Series Fuse Rating", f"{max_fuse} A"),
        ("Power Tolerance", power_tol),
    ]
    row_h = 23
    for ri, (label, val) in enumerate(elec_rows):
        ry = elec_y + 12 + ri * row_h
        bg = "#f5f5f5" if ri % 2 == 0 else "#ffffff"
        svg.append(
            f'<rect x="30" y="{ry}" width="320" height="{row_h}" fill="{bg}" stroke="#ccc" stroke-width="0.5"/>'
        )
        svg.append(f'<text x="38" y="{ry + 15}" font-size="9" font-family="Arial" fill="#000">{label}</text>')
        svg.append(
            f'<text x="342" y="{ry + 15}" text-anchor="end" font-size="9" font-weight="600" '
            f'font-family="Arial" fill="#000000">{val}</text>'
        )

    # *STC footnote
    svg.append(
        f'<text x="30" y="{elec_y + 12 + len(elec_rows) * row_h + 12}" font-size="7" '
        f'font-family="Arial" fill="#666" font-style="italic">'
        f"* STC: Irradiance 1000 W/m², AM1.5, Cell Temp 25°C</text>"
    )

    # ── Temperature Coefficients (below electrical) ───────────────────
    tc_y = elec_y + 12 + len(elec_rows) * row_h + 28
    svg.append(
        f'<text x="35" y="{tc_y}" font-size="10" font-weight="700" '
        f'font-family="Arial" fill="#000">TEMPERATURE COEFFICIENTS</text>'
    )
    tc_rows = [
        ("Pmax (α)", f"{tc_pmax:+.2f} %/°C"),
        ("Voc (β)", f"{tc_voc:+.2f} %/°C"),
        ("Isc (γ)", f"{tc_isc:+.2f} %/°C"),
        ("NOCT", f"{noct:.0f} ± 2 °C"),
    ]
    for ri, (label, val) in enumerate(tc_rows):
        ry = tc_y + 12 + ri * row_h
        bg = "#f5f5f5" if ri % 2 == 0 else "#ffffff"
        svg.append(
            f'<rect x="30" y="{ry}" width="320" height="{row_h}" fill="{bg}" stroke="#ccc" stroke-width="0.5"/>'
        )
        svg.append(f'<text x="38" y="{ry + 15}" font-size="9" font-family="Arial" fill="#000">{label}</text>')
        svg.append(
            f'<text x="342" y="{ry + 15}" text-anchor="end" font-size="9" font-weight="600" '
            f'font-family="Arial" fill="#000000">{val}</text>'
        )

    # ════════════════════════════════
    # RIGHT COLUMN (x=360 to 1250)
    # ════════════════════════════════
    rx = 360

    # ── Mechanical Specifications ──────────────────────────────────────
    mech_y = 72
    svg.append(
        f'<text x="{rx}" y="{mech_y}" font-size="10" font-weight="700" '
        f'font-family="Arial" fill="#000">MECHANICAL SPECIFICATIONS</text>'
    )
    mech_rows = [
        (
            "Dimensions (L × W × H)",
            f"{length_mm:.0f} × {width_mm:.0f} × {depth_mm:.0f} mm  ({length_in:.1f} × {width_in:.1f} × {depth_in:.1f} in)",
        ),
        ("Weight", f"{weight_kg} kg  ({weight_lbs:.1f} lbs)"),
        ("Cell Technology", f"{cell_count} {cell_type}" + (" Bifacial" if bifacial else "")),
        ("Cell Configuration", f"{cell_count}-cell {technology} configuration"),
        ("Frame", "Anodized aluminum alloy"),
        ("Junction Box", "IP68, bypass diodes"),
        ("Connector", "MC4 compatible (± leads)"),
    ]
    for ri, (label, val) in enumerate(mech_rows):
        ry2 = mech_y + 14 + ri * row_h
        bg = "#f5f5f5" if ri % 2 == 0 else "#ffffff"
        svg.append(
            f'<rect x="{rx}" y="{ry2}" width="870" height="{row_h}" fill="{bg}" stroke="#ccc" stroke-width="0.5"/>'
        )
        svg.append(
            f'<text x="{rx + 8}" y="{ry2 + 15}" font-size="9" font-family="Arial" fill="#000">{label}</text>'
        )
        svg.append(
            f'<text x="{rx + 300}" y="{ry2 + 15}" font-size="9" font-weight="600" '
            f'font-family="Arial" fill="#000000">{val}</text>'
        )

    # ── Operating Conditions ──────────────────────────────────────────
    oc_y = mech_y + 14 + len(mech_rows) * row_h + 20
    svg.append(
        f'<text x="{rx}" y="{oc_y}" font-size="10" font-weight="700" '
        f'font-family="Arial" fill="#000">OPERATING CONDITIONS</text>'
    )
    oc_rows = [
        ("Operating Temperature Range", "−40°C to +85°C  (−40°F to +185°F)"),
        ("Max Wind Load", "3,600 Pa  (75.2 psf)"),
        ("Max Snow / Static Load", "5,400 Pa  (112.8 psf)"),
        ("Max Hail Speed", '23 m/s  (51 mph), ∅ 25mm (1")'),
        ("Relative Humidity", "0–100 %"),
        ("Altitude", "≤ 2000 m without derating"),
    ]
    for ri, (label, val) in enumerate(oc_rows):
        ry2 = oc_y + 14 + ri * row_h
        bg = "#f5f5f5" if ri % 2 == 0 else "#ffffff"
        svg.append(
            f'<rect x="{rx}" y="{ry2}" width="870" height="{row_h}" fill="{bg}" stroke="#ccc" stroke-width="0.5"/>'
        )
        svg.append(
            f'<text x="{rx + 8}" y="{ry2 + 15}" font-size="9" font-family="Arial" fill="#000">{label}</text>'
        )
        svg.append(
            f'<text x="{rx + 300}" y="{ry2 + 15}" font-size="9" font-weight="600" '
            f'font-family="Arial" fill="#000000">{val}</text>'
        )

    # ── BIPV / Bifacial Performance ──────────────────────────────────
    bif_y = oc_y + 14 + len(oc_rows) * row_h + 20
    svg.append(
        f'<text x="{rx}" y="{bif_y}" font-size="10" font-weight="700" '
        f'font-family="Arial" fill="#000">BIFACIAL PERFORMANCE</text>'
    )
    bif_rows = (
        [
            ("Bifaciality Factor", f"≥ {bifacial_gain:.0f} %" if bifacial else "N/A"),
            ("Rear Irradiance Gain", "5–25 % (site dependent)" if bifacial else "N/A"),
        ]
        if bifacial
        else []
    )
    for ri, (label, val) in enumerate(bif_rows):
        ry2 = bif_y + 14 + ri * row_h
        bg = "#f5f5f5" if ri % 2 == 0 else "#ffffff"
        svg.append(
            f'<rect x="{rx}" y="{ry2}" width="870" height="{row_h}" fill="{bg}" stroke="#ccc" stroke-width="0.5"/>'
        )
        svg.append(
            f'<text x="{rx + 8}" y="{ry2 + 15}" font-size="9" font-family="Arial" fill="#000">{label}</text>'
        )
        svg.append(
            f'<text x="{rx + 300}" y="{ry2 + 15}" font-size="9" font-weight="600" '
            f'font-family="Arial" fill="#000000">{val}</text>'
        )

    # ── I-V Curve diagram (simplified) ───────────────────────────────
    iv_x, iv_y = rx, bif_y + 14 + len(bif_rows) * row_h + 22
    iv_w, iv_h = 420, 160
    svg.append(
        f'<rect x="{iv_x}" y="{iv_y}" width="{iv_w}" height="{iv_h}" '
        f'fill="#f8f9fa" stroke="#000" stroke-width="1"/>'
    )
    svg.append(
        f'<text x="{iv_x + iv_w // 2}" y="{iv_y + 14}" text-anchor="middle" '
        f'font-size="9" font-weight="700" font-family="Arial" fill="#000">I-V CHARACTERISTIC CURVE (STC)</text>'
    )
    # Axes
    ax_ox, ax_oy = iv_x + 45, iv_y + iv_h - 25
    ax_w, ax_h = iv_w - 60, iv_h - 45
    svg.append(f'<line x1="{ax_ox}" y1="{iv_y + 20}" x2="{ax_ox}" y2="{ax_oy}" stroke="#000" stroke-width="1"/>')
    svg.append(f'<line x1="{ax_ox}" y1="{ax_oy}" x2="{ax_ox + ax_w}" y2="{ax_oy}" stroke="#000" stroke-width="1"/>')
    svg.append(
        f'<text x="{ax_ox + ax_w // 2}" y="{ax_oy + 18}" text-anchor="middle" '
        f'font-size="7" font-family="Arial" fill="#333">Voltage (V) — Voc = 37.5V</text>'
    )
    svg.append(
        f'<text x="{ax_ox - 10}" y="{ax_oy - ax_h // 2}" text-anchor="middle" '
        f'font-size="7" font-family="Arial" fill="#333" '
        f'transform="rotate(-90,{ax_ox - 10},{ax_oy - ax_h // 2})">Current (A) — Isc = 14.19A</text>'
    )

    # I-V curve path (parametric approximation)
    # Points: (0, Isc), knee at (Vmp, Imp), (Voc, 0)
    def iv_pt(v_norm, i_norm):
        return (ax_ox + v_norm * ax_w, ax_oy - i_norm * ax_h)

    # Normalized: Voc=37.5, Isc=14.19, Vmp=31.7, Imp=13.56
    # Alias for I-V curve rendering (local names used in the curve math below)
    # These shadow the outer variables intentionally for the curve drawing code
    imp_val = imp  # alias used by I-V curve code
    pts = []
    for step in range(21):
        v = voc * step / 20
        v_n = v / voc
        # Simplified single-diode model approximation
        if v_n < vmp / voc:
            i = isc - (isc - imp_val) * (v_n / (vmp / voc)) ** 0.15
        else:
            i = imp_val * max(0, 1 - ((v - vmp) / (voc - vmp)) ** 2.5)
        i_n = i / isc
        px2, py2 = iv_pt(v_n, i_n)
        pts.append(f"{px2:.1f},{py2:.1f}")
    svg.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="#000000" stroke-width="2"/>')
    # MPP marker
    mpp_x, mpp_y = iv_pt(vmp / voc, imp_val / isc)
    svg.append(f'<circle cx="{mpp_x:.1f}" cy="{mpp_y:.1f}" r="4" fill="#e05" stroke="none"/>')
    svg.append(
        f'<text x="{mpp_x + 6:.1f}" y="{mpp_y - 4:.1f}" font-size="7" font-family="Arial" fill="#e05">'
        f"MPP ({vmp}V, {imp_val}A)</text>"
    )
    # Tick marks
    for vi in [0, voc * 0.25, voc * 0.5, voc * 0.75, voc]:
        tx = ax_ox + (vi / voc) * ax_w
        svg.append(
            f'<line x1="{tx:.1f}" y1="{ax_oy}" x2="{tx:.1f}" y2="{ax_oy + 3}" stroke="#000" stroke-width="0.8"/>'
        )
        svg.append(
            f'<text x="{tx:.1f}" y="{ax_oy + 10}" text-anchor="middle" font-size="6" '
            f'font-family="Arial" fill="#555">{vi}</text>'
        )
    for ii in [0, isc * 0.33, isc * 0.67, isc]:
        ty = ax_oy - (ii / isc) * ax_h
        svg.append(
            f'<line x1="{ax_ox - 3}" y1="{ty:.1f}" x2="{ax_ox}" y2="{ty:.1f}" stroke="#000" stroke-width="0.8"/>'
        )
        svg.append(
            f'<text x="{ax_ox - 5}" y="{ty + 3:.1f}" text-anchor="end" font-size="6" '
            f'font-family="Arial" fill="#555">{ii}</text>'
        )

    # ── P-V Curve (power) ─────────────────────────────────────────────
    pv_x = iv_x + iv_w + 20
    pv_w, pv_h = iv_w - 10, iv_h
    svg.append(
        f'<rect x="{pv_x}" y="{iv_y}" width="{pv_w}" height="{pv_h}" '
        f'fill="#f8f9fa" stroke="#000" stroke-width="1"/>'
    )
    svg.append(
        f'<text x="{pv_x + pv_w // 2}" y="{iv_y + 14}" text-anchor="middle" '
        f'font-size="9" font-weight="700" font-family="Arial" fill="#000">POWER CURVE (STC)</text>'
    )
    pax_ox, pax_oy = pv_x + 45, iv_y + pv_h - 25
    pax_w, pax_h = pv_w - 60, pv_h - 45
    svg.append(f'<line x1="{pax_ox}" y1="{iv_y + 20}" x2="{pax_ox}" y2="{pax_oy}" stroke="#000" stroke-width="1"/>')
    svg.append(
        f'<line x1="{pax_ox}" y1="{pax_oy}" x2="{pax_ox + pax_w}" y2="{pax_oy}" stroke="#000" stroke-width="1"/>'
    )
    svg.append(
        f'<text x="{pax_ox + pax_w // 2}" y="{pax_oy + 18}" text-anchor="middle" '
        f'font-size="7" font-family="Arial" fill="#333">Voltage (V)</text>'
    )
    svg.append(
        f'<text x="{pax_ox - 10}" y="{pax_oy - pax_h // 2}" text-anchor="middle" '
        f'font-size="7" font-family="Arial" fill="#333" '
        f'transform="rotate(-90,{pax_ox - 10},{pax_oy - pax_h // 2})">Power (W)</text>'
    )
    # P-V curve
    p_max = 455
    pv_pts = []
    for step in range(21):
        v = voc * step / 20
        v_n = v / voc
        if v_n < vmp / voc:
            i = isc - (isc - imp_val) * (v_n / (vmp / voc)) ** 0.15
        else:
            i = imp_val * max(0, 1 - ((v - vmp) / (voc - vmp)) ** 2.5)
        p = v * i
        p_n = p / p_max
        ppx = pax_ox + v_n * pax_w
        ppy = pax_oy - p_n * pax_h
        pv_pts.append(f"{ppx:.1f},{ppy:.1f}")
    svg.append(f'<polyline points="{" ".join(pv_pts)}" fill="none" stroke="#c05020" stroke-width="2"/>')
    mpp_px = pax_ox + (vmp / voc) * pax_w
    mpp_py = pax_oy - (p_max / p_max) * pax_h
    svg.append(f'<circle cx="{mpp_px:.1f}" cy="{mpp_py:.1f}" r="4" fill="#e05" stroke="none"/>')
    svg.append(
        f'<text x="{mpp_px + 5:.1f}" y="{mpp_py - 4:.1f}" font-size="7" '
        f'font-family="Arial" fill="#e05">Pmax = 455W</text>'
    )

    # ── Footer note ───────────────────────────────────────────────────
    note_y = iv_y + iv_h + 16
    svg.append(
        f'<text x="{rx}" y="{note_y}" font-size="8" font-family="Arial" fill="#555">'
        f"NOTE: Specifications are nominal values and subject to manufacturing tolerances. "
        f"Refer to manufacturer's current datasheet for most recent specifications.</text>"
    )

    # ── Title block ───────────────────────────────────────────────────
    svg.append(
        renderer._svg_title_block(VW, VH, "R-001", "EQUIPMENT SPEC (MODULE)", f"{mfr} {model}", "11 of 15", address, today)
    )

    content = "\n".join(svg)
    return (
        f'<div class="page">'
        f'<svg width="100%" height="100%" viewBox="0 0 {VW} {VH}" '
        f'xmlns="http://www.w3.org/2000/svg" style="background:#fff;">'
        f"{content}</svg></div>"
    )
