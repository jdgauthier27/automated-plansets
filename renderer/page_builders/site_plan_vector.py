"""Page builder: Site Plan — Vector view + dispatcher (PV-3)
===========================================================
Professional engineering site plan on white paper.
Split from site_plan.py.
"""

import math

from renderer.shared.geo_utils import meters_per_pixel, azimuth_label
from renderer.svg_helpers import ft_in
from renderer.page_builders.site_plan_satellite import build_site_plan_satellite


def build_site_plan_page(
    renderer,
    insight,
    sat_b64: str,
    page_w: int,
    page_h: int,
    num_api_panels: int,
    address: str,
    today: str,
    placements,
    total_panels: int = 0,
) -> str:
    """PV-3: Professional architectural site plan."""
    if not insight or not insight.panels:
        return _build_blank_site_plan(renderer, address, today)

    _limit = total_panels or num_api_panels or 0
    panels = insight.panels[:_limit] if _limit else insight.panels
    mpp = meters_per_pixel(insight.lat)
    n_panels = len(panels)
    if renderer._project and renderer._project.num_panels and n_panels == renderer._project.num_panels:
        total_kw_display = round(renderer._project.system_dc_kw, 2)
    else:
        total_kw_display = round(n_panels * renderer.panel.kw, 2)

    if sat_b64:
        return build_site_plan_satellite(
            renderer, insight, sat_b64, page_w, page_h, panels, mpp, n_panels, total_kw_display, address, today
        )

    return _build_site_plan_vector(
        renderer, insight, panels, mpp, n_panels, total_kw_display, address, today
    )



def _build_site_plan_vector(
    renderer, insight, panels, mpp, n_panels, total_kw_display, address, today
) -> str:
    """PV-3 Vector: Professional engineering site plan on white paper."""
    # ══════════════════════════════════════════════════════════════
    # VECTOR SITE PLAN (no satellite image)
    # Professional architectural drawing on white paper
    # ══════════════════════════════════════════════════════════════
    VW, VH = 1280, 960
    svg = []

    # ── Defs: arrow markers, hatching patterns ─────────────────────
    svg.append("""<defs>
      <marker id="dim-arrow-l" markerWidth="8" markerHeight="6" refX="0" refY="3" orient="auto">
        <polygon points="0,3 8,0 8,6" fill="#000"/>
      </marker>
      <marker id="dim-arrow-r" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
        <polygon points="8,3 0,0 0,6" fill="#000"/>
      </marker>
      <pattern id="grass-hatch" patternUnits="userSpaceOnUse" width="8" height="8">
        <line x1="0" y1="8" x2="4" y2="0" stroke="#c0d8b0" stroke-width="0.5"/>
      </pattern>
      <pattern id="panel-hatch" patternUnits="userSpaceOnUse" width="6" height="6">
        <rect width="6" height="6" fill="#d0dff0"/>
        <line x1="0" y1="0" x2="6" y2="6" stroke="#8ab" stroke-width="0.3"/>
      </pattern>
    </defs>""")

    # ── Page border ────────────────────────────────────────────────
    svg.append(
        f'<rect x="15" y="15" width="{VW - 30}" height="{VH - 30}" fill="none" stroke="#000" stroke-width="2"/>'
    )

    # ── Compute real-world dimensions from panel data ──────────────
    # Get panel positions in meters relative to building center
    panel_positions_m = []
    for p in panels:
        dx_m = (p.center_lng - insight.lng) * math.cos(math.radians(insight.lat)) * 111319.5
        dy_m = (p.center_lat - insight.lat) * 111319.5
        panel_positions_m.append((dx_m, dy_m))

    # Panel cluster bounds in meters
    p_xs = [pos[0] for pos in panel_positions_m]
    p_ys = [pos[1] for pos in panel_positions_m]
    cluster_cx_m = (min(p_xs) + max(p_xs)) / 2
    cluster_cy_m = (min(p_ys) + max(p_ys)) / 2

    # Building dimensions — use GeoTIFF for accurate sizing
    _bldg_dims = renderer._building_dims_ft
    if _bldg_dims:
        bldg_w_m = _bldg_dims[0] * 0.3048  # ft → m
        bldg_h_m = _bldg_dims[1] * 0.3048
    else:
        bldg_w_m = 12.0  # typical house width
        bldg_h_m = 8.0  # typical house depth
        if insight.roof_segments:
            max_area = max(s.area_m2 for s in insight.roof_segments)
            bldg_w_m = max(10.0, math.sqrt(max_area * 2) * 1.2)
            bldg_h_m = max(7.0, math.sqrt(max_area * 2) * 0.8)

    # Property dimensions (typical suburban lot)
    lot_w_m = max(bldg_w_m + 8.0, 18.0)  # min 4m setback each side
    lot_h_m = max(bldg_h_m + 16.0, 30.0)  # front + back setbacks

    # Imperial vs metric for dimension labels
    use_imperial = (renderer._code_prefix == "NEC")

    def _dim_label(meters: float) -> str:
        """Format a dimension in imperial (ft-in) or metric (m) based on jurisdiction."""
        if use_imperial:
            return ft_in(meters / 0.3048)
        return f"{meters:.1f}m"

    # ── Scale: fit the property into the drawing area ──────────────
    draw_area_w = VW - 120  # margins for labels/dimensions
    draw_area_h = VH - 200  # top margin + title block
    draw_cx = VW / 2
    draw_top = 80

    scale_x = draw_area_w / lot_w_m
    scale_y = draw_area_h / lot_h_m
    scale = min(scale_x, scale_y) * 0.85  # leave breathing room
    scale_label = f"1:{1 / scale * 25.4:.0f}"  # approximate

    def m_to_px(mx, my):
        """Convert meters (relative to lot center) to SVG pixels."""
        return (draw_cx + mx * scale, draw_top + draw_area_h / 2 + my * scale)

    # ── Property boundary (dash-dot line) ──────────────────────────
    lot_x1, lot_y1 = m_to_px(-lot_w_m / 2, -lot_h_m / 2)
    lot_x2, lot_y2 = m_to_px(lot_w_m / 2, lot_h_m / 2)

    # Grass fill
    svg.append(
        f'<rect x="{lot_x1:.0f}" y="{lot_y1:.0f}" '
        f'width="{lot_x2 - lot_x1:.0f}" height="{lot_y2 - lot_y1:.0f}" '
        f'fill="url(#grass-hatch)" opacity="0.3"/>'
    )

    # Property line
    svg.append(
        f'<rect x="{lot_x1:.0f}" y="{lot_y1:.0f}" '
        f'width="{lot_x2 - lot_x1:.0f}" height="{lot_y2 - lot_y1:.0f}" '
        f'fill="none" stroke="#000" stroke-width="1.5" '
        f'stroke-dasharray="12,3,3,3"/>'
    )

    # Property line label
    svg.append(
        f'<text x="{(lot_x1 + lot_x2) / 2:.0f}" y="{lot_y1 - 6:.0f}" '
        f'text-anchor="middle" font-size="9" font-family="Arial" '
        f'fill="#444" font-style="italic">PROPERTY LINE (TYP.)</text>'
    )

    # ── Street at bottom ───────────────────────────────────────────
    street_y = lot_y2 + 20
    street_h = 50
    svg.append(
        f'<rect x="{lot_x1 - 40:.0f}" y="{street_y:.0f}" '
        f'width="{lot_x2 - lot_x1 + 80:.0f}" height="{street_h:.0f}" '
        f'fill="#e8e8e8" stroke="#000" stroke-width="0.5"/>'
    )
    # Center line
    svg.append(
        f'<line x1="{lot_x1 - 40:.0f}" y1="{street_y + street_h / 2:.0f}" '
        f'x2="{lot_x2 + 40:.0f}" y2="{street_y + street_h / 2:.0f}" '
        f'stroke="#888" stroke-width="1" stroke-dasharray="15,10"/>'
    )
    # Street name
    if renderer._project and renderer._project.street_name:
        street_name = renderer._project.street_name
    elif "," in address:
        import re as _re2

        _raw = address.split(",")[0].strip()
        street_name = _re2.sub(r"^\d+\s*", "", _raw).upper()
    else:
        street_name = "STREET"
    svg.append(
        f'<text x="{draw_cx:.0f}" y="{street_y + street_h / 2 + 4:.0f}" '
        f'text-anchor="middle" font-size="10" font-family="Arial" '
        f'fill="#555" font-weight="600" letter-spacing="2">{street_name.upper()}</text>'
    )

    # ── Sidewalk ───────────────────────────────────────────────────
    sw_y = street_y - 10
    svg.append(
        f'<rect x="{lot_x1 - 20:.0f}" y="{sw_y:.0f}" '
        f'width="{lot_x2 - lot_x1 + 40:.0f}" height="10" '
        f'fill="#f0f0f0" stroke="#999" stroke-width="0.3"/>'
    )

    # ── Driveway ──────────────────────────────────────────────────
    drv_w = 3.5 * scale
    drv_x = lot_x1 + (lot_x2 - lot_x1) * 0.25
    svg.append(
        f'<rect x="{drv_x:.0f}" y="{lot_y2 - 2:.0f}" '
        f'width="{drv_w:.0f}" height="{sw_y - lot_y2 + 12:.0f}" '
        f'fill="#d8d8d8" stroke="#999" stroke-width="0.5"/>'
    )
    svg.append(
        f'<text x="{drv_x + drv_w / 2:.0f}" y="{lot_y2 + 15:.0f}" '
        f'text-anchor="middle" font-size="7" font-family="Arial" fill="#777">DRVWY</text>'
    )

    # ── Building footprint (axis-aligned rectangle) ─────────────────
    bldg_offset_y = -2.0  # building offset from lot center (slightly toward front)

    bx1, by1 = m_to_px(-bldg_w_m / 2, bldg_offset_y - bldg_h_m / 2)
    bx2, by2 = m_to_px(bldg_w_m / 2, bldg_offset_y + bldg_h_m / 2)
    svg.append(
        f'<rect x="{bx1:.0f}" y="{by1:.0f}" '
        f'width="{bx2 - bx1:.0f}" height="{by2 - by1:.0f}" '
        f'fill="#f5f3f0" stroke="#000" stroke-width="2"/>'
    )

    # Building label
    svg.append(
        f'<text x="{(bx1 + bx2) / 2:.0f}" y="{(by1 + by2) / 2 + 4:.0f}" '
        f'text-anchor="middle" font-size="11" font-family="Arial" '
        f'fill="#333" font-weight="700">RESIDENCE</text>'
    )
    svg.append(
        f'<text x="{(bx1 + bx2) / 2:.0f}" y="{(by1 + by2) / 2 + 18:.0f}" '
        f'text-anchor="middle" font-size="9" font-family="Arial" fill="#666">'
        f"{_dim_label(bldg_w_m)} × {_dim_label(bldg_h_m)}</text>"
    )

    # ── Roof ridge line ────────────────────────────────────────────
    ridge_y = (by1 + by2) / 2
    svg.append(
        f'<line x1="{bx1:.0f}" y1="{ridge_y:.0f}" '
        f'x2="{bx2:.0f}" y2="{ridge_y:.0f}" '
        f'stroke="#000" stroke-width="1" stroke-dasharray="6,3"/>'
    )
    svg.append(
        f'<text x="{bx2 + 6:.0f}" y="{ridge_y + 4:.0f}" '
        f'font-size="8" font-family="Arial" fill="#555" font-style="italic">RIDGE</text>'
    )

    # ── Eave lines ─────────────────────────────────────────────────
    eave_overhang = 0.5 * scale  # 0.5m overhang
    svg.append(
        f'<line x1="{bx1 - eave_overhang:.0f}" y1="{by1:.0f}" '
        f'x2="{bx2 + eave_overhang:.0f}" y2="{by1:.0f}" '
        f'stroke="#666" stroke-width="0.8" stroke-dasharray="3,2"/>'
    )
    svg.append(
        f'<line x1="{bx1 - eave_overhang:.0f}" y1="{by2:.0f}" '
        f'x2="{bx2 + eave_overhang:.0f}" y2="{by2:.0f}" '
        f'stroke="#666" stroke-width="0.8" stroke-dasharray="3,2"/>'
    )

    # ── Solar panel array (south side of ridge) ────────────────────
    # Place panels on the south (bottom) side of the building
    # Use actual panel positions relative to cluster center, mapped onto south roof
    array_cx = (bx1 + bx2) / 2
    array_cy = (ridge_y + by2) / 2  # center of south roof face

    # Precompute panel corners in SVG coords (matching SolarMap.jsx geometry)
    half_w = insight.panel_width_m / 2
    half_h = insight.panel_height_m / 2
    corners_local = [(+half_w, +half_h), (+half_w, -half_h), (-half_w, -half_h), (-half_w, +half_h)]
    all_panel_corners = []
    for idx, p_obj in enumerate(panels):
        orientation = 90 if p_obj.orientation == "PORTRAIT" else 0
        seg_idx = getattr(p_obj, "segment_index", 0)
        seg = insight.roof_segments[seg_idx] if seg_idx < len(insight.roof_segments) else None
        azimuth = seg.azimuth_deg if seg else 180
        corner_svgs = []
        for x, y in corners_local:
            distance = math.sqrt(x * x + y * y)
            bearing_deg = math.degrees(math.atan2(y, x)) + orientation + azimuth
            bearing_rad = math.radians(bearing_deg)
            dx = distance * math.sin(bearing_rad)
            dy = distance * math.cos(bearing_rad)
            pmx, pmy = panel_positions_m[idx]
            rel_x = (pmx - cluster_cx_m + dx) * scale
            rel_y = -(pmy - cluster_cy_m + dy) * scale  # Y inverted
            corner_svgs.append((array_cx + rel_x, array_cy + rel_y))
        all_panel_corners.append(corner_svgs)

    # Array bounding box (from actual rotated corners)
    all_cx = [cx for corners in all_panel_corners for cx, cy in corners]
    all_cy = [cy for corners in all_panel_corners for cx, cy in corners]
    arr_x1 = min(all_cx)
    arr_y1 = min(all_cy)
    arr_x2 = max(all_cx)
    arr_y2 = max(all_cy)
    arr_w = arr_x2 - arr_x1
    arr_h = arr_y2 - arr_y1

    # Array background fill
    svg.append(
        f'<rect x="{arr_x1:.0f}" y="{arr_y1:.0f}" '
        f'width="{arr_w:.0f}" height="{arr_h:.0f}" '
        f'fill="url(#panel-hatch)" stroke="none"/>'
    )

    # Draw individual panels
    for idx, corner_svgs in enumerate(all_panel_corners):
        pts = " ".join(f"{cx:.1f},{cy:.1f}" for cx, cy in corner_svgs)
        svg.append(f'<polygon points="{pts}" fill="#ffffff" stroke="#000000" stroke-width="1"/>')
        # Cell grid lines (interpolated along edges)
        for ci in range(1, 3):
            t = ci / 3.0
            lx1 = corner_svgs[0][0] + t * (corner_svgs[1][0] - corner_svgs[0][0])
            ly1 = corner_svgs[0][1] + t * (corner_svgs[1][1] - corner_svgs[0][1])
            lx2 = corner_svgs[3][0] + t * (corner_svgs[2][0] - corner_svgs[3][0])
            ly2 = corner_svgs[3][1] + t * (corner_svgs[2][1] - corner_svgs[3][1])
            svg.append(
                f'<line x1="{lx1:.1f}" y1="{ly1:.1f}" '
                f'x2="{lx2:.1f}" y2="{ly2:.1f}" '
                f'stroke="#cccccc" stroke-width="0.5"/>'
            )
        # Panel number at centroid
        pcx = sum(cx for cx, cy in corner_svgs) / 4
        pcy = sum(cy for cx, cy in corner_svgs) / 4
        svg.append(
            f'<text x="{pcx:.1f}" y="{pcy + 3:.1f}" text-anchor="middle" '
            f'font-size="7" font-family="Arial" fill="#000000" font-weight="600">'
            f"{idx + 1}</text>"
        )

    # Array outline (bold dashed)
    svg.append(
        f'<rect x="{arr_x1 - 3:.0f}" y="{arr_y1 - 3:.0f}" '
        f'width="{arr_w + 6:.0f}" height="{arr_h + 6:.0f}" '
        f'fill="none" stroke="#000000" stroke-width="1.5" stroke-dasharray="8,4"/>'
    )

    # Array label with leader
    arr_label_x = arr_x2 + 40
    arr_label_y = arr_y1 + 10
    svg.append(
        f'<line x1="{arr_x2 + 3:.0f}" y1="{(arr_y1 + arr_y2) / 2:.0f}" '
        f'x2="{arr_label_x:.0f}" y2="{arr_label_y:.0f}" '
        f'stroke="#000" stroke-width="0.8"/>'
    )
    svg.append(f'<circle cx="{arr_x2 + 3:.0f}" cy="{(arr_y1 + arr_y2) / 2:.0f}" r="2" fill="#000"/>')

    # Array callout box
    cb_w, cb_h = 180, 70
    svg.append(
        f'<rect x="{arr_label_x:.0f}" y="{arr_label_y - 10:.0f}" '
        f'width="{cb_w}" height="{cb_h}" '
        f'fill="#fff" stroke="#000" stroke-width="1"/>'
    )
    svg.append(
        f'<text x="{arr_label_x + 8:.0f}" y="{arr_label_y + 4:.0f}" '
        f'font-size="10" font-weight="700" font-family="Arial" fill="#000">'
        f"PV ARRAY ({n_panels} PANELS)</text>"
    )
    svg.append(
        f'<text x="{arr_label_x + 8:.0f}" y="{arr_label_y + 18:.0f}" '
        f'font-size="9" font-family="Arial" fill="#333">'
        f"{renderer.panel.name}</text>"
    )
    svg.append(
        f'<text x="{arr_label_x + 8:.0f}" y="{arr_label_y + 31:.0f}" '
        f'font-size="9" font-family="Arial" fill="#333">'
        f"{total_kw_display:.2f} kW DC  |  {renderer.panel.wattage}W/panel</text>"
    )
    _orient_label = (
        renderer._project.panel_orientation.upper()
        if renderer._project and hasattr(renderer._project, "panel_orientation")
        else "PORTRAIT"
    )
    svg.append(
        f'<text x="{arr_label_x + 8:.0f}" y="{arr_label_y + 44:.0f}" '
        f'font-size="9" font-family="Arial" fill="#333">{_orient_label} orientation</text>'
    )

    # ── Array dimension lines ──────────────────────────────────────
    # Bottom dimension (array width)
    dim_y = arr_y2 + 20
    svg.append(
        f'<line x1="{arr_x1:.0f}" y1="{arr_y2:.0f}" '
        f'x2="{arr_x1:.0f}" y2="{dim_y + 5:.0f}" '
        f'stroke="#000" stroke-width="0.5"/>'
    )
    svg.append(
        f'<line x1="{arr_x2:.0f}" y1="{arr_y2:.0f}" '
        f'x2="{arr_x2:.0f}" y2="{dim_y + 5:.0f}" '
        f'stroke="#000" stroke-width="0.5"/>'
    )
    svg.append(
        f'<line x1="{arr_x1:.0f}" y1="{dim_y:.0f}" '
        f'x2="{arr_x2:.0f}" y2="{dim_y:.0f}" '
        f'stroke="#000" stroke-width="0.7" '
        f'marker-start="url(#dim-arrow-l)" marker-end="url(#dim-arrow-r)"/>'
    )
    svg.append(
        f'<text x="{(arr_x1 + arr_x2) / 2:.0f}" y="{dim_y + 14:.0f}" '
        f'text-anchor="middle" font-size="9" font-family="Arial" fill="#000">'
        f"{arr_w / scale:.2f} m</text>"
    )

    # Right dimension (array depth)
    dim_x = arr_x1 - 20
    svg.append(
        f'<line x1="{arr_x1:.0f}" y1="{arr_y1:.0f}" '
        f'x2="{dim_x - 5:.0f}" y2="{arr_y1:.0f}" '
        f'stroke="#000" stroke-width="0.5"/>'
    )
    svg.append(
        f'<line x1="{arr_x1:.0f}" y1="{arr_y2:.0f}" '
        f'x2="{dim_x - 5:.0f}" y2="{arr_y2:.0f}" '
        f'stroke="#000" stroke-width="0.5"/>'
    )
    svg.append(
        f'<line x1="{dim_x:.0f}" y1="{arr_y1:.0f}" '
        f'x2="{dim_x:.0f}" y2="{arr_y2:.0f}" '
        f'stroke="#000" stroke-width="0.7" '
        f'marker-start="url(#dim-arrow-l)" marker-end="url(#dim-arrow-r)"/>'
    )
    svg.append(
        f'<text x="{dim_x - 5:.0f}" y="{(arr_y1 + arr_y2) / 2:.0f}" '
        f'text-anchor="middle" font-size="9" font-family="Arial" fill="#000" '
        f'transform="rotate(-90,{dim_x - 5:.0f},{(arr_y1 + arr_y2) / 2:.0f})">'
        f"{arr_h / scale:.2f} m</text>"
    )

    # ── Property dimension lines ───────────────────────────────────
    # Top (lot width)
    pdim_y = lot_y1 - 18
    svg.append(
        f'<line x1="{lot_x1:.0f}" y1="{lot_y1:.0f}" '
        f'x2="{lot_x1:.0f}" y2="{pdim_y - 3:.0f}" stroke="#000" stroke-width="0.5"/>'
    )
    svg.append(
        f'<line x1="{lot_x2:.0f}" y1="{lot_y1:.0f}" '
        f'x2="{lot_x2:.0f}" y2="{pdim_y - 3:.0f}" stroke="#000" stroke-width="0.5"/>'
    )
    svg.append(
        f'<line x1="{lot_x1:.0f}" y1="{pdim_y:.0f}" '
        f'x2="{lot_x2:.0f}" y2="{pdim_y:.0f}" '
        f'stroke="#000" stroke-width="0.7" '
        f'marker-start="url(#dim-arrow-l)" marker-end="url(#dim-arrow-r)"/>'
    )
    svg.append(
        f'<text x="{(lot_x1 + lot_x2) / 2:.0f}" y="{pdim_y - 4:.0f}" '
        f'text-anchor="middle" font-size="9" font-family="Arial" fill="#000">'
        f"{_dim_label(lot_w_m)}</text>"
    )

    # Left side (lot depth)
    pdim_x = lot_x1 - 18
    svg.append(
        f'<line x1="{lot_x1:.0f}" y1="{lot_y1:.0f}" '
        f'x2="{pdim_x - 3:.0f}" y2="{lot_y1:.0f}" stroke="#000" stroke-width="0.5"/>'
    )
    svg.append(
        f'<line x1="{lot_x1:.0f}" y1="{lot_y2:.0f}" '
        f'x2="{pdim_x - 3:.0f}" y2="{lot_y2:.0f}" stroke="#000" stroke-width="0.5"/>'
    )
    svg.append(
        f'<line x1="{pdim_x:.0f}" y1="{lot_y1:.0f}" '
        f'x2="{pdim_x:.0f}" y2="{lot_y2:.0f}" '
        f'stroke="#000" stroke-width="0.7" '
        f'marker-start="url(#dim-arrow-l)" marker-end="url(#dim-arrow-r)"/>'
    )
    svg.append(
        f'<text x="{pdim_x - 5:.0f}" y="{(lot_y1 + lot_y2) / 2:.0f}" '
        f'text-anchor="middle" font-size="9" font-family="Arial" fill="#000" '
        f'transform="rotate(-90,{pdim_x - 5:.0f},{(lot_y1 + lot_y2) / 2:.0f})">'
        f"{_dim_label(lot_h_m)}</text>"
    )

    # ── Building setback dimensions ────────────────────────────────
    # Front setback (building to property line at bottom)
    front_setback_m = (lot_h_m / 2) - (bldg_offset_y + bldg_h_m / 2)
    fs_y1 = by2
    fs_y2 = lot_y2
    fs_x = bx2 + 30
    svg.append(
        f'<line x1="{fs_x:.0f}" y1="{fs_y1:.0f}" '
        f'x2="{fs_x:.0f}" y2="{fs_y2:.0f}" '
        f'stroke="#cc0000" stroke-width="0.7" '
        f'marker-start="url(#dim-arrow-l)" marker-end="url(#dim-arrow-r)"/>'
    )
    svg.append(
        f'<text x="{fs_x + 5:.0f}" y="{(fs_y1 + fs_y2) / 2 + 3:.0f}" '
        f'font-size="8" font-family="Arial" fill="#cc0000">'
        f"{_dim_label(front_setback_m)} SETBACK</text>"
    )

    # ── Equipment callout symbols (UM / MP / LC / INV / DCD) ──────────
    # Professional style: circle bubble with code + horizontal leader + description box

    def _equip_callout(cx, cy, code, label1, label2="", right=True, lw=185):
        """Return SVG string for a professional equipment callout symbol."""
        r = 12
        parts = []
        # Circle bubble with abbreviated code
        parts.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="#ffffff" stroke="#000000" stroke-width="1.5"/>'
        )
        parts.append(
            f'<text x="{cx:.1f}" y="{cy + 4:.1f}" text-anchor="middle" '
            f'font-size="8" font-weight="700" font-family="Arial" fill="#000">{code}</text>'
        )
        # Horizontal leader line
        lx1 = cx + (r if right else -r)
        lx2 = cx + (r + 22 if right else -(r + 22))
        parts.append(
            f'<line x1="{lx1:.1f}" y1="{cy:.1f}" x2="{lx2:.1f}" y2="{cy:.1f}" stroke="#000" stroke-width="0.8"/>'
        )
        # Description box
        bx = lx2 if right else lx2 - lw
        bh = 26 if label2 else 18
        by_box = cy - bh / 2
        parts.append(
            f'<rect x="{bx:.1f}" y="{by_box:.1f}" width="{lw}" height="{bh}" '
            f'fill="#f8f8f8" stroke="#000" stroke-width="0.8"/>'
        )
        ty1 = cy + (-4 if label2 else 4)
        parts.append(
            f'<text x="{bx + 5:.1f}" y="{ty1:.1f}" '
            f'font-size="8" font-weight="700" font-family="Arial" fill="#000">{label1}</text>'
        )
        if label2:
            parts.append(
                f'<text x="{bx + 5:.1f}" y="{cy + 10:.1f}" '
                f'font-size="7" font-family="Arial" fill="#555">{label2}</text>'
            )
        return "\n".join(parts)

    # Get primary roof segment data (used here and by roof detail box below)
    _seg0 = insight.roof_segments[0] if insight.roof_segments else None
    _az_s = round(_seg0.azimuth_deg) if _seg0 else 180
    _pit_s = round(_seg0.pitch_deg) if _seg0 else 18

    # Equipment center positions (right side = JB/LC; left side = MP/UM)
    # Microinverter system: NO DCD (DC disconnect), NO separate INV box.
    # JB = Junction Box (NEMA 3R) where AC trunk cables from roof merge.
    _jb_cx = bx2 + 38
    _jb_cy = ridge_y + 28  # Junction box (AC trunk merge)
    _lc_cx = bx2 + 38
    _lc_cy = ridge_y + 80  # Load center / AC OCPD
    _mp_cx = bx1 - 38
    _mp_cy = (by1 + by2) * 0.55  # Main service panel
    _um_cx = bx1 - 38
    _um_cy = by2 + 35  # Utility meter

    # Draw equipment callout symbols (all AC — no DC disconnect in microinverter system)
    svg.append(
        _equip_callout(
            _jb_cx,
            _jb_cy,
            "JB",
            "JUNCTION BOX (NEMA 3R)",
            f"AC TRUNK MERGE — {renderer._code_prefix} {'300.10' if renderer._code_prefix == 'NEC' else '12-3000'}",
            right=True,
            lw=215,
        )
    )
    svg.append(
        _equip_callout(
            _lc_cx,
            _lc_cy,
            "LC",
            "LOAD CENTER / AC OCPD",
            f"30A 2P / 240V BACKFED — {renderer._code_prefix} {'705.12' if renderer._code_prefix == 'NEC' else '64-056'}",
            right=True,
            lw=215,
        )
    )
    svg.append(
        _equip_callout(_mp_cx, _mp_cy, "MP", "MAIN SERVICE PANEL", "200A / 240V — INTERIOR", right=False, lw=190)
    )
    svg.append(
        _equip_callout(
            _um_cx, _um_cy, "UM", "UTILITY METER", f"{renderer._utility_name} — BIDIRECTIONAL", right=False, lw=200
        )
    )

    # ── Conduit runs (dashed lines connecting equipment) ──────────────
    # All conduit runs are AC in a microinverter system — no DC conduit.
    # AC trunk: Array right edge → JB (AC trunk cables exit roof at eave)
    svg.append(
        f'<line x1="{arr_x2:.1f}" y1="{(arr_y1 + arr_y2) / 2:.1f}" '
        f'x2="{_jb_cx - 12:.1f}" y2="{_jb_cy:.1f}" '
        f'stroke="#cc0000" stroke-width="1.5" stroke-dasharray="8,4"/>'
    )
    # JB → LC (AC conduit through attic/wall)
    svg.append(
        f'<line x1="{_jb_cx - 12:.1f}" y1="{_jb_cy:.1f}" '
        f'x2="{_lc_cx - 12:.1f}" y2="{_lc_cy:.1f}" '
        f'stroke="#cc0000" stroke-width="1.5" stroke-dasharray="8,4"/>'
    )
    # LC → MP (AC service conductors, horizontal run through wall)
    svg.append(
        f'<line x1="{_lc_cx - 12:.1f}" y1="{_lc_cy:.1f}" '
        f'x2="{_mp_cx + 12:.1f}" y2="{_mp_cy:.1f}" '
        f'stroke="#cc0000" stroke-width="1.5" stroke-dasharray="8,4"/>'
    )
    # MP → UM (service entrance)
    svg.append(
        f'<line x1="{_mp_cx:.1f}" y1="{_mp_cy + 12:.1f}" '
        f'x2="{_um_cx:.1f}" y2="{_um_cy - 12:.1f}" '
        f'stroke="#cc0000" stroke-width="1.5" stroke-dasharray="8,4"/>'
    )

    # ── System legend (left margin, top area) ────────────────────────
    leg_x, leg_y_s = 28, 175
    leg_w = 310
    legend_entries = [
        ("line", "#cc0000", "8,4", f'AC CONDUIT ({renderer._wire_type} IN \u00be" EMT)'),
        ("line", "#cc0000", "3,2", "FIRE SETBACK LINE (3\u2019-0\u201d TYP.)"),
        ("sym", "UM", "", "UTILITY METER"),
        ("sym", "MP", "", "MAIN SERVICE PANEL"),
        ("sym", "JB", "", "JUNCTION BOX (NEMA 3R)"),
        ("sym", "LC", "", "LOAD CENTER / AC OCPD"),
    ]
    leg_row_h = 18
    # +37px for the module/microinverter panel-icon entry appended after loop
    _mi_entry_h = 37
    leg_h_s = 18 + len(legend_entries) * leg_row_h + _mi_entry_h + 4
    svg.append(
        f'<rect x="{leg_x}" y="{leg_y_s}" width="{leg_w}" height="{leg_h_s}" '
        f'fill="#fff" stroke="#000" stroke-width="1"/>'
    )
    svg.append(
        f'<rect x="{leg_x}" y="{leg_y_s}" width="{leg_w}" height="18" '
        f'fill="#d8d8d8" stroke="#000" stroke-width="1"/>'
    )
    svg.append(
        f'<text x="{leg_x + leg_w // 2}" y="{leg_y_s + 13}" text-anchor="middle" '
        f'font-size="9" font-weight="700" font-family="Arial" fill="#000">SYSTEM LEGEND</text>'
    )
    for li, entry in enumerate(legend_entries):
        ily = leg_y_s + 18 + li * leg_row_h
        if li > 0:
            svg.append(
                f'<line x1="{leg_x + 1}" y1="{ily}" x2="{leg_x + leg_w - 1}" y2="{ily}" '
                f'stroke="#ddd" stroke-width="0.5"/>'
            )
        item_cy = ily + leg_row_h / 2
        if entry[0] == "line":
            _, col, dash, lbl = entry
            svg.append(
                f'<line x1="{leg_x + 8}" y1="{item_cy:.1f}" '
                f'x2="{leg_x + 48}" y2="{item_cy:.1f}" '
                f'stroke="{col}" stroke-width="1.5" stroke-dasharray="{dash}"/>'
            )
            svg.append(
                f'<text x="{leg_x + 55}" y="{item_cy + 4:.1f}" font-size="8" '
                f'font-family="Arial" fill="#000">{lbl}</text>'
            )
        else:
            _, code, _, lbl = entry
            svg.append(
                f'<circle cx="{leg_x + 18}" cy="{item_cy:.1f}" r="9" fill="#fff" stroke="#000" stroke-width="1"/>'
            )
            svg.append(
                f'<text x="{leg_x + 18}" y="{item_cy + 3:.1f}" text-anchor="middle" '
                f'font-size="6" font-weight="700" font-family="Arial" fill="#000">{code}</text>'
            )
            svg.append(
                f'<text x="{leg_x + 33}" y="{item_cy + 4:.1f}" font-size="8" '
                f'font-family="Arial" fill="#000">{lbl}</text>'
            )

    # ── Module / microinverter entry appended below equipment symbols ──────
    # Matches Cubillas PV-3 System Legend: small panel icon + model description.
    _vp_mi_y = leg_y_s + 18 + len(legend_entries) * leg_row_h + 4
    _vp_mi_icon_x = leg_x + 5
    _vp_mi_icon_w, _vp_mi_icon_h = 28, 16
    svg.append(
        f'<line x1="{leg_x + 1}" y1="{_vp_mi_y}" x2="{leg_x + leg_w - 1}" '
        f'y2="{_vp_mi_y}" stroke="#ddd" stroke-width="0.5"/>'
    )
    svg.append(
        f'<rect x="{_vp_mi_icon_x}" y="{_vp_mi_y + 2}" width="{_vp_mi_icon_w}" '
        f'height="{_vp_mi_icon_h}" fill="#ffffff" stroke="#000000" stroke-width="1"/>'
    )
    for _ci in range(1, 3):
        _gcx = _vp_mi_icon_x + _ci * _vp_mi_icon_w // 3
        svg.append(
            f'<line x1="{_gcx}" y1="{_vp_mi_y + 4}" '
            f'x2="{_gcx}" y2="{_vp_mi_y + _vp_mi_icon_h - 2}" '
            f'stroke="#aaaaaa" stroke-width="0.5"/>'
        )
    svg.append(
        f'<line x1="{_vp_mi_icon_x + 2}" y1="{_vp_mi_y + _vp_mi_icon_h // 2 + 2}" '
        f'x2="{_vp_mi_icon_x + _vp_mi_icon_w - 2}" '
        f'y2="{_vp_mi_y + _vp_mi_icon_h // 2 + 2}" '
        f'stroke="#aaaaaa" stroke-width="0.5"/>'
    )
    _vp_mi_lines = [
        f"({n_panels}) {renderer.panel.name} [{renderer.panel.wattage}W]",
        f"WITH {renderer.INV_MODEL_SHORT} [240V]",
        "MICROINVERTERS MOUNTED UNDER EACH MODULE.",
    ]
    for _li, _lt in enumerate(_vp_mi_lines):
        svg.append(
            f'<text x="{leg_x + 38}" y="{_vp_mi_y + 8 + _li * 10}" '
            f'font-size="6" font-family="Arial" fill="#000">{_lt}</text>'
        )

    # ── Additional notes box (left margin, above scale bar) ─────────
    an_x, an_y = 28, VH - 290
    an_w = 440
    notes_items = [
        "1. CONDUIT PATH SHOWN DIAGRAMMATICALLY. FINAL ROUTING TO BE FIELD-VERIFIED BY INSTALLER.",
        f'2. ALL DC CONDUIT: \u00be" EMT MINIMUM, GROUNDED AND BONDED PER {renderer._code_prefix} {"690.43" if renderer._code_prefix == "NEC" else "64-100"}.',
        f'3. ALL AC CONDUIT: \u00be" EMT MINIMUM PER {"UL listed" if renderer._code_prefix == "NEC" else "CSA C22.2 No.211.2"}.',
        "4. CONDUIT PENETRATIONS THROUGH ROOF/WALLS TO BE SEALED WEATHERTIGHT.",
        "5. EQUIPMENT LOCATIONS SHOWN ARE APPROXIMATE — VERIFY ON SITE BEFORE INSTALLATION.",
    ]
    an_row_h = 14
    an_h = 18 + len(notes_items) * an_row_h + 6
    svg.append(
        f'<rect x="{an_x}" y="{an_y}" width="{an_w}" height="{an_h}" fill="#fff" stroke="#000" stroke-width="1"/>'
    )
    svg.append(
        f'<rect x="{an_x}" y="{an_y}" width="{an_w}" height="18" fill="#d8d8d8" stroke="#000" stroke-width="1"/>'
    )
    svg.append(
        f'<text x="{an_x + an_w // 2}" y="{an_y + 13}" text-anchor="middle" '
        f'font-size="9" font-weight="700" font-family="Arial" fill="#000">ADDITIONAL NOTES</text>'
    )
    for ni, note in enumerate(notes_items):
        ny = an_y + 18 + ni * an_row_h + 10
        svg.append(f'<text x="{an_x + 6}" y="{ny}" font-size="7.5" font-family="Arial" fill="#000">{note}</text>')

    # ── Fire setback annotation ────────────────────────────────────
    # 3ft (0.914m) from ridge per IFC
    fire_offset = 0.914 * scale
    fs_line_y = ridge_y + fire_offset
    svg.append(
        f'<line x1="{bx1:.0f}" y1="{fs_line_y:.0f}" '
        f'x2="{bx2:.0f}" y2="{fs_line_y:.0f}" '
        f'stroke="#cc0000" stroke-width="0.8" stroke-dasharray="4,2"/>'
    )
    svg.append(
        f'<text x="{bx1 - 5:.0f}" y="{fs_line_y + 3:.0f}" '
        f'text-anchor="end" font-size="7" font-family="Arial" fill="#cc0000">'
        f"3' FIRE SETBACK</text>"
    )

    # ── Scale bar ──────────────────────────────────────────────────
    sb_x = 40
    sb_y = VH - 155
    scale_5m_px = 5.0 * scale
    svg.append(
        f'<line x1="{sb_x}" y1="{sb_y}" x2="{sb_x + scale_5m_px:.0f}" '
        f'y2="{sb_y}" stroke="#000" stroke-width="1.5"/>'
    )
    # Tick marks
    for i in range(6):
        tx = sb_x + i * scale
        svg.append(
            f'<line x1="{tx:.0f}" y1="{sb_y - 4}" x2="{tx:.0f}" y2="{sb_y + 4}" stroke="#000" stroke-width="1"/>'
        )
        svg.append(
            f'<text x="{tx:.0f}" y="{sb_y + 14}" text-anchor="middle" '
            f'font-size="7" font-family="Arial" fill="#000">{i}m</text>'
        )

    # ── North arrow ────────────────────────────────────────────────
    na_x = VW - 80
    na_y = 65
    svg.append(
        f'<g transform="translate({na_x},{na_y})">'
        f'<circle cx="0" cy="0" r="22" fill="#fff" stroke="#000" stroke-width="1.5"/>'
        f'<polygon points="0,-18 -6,8 0,2 6,8" fill="#000"/>'
        f'<polygon points="0,-18 6,8 0,2 -6,8" fill="none" stroke="#000" stroke-width="0.8"/>'
        f'<text x="0" y="-24" text-anchor="middle" font-size="12" '
        f'font-weight="700" font-family="Arial" fill="#000">N</text>'
        f'<circle cx="0" cy="0" r="2" fill="#000"/>'
        f"</g>"
    )

    # ── Roof detail box (top-right, below north arrow) ──────────────
    rd_x = VW - 270
    rd_y = 100
    rd_w = 255
    roof_detail_rows = [
        ("ROOF TYPE:", renderer._roof_material_display.upper()),
        ("SECTION:", f"S-1 (PRIMARY {azimuth_label(_az_s)} FACE)"),
        ("MODULE COUNT:", f"{n_panels} MODULES"),
        ("SYSTEM SIZE:", f"{total_kw_display:.2f} kW DC"),
        ("AZIMUTH:", f"{_az_s}\u00b0 ({azimuth_label(_az_s)})"),
        ("PITCH:", f"{_pit_s}\u00b0"),
        ("SCALE:", '1/8" = 1\'-0"'),
    ]
    rd_row_h = 16
    rd_h = 18 + len(roof_detail_rows) * rd_row_h + 2
    svg.append(
        f'<rect x="{rd_x}" y="{rd_y}" width="{rd_w}" height="{rd_h}" fill="#fff" stroke="#000" stroke-width="1"/>'
    )
    svg.append(
        f'<rect x="{rd_x}" y="{rd_y}" width="{rd_w}" height="18" fill="#d8d8d8" stroke="#000" stroke-width="1"/>'
    )
    svg.append(
        f'<text x="{rd_x + rd_w // 2}" y="{rd_y + 13}" text-anchor="middle" '
        f'font-size="9" font-weight="700" font-family="Arial" fill="#000">ROOF DETAIL \u2014 SECTION S-1</text>'
    )
    for ri, (k, v) in enumerate(roof_detail_rows):
        rry = rd_y + 18 + ri * rd_row_h
        if ri > 0:
            svg.append(
                f'<line x1="{rd_x + 1}" y1="{rry}" x2="{rd_x + rd_w - 1}" y2="{rry}" '
                f'stroke="#ccc" stroke-width="0.5"/>'
            )
        svg.append(
            f'<line x1="{rd_x + 108}" y1="{rry}" x2="{rd_x + 108}" y2="{rry + rd_row_h}" '
            f'stroke="#ddd" stroke-width="0.5"/>'
        )
        svg.append(
            f'<text x="{rd_x + 5}" y="{rry + 11}" font-size="8" font-weight="700" '
            f'font-family="Arial" fill="#000">{k}</text>'
        )
        svg.append(
            f'<text x="{rd_x + 113}" y="{rry + 11}" font-size="8" font-family="Arial" fill="#333">{v}</text>'
        )

    # ── Title block ────────────────────────────────────────────────
    svg.append(
        renderer._svg_title_block(VW, VH, "PV-3", "Site Plan", "Aerial + Mercator Panels", "3 of 13", address, today)
    )

    content = "\n".join(svg)
    return (
        f'<div class="page">'
        f'<svg width="100%" height="100%" viewBox="0 0 {VW} {VH}" '
        f'xmlns="http://www.w3.org/2000/svg" style="background:#ffffff;">'
        f"{content}</svg></div>"
    )



def _build_blank_site_plan(renderer, address: str, today: str) -> str:
    """Fallback site plan when no API data."""
    return f"""<div class="page">
      <svg width="100%" height="100%" viewBox="0 0 1280 960" xmlns="http://www.w3.org/2000/svg" style="background:#fff;">
    <rect x="10" y="10" width="1260" height="940" fill="none" stroke="#000" stroke-width="2"/>
    <rect x="20" y="20" width="1240" height="820" fill="#f5f5f5"/>
    <text x="640" y="440" text-anchor="middle" font-size="14" font-family="Arial" fill="#999">Site plan data not available</text>

    <g transform="translate(750, 850)">
      <rect x="0" y="0" width="520" height="100" fill="#fff" stroke="#000" stroke-width="1"/>
      <text x="10" y="16" font-size="10" font-weight="700" font-family="Arial" fill="#000">{renderer.company}</text>
      <text x="320" y="20" font-size="11" font-weight="700" font-family="Arial" fill="#000">PV-3</text>
      <text x="320" y="55" font-size="9" font-family="Arial" fill="#666">2 of 8</text>
    </g>
      </svg>
    </div>"""

