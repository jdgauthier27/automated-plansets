#!/usr/bin/env python3
"""
Test script: Renders the 34 rue Bernier planset using Mercator projection
with the saved Google Solar API response (no API key needed).

Usage:
    python test_mercator.py

Expects solar_raw_response.json in ../api_data/ or at the hardcoded path.
"""

import json
import logging
import math
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("test_mercator")

# ── Load saved API response ──────────────────────────────────────────────
# Try multiple paths
raw_path = None
for candidate in [
    Path(__file__).parent.parent / "api_data" / "solar_raw_response.json",
    Path("/sessions/confident-affectionate-franklin/solar_raw_response.json"),
    Path(__file__).parent / "solar_raw_response.json",
]:
    if candidate.exists():
        raw_path = candidate
        break

if not raw_path:
    print("ERROR: Cannot find solar_raw_response.json")
    sys.exit(1)

with open(raw_path) as f:
    raw_data = json.load(f)

# Parse into BuildingInsight using the client's parser
client = GoogleSolarClient()
insight = client._parse_response(raw_data, "34 rue Bernier, Gatineau, QC J8Z 1E8")

logger.info("Loaded %d panels, %d segments", len(insight.panels), len(insight.roof_segments))
logger.info("Building center: %.6f, %.6f", insight.lat, insight.lng)
logger.info("Panel dims: %.3fm x %.3fm", insight.panel_height_m, insight.panel_width_m)

# ── Auto-size to ~7309 kWh (100% offset) ─────────────────────────────────
annual_consumption = 7309  # kWh
target_kwh = annual_consumption * 1.0  # 100% offset

# Find the right panel config from API
best_config = None
for cfg in raw_data.get("solarPotential", {}).get("solarPanelConfigs", []):
    if cfg.get("yearlyEnergyDcKwh", 0) >= target_kwh:
        best_config = cfg
        break
if not best_config:
    configs = raw_data.get("solarPotential", {}).get("solarPanelConfigs", [])
    best_config = configs[-1] if configs else {"panelsCount": 13}

num_panels = best_config.get("panelsCount", 13)
logger.info("Auto-sized to %d panels for target %.0f kWh/yr (API config: %.0f kWh/yr)",
            num_panels, target_kwh, best_config.get("yearlyEnergyDcKwh", 0))

# ── Generate satellite image placeholder ──────────────────────────────────
# Since we don't have an API key, create a green placeholder
# In production, _fetch_satellite_image would get the real one
import numpy as np
from PIL import Image

# Create a realistic dark satellite-like background (1280x960)
img_w, img_h = 1280, 960
bg = np.zeros((img_h, img_w, 3), dtype=np.uint8)
# Dark gray-green for yards/roofs
bg[:, :] = [35, 50, 35]
# Add some texture
np.random.seed(42)
noise = np.random.randint(-15, 15, (img_h, img_w, 3), dtype=np.int16)
bg = np.clip(bg.astype(np.int16) + noise, 0, 255).astype(np.uint8)
# Draw rough building outline at center
cx, cy = img_w // 2, img_h // 2
bg[cy-60:cy+60, cx-100:cx+100] = [90, 85, 80]  # building footprint

logger.info("Created %dx%d placeholder satellite image", img_w, img_h)

# ── Build planset data ────────────────────────────────────────────────────
# Also need placements for the schedule table (using abstract method)
roofs, scale = solar_insight_to_roof_faces(insight)

panel_spec = PanelSpec(
    name="LONGi Hi-MO 7 LR7-54HGBB-455M",
    wattage=455,
    width_ft=3.72,  # 1134mm
    height_ft=5.91,  # 1800mm
)
config = PlacementConfig(
    row_spacing_ft=0.5,
    col_spacing_ft=0.25,
    orientation="auto",
    max_panels=num_panels,
    sun_hours_peak=3.90,
)

placer = PanelPlacer(panel=panel_spec, config=config)
placements = placer.place_on_roofs(roofs, scale)

total_panels = sum(pr.total_panels for pr in placements)
total_kw = sum(pr.total_kw for pr in placements)
total_kwh = sum(pr.estimated_annual_kwh for pr in placements)
logger.info("Placement: %d panels, %.1f kW, %.0f kWh/yr", total_panels, total_kw, total_kwh)

# ── Create virtual page with satellite image ──────────────────────────────
virtual_page = PageData(
    page_number=1,
    width=1280,
    height=960,
    scale_factor=scale,
    raster_image=bg,  # use placeholder satellite image to test _build_site_plan_satellite
)
planset = PlansetData(
    filepath="(Google Solar API: 34 rue Bernier, Gatineau, QC)",
    total_pages=1,
    pages=[virtual_page],
    metadata={"address": "34 rue Bernier, Gatineau, QC J8Z 1E8"},
)

# ── Render ────────────────────────────────────────────────────────────────
html_renderer = HtmlRenderer(
    panel_spec=panel_spec,
    company_name="Quebec Solaire",
    project_name="Installation Solaire — 34 rue Bernier, Gatineau, QC",
    # API key enables real vicinity/aerial map thumbnails on the cover page.
    # Falls back to placeholder boxes if key is absent or network fails.
    api_key="AIzaSyCddcFWFRf_zoV5IPv_8FhgquGPxSdmI5M",
)

output_path = str(Path(__file__).parent.parent / "generated_plansets" / "34_rue_Bernier_planset.html")
html_renderer.render(
    planset, placements, output_path,
    building_insight=insight,
    num_api_panels=num_panels,
)

logger.info("=" * 60)
logger.info("Output: %s", output_path)
logger.info("=" * 60)
print(f"\nSUCCESS: {output_path}")
