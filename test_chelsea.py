#!/usr/bin/env python3
"""
Test script: Renders the 42 Ch. de Charlotte, Chelsea, QC planset
using the saved Google Solar API response (no API key needed at render time).

Usage:
    python test_chelsea.py
"""

import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from google_solar import (
    GoogleSolarClient, BuildingInsight, SolarRoofSegment, SolarPanel,
    solar_insight_to_roof_faces,
)
from panel_placer import PanelPlacer, PanelSpec, PlacementConfig
from html_renderer import HtmlRenderer
from pdf_parser import PlansetData, PageData
from satellite_fetch import fetch_satellite_mosaic

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("test_chelsea")

GOOGLE_API_KEY = "AIzaSyCddcFWFRf_zoV5IPv_8FhgquGPxSdmI5M"


# ── Load saved API response ──────────────────────────────────────────────
raw_path = Path(__file__).parent.parent / "api_data" / "chelsea_42_charlotte_real.json"

if not raw_path.exists():
    print(f"ERROR: Cannot find {raw_path}")
    sys.exit(1)

with open(raw_path) as f:
    raw_data = json.load(f)

# Parse into BuildingInsight
client = GoogleSolarClient()
insight = client._parse_response(raw_data, "42 Ch. de Charlotte, Chelsea, QC J9B 2E7")

logger.info("Loaded %d panels, %d segments", len(insight.panels), len(insight.roof_segments))
logger.info("Building center: %.6f, %.6f", insight.lat, insight.lng)
logger.info("Panel dims: %.3fm x %.3fm", insight.panel_height_m, insight.panel_width_m)

# ── Auto-size to target consumption (100% offset) ─────────────────────
annual_consumption = 12000  # kWh — typical 3-4 bedroom Chelsea, QC
target_kwh = annual_consumption * 1.0

best_config = None
for cfg in raw_data.get("solarPotential", {}).get("solarPanelConfigs", []):
    if cfg.get("yearlyEnergyDcKwh", 0) >= target_kwh:
        best_config = cfg
        break
if not best_config:
    configs = raw_data.get("solarPotential", {}).get("solarPanelConfigs", [])
    best_config = configs[-1] if configs else {"panelsCount": 22}

num_panels = best_config.get("panelsCount", 22)
logger.info("Auto-sized to %d panels for target %.0f kWh/yr (API config: %.0f kWh/yr)",
            num_panels, target_kwh, best_config.get("yearlyEnergyDcKwh", 0))

# ── Panel spec & placement ────────────────────────────────────────────
roofs, scale = solar_insight_to_roof_faces(insight)

panel_spec = PanelSpec(
    name="LONGi Hi-MO 7 LR7-54HGBB-455M",
    wattage=455,
    width_ft=3.72,   # 1134mm
    height_ft=5.91,  # 1800mm
)
config = PlacementConfig(
    row_spacing_ft=0.5,
    col_spacing_ft=0.25,
    orientation="auto",
    max_panels=num_panels,
    sun_hours_peak=3.85,  # Chelsea, QC (slightly less than Gatineau)
)

placer = PanelPlacer(panel=panel_spec, config=config)
placements = placer.place_on_roofs(roofs, scale)

total_panels = sum(pr.total_panels for pr in placements)
total_kw = sum(pr.total_kw for pr in placements)
total_kwh = sum(pr.estimated_annual_kwh for pr in placements)
logger.info("Placement: %d panels, %.1f kW, %.0f kWh/yr", total_panels, total_kw, total_kwh)

# ── Fetch satellite imagery via Map Tiles API ────────────────────────
sat_image = None
try:
    sat_image = fetch_satellite_mosaic(
        lat=insight.lat, lng=insight.lng,
        api_key=GOOGLE_API_KEY,
        zoom=20, out_w=1280, out_h=960,
    )
except Exception as e:
    logger.warning("Satellite fetch failed (%s) — using vector fallback", e)

# ── Virtual page ──────────────────────────────────────────────────────
virtual_page = PageData(
    page_number=1,
    width=1280,
    height=960,
    scale_factor=scale,
    raster_image=sat_image,
)
planset = PlansetData(
    filepath="(Google Solar API: 42 Ch. de Charlotte, Chelsea, QC J9B 2E7)",
    total_pages=1,
    pages=[virtual_page],
    metadata={"address": "42 Ch. de Charlotte, Chelsea, QC J9B 2E7"},
)

# ── Render ────────────────────────────────────────────────────────────
html_renderer = HtmlRenderer(
    panel_spec=panel_spec,
    company_name="Quebec Solaire",
    project_name="Installation Solaire — 42 Ch. de Charlotte, Chelsea, QC",
    api_key=GOOGLE_API_KEY,
)

output_path = str(Path(__file__).parent.parent / "generated_plansets" / "42_Charlotte_Chelsea_planset.html")
html_renderer.render(
    planset, placements, output_path,
    building_insight=insight,
    num_api_panels=num_panels,
)

logger.info("=" * 60)
logger.info("Output: %s", output_path)
logger.info("=" * 60)
print(f"\nSUCCESS: {output_path}")
