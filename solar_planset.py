#!/usr/bin/env python3
"""
Solar Planset Tool — CLI Entry Point
=====================================
Two modes of operation:

  1. PDF mode — reads a PDF planset, detects roofs, places panels
     python solar_planset.py input.pdf [options]

  2. Address mode — uses Google Solar API for roof data (no PDF needed)
     python solar_planset.py --address "123 Rue Main, Montréal, QC" [options]

Examples
--------
    # PDF mode — auto-detect everything
    python solar_planset.py site_plan.pdf

    # Address mode — Quebec address via Google Solar API
    python solar_planset.py --address "1234 Rue Sainte-Catherine, Montréal, QC" \\
        --google-api-key YOUR_KEY

    # Address mode with custom panel + Quebec electrical
    python solar_planset.py --address "456 Boul René-Lévesque, Québec, QC" \\
        --google-api-key YOUR_KEY \\
        --panel-wattage 410 --panel-name "Canadian Solar CS6W-410MS" \\
        --quebec-electrical

    # PDF mode with custom panel spec
    python solar_planset.py site_plan.pdf \\
        --panel-wattage 410 \\
        --panel-width 3.42 --panel-height 6.92

    # Commercial flat roof with tilt racks
    python solar_planset.py warehouse.pdf \\
        --roof-pitch 0 --tilt 10 --row-spacing 4.0
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

# Ensure the tool's own directory is on the path
sys.path.insert(0, str(Path(__file__).parent))

from pdf_parser import PlansetData, PageData
from panel_placer import PanelPlacer, PanelSpec, PlacementConfig
from catalog.loader import EquipmentCatalog
from models.project import ProjectSpec
from html_renderer import HtmlRenderer
import data_export


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def parse_args():
    p = argparse.ArgumentParser(
        prog="solar_planset",
        description="Automatically place solar panels on a roof and generate an annotated planset.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Input mode (mutually exclusive: PDF or address)
    input_group = p.add_mutually_exclusive_group(required=True)
    input_group.add_argument("input_pdf", nargs="?", default=None,
                             help="Path to the input PDF planset (PDF mode)")
    input_group.add_argument("--address", type=str, default=None,
                             help="Street address for Google Solar API lookup (address mode)")

    # Google Solar API
    g_api = p.add_argument_group("Google Solar API (address mode)")
    g_api.add_argument("--google-api-key", type=str, default=None,
                       help="Google API key (or set GOOGLE_SOLAR_API_KEY env var)")
    g_api.add_argument("--lat", type=float, default=None, help="Latitude (alternative to address)")
    g_api.add_argument("--lng", type=float, default=None, help="Longitude (alternative to address)")
    g_api.add_argument("--satellite-bg", action="store_true", default=True,
                       help="Fetch satellite imagery as background (default: True)")
    g_api.add_argument("--no-satellite-bg", action="store_true",
                       help="Disable satellite imagery background")

    # Quebec electrical
    g_qc = p.add_argument_group("Quebec Electrical (CEC Section 64)")
    g_qc.add_argument("--quebec-electrical", action="store_true",
                      help="Include Quebec CEC Section 64 electrical design pages")
    g_qc.add_argument("--panel-voc", type=float, default=49.5, help="Panel Voc (V)")
    g_qc.add_argument("--panel-isc", type=float, default=10.2, help="Panel Isc (A)")
    g_qc.add_argument("--micro-inverter", type=str, default="Enphase IQ8+",
                      help="Micro-inverter model name")
    g_qc.add_argument("--micro-inverter-watts", type=float, default=300,
                      help="Micro-inverter continuous watts")
    g_qc.add_argument("--residential", action="store_true", default=True,
                      help="Residential installation (default)")
    g_qc.add_argument("--commercial", action="store_true",
                      help="Commercial installation (3-phase)")

    # Sizing
    g_size = p.add_argument_group("System Sizing")
    g_size.add_argument("--target-kwh", type=float, default=None,
                        help="Target annual kWh production (auto-calculates panel count)")
    g_size.add_argument("--target-offset", type=float, default=None,
                        help="Target offset %% of consumption (use with --annual-consumption)")
    g_size.add_argument("--annual-consumption", type=float, default=None,
                        help="Annual electricity consumption in kWh (from utility bill)")

    p.add_argument("-o", "--output-dir", default=".", help="Output directory (default: current dir)")
    p.add_argument("--output-name", default=None, help="Base name for output files")

    # Page selection (PDF mode only)
    p.add_argument("--pages", type=str, default=None,
                   help="Comma-separated page numbers to process (1-indexed, PDF mode only)")

    # Panel specs
    g = p.add_argument_group("Panel Specifications")
    g.add_argument("--panel-name", default="Generic 400W", help="Panel model name")
    g.add_argument("--panel-wattage", type=float, default=400, help="Panel wattage (Wp)")
    g.add_argument("--panel-width", type=float, default=3.42, help="Panel width in feet")
    g.add_argument("--panel-height", type=float, default=6.92, help="Panel height in feet")

    # Layout config
    g2 = p.add_argument_group("Layout Configuration")
    g2.add_argument("--orientation", choices=["auto", "portrait", "landscape"], default="auto",
                    help="Panel orientation strategy")
    g2.add_argument("--row-spacing", type=float, default=0.5, help="Row spacing in feet")
    g2.add_argument("--col-spacing", type=float, default=0.25, help="Column spacing in feet")
    g2.add_argument("--tilt", type=float, default=0.0, help="Additional tilt angle for flat/ground mount")
    g2.add_argument("--max-panels", type=int, default=9999, help="Maximum panels to place")

    # Roof detection (PDF mode)
    g3 = p.add_argument_group("Roof Detection (PDF mode)")
    g3.add_argument("--roof-pitch", type=float, default=0.0, help="Default roof pitch in degrees")
    g3.add_argument("--fire-setback", type=float, default=3.0, help="Fire setback in feet")
    g3.add_argument("--min-roof-area", type=float, default=5000,
                    help="Minimum roof polygon area in PDF points squared")
    g3.add_argument("--manual-polygons", type=str, default=None,
                    help='JSON file with manual roof polygons: [[[x,y], ...], ...]')

    # Rendering
    g4 = p.add_argument_group("Rendering")
    g4.add_argument("--dpi", type=int, default=200, help="Rasterization DPI for image detection")
    g4.add_argument("--company", default="Solar Design Co.", help="Company name for title block")
    g4.add_argument("--project", default=None, help="Project name for title block (default: auto)")
    g4.add_argument("--sun-hours", type=float, default=4.5, help="Peak sun hours for kWh estimate")

    # Export
    g5 = p.add_argument_group("Export")
    g5.add_argument("--no-csv", action="store_true", help="Skip CSV export")
    g5.add_argument("--no-json", action="store_true", help="Skip JSON export")
    g5.add_argument("--bom", action="store_true", help="Also export a Bill of Materials CSV")

    # Equipment catalog
    g_cat = p.add_argument_group("Equipment Catalog")
    g_cat.add_argument("--panel-id", type=str, default=None,
                       help="Panel ID from catalog (e.g., longi-himo7-455, canadian-solar-hiku7-440)")
    g_cat.add_argument("--inverter-id", type=str, default=None,
                       help="Inverter ID from catalog (e.g., solis-s6-eh1p5k, hoymiles-hms-800)")
    g_cat.add_argument("--racking-id", type=str, default=None,
                       help="Racking ID from catalog (e.g., ironridge-xr10, k2-crossrail-48x)")
    g_cat.add_argument("--roof-material", type=str, default="asphalt_shingle",
                       choices=["asphalt_shingle", "composite_shingle", "metal_standing_seam",
                                "clay_tile", "concrete_tile", "flat_membrane"],
                       help="Roof material (affects attachment selection)")
    g_cat.add_argument("--main-breaker", type=int, default=200,
                       help="Main panel breaker size in amps (default: 200)")
    g_cat.add_argument("--bus-rating", type=int, default=225,
                       help="Main panel bus rating in amps (default: 225)")
    g_cat.add_argument("--list-equipment", action="store_true",
                       help="List available equipment in catalog and exit")

    # Misc
    p.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")

    return p.parse_args()


# ═══════════════════════════════════════════════════════════════════════════════
# ADDRESS MODE — Google Solar API
# ═══════════════════════════════════════════════════════════════════════════════

def _detect_country(address: str) -> str:
    """Detect country from address string. Returns 'US' or 'CA' (Canada)."""
    # Canadian provinces/territories pattern: ', XX ' or ', XX,' or end-of-string
    _CA_PROVINCES = {
        "QC", "ON", "BC", "AB", "MB", "SK", "NS", "NB", "NL", "PE", "YT", "NT", "NU"
    }
    addr_upper = address.upper()
    # Check for explicit country suffix
    if addr_upper.endswith(", USA") or ", USA," in addr_upper or addr_upper.endswith(" USA"):
        return "US"
    if addr_upper.endswith(", CANADA") or ", CANADA," in addr_upper:
        return "CA"
    # Check for Canadian postal code pattern (letter-digit-letter digit-letter-digit)
    import re
    if re.search(r'\b[A-Z]\d[A-Z]\s*\d[A-Z]\d\b', addr_upper):
        return "CA"
    # Check for Canadian province abbreviation preceded by comma+space
    for prov in _CA_PROVINCES:
        if (f", {prov} " in addr_upper or f", {prov}," in addr_upper
                or addr_upper.endswith(f", {prov}")):
            return "CA"
    # Check for 5-digit US ZIP code
    if re.search(r',\s*[A-Z]{2}\s+\d{5}(-\d{4})?\s*$', addr_upper):
        return "US"
    # Default to Canada (tool originally built for Quebec)
    return "CA"


def run_address_mode(args, logger):
    """Run the tool in address mode using Google Solar API data."""
    from google_solar import GoogleSolarClient, solar_insight_to_roof_faces
    import numpy as np

    api_key = args.google_api_key or os.environ.get("GOOGLE_SOLAR_API_KEY")
    client = GoogleSolarClient(api_key=api_key)

    address = args.address
    country = _detect_country(address)
    logger.info("Detected country: %s", "United States" if country == "US" else "Canada")
    logger.info("=" * 60)
    logger.info("SOLAR PLANSET TOOL — Address Mode")
    logger.info("=" * 60)
    logger.info("Address: %s", address)

    # ── 1. Fetch building insight ─────────────────────────────────────
    insight = client.get_building_insight(
        address=address, lat=args.lat, lng=args.lng
    )

    logger.info("Building: %s", insight.address)
    logger.info("  Location: %.6f, %.6f", insight.lat, insight.lng)
    logger.info("  Imagery quality: %s", insight.imagery_quality)
    logger.info("  Roof segments: %d", len(insight.roof_segments))
    for seg in insight.roof_segments:
        logger.info("    Seg %d: %.0f m², pitch=%.0f°, azimuth=%.0f°",
                     seg.index, seg.area_m2, seg.pitch_deg, seg.azimuth_deg)
    logger.info("  API max panels: %d", insight.max_panels)
    logger.info("  API max system: %.1f kW / %.0f kWh/yr",
                 insight.max_kw, insight.max_annual_kwh)

    # ── 2. Convert to RoofFaces ───────────────────────────────────────
    roofs, scale = solar_insight_to_roof_faces(insight)
    logger.info("Converted %d roof faces, scale=%.2f pts/ft", len(roofs), scale)

    # ── 2b. Auto-size system if target specified ────────────────────
    max_panels = args.max_panels
    target_kwh = args.target_kwh
    if args.annual_consumption and args.target_offset:
        target_kwh = args.annual_consumption * (args.target_offset / 100.0)
    if target_kwh:
        kwh_per_panel = args.panel_wattage * args.sun_hours * 365 * 0.80 / 1000.0
        panels_needed = int(target_kwh / kwh_per_panel + 0.99)  # round up
        max_panels = min(max_panels, panels_needed)
        logger.info("Auto-sizing: target %.0f kWh/yr → %d panels (%.1f kWh/panel/yr)",
                     target_kwh, panels_needed, kwh_per_panel)

    # ── 3. Place panels ───────────────────────────────────────────────
    panel_spec = PanelSpec(
        name=args.panel_name,
        wattage=args.panel_wattage,
        width_ft=args.panel_width,
        height_ft=args.panel_height,
    )
    config = PlacementConfig(
        row_spacing_ft=args.row_spacing,
        col_spacing_ft=args.col_spacing,
        orientation=args.orientation,
        max_panels=max_panels,
        sun_hours_peak=args.sun_hours,
    )

    placer = PanelPlacer(panel=panel_spec, config=config)
    placements = placer.place_on_roofs(roofs, scale)

    total_panels = sum(pr.total_panels for pr in placements)
    total_kw = sum(pr.total_kw for pr in placements)
    total_kwh = sum(pr.estimated_annual_kwh for pr in placements)

    logger.info("-" * 40)
    logger.info("PLACEMENT SUMMARY")
    logger.info("  Roof faces: %d", len(roofs))
    logger.info("  Total panels: %d", total_panels)
    logger.info("  System size: %.1f kW DC", total_kw)
    logger.info("  Est. annual: %s kWh", f"{total_kwh:,.0f}")
    logger.info("-" * 40)

    # ── 4. Build virtual planset ──────────────────────────────────────
    # Fetch satellite image if available
    sat_image = None
    if api_key and not args.no_satellite_bg:
        sat_image = _fetch_satellite_image(api_key, insight.lat, insight.lng, logger)

    virtual_page = PageData(
        page_number=1,
        width=792, height=612,
        scale_factor=scale,
        raster_image=sat_image,
    )
    planset = PlansetData(
        filepath=f"(Google Solar API: {address})",
        total_pages=1,
        pages=[virtual_page],
        metadata={"address": address, "source": "google_solar_api"},
    )

    # ── 5. Render ─────────────────────────────────────────────────────
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    # Sanitize address for filename
    safe_addr = "".join(c if c.isalnum() or c in " -_" else "" for c in address)
    safe_addr = safe_addr.strip().replace(" ", "_")[:50]
    base_name = args.output_name or f"{safe_addr}_solar"

    project_name = args.project or f"Installation Solaire — {address}"

    # ── Build ProjectSpec from catalog if equipment IDs provided ────────
    project = None
    if args.panel_id or args.inverter_id or args.racking_id:
        catalog = EquipmentCatalog()
        panel_entry = catalog.get_panel(args.panel_id) if args.panel_id else None
        inverter_entry = catalog.get_inverter(args.inverter_id) if args.inverter_id else None
        racking_entry = catalog.get_racking(args.racking_id) if args.racking_id else None

        # Auto-select attachment based on roof material + racking
        attachment_entry = None
        if racking_entry:
            attachment_entry = catalog.auto_select_attachment(
                args.roof_material, racking_entry.id
            )

        # Use defaults for any missing equipment
        if not panel_entry:
            panel_entry = catalog.get_panel(catalog.list_panel_ids()[0])
        if not inverter_entry:
            inverter_entry = catalog.get_inverter(catalog.list_inverter_ids()[0])
        if not racking_entry:
            racking_entry = catalog.get_racking(catalog.list_racking_ids()[0])
        if not attachment_entry:
            from models.equipment import AttachmentCatalogEntry
            attachment_entry = AttachmentCatalogEntry(model="Generic Attachment")

        # Override panel_spec with catalog entry dimensions
        panel_spec = PanelSpec(
            name=panel_entry.model,
            wattage=panel_entry.wattage_w,
            width_ft=panel_entry.width_ft,
            height_ft=panel_entry.height_ft,
            efficiency=panel_entry.efficiency_pct / 100.0,
        )

        project = ProjectSpec(
            address=address,
            country=country,
            latitude=insight.lat,
            longitude=insight.lng,
            panel=panel_entry,
            inverter=inverter_entry,
            racking=racking_entry,
            attachment=attachment_entry,
            roof_material=args.roof_material,
            main_panel_breaker_a=args.main_breaker,
            main_panel_bus_rating_a=args.bus_rating,
            num_panels=total_panels,
            company_name=args.company,
            project_name=project_name,
            designer_name="AI Solar Design Engine",
            sun_hours_peak=args.sun_hours,
            building_insight=insight,
            placements=placements,
        )

        # Compute shade factor from annual flux GeoTIFF
        if api_key:
            try:
                flux_result = client.get_flux_and_mask(address)
                if flux_result:
                    from engine.electrical_calc import calculate_shade_factor
                    project.shade_factor = calculate_shade_factor(
                        flux_result.get("flux_bytes"),
                        mask_bytes=flux_result.get("mask_bytes"),
                    )
                    logger.info("  Shade factor: %.3f", project.shade_factor)
            except Exception as _e:
                logger.warning("Shade factor skipped: %s", _e)

        logger.info("Using ProjectSpec with catalog equipment:")
        logger.info("  Panel: %s (%dW)", panel_entry.model_short, panel_entry.wattage_w)
        logger.info("  Inverter: %s (%s)", inverter_entry.model_short, inverter_entry.type)
        logger.info("  Racking: %s", racking_entry.model)
        logger.info("  Attachment: %s", attachment_entry.model)
        logger.info("  Roof: %s", args.roof_material)

    html_renderer = HtmlRenderer(
        panel_spec=panel_spec,
        company_name=args.company,
        project_name=project_name,
        project=project,
    )
    html_out = str(output_dir / f"{base_name}.html")
    html_renderer.render(
        planset, placements, html_out,
        building_insight=insight,
        num_api_panels=max_panels if max_panels < 9999 else None,
    )
    logger.info("HTML planset: %s", html_out)

    # ── 5b. Quebec electrical pages ───────────────────────────────────
    if args.quebec_electrical:
        _append_quebec_electrical(
            html_out, args, panel_spec, total_panels, total_kw, total_kwh, address, logger
        )

    # ── 6. Data exports ───────────────────────────────────────────────
    if not args.no_json:
        json_out = str(output_dir / f"{base_name}.json")
        data_export.export_json(
            json_out, address, total_panels, total_kw, total_kwh,
            panel_spec.name, panel_spec.wattage,
        )
        logger.info("JSON export: %s", json_out)

    if not args.no_csv:
        csv_out = str(output_dir / f"{base_name}_panels.csv")
        data_export.export_csv(csv_out, placements)
        logger.info("CSV export: %s", csv_out)

    if args.bom:
        bom_out = str(output_dir / f"{base_name}_bom.csv")
        data_export.export_bom(bom_out, total_panels, panel_spec.name, panel_spec.wattage)
        logger.info("BOM export: %s", bom_out)

    # ── Done ──────────────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("DONE — Output files in: %s", output_dir)
    logger.info("=" * 60)

    return html_out


def _fetch_satellite_image(api_key, lat, lng, logger):
    """Fetch a satellite image from Google Maps Static API for the roof plan background."""
    import urllib.request
    try:
        url = (
            f"https://maps.googleapis.com/maps/api/staticmap"
            f"?center={lat},{lng}&zoom=20&size=640x480&scale=2&maptype=satellite"
            f"&key={api_key}"
        )
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=15) as resp:
            img_data = resp.read()

        # Convert to numpy array for the renderer
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(img_data)).convert("RGB")
        import numpy as np
        arr = np.array(img)
        logger.info("Satellite image fetched: %dx%d", arr.shape[1], arr.shape[0])
        return arr
    except Exception as e:
        logger.warning("Could not fetch satellite image: %s", e)
        return None


def _append_quebec_electrical(html_path, args, spec, total_panels, total_kw, total_kwh, address, logger):
    """Append CEC Section 64 electrical design + Quebec code pages to the HTML planset."""
    from quebec_electrical import (
        QuebecElectricalCalculator, MicroInverterSpec, InverterSpec,
        get_quebec_code_notes, HQ_INCENTIVE_PER_KW,
    )

    is_residential = not args.commercial

    calc = QuebecElectricalCalculator(
        panel_wattage=args.panel_wattage,
        panel_voc=args.panel_voc,
        panel_isc=args.panel_isc,
        is_residential=is_residential,
    )

    micro = MicroInverterSpec(name=args.micro_inverter, max_continuous_w=args.micro_inverter_watts)
    elec = calc.design_micro_inverter_system(total_panels, micro)

    logger.info("Quebec Electrical Design:")
    logger.info("  AC output: %s kW", elec.system_kw_ac)
    logger.info("  Breaker: %s A", elec.ac_breaker_size_a)
    logger.info("  Conductor: %s", elec.ac_conductor_size)
    logger.info("  HQ incentive: $%s", f"{elec.hq_incentive_estimate:,.0f}")
    if elec.code_violations:
        logger.warning("  VIOLATIONS: %s", elec.code_violations)

    # Build electrical detail HTML
    labels_html = ""
    for lb in elec.required_labels:
        text_escaped = lb["text"].replace("\n", "<br>")
        labels_html += f"""
        <div style="margin-bottom:10px; padding:10px; background:#fff5f5; border-left:4px solid #c00; border-radius:4px;">
          <div style="font-size:11px; color:#888; margin-bottom:3px;">{lb["location"]}</div>
          <div style="font-size:13px; font-weight:600; color:#900;">{text_escaped}</div>
          <div style="font-size:10px; color:#999; margin-top:3px;">{lb["spec"]}</div>
        </div>"""

    disconnects_html = "".join(
        f'<li style="font-size:13px; margin-bottom:4px;">{d}</li>'
        for d in elec.disconnect_locations
    )

    notes = get_quebec_code_notes()
    notes_html = "".join(
        f'<li style="font-size:12px; color:#444; line-height:1.7; margin-bottom:5px;">{n}</li>'
        for n in notes
    )

    elec_rate = 0.0738
    annual_savings = total_kwh * elec_rate
    payback_cost = total_kw * 2500
    net_cost = payback_cost - elec.hq_incentive_estimate
    payback_years = net_cost / annual_savings if annual_savings > 0 else 99

    inverter_name = elec.micro_inverter.name if elec.micro_inverter else (elec.inverter.name if elec.inverter else "N/A")

    extra_pages = f"""

<!-- ELECTRICAL DESIGN (CEC SECTION 64) -->
<div class="page" style="background:white; width:1020px; margin:24px auto; box-shadow:0 2px 12px rgba(0,0,0,0.12); border-radius:6px; overflow:hidden; page-break-after:always;">
  <div style="background:linear-gradient(135deg,#1a3366,#264073); padding:14px 24px; color:white; font-size:18px; font-weight:600;">
    S-6: ELECTRICAL DESIGN — CEC Section 64 / Code du Québec
  </div>
  <div style="padding:24px 36px;">
    <div style="display:grid; grid-template-columns:1fr 1fr; gap:20px; margin-bottom:24px;">
      <div style="background:#f8f9fc; border:1px solid #e2e4ea; border-radius:8px; padding:18px;">
        <h3 style="font-size:14px; margin-bottom:12px; color:#1a3366;">System Specifications</h3>
        <table style="width:100%; font-size:13px;">
          <tr><td style="color:#666; padding:4px 0;">Panels</td><td style="font-weight:600;">{total_panels}x {spec.name}</td></tr>
          <tr><td style="color:#666; padding:4px 0;">DC Rating</td><td style="font-weight:600;">{total_kw:.1f} kW</td></tr>
          <tr><td style="color:#666; padding:4px 0;">AC Rating</td><td style="font-weight:600;">{elec.system_kw_ac} kW</td></tr>
          <tr><td style="color:#666; padding:4px 0;">Inverter</td><td style="font-weight:600;">{inverter_name}</td></tr>
          <tr><td style="color:#666; padding:4px 0;">Est. Annual</td><td style="font-weight:600;">{total_kwh:,.0f} kWh</td></tr>
        </table>
      </div>
      <div style="background:#f8f9fc; border:1px solid #e2e4ea; border-radius:8px; padding:18px;">
        <h3 style="font-size:14px; margin-bottom:12px; color:#1a3366;">AC Circuit Design (Rule 64-100)</h3>
        <table style="width:100%; font-size:13px;">
          <tr><td style="color:#666; padding:4px 0;">AC Current</td><td style="font-weight:600;">{elec.ac_continuous_current_a} A continuous</td></tr>
          <tr><td style="color:#666; padding:4px 0;">x 1.25</td><td style="font-weight:600;">{elec.ac_continuous_current_a * 1.25:.1f} A</td></tr>
          <tr><td style="color:#666; padding:4px 0;">Breaker</td><td style="font-weight:600;">{elec.ac_breaker_size_a} A (2-pole)</td></tr>
          <tr><td style="color:#666; padding:4px 0;">Conductor</td><td style="font-weight:600;">{elec.ac_conductor_size} copper</td></tr>
          <tr><td style="color:#666; padding:4px 0;">Bond</td><td style="font-weight:600;">{elec.bond_conductor_size}</td></tr>
        </table>
      </div>
    </div>

    <h3 style="font-size:14px; margin-bottom:8px; color:#1a3366;">Disconnect Locations (CEC 64-060, 84-022)</h3>
    <ul style="margin-bottom:20px; padding-left:20px;">{disconnects_html}</ul>

    <h3 style="font-size:14px; margin-bottom:8px; color:#1a3366;">Rapid Shutdown (CEC 64-218)</h3>
    <p style="font-size:12px; color:#444; margin-bottom:20px; line-height:1.6;">{elec.rapid_shutdown_notes}</p>

    <div style="background:#f0f8ff; border:1px solid #b3d9ff; border-radius:8px; padding:16px; margin-bottom:20px;">
      <h3 style="font-size:14px; margin-bottom:8px; color:#0066cc;">Hydro-Québec Net Metering</h3>
      <table style="width:100%; font-size:13px;">
        <tr><td style="color:#666; padding:3px 0;">Eligible</td><td style="font-weight:600;">{"Oui" if elec.hq_eligible else "Non"}</td></tr>
        <tr><td style="color:#666; padding:3px 0;">Incentive (2025)</td><td style="font-weight:600;">${elec.hq_incentive_estimate:,.0f} ($1,000/kW)</td></tr>
        <tr><td style="color:#666; padding:3px 0;">Est. Annual Savings</td><td style="font-weight:600;">${annual_savings:,.0f}/yr (Rate D: $0.0738/kWh)</td></tr>
        <tr><td style="color:#666; padding:3px 0;">Est. Net Cost</td><td style="font-weight:600;">${net_cost:,.0f} (after incentive)</td></tr>
        <tr><td style="color:#666; padding:3px 0;">Simple Payback</td><td style="font-weight:600;">{payback_years:.1f} years</td></tr>
      </table>
    </div>
  </div>
</div>

<!-- REQUIRED LABELS (CEC 64-060 to 64-222) -->
<div class="page" style="background:white; width:1020px; margin:24px auto; box-shadow:0 2px 12px rgba(0,0,0,0.12); border-radius:6px; overflow:hidden; page-break-after:always;">
  <div style="background:linear-gradient(135deg,#1a3366,#264073); padding:14px 24px; color:white; font-size:18px; font-weight:600;">
    S-7: REQUIRED LABELS — CEC Rules 64-060 to 64-222
  </div>
  <div style="padding:24px 36px;">
    <p style="font-size:12px; color:#666; margin-bottom:16px;">
      All labels must be permanent lamicoid engraved plates, white lettering on RED background, per CEC requirements.
    </p>
    {labels_html}
  </div>
</div>

<!-- CODE REFERENCES (QUEBEC) -->
<div class="page" style="background:white; width:1020px; margin:24px auto; box-shadow:0 2px 12px rgba(0,0,0,0.12); border-radius:6px; overflow:hidden; page-break-after:always;">
  <div style="background:linear-gradient(135deg,#1a3366,#264073); padding:14px 24px; color:white; font-size:18px; font-weight:600;">
    S-8: CODE REFERENCES — CSA C22.1 / Code du Québec / Hydro-Québec
  </div>
  <div style="padding:24px 36px;">
    <ol style="padding-left:20px;">{notes_html}</ol>
  </div>
</div>

"""

    with open(html_path, "r") as f:
        html = f.read()
    html = html.replace("</body>", extra_pages + "\n</body>")
    with open(html_path, "w") as f:
        f.write(html)

    logger.info("Appended Quebec electrical pages (S-6, S-7, S-8)")


# ═══════════════════════════════════════════════════════════════════════════════
# PDF MODE — Original planset parsing
# ═══════════════════════════════════════════════════════════════════════════════

def run_pdf_mode(args, logger):
    """Run the tool in PDF mode, parsing a PDF planset."""
    input_path = Path(args.input_pdf).resolve()
    if not input_path.exists():
        logger.error("Input file not found: %s", input_path)
        sys.exit(1)

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    base_name = args.output_name or (input_path.stem + "_solar")

    # ── 1. Parse PDF ─────────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("SOLAR PLANSET TOOL — PDF Mode")
    logger.info("=" * 60)
    logger.info("Input: %s", input_path)

    parser = PlansetParser(dpi=args.dpi)
    planset = parser.parse(str(input_path))
    logger.info("Parsed %d pages", planset.total_pages)

    if args.pages:
        page_nums = {int(x.strip()) for x in args.pages.split(",")}
        planset.pages = [p for p in planset.pages if p.page_number in page_nums]
        logger.info("Processing pages: %s", sorted(page_nums))

    # ── 2. Detect roofs ──────────────────────────────────────────────────
    manual_polys = None
    if args.manual_polygons:
        with open(args.manual_polygons) as f:
            manual_polys = json.load(f)

    detector = RoofDetector(
        min_area_pts=args.min_roof_area,
        setback_ft={"ridge": 1.5, "eave": 1.0, "hip": 1.5, "valley": 0.5,
                     "fire": args.fire_setback},
        pitch_default=args.roof_pitch,
    )

    all_roofs = []
    for page in planset.pages:
        result = detector.detect(page, manual_polys)
        all_roofs.extend(result.roofs)
        logger.info("Page %d: detected %d roof face(s) (confidence: %.0f%%)",
                     page.page_number, len(result.roofs), result.confidence * 100)

    if not all_roofs:
        logger.warning("No roofs detected! Try --manual-polygons or a different --min-roof-area.")
        logger.warning("Generating a blank planset anyway...")

    # ── 3. Place panels ──────────────────────────────────────────────────
    panel_spec = PanelSpec(
        name=args.panel_name,
        wattage=args.panel_wattage,
        width_ft=args.panel_width,
        height_ft=args.panel_height,
    )
    config = PlacementConfig(
        row_spacing_ft=args.row_spacing,
        col_spacing_ft=args.col_spacing,
        orientation=args.orientation,
        tilt_deg=args.tilt,
        max_panels=args.max_panels,
        sun_hours_peak=args.sun_hours,
    )

    placer = PanelPlacer(panel=panel_spec, config=config)
    scale = planset.pages[0].scale_factor if planset.pages else 1.0
    placements = placer.place_on_roofs(all_roofs, scale)

    total_panels = sum(pr.total_panels for pr in placements)
    total_kw = sum(pr.total_kw for pr in placements)
    total_kwh = sum(pr.estimated_annual_kwh for pr in placements)

    logger.info("-" * 40)
    logger.info("PLACEMENT SUMMARY")
    logger.info("  Roof faces: %d", len(all_roofs))
    logger.info("  Total panels: %d", total_panels)
    logger.info("  System size: %.1f kW DC", total_kw)
    logger.info("  Est. annual: %s kWh", f"{total_kwh:,.0f}")
    logger.info("-" * 40)

    # ── 4. Render annotated PDF ──────────────────────────────────────────
    project_name = args.project or "Solar Installation"

    renderer = PlansetRenderer(
        panel_spec=panel_spec,
        company_name=args.company,
        project_name=project_name,
    )
    pdf_out = str(output_dir / f"{base_name}.pdf")
    renderer.render(planset, placements, pdf_out)
    logger.info("Annotated planset: %s", pdf_out)

    # ── 4b. Render HTML ─────────────────────────────────────────────────
    html_renderer = HtmlRenderer(
        panel_spec=panel_spec,
        company_name=args.company,
        project_name=project_name,
    )
    html_out = str(output_dir / f"{base_name}.html")
    html_renderer.render(planset, placements, html_out)
    logger.info("HTML planset: %s", html_out)

    # ── 4c. Quebec electrical pages (if requested) ───────────────────────
    if args.quebec_electrical:
        _append_quebec_electrical(
            html_out, args, panel_spec, total_panels, total_kw, total_kwh,
            "See PDF planset", logger
        )

    # ── 5. Data exports ──────────────────────────────────────────────────
    exporter = DataExporter(panel_spec=panel_spec)

    if not args.no_json:
        json_out = str(output_dir / f"{base_name}.json")
        exporter.export_json(placements, json_out)
        logger.info("JSON export: %s", json_out)

    if not args.no_csv:
        csv_out = str(output_dir / f"{base_name}_panels.csv")
        exporter.export_csv(placements, csv_out)
        logger.info("CSV export: %s", csv_out)

    if args.bom:
        bom_out = str(output_dir / f"{base_name}_bom.csv")
        exporter.export_bom(placements, bom_out)
        logger.info("BOM export: %s", bom_out)

    logger.info("=" * 60)
    logger.info("DONE — Output files in: %s", output_dir)
    logger.info("=" * 60)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    args = parse_args()
    setup_logging(args.verbose)
    logger = logging.getLogger("solar_planset")

    # List equipment catalog and exit
    if args.list_equipment:
        catalog = EquipmentCatalog()
        print("\n=== PANELS ===")
        for pid, p in catalog.panels.items():
            print(f"  {pid:30s}  {p.model_short:20s}  {p.wattage_w}W  {p.manufacturer}")
        print("\n=== INVERTERS ===")
        for iid, inv in catalog.inverters.items():
            print(f"  {iid:30s}  {inv.model_short:20s}  {inv.type:6s}  {inv.rated_ac_output_w}W  {inv.manufacturer}")
        print("\n=== RACKING ===")
        for rid, r in catalog.racking.items():
            print(f"  {rid:30s}  {r.model:20s}  {r.manufacturer}")
        print("\n=== ATTACHMENTS ===")
        for aid, a in catalog.attachments.items():
            print(f"  {aid:30s}  {a.model:20s}  roofs={a.compatible_roof_materials}")
        print()
        return

    if args.address:
        run_address_mode(args, logger)
    else:
        run_pdf_mode(args, logger)


if __name__ == "__main__":
    main()
