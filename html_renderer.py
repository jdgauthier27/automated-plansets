"""
HTML Planset Renderer — Professional Engineering Drawings
===========================================================
Generates a multi-page professional solar permit planset as white-paper
engineering drawings suitable for permit submission.

Pages generated (Cubillas PV-prefix naming):
  PV-1:   Cover page
  PV-2:   Property plan
  PV-3:   Site plan (satellite + Mercator panels)
  PV-3.1: Racking/framing plan (vector)
  PV-4:   Single-line diagram
  PV-4.1: Electrical calculations
  PV-5:   Mounting details & BOM
  PV-6:   Signage/placards
  PV-6.1: Placard house
  PV-7:   Microinverter circuit map
  PV-8.1: Module datasheet
  PV-8.2: Racking datasheet
  PV-8.3: Attachment datasheet

Design:
  - WHITE paper background with black text/lines (engineering drawing standard)
  - Professional title block in BOTTOM-RIGHT corner
  - Pages 1280×960 (11×8.5" landscape at screen resolution)
  - Panels rendered REALISTICALLY on satellite (dark navy fill, cell grid, aluminum frame)
  - Mercator projection for accurate positioning
"""

import base64
import io
import logging
import math
import os
import ssl
import urllib.request
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

from panel_placer import PanelPlacement, PanelSpec, PlacementResult
from pdf_parser import PlansetData
from shapely.geometry import LineString, Polygon as ShapelyPolygon

# Import ProjectSpec and equipment models (optional — falls back to legacy mode)
try:
    from models.project import ProjectSpec
    from models.equipment import PanelCatalogEntry, InverterCatalogEntry
    from engine.bom_calculator import calculate_bom, BOMItem, calculate_project_cost
    from engine.electrical_calc import calculate_string_config, calculate_monthly_production

    HAS_PROJECT_SPEC = True
except ImportError:
    HAS_PROJECT_SPEC = False

logger = logging.getLogger(__name__)


class HtmlRenderer:
    """Renders a full engineering planset as a self-contained HTML file.

    Accepts either:
      - A ProjectSpec (new mode — all equipment from catalog)
      - Legacy PanelSpec + company/designer args (backward compatible)
    """

    # Satellite image constants
    SAT_ZOOM = 20
    SAT_SCALE = 2
    SAT_SIZE_W = 640
    SAT_SIZE_H = 480
    SAT_PX_W = 1280
    SAT_PX_H = 960

    # Professional color palette (engineering drawing standard)
    COLORS = {
        # Paper and text
        "paper_bg": "#ffffff",
        "paper_border": "#000000",
        "text_primary": "#000000",
        "text_secondary": "#333333",
        "text_light": "#666666",
        # Panels on satellite (realistic)
        "panel_fill": "#0c1a2e",  # dark navy
        "panel_cell_grid": "rgba(30,58,138,0.3)",  # dark blue grid
        "panel_frame": "rgba(160,175,195,0.55)",  # silver aluminum
        # Vector drawing
        "roof_outline": "#000000",
        "setback_line": "#cc0000",
        "dimension_line": "#444444",
        "dimension_text": "#222222",
        "grid_light": "#f0f0f0",
        "grid_medium": "#d8d8d8",
        # Electrical
        "wire_dc": "#0066cc",
        "wire_ac": "#cc0000",
        "wire_ground": "#00aa00",
        "inverter": "#e8e8e8",
        "breaker": "#f0f0f0",
        # Wiring (string plan)
        "string_1": "#0066cc",
        "string_2": "#ff6600",
        "string_3": "#00aa00",
        "string_4": "#aa00aa",
        "string_5": "#ffaa00",
    }

    # ── Equipment spec accessors ───────────────────────────────────────
    # These properties read from ProjectSpec when available, otherwise
    # fall back to legacy hardcoded defaults for backward compatibility.

    @property
    def INV_AC_WATTS_PER_UNIT(self) -> int:
        """Inverter AC output per unit (VA). From catalog or legacy default."""
        if self._project:
            return self._project.inverter.rated_ac_output_w
        return 384  # legacy Enphase IQ8A default

    @property
    def INV_AC_AMPS_PER_UNIT(self) -> float:
        """Inverter AC current per unit (A). From catalog or legacy default."""
        if self._project:
            return self._project.inverter.max_ac_amps
        return 1.6

    @property
    def INV_MODEL_SHORT(self) -> str:
        if self._project:
            return self._project.inverter.model_short
        return "Enphase IQ8A"

    @property
    def INV_MODEL_FULL(self) -> str:
        if self._project:
            inv = self._project.inverter
            return f"{inv.manufacturer.upper()} {inv.model} [{inv.ac_voltage_v}V] GRID-TIED {'MICROINVERTER' if inv.is_micro else 'STRING INVERTER'}"
        return "ENPHASE IQ8A [240V] GRID-TIED MICROINVERTER"

    @property
    def _panel_voc(self) -> float:
        if self._project:
            return self._project.panel.voc_v
        return 37.5

    @property
    def _panel_vmp(self) -> float:
        if self._project:
            return self._project.panel.vmp_v
        return 31.7

    @property
    def _panel_isc(self) -> float:
        if self._project:
            return self._project.panel.isc_a
        return 14.19

    @property
    def _panel_imp(self) -> float:
        if self._project:
            return self._project.panel.imp_a
        return 13.56

    @property
    def _panel_temp_coeff_voc(self) -> float:
        """Temperature coefficient of Voc as fraction (e.g., -0.0024)."""
        if self._project:
            return self._project.panel.temp_coeff_voc_frac
        return -0.0024

    @property
    def _panel_temp_coeff_isc(self) -> float:
        if self._project:
            return self._project.panel.temp_coeff_isc_frac
        return 0.0005

    @property
    def _panel_model_full(self) -> str:
        if self._project:
            p = self._project.panel
            return f"{p.manufacturer} {p.model}"
        return "LONGi Hi-MO 7 LR7-54HGBB-455M"

    @property
    def _panel_model_short(self) -> str:
        if self._project:
            return self._project.panel.model_short
        return "LONGi Hi-MO 7"

    @property
    def _panel_wattage(self) -> int:
        if self._project:
            return self._project.panel.wattage_w
        return self.panel.wattage if hasattr(self, "panel") else 455

    @property
    def _racking_model(self) -> str:
        if self._project:
            return self._project.racking.model
        return "XR10"

    @property
    def _racking_manufacturer(self) -> str:
        if self._project:
            return self._project.racking.manufacturer
        return "IronRidge"

    @property
    def _racking_full(self) -> str:
        if self._project:
            r = self._project.racking
            return f"{r.manufacturer} {r.model}"
        return "IronRidge XR10"

    @property
    def _attachment_model(self) -> str:
        if self._project:
            return self._project.attachment.model
        return "FlashFoot2"

    @property
    def _attachment_manufacturer(self) -> str:
        if self._project:
            return self._project.attachment.manufacturer
        return "IronRidge"

    @property
    def _attachment_full(self) -> str:
        if self._project:
            a = self._project.attachment
            return f"{a.manufacturer} {a.model}"
        return "IronRidge FlashFoot2"

    @property
    def _jurisdiction(self):
        """Get the jurisdiction engine for this project."""
        if not hasattr(self, "_jurisdiction_cache"):
            self._jurisdiction_cache = None
        if self._jurisdiction_cache:
            return self._jurisdiction_cache

        if self._project:
            jid = self._project.jurisdiction_id
            city = self._project.municipality or ""
            if not city and self._project.address:
                # Extract city from address
                parts = self._project.address.split(",")
                if len(parts) >= 2:
                    city = parts[1].strip()

            if jid == "nec_florida" or (
                not jid
                and self._project.country == "US"
                and any(s in self._project.address.lower() for s in ["florida", ", fl ", ", fl,"])
            ):
                from jurisdiction.nec_florida import FloridaNECJurisdiction

                self._jurisdiction_cache = FloridaNECJurisdiction(city=city)
            elif jid == "nec_california" or (
                not jid
                and self._project.country == "US"
                and any(s in self._project.address.lower() for s in ["california", ", ca ", ", ca,"])
            ):
                from jurisdiction.nec_california import NECCaliforniaEngine

                self._jurisdiction_cache = NECCaliforniaEngine(city=city)
            elif jid == "cec_ontario" or (
                not jid
                and self._project.country == "CA"
                and getattr(self._project, "province_or_state", "").upper() == "ON"
            ):
                # Ontario: ESA/ECRA licensing, Hydro One or Toronto Hydro
                from jurisdiction.cec_ontario import OntarioJurisdiction

                self._jurisdiction_cache = OntarioJurisdiction(city=city)
            elif jid == "cec_bc" or (
                not jid
                and self._project.country == "CA"
                and (
                    getattr(self._project, "province_or_state", "").upper() == "BC"
                    or city.lower()
                    in {
                        "vancouver",
                        "victoria",
                        "kelowna",
                        "surrey",
                        "burnaby",
                        "richmond",
                        "abbotsford",
                        "coquitlam",
                        "langley",
                        "saanich",
                        "nanaimo",
                        "kamloops",
                        "prince george",
                        "penticton",
                        "vernon",
                        "trail",
                        "nelson",
                        "castlegar",
                        "chilliwack",
                        "north vancouver",
                        "west vancouver",
                        "new westminster",
                        "port coquitlam",
                        "port moody",
                    }
                )
            ):
                from jurisdiction.cec_bc import BCJurisdiction

                self._jurisdiction_cache = BCJurisdiction(city=city)
            elif jid == "nec_texas" or (
                not jid
                and self._project.country == "US"
                and any(s in self._project.address.lower() for s in ["texas", ", tx ", ", tx,"])
            ):
                from jurisdiction.nec_texas import TexasNECJurisdiction

                self._jurisdiction_cache = TexasNECJurisdiction(city=city)
            elif jid == "nec_illinois" or (
                not jid
                and self._project.country == "US"
                and any(s in self._project.address.lower() for s in ["illinois", ", il ", ", il,"])
            ):
                from jurisdiction.nec_illinois import IllinoisJurisdiction

                self._jurisdiction_cache = IllinoisJurisdiction(city=city)
            elif jid == "nec_newyork" or (
                not jid
                and self._project.country == "US"
                and any(s in self._project.address.lower() for s in ["new york", ", ny ", ", ny,"])
            ):
                from jurisdiction.nec_newyork import NYJurisdiction

                self._jurisdiction_cache = NYJurisdiction(city=city)
            elif jid == "cec_quebec" or (not jid and self._project.country == "CA"):
                from jurisdiction.cec_quebec import CECQuebecEngine

                self._jurisdiction_cache = CECQuebecEngine()
            else:
                from jurisdiction.nec_base import NECBaseEngine

                self._jurisdiction_cache = NECBaseEngine()
        else:
            from jurisdiction.nec_base import NECBaseEngine

            self._jurisdiction_cache = NECBaseEngine()

        return self._jurisdiction_cache

    @property
    def _code_prefix(self) -> str:
        """'NEC' for US jurisdictions, 'CEC' for Canadian."""
        if self._project and self._project.country == "US":
            return "NEC"
        return "CEC"

    @property
    def _wire_type(self) -> str:
        """Wire type designation: 'THWN-2' for US, 'RW90-XLPE' for CA."""
        if self._project and self._project.country == "US":
            return "THWN-2"
        return "RW90-XLPE"

    @property
    def _building_code(self) -> str:
        """Building code abbreviation from jurisdiction engine."""
        return self._jurisdiction.get_building_code()

    @property
    def _safety_std(self) -> str:
        """Safety standard prefix: 'UL' for US, 'CSA' for CA."""
        if self._project and self._project.country == "US":
            return "UL"
        return "CSA"

    @property
    def _code_edition(self) -> str:
        """Full code edition string from jurisdiction engine."""
        return self._jurisdiction.get_code_edition()

    @property
    def _license_body(self) -> str:
        """Licensing body abbreviation from jurisdiction engine."""
        return self._jurisdiction.get_licensing_body()

    @property
    def _license_body_full(self) -> str:
        """Full licensing body name from jurisdiction engine."""
        return self._jurisdiction.get_licensing_body_full()

    @property
    def _utility_name(self) -> str:
        """Utility company name from jurisdiction engine."""
        city = ""
        if self._project:
            city = self._project.municipality or ""
        return self._jurisdiction.get_utility_info(city).get("name", "Utility")

    @property
    def _utility_info(self) -> dict:
        """Full utility info dict from jurisdiction engine."""
        city = ""
        if self._project:
            city = self._project.municipality or ""
        return self._jurisdiction.get_utility_info(city)

    @property
    def _building_dims_ft(self) -> Optional[Tuple[float, float]]:
        """Building width and depth in feet from GeoTIFF outline.

        Returns (width_ft, depth_ft) or None if no outline available.
        Uses the minimum rotated rectangle to get true building dimensions
        (not inflated by diagonal bounding box).
        """
        if not (self._project and self._project.building_outline_ft
                and len(self._project.building_outline_ft) >= 3):
            return None
        poly = ShapelyPolygon(self._project.building_outline_ft)
        rect = poly.minimum_rotated_rectangle
        coords = list(rect.exterior.coords)
        # Rectangle has 5 coords (closed ring) — measure two adjacent edges
        edge1 = math.sqrt((coords[1][0] - coords[0][0]) ** 2 + (coords[1][1] - coords[0][1]) ** 2)
        edge2 = math.sqrt((coords[2][0] - coords[1][0]) ** 2 + (coords[2][1] - coords[1][1]) ** 2)
        return (max(edge1, edge2), min(edge1, edge2))

    @property
    def _design_temps(self) -> dict:
        """Design temperatures from jurisdiction engine."""
        city = ""
        if self._project:
            city = self._project.municipality or ""
        return self._jurisdiction.get_design_temperatures(city)

    @property
    def _roof_material_display(self) -> str:
        if self._project:
            return self._project.roof_material_display
        return "Composite Shingle"

    @property
    def _main_breaker_a(self) -> int:
        if self._project:
            return self._project.main_panel_breaker_a
        return 200

    @property
    def _bus_rating_a(self) -> int:
        if self._project:
            return self._project.main_panel_bus_rating_a
        return 225

    @property
    def _max_per_branch(self) -> int:
        """Max inverter units per branch circuit (microinverter only)."""
        if self._project and self._project.inverter.is_micro:
            return self._project.inverter.max_units_per_branch_15a or 7
        return 7

    def _calc_ac_kw(self, n_panels: int) -> float:
        """Compute system AC capacity from panel count × inverter output."""
        if self._project and self._project.inverter.is_string:
            return self._project.inverter.ac_kw
        return round(n_panels * self.INV_AC_WATTS_PER_UNIT / 1000, 2)

    def __init__(
        self,
        panel_spec: PanelSpec = None,
        company_name: str = "Solar Co.",
        project_name: str = "Solar Installation",
        designer: str = "AI Solar Design Engine",
        api_key: Optional[str] = None,
        project: "ProjectSpec" = None,
    ):
        """Initialize renderer.

        New mode: pass project=ProjectSpec (all equipment from catalog).
        Legacy mode: pass panel_spec + company/designer args.
        """
        self._project = project

        if project:
            # New mode: derive legacy fields from ProjectSpec
            self.panel = PanelSpec(
                name=project.panel.model,
                wattage=project.panel.wattage_w,
                width_ft=project.panel.width_ft,
                height_ft=project.panel.height_ft,
                efficiency=project.panel.efficiency_pct / 100.0,
            )
            self.company = project.company_name
            self.project_name = project.project_name
            self.designer = project.designer_name
            self.api_key = api_key or os.environ.get("GOOGLE_SOLAR_API_KEY", "")
            # Keep self.project for backward compat (string, not ProjectSpec)
            self.project = project.project_name
        else:
            # Legacy mode
            self.panel = panel_spec or PanelSpec()
            self.company = company_name
            self.project = project_name
            self.designer = designer
            self.api_key = api_key or os.environ.get("GOOGLE_SOLAR_API_KEY", "")

    # ── Address / AHJ helpers ────────────────────────────────────────────

    @staticmethod
    def _extract_municipality(address: str) -> str:
        """Extract the municipality name from a comma-separated address string.

        Examples:
          "34 rue Bernier, Gatineau, QC J8Z 1E8"  →  "Gatineau"
          "42 Ch. de Charlotte, Chelsea, QC J9B 2E7" →  "Chelsea"
          "123 Main St"  →  "Unknown"  (fallback)
        """
        parts = [p.strip() for p in address.split(",")]
        if len(parts) >= 2:
            city = parts[1].strip()
            # Remove trailing postal code token if present (e.g. "Vancouver V5K 1A1" → "Vancouver")
            # Only strip last word if it looks like a postal code (numeric or alphanumeric like "J8T")
            tokens = city.split()
            if tokens and (
                tokens[-1][0].isdigit()
                or (len(tokens[-1]) >= 3 and tokens[-1][0].isalpha() and tokens[-1][1].isdigit())
            ):
                city = " ".join(tokens[:-1]).strip()
            if not city:
                city = parts[1].strip()
            if city:
                return city
        return "Unknown"

    def _build_monthly_chart_svg(self, annual_kwh: float, width: int = 240, height: int = 80) -> str:
        """Monthly production SVG chart — delegated to renderer.page_builders.cover_page."""
        from renderer.page_builders.cover_page import _build_monthly_chart_svg
        return _build_monthly_chart_svg(self, annual_kwh, width, height)

    def _make_ahj_label(self, address: str) -> str:
        """Return the AHJ label string for a given address.

        Delegates to the jurisdiction engine so that neighborhood names within
        larger cities (e.g. Encino → City of Los Angeles) resolve correctly.
        """
        city = HtmlRenderer._extract_municipality(address)
        jur = self._jurisdiction
        if hasattr(jur, "get_ahj_label"):
            return jur.get_ahj_label(city)
        if self._project and self._project.country == "US":
            return f"City of {city}"
        return f"Ville de {city} / RBQ"

    # ── Mercator projection (KEEP EXACTLY AS IS) ────────────────────────

    @staticmethod
    def _meters_per_pixel(lat_deg: float, zoom: int = 20, scale: int = 2) -> float:
        """
        Compute meters-per-pixel for a Google Maps Static API image.
        Formula: 156543.03392 × cos(lat) / 2^zoom / scale
        At lat 45.46°, zoom 20, scale 2: ~0.05235 m/pixel
        """
        lat_rad = math.radians(lat_deg)
        return 156543.03392 * math.cos(lat_rad) / (2**zoom) / scale

    @staticmethod
    def _latlng_to_pixel(
        lat: float,
        lng: float,
        center_lat: float,
        center_lng: float,
        mpp: float,
        img_w: int = 1280,
        img_h: int = 960,
    ) -> Tuple[float, float]:
        """
        Convert a lat/lng to pixel coordinates on the satellite image.
        Uses equirectangular approximation (accurate at this scale).

        dx_meters = (lng - center_lng) × cos(center_lat) × 111319.5
        dy_meters = (lat - center_lat) × 111319.5
        pixel_x = img_w/2 + dx_meters / mpp
        pixel_y = img_h/2 - dy_meters / mpp  (Y inverted)
        """
        center_lat_rad = math.radians(center_lat)
        dx_meters = (lng - center_lng) * math.cos(center_lat_rad) * 111319.5
        dy_meters = (lat - center_lat) * 111319.5
        pixel_x = img_w / 2 + dx_meters / mpp
        pixel_y = img_h / 2 - dy_meters / mpp
        return pixel_x, pixel_y

    # ── Google Maps Static API helper ─────────────────────────────────

    def _fetch_map_b64(
        self,
        lat: float,
        lng: float,
        zoom: int,
        maptype: str,
        size: str = "380x220",
    ) -> str:
        """Fetch a Google Maps Static API image and return as base64 PNG string.

        Returns empty string on any error (no key, network failure, etc.).
        The caller should treat "" as "show placeholder".
        """
        if not self.api_key:
            return ""
        try:
            marker = f"color:red%7C{lat},{lng}"
            url = (
                f"https://maps.googleapis.com/maps/api/staticmap"
                f"?center={lat},{lng}"
                f"&zoom={zoom}"
                f"&size={size}"
                f"&maptype={maptype}"
                f"&markers={marker}"
                f"&key={self.api_key}"
            )
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=12, context=ssl._create_unverified_context()) as resp:
                img_bytes = resp.read()
            return base64.b64encode(img_bytes).decode("ascii")
        except Exception as exc:
            logger.warning("Map fetch failed (%s zoom=%d): %s", maptype, zoom, exc)
            return ""

    # ── Main render entry point ────────────────────────────────────────

    def render(
        self,
        planset: PlansetData,
        placements: List[PlacementResult],
        output_path: str,
        building_insight=None,
        num_api_panels: int = 0,
        quebec_electrical: bool = False,
    ) -> str:
        """Generate the full HTML planset and write to output_path."""
        # Gather stats
        total_panels = sum(pr.total_panels for pr in placements)
        total_kw = sum(pr.total_kw for pr in placements)
        total_kwh = sum(pr.estimated_annual_kwh for pr in placements)

        if num_api_panels and not total_panels:
            total_panels = num_api_panels
            total_kw = round(num_api_panels * self.panel.kw, 2)
            total_kwh = round(total_kw * 3.80 * 365, 0)

        # If the project specifies more panels than the placer found (e.g. demo data
        # has small roof faces), use the authoritative project num_panels.
        if self._project and self._project.num_panels and self._project.num_panels > total_panels:
            total_panels = self._project.num_panels
            total_kw = round(total_panels * self.panel.kw, 2)
            # Also use the authoritative production figure from the project spec so the
            # cover page is internally consistent (panel count, kW, and kWh all match).
            if self._project.target_production_kwh > 0:
                total_kwh = self._project.target_production_kwh
            else:
                total_kwh = round(self._project.estimated_annual_kwh, 0)

        if building_insight and building_insight.panels and num_api_panels:
            api_panels = building_insight.panels[:num_api_panels]
            api_kwh = sum(p.yearly_energy_kwh for p in api_panels)
            if api_kwh > 0:
                total_kwh = round(api_kwh, 0)

        address = planset.metadata.get("address", "")
        if not address and self._project and self._project.address:
            address = self._project.address

        # Build satellite base64
        sat_b64 = ""
        if planset.pages and planset.pages[0].raster_image is not None:
            sat_b64 = self._image_to_b64(planset.pages[0].raster_image)

        page_w = planset.pages[0].width if planset.pages else self.SAT_PX_W
        page_h = planset.pages[0].height if planset.pages else self.SAT_PX_H

        today = date.today().strftime("%Y-%m-%d")

        # Fetch vicinity and aerial map thumbnails for the cover page.
        # These call the Google Maps Static API; gracefully fall back to
        # placeholder boxes when no API key is present (e.g. test runs).
        vicinity_map_b64 = ""
        aerial_map_b64 = ""
        if self.api_key and building_insight:
            # Use confirmed coordinates from ProjectSpec if available,
            # otherwise fall back to API-returned coordinates
            if self._project and self._project.latitude != 0:
                map_lat = self._project.latitude
                map_lng = self._project.longitude
            else:
                map_lat = building_insight.lat
                map_lng = building_insight.lng
            logger.info("Fetching location maps for cover page (%.5f, %.5f)…", map_lat, map_lng)
            vicinity_map_b64 = self._fetch_map_b64(map_lat, map_lng, zoom=14, maptype="roadmap", size="380x220")
            aerial_map_b64 = self._fetch_map_b64(map_lat, map_lng, zoom=19, maptype="satellite", size="380x220")
            if vicinity_map_b64:
                logger.info("Vicinity map fetched OK (%d bytes b64)", len(vicinity_map_b64))
            if aerial_map_b64:
                logger.info("Aerial map fetched OK (%d bytes b64)", len(aerial_map_b64))

        # Build all pages
        pages_html = []

        # A-100: Cover Sheet (new A-series, first page)
        pages_html.append(self._build_cover_sheet_page(address, today, total_panels, total_kw))

        # PV-1: Cover
        pages_html.append(
            self._build_cover_page(
                address,
                total_panels,
                total_kw,
                total_kwh,
                today,
                building_insight,
                vicinity_map_b64=vicinity_map_b64,
                aerial_map_b64=aerial_map_b64,
            )
        )

        # PV-2: Property plan
        pages_html.append(self._build_property_plan_page(address, today, building_insight))

        # PV-3: Site plan (satellite + panels)
        pages_html.append(
            self._build_site_plan_page(
                building_insight, sat_b64, page_w, page_h, num_api_panels, address, today, placements, total_panels
            )
        )

        # PV-3.1: Racking plan (vector)
        pages_html.append(self._build_racking_plan_page(building_insight, num_api_panels, address, today, placements))

        # PV-4: Single-line diagram
        pages_html.append(self._build_single_line_diagram(total_panels, total_kw, address, today))

        # PV-4.1: Electrical calculations
        pages_html.append(self._build_electrical_calcs_page(total_panels, total_kw, address, today))

        # PV-5: Mounting details & BOM
        pages_html.append(self._build_mounting_details_page(total_panels, total_kw, address, today, building_insight))

        # PV-6: Signage/placards
        pages_html.append(self._build_signage_page(address, today))

        # PV-6.1: Placard house
        pages_html.append(self._build_placard_house_page(address, today))

        # PV-7: Circuit map
        pages_html.append(self._build_string_plan_page(building_insight, total_panels, address, today))

        # PV-8.1: Module datasheet
        pages_html.append(self._build_module_datasheet_page(address, today))

        # PV-8.2: Racking datasheet
        pages_html.append(self._build_racking_datasheet_page(address, today))

        # PV-8.3: Attachment datasheet
        pages_html.append(self._build_attachment_datasheet_page(address, today))

        # A-200: Electrical Single Line Diagram
        pages_html.append(self._build_single_line_diagram_page(self._project, placements))

        # A-300: Electrical Details (grounding schedule, conduit routing, OCPD)
        pages_html.append(self._build_electrical_details_page(self._project, placements))

        # Assemble full HTML
        html = self._assemble_html(pages_html)

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)

        logger.info("Wrote planset HTML (%d pages): %s", len(pages_html), output_path)
        return output_path

    # ════════════════════════════════════════════════════════════════════
    # PAGE BUILDERS
    # ════════════════════════════════════════════════════════════════════

    def _build_cover_page(
        self,
        address: str,
        total_panels: int,
        total_kw: float,
        total_kwh: float,
        today: str,
        insight,
        vicinity_map_b64: str = "",
        aerial_map_b64: str = "",
    ) -> str:
        """PV-1: Cover Page — delegated to renderer.page_builders.cover_page."""
        from renderer.page_builders.cover_page import build_cover_page
        return build_cover_page(
            self, address, total_panels, total_kw, total_kwh, today,
            insight, vicinity_map_b64, aerial_map_b64,
        )
    def _build_property_plan_page(self, address: str, today: str, insight=None) -> str:
        """PV-2: Property Plan — delegated to renderer.page_builders.property_plan."""
        from renderer.page_builders.property_plan import build_property_plan_page
        return build_property_plan_page(self, address, today, insight)
    def _build_site_plan_page(
        self,
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
        """PV-3: Site Plan — delegated to renderer.page_builders.site_plan_vector."""
        from renderer.page_builders.site_plan_vector import build_site_plan_page
        return build_site_plan_page(
            self, insight, sat_b64, page_w, page_h, num_api_panels,
            address, today, placements, total_panels,
        )
    def _build_racking_plan_page(
        self, insight, num_api_panels: int, address: str, today: str, placements=None
    ) -> str:
        """PV-3.1: Racking Plan — delegated to renderer.page_builders.racking_plan."""
        from renderer.page_builders.racking_plan import build_racking_plan_page
        return build_racking_plan_page(self, insight, num_api_panels, address, today, placements)
    def _build_string_plan_page(self, insight, total_panels: int, address: str, today: str) -> str:
        """PV-7: String Plan — delegated to renderer.page_builders.string_plan."""
        from renderer.page_builders.string_plan import build_string_plan_page
        return build_string_plan_page(self, insight, total_panels, address, today)

    def _build_single_line_diagram(self, total_panels: int, total_kw: float, address: str, today: str) -> str:
        """PV-4: Single-Line Diagram — delegated to renderer.page_builders.single_line_diagram."""
        from renderer.page_builders.single_line_diagram import build_single_line_diagram
        return build_single_line_diagram(self, total_panels, total_kw, address, today)
    def _build_electrical_calcs_page(self, total_panels: int, total_kw: float, address: str, today: str) -> str:
        """PV-4.1: Electrical Calculations — delegated to renderer.page_builders.electrical_calcs."""
        from renderer.page_builders.electrical_calcs import build_electrical_calcs_page
        return build_electrical_calcs_page(self, total_panels, total_kw, address, today)
    def _build_signage_page(self, address: str, today: str) -> str:
        """PV-6: Electrical Labels — delegated to renderer.page_builders.signage."""
        from renderer.page_builders.signage import build_signage_page
        return build_signage_page(self, address, today)
    def _build_placard_house_page(self, address: str, today: str) -> str:
        """PV-6.1: Placard House — delegated to renderer.page_builders.placard_house."""
        from renderer.page_builders.placard_house import build_placard_house_page
        return build_placard_house_page(self, address, today)
    def _build_mounting_details_page(
        self, total_panels: int, total_kw: float, address: str, today: str, insight
    ) -> str:
        """PV-5: Mounting Details and BOM — delegated to renderer.page_builders.mounting_details."""
        from renderer.page_builders.mounting_details import build_mounting_details_page
        return build_mounting_details_page(self, total_panels, total_kw, address, today, insight)

    # ════════════════════════════════════════════════════════════════════
    # DATASHEET PAGES  (PV-8.1, PV-8.2, PV-8.3)
    # ════════════════════════════════════════════════════════════════════

    def _build_module_datasheet_page(self, address: str, today: str) -> str:
        """PV-8.1: Module Datasheet — delegated to renderer.page_builders.module_datasheet."""
        from renderer.page_builders.module_datasheet import build_module_datasheet_page
        return build_module_datasheet_page(self, address, today)

    def _build_racking_datasheet_page(self, address: str, today: str) -> str:
        """PV-8.2: Racking Datasheet — delegated to renderer.page_builders.racking_datasheet."""
        from renderer.page_builders.racking_datasheet import build_racking_datasheet_page
        return build_racking_datasheet_page(self, address, today)

    def _build_attachment_datasheet_page(self, address: str, today: str) -> str:
        """PV-8.3: Attachment Datasheet — delegated to renderer.page_builders.attachment_datasheet."""
        from renderer.page_builders.attachment_datasheet import build_attachment_datasheet_page
        return build_attachment_datasheet_page(self, address, today)

    def _build_single_line_diagram_page(self, project, placements) -> str:
        """A-200: Electrical Single Line Diagram — delegated to renderer.page_builders.single_line_a200."""
        from renderer.page_builders.single_line_a200 import build_single_line_diagram_page
        return build_single_line_diagram_page(self, project, placements)

    def _build_electrical_details_page(self, project, placements) -> str:
        """A-300: Electrical Details — delegated to renderer.page_builders.electrical_details."""
        from renderer.page_builders.electrical_details import build_electrical_details_page
        return build_electrical_details_page(self, project, placements)

    def _build_cover_sheet_page(self, address: str, today: str, total_panels: int, total_kw: float) -> str:
        """A-100: Cover Sheet — delegated to renderer.page_builders.cover_sheet."""
        from renderer.page_builders.cover_sheet import build_cover_sheet_page
        return build_cover_sheet_page(self, address, today, total_panels, total_kw)

    # ════════════════════════════════════════════════════════════════════
    # HTML ASSEMBLY
    # ════════════════════════════════════════════════════════════════════

    def _assemble_html(self, pages_html: List[str]) -> str:
        """Assemble all pages into a single HTML document."""
        pages_content = "\n".join(pages_html)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Solar Permit Plan Set</title>
  <style>
    * {{
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }}

    body {{
      background: #e8e8e8;
      font-family: Arial, sans-serif;
      color: #000;
    }}

    .page {{
      width: 1280px;
      height: 960px;
      margin: 20px auto;
      background: #fff;
      box-shadow: 0 2px 8px rgba(0,0,0,0.15);
      page-break-after: always;
    }}

    svg {{
      width: 100%;
      height: 100%;
      display: block;
    }}

    /* ── Print / PDF Export ────────────────────────────────── */
    @media print {{
      @page {{
        size: 11in 8.5in landscape;
        margin: 0;
      }}
      body {{
        background: #fff !important;
        margin: 0;
        padding: 0;
      }}
      /* Force browsers to preserve background colors & images */
      *, *::before, *::after {{
        -webkit-print-color-adjust: exact !important;
        print-color-adjust: exact !important;
        color-adjust: exact !important;
      }}
      .page {{
        width: 11in;
        height: 8.5in;
        margin: 0;
        box-shadow: none;
        page-break-after: always;
        page-break-inside: avoid;
      }}
      /* Preserve SVG fills, strokes, and satellite imagery */
      svg, svg *, svg image {{
        -webkit-print-color-adjust: exact !important;
        print-color-adjust: exact !important;
      }}
      /* Hide interactive UI elements when printing */
      #export-toolbar {{
        display: none !important;
      }}
    }}
  </style>
</head>
<body>
{pages_content}

<!-- Export PDF Toolbar (hidden when printing) -->
<div id="export-toolbar" style="
  position: fixed; bottom: 20px; right: 20px; z-index: 9999;
  display: flex; flex-direction: column; align-items: flex-end; gap: 6px;
">
  <button onclick="window.print()" style="
    padding: 10px 20px; border: none; border-radius: 6px;
    background: #000; color: #fff; font-size: 13px; font-weight: 600;
    font-family: Arial, sans-serif; cursor: pointer;
    box-shadow: 0 2px 8px rgba(0,0,0,0.3);
    display: flex; align-items: center; gap: 8px;
  ">
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <path d="M4 1h8v3H4V1zm-2 3h12a2 2 0 012 2v5h-3v4H3v-4H0V6a2 2 0 012-2zm3 7h6v3H5v-3zm7-4a1 1 0 100-2 1 1 0 000 2z" fill="#fff"/>
    </svg>
    Export PDF
  </button>
  <span style="font-size: 10px; color: #888; font-family: Arial, sans-serif;">
    Ctrl+P &bull; Landscape &bull; No margins
  </span>
</div>
</body>
</html>"""

    # ════════════════════════════════════════════════════════════════════
    # UTILITY METHODS
    # ════════════════════════════════════════════════════════════════════

    def _svg_title_block(
        self,
        vw: int,
        vh: int,
        sheet_id: str,
        sheet_title: str,
        subtitle: str,
        page_of: str,
        address: str,
        today: str,
        transparent: bool = False,
    ) -> str:
        """Generate a reusable SVG title block matching the Cubillas/All Valley Solar standard.

        Layout (520 × 130 px, bottom-right corner):
          Row 1 (28px):  Owner name (bold) + address
          Row 2 (17px):  AHJ
          Row 3 (38px):  Contractor info (left) | Contractor signature (right)
          Row 4 (16px):  Sheet title (centered)
          Row 5 (31px):  Date / Drawn By | REV #1 | REV #2 | REV #3
          Right col:     Sheet ID (large bold) spanning full height

        Args:
            vw, vh: SVG viewport width/height
            transparent: If True, uses semi-transparent dark background (for satellite pages)
        """
        tb_w, tb_h = 520, 130
        tb_x = vw - tb_w - 15
        tb_y = vh - tb_h - 15

        # Color scheme
        fill = "rgba(0,0,0,0.75)" if transparent else "#ffffff"
        text_fill = "#ffffff" if transparent else "#000000"
        sub_fill = "rgba(255,255,255,0.65)" if transparent else "#444444"
        border = "rgba(255,255,255,0.35)" if transparent else "#000000"
        div_c = "rgba(255,255,255,0.25)" if transparent else "#aaaaaa"

        # Derive owner name from address (street address before first comma)
        owner_name = address.split(",")[0].strip().upper() + " RESIDENCE"

        # Key x positions
        DIV_X = tb_x + 350  # left/right column divider
        SIG_DIV = tb_x + 192  # divider within row 3 (contractor vs signature)

        # Key row y-positions (from tb_y)
        y1 = tb_y + 28  # end of row 1 (owner/addr)
        y2 = tb_y + 45  # end of row 2 (AHJ)
        y3 = tb_y + 83  # end of row 3 (contractor/sig)
        y4 = tb_y + 99  # end of row 4 (sheet title)
        # row 5: y4 → tb_y+130

        parts = []

        # ── Outer border ──────────────────────────────────────────────────
        parts.append(
            f'<rect x="{tb_x}" y="{tb_y}" width="{tb_w}" height="{tb_h}" '
            f'fill="{fill}" stroke="{border}" stroke-width="1.5"/>'
        )

        # ── Vertical divider (left col / right col) ───────────────────────
        parts.append(
            f'<line x1="{DIV_X}" y1="{tb_y}" x2="{DIV_X}" y2="{tb_y + tb_h}" stroke="{border}" stroke-width="0.8"/>'
        )

        # ── Horizontal row dividers (left column only) ────────────────────
        for yd in [y1, y2, y3, y4]:
            parts.append(f'<line x1="{tb_x}" y1="{yd}" x2="{DIV_X}" y2="{yd}" stroke="{div_c}" stroke-width="0.5"/>')

        lx = tb_x + 6  # left text margin

        # ── Row 1: Owner name + address ───────────────────────────────────
        parts.append(
            f'<text x="{lx}" y="{tb_y + 14}" font-size="11" font-weight="700" '
            f'font-family="Arial" fill="{text_fill}">{owner_name}</text>'
        )
        parts.append(
            f'<text x="{lx}" y="{tb_y + 26}" font-size="7.5" font-family="Arial" fill="{sub_fill}">{address}</text>'
        )

        # ── Row 2: AHJ ────────────────────────────────────────────────────
        parts.append(
            f'<text x="{lx}" y="{y1 + 12}" font-size="8.5" '
            f'font-family="Arial" fill="{text_fill}">AHJ: {self._make_ahj_label(address)}</text>'
        )

        # ── Row 3: Contractor info (left) + Signature (right) ─────────────
        # Inner vertical divider separating contractor and signature sub-columns
        parts.append(f'<line x1="{SIG_DIV}" y1="{y2}" x2="{SIG_DIV}" y2="{y3}" stroke="{div_c}" stroke-width="0.5"/>')
        # Contractor info
        parts.append(
            f'<text x="{lx}" y="{y2 + 12}" font-size="8.5" font-weight="700" '
            f'font-family="Arial" fill="{text_fill}">{self.company}</text>'
        )
        parts.append(
            f'<text x="{lx}" y="{y2 + 23}" font-size="7" '
            f'font-family="Arial" fill="{sub_fill}">{self._project.company_license if self._project and self._project.company_license else self._license_body}</text>'
        )
        parts.append(
            f'<text x="{lx}" y="{y2 + 33}" font-size="7" '
            f'font-family="Arial" fill="{sub_fill}">{self._project.company_email if self._project and self._project.company_email else ""}</text>'
        )
        # Contractor signature area
        parts.append(
            f'<text x="{SIG_DIV + 5}" y="{y2 + 11}" font-size="6.5" '
            f'font-family="Arial" fill="{sub_fill}">CONTRACTOR SIGNATURE</text>'
        )
        parts.append(
            f'<line x1="{SIG_DIV + 5}" y1="{y3 - 9}" x2="{DIV_X - 5}" y2="{y3 - 9}" '
            f'stroke="{div_c}" stroke-width="0.8"/>'
        )

        # ── Row 4: Sheet title ────────────────────────────────────────────
        cx_left = tb_x + 175  # center of left column
        parts.append(
            f'<text x="{cx_left}" y="{y3 + 11}" text-anchor="middle" font-size="9" '
            f'font-weight="700" font-family="Arial" fill="{text_fill}">{sheet_title.upper()}</text>'
        )

        # ── Row 5: Date / Drawn By + REV boxes ────────────────────────────
        parts.append(
            f'<text x="{lx}" y="{y4 + 11}" font-size="7.5" font-family="Arial" fill="{text_fill}">DATE: {today}</text>'
        )
        drawn_label = (self.designer[:8] if len(self.designer) > 8 else self.designer).upper()
        parts.append(
            f'<text x="{lx}" y="{y4 + 22}" font-size="7.5" '
            f'font-family="Arial" fill="{text_fill}">DRAWN BY: {drawn_label}</text>'
        )
        # Three revision boxes
        rev_start = tb_x + 105
        rev_bw = 81  # box width for each REV column
        rev_bh = tb_h - (y4 - tb_y) - 2  # ≈ 29px
        for i, rev_lbl in enumerate(["REV #1:", "REV #2:", "REV #3:"]):
            rx = rev_start + i * rev_bw
            parts.append(
                f'<rect x="{rx}" y="{y4 + 1}" width="{rev_bw - 1}" height="{rev_bh}" '
                f'fill="none" stroke="{div_c}" stroke-width="0.5"/>'
            )
            parts.append(
                f'<text x="{rx + 3}" y="{y4 + 10}" font-size="6.5" '
                f'font-family="Arial" fill="{sub_fill}">{rev_lbl}</text>'
            )

        # ── Right column: Sheet ID (large) + labels + page # ─────────────
        cx_right = (DIV_X + tb_x + tb_w) // 2  # center of right column

        parts.append(
            f'<text x="{cx_right}" y="{tb_y + 62}" text-anchor="middle" font-size="28" '
            f'font-weight="700" font-family="Arial" fill="{text_fill}">{sheet_id}</text>'
        )
        # Sheet title in right column — no truncation; right column is 170px wide,
        # all current titles (≤24 chars) fit at 8.5px (~113px). Subtitle uses 6.5px
        # to accommodate the longest subtitle (~43 chars, ≈153px at 3.57px/char).
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

    @staticmethod
    def _image_to_b64(img_array: np.ndarray) -> str:
        """Convert numpy image array to base64 PNG string."""
        img = Image.fromarray(img_array)
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return base64.b64encode(buf.getvalue()).decode("ascii")

    @staticmethod
    def _azimuth_label(az: float) -> str:
        """Convert azimuth degrees to compass direction."""
        dirs = [
            (0, "N"),
            (45, "NE"),
            (90, "E"),
            (135, "SE"),
            (180, "S"),
            (225, "SW"),
            (270, "W"),
            (315, "NW"),
            (360, "N"),
        ]
        for deg, lbl in dirs:
            if abs(az - deg) <= 22.5:
                return lbl
        return "S"
