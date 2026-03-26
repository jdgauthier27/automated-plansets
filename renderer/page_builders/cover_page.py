"""Page builder: Cover Page (PV-1 / T-00)
==========================================
Extracted from HtmlRenderer._build_cover_page.

This is the ONLY HTML-formatted page (not SVG). It uses HTML divs, tables,
and flexbox layout — very different from all other SVG-based pages.
"""

try:
    from engine.electrical_calc import calculate_monthly_production
    HAS_MONTHLY = True
except ImportError:
    HAS_MONTHLY = False


def _build_monthly_chart_svg(renderer, annual_kwh: float, width: int = 240, height: int = 80) -> str:
    """Build a compact SVG bar chart showing monthly production.

    Args:
        renderer: HtmlRenderer instance (needs _project).
        annual_kwh: Total annual kWh — used to generate monthly breakdown.
        width: SVG canvas width in px.
        height: SVG canvas height in px (bars only; labels add ~12px below).

    Returns:
        SVG string ready for embedding in HTML, or empty string if unavailable.
    """
    if not HAS_MONTHLY or not renderer._project:
        return ""
    try:
        months = calculate_monthly_production(renderer._project, annual_kwh)
    except Exception:
        return ""

    month_abbr = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"]
    n = len(months)
    pad_l, pad_r = 4, 4
    bar_area_w = width - pad_l - pad_r
    bar_w = bar_area_w / n
    bar_gap = max(1, bar_w * 0.15)
    bar_net = bar_w - bar_gap

    max_kwh = max((m.kwh for m in months), default=1) or 1
    chart_h = height - 14  # leave 14px for month labels

    bars = []
    for i, m in enumerate(months):
        x = pad_l + i * bar_w + bar_gap / 2
        bh = max(2, (m.kwh / max_kwh) * chart_h)
        y = chart_h - bh
        # Blue shading by production level
        if m.kwh >= max_kwh * 0.75:
            fill = "#1565c0"
        elif m.kwh >= max_kwh * 0.5:
            fill = "#1e88e5"
        else:
            fill = "#90caf9"
        bars.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_net:.1f}" height="{bh:.1f}" fill="{fill}" rx="1"/>')
        lx = x + bar_net / 2
        bars.append(
            f'<text x="{lx:.1f}" y="{chart_h + 11:.1f}" '
            f'font-size="7" fill="#555" text-anchor="middle">{month_abbr[i]}</text>'
        )
        if bh >= 12:
            bars.append(
                f'<text x="{lx:.1f}" y="{y - 1:.1f}" '
                f'font-size="6" fill="#333" text-anchor="middle">{m.kwh:.0f}</text>'
            )

    svg_h = height + 2
    return f'<svg width="{width}" height="{svg_h}" xmlns="http://www.w3.org/2000/svg">{"".join(bars)}</svg>'


def build_cover_page(
    renderer,
    address: str,
    total_panels: int,
    total_kw: float,
    total_kwh: float,
    today: str,
    insight,
    vicinity_map_b64: str = "",
    aerial_map_b64: str = "",
) -> str:
    """PV-1: Professional permit cover page matching Cubillas/All Valley Solar standard.

    Layout (1280×960px landscape):
      - Top header bar: company + "PHOTOVOLTAIC SYSTEM" title + address
      - System summary strip: 6-box horizontal (DC kW, AC kW, panels, kWh/yr, panel model, AHJ)
      - 3-column notes area: General Notes (17) | Electrical Notes (17) | Sheet Index + Governing Codes
      - Right column includes: Location Maps (vicinity + aerial) + Sheet Index + Governing Codes
      - Bottom title block: contractor info, revision tracking, date, sheet number
    """
    sheets = [
        ("T-00", "Cover Page"),
        ("G-01", "Electrical Notes"),
        ("A-101", "Site Plan"),
        ("A-102", "Racking and Framing Plan"),
        ("A-103", "String Plan"),
        ("A-104", "Attachment Detail"),
        ("E-601", "Electrical Line Diagram"),
        ("E-602", f"Specifications — {renderer._panel_model_short}"),
        ("E-603", "Signage"),
        ("E-604", "Placard"),
    ]

    sys_ac = renderer._calc_ac_kw(total_panels)  # 13 × 384VA = 4.99 kW AC

    # Roof segment data for system summary
    seg_azimuth = "175°"
    seg_pitch = "19°"
    if insight and insight.roof_segments:
        primary = insight.roof_segments[0]
        seg_azimuth = f"{primary.azimuth_deg:.0f}°"
        seg_pitch = f"{primary.pitch_deg:.0f}°"

    # ── Sheet index rows ─────────────────────────────────────────────
    sheet_rows = "".join(
        f"<tr>"
        f'<td style="padding:2px 6px; border:1px solid #ccc; font-weight:700; width:60px;">{sid}</td>'
        f'<td style="padding:2px 6px; border:1px solid #ccc;">{title}</td>'
        f"</tr>\n"
        for sid, title in sheets
    )

    # ── General Notes — from jurisdiction engine ────────────────────
    general_notes = renderer._jurisdiction.get_general_notes()
    # Strip leading numbers if present (engine may include "1. ", "2. " etc.)
    general_notes = [n.lstrip("0123456789. ") if n[0:1].isdigit() else n for n in general_notes]

    # ── Electrical Notes — from jurisdiction engine ──────────────────
    electrical_notes = renderer._jurisdiction.get_electrical_notes()
    electrical_notes = [n.lstrip("0123456789. ") if n and n[0:1].isdigit() else n for n in electrical_notes]

    def note_item(i, text):
        return (
            f'<div style="display:flex; margin-bottom:3px; line-height:1.35;">'
            f'<span style="min-width:18px; font-weight:700; color:#000;">{i}.</span>'
            f'<span style="color:#111;">{text}</span>'
            f"</div>"
        )

    gen_notes_html = "".join(note_item(i + 1, n) for i, n in enumerate(general_notes))
    elec_notes_html = "".join(note_item(i + 1, n) for i, n in enumerate(electrical_notes))

    # ── Map thumbnails (real or placeholder) ─────────────────────────
    _map_img_style = "width:100%; height:110px; object-fit:cover; border:1px solid #aaa; display:block;"
    _map_placeholder_style = (
        "width:100%; height:110px; background:#e8eef3; border:1px solid #aaa; "
        "display:flex; flex-direction:column; align-items:center; "
        "justify-content:center; box-sizing:border-box;"
    )
    if vicinity_map_b64:
        vicinity_map_html = (
            f'<img src="data:image/png;base64,{vicinity_map_b64}" style="{_map_img_style}" alt="Vicinity Map"/>'
        )
    else:
        vicinity_map_html = (
            f'<div style="{_map_placeholder_style}">'
            f'<svg width="32" height="32" viewBox="0 0 32 32" fill="none">'
            f'<circle cx="16" cy="14" r="6" stroke="#999" stroke-width="1.5" fill="none"/>'
            f'<line x1="16" y1="20" x2="16" y2="27" stroke="#999" stroke-width="1.5"/>'
            f'<line x1="4" y1="8" x2="28" y2="8" stroke="#ccc" stroke-width="1"/>'
            f'<line x1="4" y1="14" x2="8" y2="14" stroke="#ccc" stroke-width="1"/>'
            f'<line x1="24" y1="14" x2="28" y2="14" stroke="#ccc" stroke-width="1"/>'
            f"</svg>"
            f'<div style="font-size:8px; color:#999; margin-top:4px;">VICINITY MAP</div>'
            f'<div style="font-size:7px; color:#bbb;">Google Maps (no key)</div>'
            f"</div>"
        )
    if aerial_map_b64:
        aerial_map_html = (
            f'<img src="data:image/png;base64,{aerial_map_b64}" style="{_map_img_style}" alt="Aerial View"/>'
        )
    else:
        aerial_map_html = (
            f'<div style="{_map_placeholder_style}">'
            f'<svg width="32" height="32" viewBox="0 0 32 32" fill="none">'
            f'<rect x="4" y="4" width="24" height="24" rx="2" stroke="#999" stroke-width="1.5" fill="none"/>'
            f'<rect x="10" y="10" width="8" height="6" fill="#ccc"/>'
            f'<line x1="4" y1="16" x2="28" y2="16" stroke="#bbb" stroke-width="0.75" stroke-dasharray="2,2"/>'
            f'<line x1="16" y1="4" x2="16" y2="28" stroke="#bbb" stroke-width="0.75" stroke-dasharray="2,2"/>'
            f"</svg>"
            f'<div style="font-size:8px; color:#999; margin-top:4px;">AERIAL VIEW</div>'
            f'<div style="font-size:7px; color:#bbb;">Google Maps (no key)</div>'
            f"</div>"
        )

    # Monthly production chart
    monthly_chart_svg = _build_monthly_chart_svg(renderer, total_kwh)

    # Governing codes
    governing_codes_html = "".join(
        f'<div><b>{c["code"]}</b> — {c["title"]} ({c["edition"]})</div>'
        for c in renderer._jurisdiction.get_governing_codes()
    )

    # Utility info
    _municipality = renderer._project.municipality if renderer._project else ""
    _utility_name = renderer._jurisdiction.get_utility_info(_municipality).get("name", "Utility")

    # Target offset
    _offset_pct = 0
    if renderer._project and renderer._project.target_offset_pct:
        _offset_pct = renderer._project.target_offset_pct
    elif renderer._project and renderer._project.annual_consumption_kwh:
        _offset_pct = round(total_kwh / renderer._project.annual_consumption_kwh * 100)

    return f"""<div class="page">
<div style="width:1280px; height:960px; background:#ffffff; font-family:Arial,sans-serif; position:relative; overflow:hidden; box-sizing:border-box;">

  <!-- ═══ OUTER BORDER ═══ -->
  <div style="position:absolute; top:10px; left:10px; right:10px; bottom:10px; border:2px solid #000; pointer-events:none; z-index:10;"></div>

  <!-- ═══ PROJECT IDENTIFICATION HEADER (Cubillas standard) ═══ -->
  <!-- In Cubillas PV-1, the homeowner name is the largest/most prominent element,  -->
  <!-- centered with PHOTOVOLTAIC SYSTEM subtitle, address, and system specs below. -->
  <div style="margin:10px 10px 0 10px; border-bottom:2px solid #000; display:flex; align-items:stretch;">

    <!-- Left band: company name -->
    <div style="flex:0 0 130px; padding:8px 10px; border-right:1px solid #000; display:flex; flex-direction:column; justify-content:center; align-items:flex-start;">
      <div style="font-size:12px; font-weight:700; color:#000; letter-spacing:0.5px;">{renderer.company.upper()}</div>
      <div style="font-size:7.5px; color:#555; margin-top:3px; line-height:1.4;">Licensed Solar Contractor<br>{renderer._license_body}</div>
    </div>

    <!-- CENTER: Large homeowner title + system specs (matches Cubillas layout verbatim) -->
    <div style="flex:1; padding:10px 20px 8px; text-align:center; border-right:1px solid #000;">
      <div style="font-size:28px; font-weight:700; color:#000; letter-spacing:1px; line-height:1.1;">{address.split(",")[0].upper()} RESIDENCE</div>
      <div style="font-size:14px; font-weight:700; color:#000; margin-top:4px; letter-spacing:1px;">PHOTOVOLTAIC SYSTEM</div>
      <div style="font-size:10px; color:#222; margin-top:3px;">{address}</div>
      <div style="height:1px; background:#000; margin:6px 40px;"></div>
      <div style="font-size:11px; font-weight:700; color:#000; margin-top:4px;">
        SYSTEM SIZE: &nbsp;{total_kw:.2f} kW-DC &nbsp;| &nbsp;{sys_ac:.2f} kW-AC
      </div>
      <div style="font-size:10px; font-weight:700; color:#000; margin-top:5px;">
        MODULE: &nbsp;({total_panels}) {renderer.panel.name} [{renderer.panel.wattage}W] WITH
      </div>
      <div style="font-size:10px; font-weight:700; color:#000; margin-top:1px;">
        INTEGRATED MICROINVERTERS {renderer.INV_MODEL_SHORT}
      </div>
      <div style="font-size:10px; font-weight:700; color:#000; margin-top:5px;">
        MONITORING: &nbsp;ENPHASE ENVOY (AC GATEWAY)
      </div>
    </div>

    <!-- Right band: AHJ + date -->
    <div style="flex:0 0 150px; padding:8px 10px; display:flex; flex-direction:column; justify-content:center; align-items:flex-end;">
      <div style="font-size:9px; color:#333; text-align:right; line-height:1.6;">
        <div><b>AHJ:</b> {renderer._make_ahj_label(address)}</div>
        <div><b>Date:</b> {today}</div>
        <div style="margin-top:4px;"><b>Utility:</b> {_utility_name}</div>
        <div><b>Az:</b> {seg_azimuth} &nbsp; <b>Tilt:</b> {seg_pitch}</div>
        <div style="margin-top:4px;"><b>Est. Annual:</b> {total_kwh:,.0f} kWh</div>
        <div><b>Offset:</b> {_offset_pct:.0f}%</div>
      </div>
    </div>

  </div>

  <!-- ═══ MAIN CONTENT: 3 columns ═══ -->
  <div style="margin:0 10px; display:flex; height:648px; border-bottom:1px solid #000;">

    <!-- LEFT COLUMN: General Notes -->
    <div style="flex:0 0 420px; border-right:1px solid #000; padding:8px 10px; overflow:hidden;">
      <div style="font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:0.8px; border-bottom:1.5px solid #000; margin-bottom:6px; padding-bottom:3px; color:#000;">GENERAL NOTES</div>
      <div style="font-size:8px; color:#111; line-height:1.35;">
        {gen_notes_html}
      </div>
    </div>

    <!-- MIDDLE COLUMN: Electrical Notes -->
    <div style="flex:0 0 420px; border-right:1px solid #000; padding:8px 10px; overflow:hidden;">
      <div style="font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:0.8px; border-bottom:1.5px solid #000; margin-bottom:6px; padding-bottom:3px; color:#000;">ELECTRICAL NOTES</div>
      <div style="font-size:8px; color:#111; line-height:1.35;">
        {elec_notes_html}
      </div>
    </div>

    <!-- RIGHT COLUMN: Location Maps + Sheet Index + Governing Codes -->
    <div style="flex:1; padding:8px 10px; display:flex; flex-direction:column; gap:8px; overflow:hidden;">

      <!-- Location Maps -->
      <div>
        <div style="font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:0.8px; border-bottom:1.5px solid #000; margin-bottom:5px; padding-bottom:3px; color:#000;">LOCATION MAPS</div>
        <div style="display:flex; gap:6px;">
          <!-- Vicinity Map (roadmap) -->
          <div style="flex:1; overflow:hidden;">
            {vicinity_map_html}
            <div style="font-size:7px; color:#555; text-align:center; margin-top:2px; font-weight:700; letter-spacing:0.3px;">VICINITY MAP &nbsp;(ZOOM 14)</div>
          </div>
          <!-- Aerial View (satellite) -->
          <div style="flex:1; overflow:hidden;">
            {aerial_map_html}
            <div style="font-size:7px; color:#555; text-align:center; margin-top:2px; font-weight:700; letter-spacing:0.3px;">AERIAL VIEW &nbsp;(ZOOM 19)</div>
          </div>
        </div>
      </div>

      <!-- Sheet Index -->
      <div>
        <div style="font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:0.8px; border-bottom:1.5px solid #000; margin-bottom:4px; padding-bottom:3px; color:#000;">SHEET INDEX</div>
        <table style="width:100%; font-size:8px; border-collapse:collapse; color:#000;">
          {sheet_rows}
        </table>
      </div>

      <!-- Governing Codes -->
      <div>
        <div style="font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:0.8px; border-bottom:1.5px solid #000; margin-bottom:4px; padding-bottom:3px; color:#000;">GOVERNING CODES &amp; STANDARDS</div>
        <div style="font-size:7.5px; color:#111; line-height:1.6;">
          {governing_codes_html}
        </div>
      </div>

      <!-- Monthly Production Chart -->
      <div>
        <div style="font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:0.8px; border-bottom:1.5px solid #000; margin-bottom:4px; padding-bottom:3px; color:#000;">EST. MONTHLY PRODUCTION (kWh)</div>
        <div style="display:flex; justify-content:center;">
          {monthly_chart_svg}
        </div>
      </div>

      <!-- Existing System Note -->
      <div style="margin-top:auto; padding:5px 8px; border:1px solid #000; background:#ffffff;">
        <div style="font-size:7.5px; font-weight:700; text-transform:uppercase; margin-bottom:2px;">EXISTING SYSTEM</div>
        <div style="font-size:7.5px; color:#444;">No existing solar system on premises. New grid-tied installation only.</div>
      </div>

    </div>
  </div>

  <!-- ═══ BOTTOM TITLE BLOCK ═══ -->
  <div style="margin:0 10px; height:105px; display:flex; border-top:0;">

    <!-- Contractor Info -->
    <div style="flex:1; padding:6px 10px; border-right:1px solid #000; display:flex; flex-direction:column; justify-content:space-between;">
      <div>
        <div style="font-size:9px; font-weight:700; text-transform:uppercase; letter-spacing:0.5px; color:#000; border-bottom:1px solid #000; margin-bottom:3px; padding-bottom:2px;">CONTRACTOR / DESIGNER</div>
        <div style="font-size:11px; font-weight:700; color:#000;">{renderer.company}</div>
        <div style="font-size:8px; color:#333;">Licensed Solar Contractor — {renderer._license_body}</div>
        <div style="font-size:8px; color:#333;">Designer: {renderer.designer}</div>
      </div>
      <div style="border-top:1px solid #999; margin-top:4px; padding-top:3px;">
        <div style="font-size:7px; color:#777;">Contractor Signature: _________________________ &nbsp;&nbsp; Date: __________</div>
      </div>
    </div>

    <!-- Project Info -->
    <div style="flex:1.2; padding:6px 10px; border-right:1px solid #000;">
      <div style="font-size:9px; font-weight:700; text-transform:uppercase; letter-spacing:0.5px; color:#000; border-bottom:1px solid #000; margin-bottom:3px; padding-bottom:2px;">PROJECT</div>
      <div style="font-size:11px; font-weight:700; color:#000;">{address.split(",")[0].upper()} RESIDENCE</div>
      <div style="font-size:8px; color:#333;">{address}</div>
      <div style="font-size:8px; color:#333; margin-top:2px;">AHJ: {renderer._make_ahj_label(address)}</div>
      <div style="font-size:8px; color:#333;">Utility: {renderer._utility_name} (Net Metering)</div>
    </div>

    <!-- Revision Block -->
    <div style="flex:0 0 200px; padding:4px 6px; border-right:1px solid #000;">
      <div style="font-size:9px; font-weight:700; text-transform:uppercase; letter-spacing:0.5px; color:#000; border-bottom:1px solid #000; margin-bottom:3px; padding-bottom:2px;">REVISIONS</div>
      <table style="width:100%; font-size:7px; border-collapse:collapse; color:#000;">
        <tr style="background:#f0f0f0;">
          <th style="padding:2px 4px; border:1px solid #ccc; text-align:left;">REV</th>
          <th style="padding:2px 4px; border:1px solid #ccc; text-align:left;">DATE</th>
          <th style="padding:2px 4px; border:1px solid #ccc; text-align:left;">DESCRIPTION</th>
          <th style="padding:2px 4px; border:1px solid #ccc; text-align:left;">BY</th>
        </tr>
        <tr>
          <td style="padding:2px 4px; border:1px solid #ccc;">1</td>
          <td style="padding:2px 4px; border:1px solid #ccc;">{today}</td>
          <td style="padding:2px 4px; border:1px solid #ccc;">Initial Issue for Permit</td>
          <td style="padding:2px 4px; border:1px solid #ccc;">SC</td>
        </tr>
        <tr><td style="padding:2px 4px; border:1px solid #ccc;">&nbsp;</td><td style="padding:2px 4px; border:1px solid #ccc;"></td><td style="padding:2px 4px; border:1px solid #ccc;"></td><td style="padding:2px 4px; border:1px solid #ccc;"></td></tr>
        <tr><td style="padding:2px 4px; border:1px solid #ccc;">&nbsp;</td><td style="padding:2px 4px; border:1px solid #ccc;"></td><td style="padding:2px 4px; border:1px solid #ccc;"></td><td style="padding:2px 4px; border:1px solid #ccc;"></td></tr>
      </table>
    </div>

    <!-- Sheet Number -->
    <div style="flex:0 0 130px; padding:6px 8px; display:flex; flex-direction:column; align-items:center; justify-content:center; background:#f8f8f8;">
      <div style="font-size:8px; text-transform:uppercase; letter-spacing:0.5px; color:#666; margin-bottom:2px;">SHEET</div>
      <div style="font-size:36px; font-weight:700; color:#000; line-height:1;">T-00</div>
      <div style="font-size:9px; color:#444; margin-top:2px;">Cover Page</div>
      <div style="font-size:7px; color:#777; margin-top:4px;">1 of {len(sheets)}</div>
    </div>
  </div>

</div>
</div>"""
