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

# Import ProjectSpec and equipment models (optional — falls back to legacy mode)
try:
    from models.project import ProjectSpec
    from models.equipment import PanelCatalogEntry, InverterCatalogEntry
    from engine.bom_calculator import calculate_bom, BOMItem
    from engine.electrical_calc import calculate_string_config
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
        return self.panel.wattage if hasattr(self, 'panel') else 455

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
        if not hasattr(self, '_jurisdiction_cache'):
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

            if jid == "nec_california" or (not jid and self._project.country == "US" and
                any(s in self._project.address.lower() for s in ["california", ", ca ", ", ca,"])):
                from jurisdiction.nec_california import NECCaliforniaEngine
                self._jurisdiction_cache = NECCaliforniaEngine(city=city)
            elif jid == "cec_ontario" or (not jid and self._project.country == "CA" and
                getattr(self._project, 'province_or_state', '').upper() == "ON"):
                # Ontario: ESA/ECRA licensing, Hydro One or Toronto Hydro
                from jurisdiction.cec_ontario import OntarioJurisdiction
                self._jurisdiction_cache = OntarioJurisdiction(city=city)
            elif jid == "cec_bc" or (not jid and self._project.country == "CA" and (
                getattr(self._project, 'province_or_state', '').upper() == "BC" or
                city.lower() in {
                    "vancouver", "victoria", "kelowna", "surrey", "burnaby",
                    "richmond", "abbotsford", "coquitlam", "langley", "saanich",
                    "nanaimo", "kamloops", "prince george", "penticton", "vernon",
                    "trail", "nelson", "castlegar", "chilliwack", "north vancouver",
                    "west vancouver", "new westminster", "port coquitlam", "port moody",
                })):
                from jurisdiction.cec_bc import BCJurisdiction
                self._jurisdiction_cache = BCJurisdiction(city=city)
            elif jid == "cec_quebec" or (not jid and self._project.country == "CA"):
                from jurisdiction.cec_quebec import CECQuebecEngine
                self._jurisdiction_cache = CECQuebecEngine()
            else:
                from jurisdiction.nec_base import NECBaseEngine
                self._jurisdiction_cache = NECBaseEngine()
        else:
            from jurisdiction.cec_quebec import CECQuebecEngine
            self._jurisdiction_cache = CECQuebecEngine()

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
        """Building code: 'CBC' for US (California), 'NBCC' for CA."""
        if self._project and self._project.country == "US":
            return "CBC"
        return "NBCC"

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
            if tokens and (tokens[-1][0].isdigit() or (len(tokens[-1]) >= 3 and tokens[-1][0].isalpha() and tokens[-1][1].isdigit())):
                city = " ".join(tokens[:-1]).strip()
            if not city:
                city = parts[1].strip()
            if city:
                return city
        return "Unknown"

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
        return 156543.03392 * math.cos(lat_rad) / (2 ** zoom) / scale

    @staticmethod
    def _latlng_to_pixel(
        lat: float, lng: float,
        center_lat: float, center_lng: float,
        mpp: float,
        img_w: int = 1280, img_h: int = 960,
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
            vicinity_map_b64 = self._fetch_map_b64(map_lat, map_lng, zoom=14, maptype="roadmap",   size="380x220")
            aerial_map_b64   = self._fetch_map_b64(map_lat, map_lng, zoom=19, maptype="satellite", size="380x220")
            if vicinity_map_b64:
                logger.info("Vicinity map fetched OK (%d bytes b64)", len(vicinity_map_b64))
            if aerial_map_b64:
                logger.info("Aerial map fetched OK (%d bytes b64)", len(aerial_map_b64))

        # Build all pages
        pages_html = []

        # PV-1: Cover
        pages_html.append(self._build_cover_page(
            address, total_panels, total_kw, total_kwh, today, building_insight,
            vicinity_map_b64=vicinity_map_b64,
            aerial_map_b64=aerial_map_b64,
        ))

        # PV-2: Property plan
        pages_html.append(self._build_property_plan_page(
            address, today, building_insight
        ))

        # PV-3: Site plan (satellite + panels)
        pages_html.append(self._build_site_plan_page(
            building_insight, sat_b64, page_w, page_h, num_api_panels,
            address, today, placements, total_panels
        ))

        # PV-3.1: Racking plan (vector)
        pages_html.append(self._build_racking_plan_page(
            building_insight, num_api_panels, address, today, placements
        ))

        # PV-4: Single-line diagram
        pages_html.append(self._build_single_line_diagram(
            total_panels, total_kw, address, today
        ))

        # PV-4.1: Electrical calculations
        pages_html.append(self._build_electrical_calcs_page(
            total_panels, total_kw, address, today
        ))

        # PV-5: Mounting details & BOM
        pages_html.append(self._build_mounting_details_page(
            total_panels, total_kw, address, today, building_insight
        ))

        # PV-6: Signage/placards
        pages_html.append(self._build_signage_page(
            address, today
        ))

        # PV-6.1: Placard house
        pages_html.append(self._build_placard_house_page(
            address, today
        ))

        # PV-7: Circuit map
        pages_html.append(self._build_string_plan_page(
            building_insight, total_panels, address, today
        ))

        # PV-8.1: Module datasheet
        pages_html.append(self._build_module_datasheet_page(
            address, today
        ))

        # PV-8.2: Racking datasheet
        pages_html.append(self._build_racking_datasheet_page(
            address, today
        ))

        # PV-8.3: Attachment datasheet
        pages_html.append(self._build_attachment_datasheet_page(
            address, today
        ))

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

    def _build_cover_page(self, address: str, total_panels: int, total_kw: float,
                         total_kwh: float, today: str, insight,
                         vicinity_map_b64: str = "",
                         aerial_map_b64: str = "") -> str:
        """PV-1: Professional permit cover page matching Cubillas/All Valley Solar standard.

        Layout (1280×960px landscape):
          - Top header bar: company + "PHOTOVOLTAIC SYSTEM" title + address
          - System summary strip: 6-box horizontal (DC kW, AC kW, panels, kWh/yr, panel model, AHJ)
          - 3-column notes area: General Notes (17) | Electrical Notes (17) | Sheet Index + Governing Codes
          - Right column includes: Location Maps (vicinity + aerial) + Sheet Index + Governing Codes
          - Bottom title block: contractor info, revision tracking, date, sheet number
        """
        sheets = [
            ("T-00",  "Cover Page"),
            ("G-01",  "Electrical Notes"),
            ("A-101", "Site Plan"),
            ("A-102", "Racking and Framing Plan"),
            ("A-103", "String Plan"),
            ("A-104", "Attachment Detail"),
            ("E-601", "Electrical Line Diagram"),
            ("E-602", f"Specifications — {self._panel_model_short}"),
            ("E-603", "Signage"),
            ("E-604", "Placard"),
        ]

        sys_ac = self._calc_ac_kw(total_panels)  # 13 × 384VA = 4.99 kW AC

        # Roof segment data for system summary
        seg_azimuth = "175°"
        seg_pitch = "19°"
        if insight and insight.roof_segments:
            primary = insight.roof_segments[0]
            seg_azimuth = f"{primary.azimuth_deg:.0f}°"
            seg_pitch = f"{primary.pitch_deg:.0f}°"

        # ── Sheet index rows ─────────────────────────────────────────────
        sheet_rows = "".join(
            f'<tr>'
            f'<td style="padding:2px 6px; border:1px solid #ccc; font-weight:700; width:60px;">{sid}</td>'
            f'<td style="padding:2px 6px; border:1px solid #ccc;">{title}</td>'
            f'</tr>\n'
            for sid, title in sheets
        )

        # ── General Notes — from jurisdiction engine ────────────────────
        general_notes = self._jurisdiction.get_general_notes()
        # Strip leading numbers if present (engine may include "1. ", "2. " etc.)
        general_notes = [n.lstrip("0123456789. ") if n[0:1].isdigit() else n for n in general_notes]

        # ── Electrical Notes — from jurisdiction engine ──────────────────
        electrical_notes = self._jurisdiction.get_electrical_notes()
        electrical_notes = [n.lstrip("0123456789. ") if n and n[0:1].isdigit() else n for n in electrical_notes]

        def note_item(i, text):
            return (
                f'<div style="display:flex; margin-bottom:3px; line-height:1.35;">'
                f'<span style="min-width:18px; font-weight:700; color:#000;">{i}.</span>'
                f'<span style="color:#111;">{text}</span>'
                f'</div>'
            )

        gen_notes_html = "".join(note_item(i+1, n) for i, n in enumerate(general_notes))
        elec_notes_html = "".join(note_item(i+1, n) for i, n in enumerate(electrical_notes))

        # ── Map thumbnails (real or placeholder) ─────────────────────────
        _map_img_style = (
            "width:100%; height:110px; object-fit:cover; "
            "border:1px solid #aaa; display:block;"
        )
        _map_placeholder_style = (
            "width:100%; height:110px; background:#e8eef3; border:1px solid #aaa; "
            "display:flex; flex-direction:column; align-items:center; "
            "justify-content:center; box-sizing:border-box;"
        )
        if vicinity_map_b64:
            vicinity_map_html = (
                f'<img src="data:image/png;base64,{vicinity_map_b64}" '
                f'style="{_map_img_style}" alt="Vicinity Map"/>'
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
                f'</svg>'
                f'<div style="font-size:8px; color:#999; margin-top:4px;">VICINITY MAP</div>'
                f'<div style="font-size:7px; color:#bbb;">Google Maps (no key)</div>'
                f'</div>'
            )
        if aerial_map_b64:
            aerial_map_html = (
                f'<img src="data:image/png;base64,{aerial_map_b64}" '
                f'style="{_map_img_style}" alt="Aerial View"/>'
            )
        else:
            aerial_map_html = (
                f'<div style="{_map_placeholder_style}">'
                f'<svg width="32" height="32" viewBox="0 0 32 32" fill="none">'
                f'<rect x="4" y="4" width="24" height="24" rx="2" stroke="#999" stroke-width="1.5" fill="none"/>'
                f'<rect x="10" y="10" width="8" height="6" fill="#ccc"/>'
                f'<line x1="4" y1="16" x2="28" y2="16" stroke="#bbb" stroke-width="0.75" stroke-dasharray="2,2"/>'
                f'<line x1="16" y1="4" x2="16" y2="28" stroke="#bbb" stroke-width="0.75" stroke-dasharray="2,2"/>'
                f'</svg>'
                f'<div style="font-size:8px; color:#999; margin-top:4px;">AERIAL VIEW</div>'
                f'<div style="font-size:7px; color:#bbb;">Google Maps (no key)</div>'
                f'</div>'
            )

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
      <div style="font-size:12px; font-weight:700; color:#000; letter-spacing:0.5px;">{self.company.upper()}</div>
      <div style="font-size:7.5px; color:#555; margin-top:3px; line-height:1.4;">Licensed Solar Contractor<br>{self._license_body}</div>
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
        MODULE: &nbsp;({total_panels}) {self.panel.name} [{self.panel.wattage}W] WITH
      </div>
      <div style="font-size:10px; font-weight:700; color:#000; margin-top:1px;">
        INTEGRATED MICROINVERTERS {self.INV_MODEL_SHORT}
      </div>
      <div style="font-size:10px; font-weight:700; color:#000; margin-top:5px;">
        MONITORING: &nbsp;ENPHASE ENVOY (AC GATEWAY)
      </div>
    </div>

    <!-- Right band: AHJ + date -->
    <div style="flex:0 0 150px; padding:8px 10px; display:flex; flex-direction:column; justify-content:center; align-items:flex-end;">
      <div style="font-size:9px; color:#333; text-align:right; line-height:1.6;">
        <div><b>AHJ:</b> {self._make_ahj_label(address)}</div>
        <div><b>Date:</b> {today}</div>
        <div style="margin-top:4px;"><b>Utility:</b> {self._jurisdiction.get_utility_info(self._project.municipality if self._project else '').get('name', 'Utility')}</div>
        <div><b>Az:</b> {seg_azimuth} &nbsp; <b>Tilt:</b> {seg_pitch}</div>
        <div style="margin-top:4px;"><b>Est. Annual:</b> {total_kwh:,.0f} kWh</div>
        <div><b>Offset:</b> {self._project.target_offset_pct if self._project and self._project.target_offset_pct else round(total_kwh / self._project.annual_consumption_kwh * 100) if self._project and self._project.annual_consumption_kwh else 0:.0f}%</div>
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
          {''.join(f'<div><b>{c["code"]}</b> — {c["title"]} ({c["edition"]})</div>' for c in self._jurisdiction.get_governing_codes())}
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
        <div style="font-size:11px; font-weight:700; color:#000;">{self.company}</div>
        <div style="font-size:8px; color:#333;">Licensed Solar Contractor — {self._license_body}</div>
        <div style="font-size:8px; color:#333;">Designer: {self.designer}</div>
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
      <div style="font-size:8px; color:#333; margin-top:2px;">AHJ: {self._make_ahj_label(address)}</div>
      <div style="font-size:8px; color:#333;">Utility: {self._utility_name} (Net Metering)</div>
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
          <td style="padding:2px 4px; border:1px solid #ccc;">QS</td>
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

    def _build_property_plan_page(self, address: str, today: str, insight=None) -> str:
        """PV-2: Property Plan — lot boundaries, building footprint, driveway, setbacks.

        Generates a permit-ready property plan showing:
          - Lot boundary (solid) with dimension annotations in feet-inches
          - Main home footprint with hatch fill
          - Detached shed (rear lot corner)
          - Driveway with gray fill
          - Fence lines (dashed, 3 sides — back + sides)
          - Street identification below lot
          - Dimension callouts (lot size, front/side setbacks)
          - North arrow, scale bar, legend, APN/parcel info box

        Scale: 10 px/ft → annotated as 1'' = 12'-0''
        """
        VW, VH = 1280, 960

        # ── Get REAL dimensions from ProjectSpec + API ───────────────────
        # Building dimensions from API roof segment bounding boxes
        bldg_w_ft = 35.0  # defaults
        bldg_d_ft = 25.0
        if self._project and self._project.building_width_ft > 0:
            bldg_w_ft = self._project.building_width_ft
            bldg_d_ft = self._project.building_depth_ft
        elif insight and insight.roof_segments:
            from engine.roof_analyzer import get_building_dimensions
            dims = get_building_dimensions(insight)
            if dims.get("width_ft", 0) > 5:
                bldg_w_ft = dims["width_ft"]
                bldg_d_ft = dims["depth_ft"]

        # Lot dimensions (from manual entry or estimated)
        lot_w_ft = 65.0
        lot_d_ft = 75.0
        if self._project and self._project.lot_width_ft > 0:
            lot_w_ft = self._project.lot_width_ft
            lot_d_ft = self._project.lot_depth_ft
        else:
            # Estimate: lot is ~2x building + setbacks
            lot_w_ft = max(65, bldg_w_ft + 30)
            lot_d_ft = max(75, bldg_d_ft + 40)

        front_setback = self._project.front_setback_ft if self._project else 15.0
        side_setback = self._project.side_setback_ft if self._project else 5.0

        # Street name from address
        street_name = ""
        if self._project and self._project.street_name:
            street_name = self._project.street_name
        elif address:
            # Extract street name from first part of address
            parts = address.split(",")[0].strip().split()
            if len(parts) > 1:
                street_name = " ".join(parts[1:]).upper()  # skip house number

        # ── Scale to fit page (auto-calculate pixels per foot) ───────────
        max_draw_w = 900   # max drawing area width in pixels
        max_draw_h = 720   # max drawing area height in pixels
        S = min(max_draw_w / lot_w_ft, max_draw_h / lot_d_ft)
        S = max(3, min(S, 12))  # clamp between 3 and 12 px/ft

        lot_w = int(lot_w_ft * S)
        lot_d = int(lot_d_ft * S)

        # Center horizontally; top margin
        lot_x1 = (VW - lot_w) // 2
        lot_y1 = 60
        lot_x2 = lot_x1 + lot_w
        lot_y2 = lot_y1 + lot_d

        # ── Building positions (from real dimensions) ────────────────────
        house_w = int(bldg_w_ft * S)
        house_d = int(bldg_d_ft * S)
        house_x1 = lot_x1 + int(side_setback * S)
        house_x2 = house_x1 + house_w
        house_y2 = lot_y2 - int(front_setback * S)
        house_y1 = house_y2 - house_d

        # Driveway: estimated 10 ft wide, right of house to street
        drv_w_ft = 10.0
        drv_x1 = min(house_x2 + int(3 * S), lot_x2 - int(drv_w_ft * S))
        drv_x2 = lot_x2
        drv_y1 = house_y2
        drv_y2 = lot_y2

        # ── Fence lines: back + two sides (dashed), stops before street ──
        f_inset = int(2 * S)                    # 20 px = 2 ft inside lot
        fence_x1 = lot_x1 + f_inset            # 335
        fence_x2 = lot_x2 - f_inset            # 945
        fence_y1 = lot_y1 + f_inset            # 80
        fence_stop_y = house_y2 - int(3 * S)   # 660 - 30 = 630

        # ── SVG assembly ─────────────────────────────────────────────────
        p = []

        # White background
        p.append(f'<rect width="{VW}" height="{VH}" fill="#ffffff"/>')

        # Engineering drawing border (outer thick + inner thin)
        p.append(f'<rect x="15" y="15" width="{VW - 30}" height="{VH - 30}" '
                 f'fill="none" stroke="#000" stroke-width="3"/>')
        p.append(f'<rect x="23" y="23" width="{VW - 46}" height="{VH - 46}" '
                 f'fill="none" stroke="#000" stroke-width="1"/>')

        # Page heading
        p.append(f'<text x="{lot_x1}" y="44" font-size="14" font-weight="700" '
                 f'font-family="Arial" fill="#000" letter-spacing="1">PROPERTY PLAN</text>')
        p.append(f'<text x="{lot_x1}" y="56" font-size="9" font-family="Arial" fill="#555">'
                 f'Lot boundaries, building footprint &amp; site features</text>')

        # SVG defs: diagonal hatch pattern for buildings
        p.append(
            '<defs>'
            '<pattern id="bldg_hatch" patternUnits="userSpaceOnUse" width="8" height="8">'
            '<path d="M-1,1 l2,-2 M0,8 l8,-8 M7,9 l2,-2" stroke="#aaa" stroke-width="0.8"/>'
            '</pattern>'
            '</defs>'
        )

        # ── Lot boundary (solid, 2.5px) ───────────────────────────────────
        p.append(f'<rect x="{lot_x1}" y="{lot_y1}" width="{lot_w}" height="{lot_d}" '
                 f'fill="none" stroke="#000" stroke-width="2.5"/>')

        # ── Fence lines (dashed) ─────────────────────────────────────────
        dash = 'stroke-dasharray="10,5"'
        p.append(f'<line x1="{fence_x1}" y1="{fence_y1}" x2="{fence_x2}" y2="{fence_y1}" '
                 f'stroke="#000" stroke-width="1.5" {dash}/>')
        p.append(f'<line x1="{fence_x1}" y1="{fence_y1}" x2="{fence_x1}" y2="{fence_stop_y}" '
                 f'stroke="#000" stroke-width="1.5" {dash}/>')
        p.append(f'<line x1="{fence_x2}" y1="{fence_y1}" x2="{fence_x2}" y2="{fence_stop_y}" '
                 f'stroke="#000" stroke-width="1.5" {dash}/>')

        # ── Driveway ─────────────────────────────────────────────────────
        p.append(f'<rect x="{drv_x1}" y="{drv_y1}" width="{drv_x2 - drv_x1}" '
                 f'height="{drv_y2 - drv_y1}" fill="#d0d0d0" stroke="#777" stroke-width="1"/>')
        drv_cx = (drv_x1 + drv_x2) // 2
        drv_cy = (drv_y1 + drv_y2) // 2
        p.append(f'<text x="{drv_cx}" y="{drv_cy}" text-anchor="middle" dominant-baseline="middle" '
                 f'font-size="8" font-family="Arial" fill="#333" '
                 f'transform="rotate(-90,{drv_cx},{drv_cy})">DRIVEWAY</text>')

        # ── Shed (optional — only drawn if lot is large enough) ─────────
        # Shed omitted for now — can be added back as a ProjectSpec field

        # ── Main home ────────────────────────────────────────────────────
        has_outline = (self._project and self._project.building_outline_ft
                       and len(self._project.building_outline_ft) >= 3)

        if has_outline:
            # Draw ACTUAL building shape from GeoTIFF polygon
            outline = self._project.building_outline_ft
            # Convert outline (x_ft, y_ft) to page coords
            # Outline is relative to building corner, scale and position within lot
            outline_xs = [pt[0] for pt in outline]
            outline_ys = [pt[1] for pt in outline]
            out_w = max(outline_xs) - min(outline_xs)
            out_h = max(outline_ys) - min(outline_ys)
            # Center outline in the lot area
            ox_off = house_x1 + (house_w - out_w * S) / 2
            oy_off = house_y1 + (house_d - out_h * S) / 2
            pts_str = " ".join(
                f"{ox_off + (x - min(outline_xs)) * S:.0f},"
                f"{oy_off + (y - min(outline_ys)) * S:.0f}"
                for x, y in outline
            )
            p.append(f'<polygon points="{pts_str}" '
                     f'fill="url(#bldg_hatch)" stroke="none"/>')
            p.append(f'<polygon points="{pts_str}" '
                     f'fill="none" stroke="#000" stroke-width="2.5"/>')
            house_cx = int(ox_off + out_w * S / 2)
            house_cy = int(oy_off + out_h * S / 2)
        else:
            # Fallback: draw as rectangle
            house_cx = (house_x1 + house_x2) // 2
            house_cy = (house_y1 + house_y2) // 2
            p.append(f'<rect x="{house_x1}" y="{house_y1}" width="{house_w}" height="{house_d}" '
                     f'fill="url(#bldg_hatch)" stroke="none"/>')
            p.append(f'<rect x="{house_x1}" y="{house_y1}" width="{house_w}" height="{house_d}" '
                     f'fill="none" stroke="#000" stroke-width="2.5"/>')

        p.append(f'<text x="{house_cx}" y="{house_cy - 10}" text-anchor="middle" '
                 f'font-size="12" font-weight="700" font-family="Arial" fill="#000">MAIN HOME</text>')
        p.append(f'<text x="{house_cx}" y="{house_cy + 8}" text-anchor="middle" '
                 f'font-size="9" font-family="Arial" fill="#444">{bldg_w_ft:.0f}\' x {bldg_d_ft:.0f}\'</text>')

        # ── Street ───────────────────────────────────────────────────────
        import re as _re
        _street_raw = address.split(",")[0].strip() if "," in address else address
        _street_label = _re.sub(r"^\d+\s*", "", _street_raw).upper()
        p.append(f'<line x1="{lot_x1 - 40}" y1="{lot_y2 + 10}" x2="{lot_x2 + 40}" y2="{lot_y2 + 10}" '
                 f'stroke="#000" stroke-width="4"/>')
        p.append(f'<text x="{(lot_x1 + lot_x2) // 2}" y="{lot_y2 + 28}" text-anchor="middle" '
                 f'font-size="11" font-weight="700" font-family="Arial" fill="#000" '
                 f'letter-spacing="2">{_street_label}</text>')

        # ── Dimension annotations ─────────────────────────────────────────
        dc = "#222"

        def dim_h(x1, x2, y, lbl, gap=-14):
            mx = (x1 + x2) // 2
            return (
                f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" stroke="{dc}" stroke-width="0.8"/>'
                f'<line x1="{x1}" y1="{y-5}" x2="{x1}" y2="{y+5}" stroke="{dc}" stroke-width="0.8"/>'
                f'<line x1="{x2}" y1="{y-5}" x2="{x2}" y2="{y+5}" stroke="{dc}" stroke-width="0.8"/>'
                f'<polygon points="{x1},{y} {x1+9},{y-3} {x1+9},{y+3}" fill="{dc}"/>'
                f'<polygon points="{x2},{y} {x2-9},{y-3} {x2-9},{y+3}" fill="{dc}"/>'
                f'<rect x="{mx-24}" y="{y+gap-7}" width="48" height="10" fill="#fff"/>'
                f'<text x="{mx}" y="{y+gap}" text-anchor="middle" '
                f'font-size="9" font-family="Arial" fill="{dc}">{lbl}</text>'
            )

        def dim_v(x, y1, y2, lbl, gap=-14):
            my = (y1 + y2) // 2
            return (
                f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{y2}" stroke="{dc}" stroke-width="0.8"/>'
                f'<line x1="{x-5}" y1="{y1}" x2="{x+5}" y2="{y1}" stroke="{dc}" stroke-width="0.8"/>'
                f'<line x1="{x-5}" y1="{y2}" x2="{x+5}" y2="{y2}" stroke="{dc}" stroke-width="0.8"/>'
                f'<polygon points="{x},{y1} {x-3},{y1+9} {x+3},{y1+9}" fill="{dc}"/>'
                f'<polygon points="{x},{y2} {x-3},{y2-9} {x+3},{y2-9}" fill="{dc}"/>'
                f'<rect x="{x+gap-24}" y="{my-7}" width="48" height="12" fill="#fff"/>'
                f'<text x="{x+gap}" y="{my+3}" text-anchor="middle" dominant-baseline="middle" '
                f'font-size="9" font-family="Arial" fill="{dc}" '
                f'transform="rotate(-90,{x+gap},{my})">{lbl}</text>'
            )

        # Helper: convert decimal feet to feet-inches string
        def ft_in(ft_val):
            feet = int(ft_val)
            inches = round((ft_val - feet) * 12)
            if inches == 12:
                feet += 1; inches = 0
            return f"{feet}'-{inches}\""

        # Lot width (above lot)
        p.append(dim_h(lot_x1, lot_x2, lot_y1 - 20, ft_in(lot_w_ft)))
        # Lot depth (left of lot)
        p.append(dim_v(lot_x1 - 40, lot_y1, lot_y2, ft_in(lot_d_ft)))
        # Front setback (right of lot, house_y2 to lot_y2)
        p.append(dim_v(lot_x2 + 38, house_y2, lot_y2, ft_in(front_setback)))
        # Left side setback (lot_x1 to house_x1, below lot)
        p.append(dim_h(lot_x1, house_x1, lot_y2 + 45, ft_in(side_setback)))

        # Front setback indicator line (dashed red)
        p.append(f'<line x1="{lot_x1 + 5}" y1="{house_y2}" x2="{lot_x2 - 5}" y2="{house_y2}" '
                 f'stroke="#aa0000" stroke-width="0.8" stroke-dasharray="6,4"/>')
        p.append(f'<text x="{lot_x1 + 10}" y="{house_y2 - 4}" font-size="7" '
                 f'font-family="Arial" fill="#aa0000">FRONT SETBACK {ft_in(front_setback)}</text>')

        # ── North arrow ───────────────────────────────────────────────────
        na_cx, na_cy, na_r = 1150, 130, 36
        p.append(f'<circle cx="{na_cx}" cy="{na_cy}" r="{na_r}" fill="none" '
                 f'stroke="#000" stroke-width="1.5"/>')
        p.append(f'<polygon points="{na_cx},{na_cy - na_r + 6} {na_cx - 11},{na_cy + 12} '
                 f'{na_cx},{na_cy - 2}" fill="#000"/>')
        p.append(f'<polygon points="{na_cx},{na_cy - na_r + 6} {na_cx + 11},{na_cy + 12} '
                 f'{na_cx},{na_cy - 2}" fill="#fff" stroke="#000" stroke-width="1"/>')
        p.append(f'<line x1="{na_cx}" y1="{na_cy - 2}" x2="{na_cx}" y2="{na_cy + na_r - 6}" '
                 f'stroke="#000" stroke-width="1.5"/>')
        p.append(f'<text x="{na_cx}" y="{na_cy - na_r - 6}" text-anchor="middle" '
                 f'font-size="15" font-weight="700" font-family="Arial" fill="#000">N</text>')

        # ── APN / Parcel info box ─────────────────────────────────────────
        apn_x, apn_y = 1080, 186
        p.append(f'<rect x="{apn_x}" y="{apn_y}" width="185" height="62" '
                 f'fill="#fff" stroke="#000" stroke-width="1"/>')
        p.append(f'<text x="{apn_x + 92}" y="{apn_y + 14}" text-anchor="middle" '
                 f'font-size="8" font-weight="700" font-family="Arial" fill="#000">PARCEL INFORMATION</text>')
        p.append(f'<line x1="{apn_x}" y1="{apn_y + 18}" x2="{apn_x + 185}" y2="{apn_y + 18}" '
                 f'stroke="#000" stroke-width="0.5"/>')
        p.append(f'<text x="{apn_x + 8}" y="{apn_y + 31}" '
                 f'font-size="8" font-family="Arial" fill="#000">APN: 07-540-01-05-XXX</text>')
        p.append(f'<text x="{apn_x + 8}" y="{apn_y + 43}" '
                 f'font-size="8" font-family="Arial" fill="#000">ZONING: R2 - RESIDENTIAL</text>')
        p.append(f'<text x="{apn_x + 8}" y="{apn_y + 55}" '
                 f'font-size="8" font-family="Arial" fill="#000">LOT AREA: 4,875 sq.ft. (452.9 m2)</text>')

        # ── Legend ────────────────────────────────────────────────────────
        lgd_x, lgd_y = 32, 565
        p.append(f'<rect x="{lgd_x}" y="{lgd_y}" width="228" height="120" '
                 f'fill="#fff" stroke="#000" stroke-width="1"/>')
        p.append(f'<text x="{lgd_x + 114}" y="{lgd_y + 15}" text-anchor="middle" '
                 f'font-size="9" font-weight="700" font-family="Arial" fill="#000">LEGEND</text>')
        p.append(f'<line x1="{lgd_x}" y1="{lgd_y + 20}" x2="{lgd_x + 228}" y2="{lgd_y + 20}" '
                 f'stroke="#000" stroke-width="0.5"/>')
        # Property line entry
        p.append(f'<line x1="{lgd_x + 10}" y1="{lgd_y + 36}" x2="{lgd_x + 55}" y2="{lgd_y + 36}" '
                 f'stroke="#000" stroke-width="2.5"/>')
        p.append(f'<text x="{lgd_x + 65}" y="{lgd_y + 40}" '
                 f'font-size="8" font-family="Arial" fill="#000">PROPERTY LINE</text>')
        # Fence line entry
        p.append(f'<line x1="{lgd_x + 10}" y1="{lgd_y + 57}" x2="{lgd_x + 55}" y2="{lgd_y + 57}" '
                 f'stroke="#000" stroke-width="1.5" stroke-dasharray="8,4"/>')
        p.append(f'<text x="{lgd_x + 65}" y="{lgd_y + 61}" '
                 f'font-size="8" font-family="Arial" fill="#000">FENCE LINE</text>')
        # Building footprint entry
        p.append(f'<rect x="{lgd_x + 10}" y="{lgd_y + 68}" width="45" height="15" '
                 f'fill="url(#bldg_hatch)" stroke="#000" stroke-width="1.5"/>')
        p.append(f'<text x="{lgd_x + 65}" y="{lgd_y + 80}" '
                 f'font-size="8" font-family="Arial" fill="#000">BUILDING FOOTPRINT</text>')
        # Driveway entry
        p.append(f'<rect x="{lgd_x + 10}" y="{lgd_y + 90}" width="45" height="15" '
                 f'fill="#d0d0d0" stroke="#777" stroke-width="1"/>')
        p.append(f'<text x="{lgd_x + 65}" y="{lgd_y + 102}" '
                 f'font-size="8" font-family="Arial" fill="#000">DRIVEWAY / PAVEMENT</text>')
        # Setback line entry
        p.append(f'<line x1="{lgd_x + 10}" y1="{lgd_y + 114}" x2="{lgd_x + 55}" y2="{lgd_y + 114}" '
                 f'stroke="#aa0000" stroke-width="1" stroke-dasharray="6,4"/>')
        p.append(f'<text x="{lgd_x + 65}" y="{lgd_y + 118}" '
                 f'font-size="8" font-family="Arial" fill="#000">SETBACK LINE</text>')

        # ── Scale bar ─────────────────────────────────────────────────────
        sb_x, sb_y = 32, 710
        p.append(f'<text x="{sb_x}" y="{sb_y - 8}" font-size="9" font-weight="700" '
                 f'font-family="Arial" fill="#000">SCALE: 1 in = 12\'-0\"</text>')
        for seg in range(3):
            fill = "#000" if seg % 2 == 0 else "#fff"
            p.append(f'<rect x="{sb_x + seg * 100}" y="{sb_y}" width="100" height="10" '
                     f'fill="{fill}" stroke="#000" stroke-width="1"/>')
        for i, ft in enumerate([0, 10, 20, 30]):
            p.append(f'<text x="{sb_x + i * 100}" y="{sb_y + 23}" text-anchor="middle" '
                     f'font-size="8" font-family="Arial" fill="#000">{ft}\'</text>')

        # ── Notes box ─────────────────────────────────────────────────────
        notes_x, notes_y = 32, 748
        notes = [
            "All dimensions are approximate. Field verify before construction.",
            "Property boundaries based on typical residential lot.",
            "Building setbacks per applicable municipal zoning by-law. Verify with AHJ.",
            "APN provided for permit reference only.",
        ]
        p.append(f'<rect x="{notes_x}" y="{notes_y}" width="270" height="70" '
                 f'fill="#ffffff" stroke="#888" stroke-width="1"/>')
        p.append(f'<text x="{notes_x + 8}" y="{notes_y + 13}" font-size="8" font-weight="700" '
                 f'font-family="Arial" fill="#000">NOTES:</text>')
        for ni, note in enumerate(notes):
            p.append(f'<text x="{notes_x + 8}" y="{notes_y + 25 + ni * 13}" '
                     f'font-size="7.5" font-family="Arial" fill="#333">{ni + 1}. {note}</text>')

        # ── Title block ───────────────────────────────────────────────────
        p.append(self._svg_title_block(
            VW, VH, "A-101", "Site Plan", "Property Plan", "2 of 13", address, today
        ))

        svg_content = "\n".join(p)
        return (
            f'<div class="page"><svg width="100%" height="100%" '
            f'viewBox="0 0 {VW} {VH}" xmlns="http://www.w3.org/2000/svg" '
            f'style="background:#fff;">{svg_content}</svg></div>'
        )

    def _build_site_plan_page(self, insight, sat_b64: str, page_w: int, page_h: int,
                             num_api_panels: int, address: str, today: str,
                             placements: List[PlacementResult],
                             total_panels: int = 0) -> str:
        """PV-3: Professional architectural site plan.

        With satellite: Shows satellite background with Mercator-projected panels,
        zoomed to panel area via SVG viewBox.

        Without satellite: Draws a proper engineering site plan on white paper —
        property boundary, building footprint, roof with ridge line, panel array,
        street, equipment locations, setback lines, dimensions, etc.
        """
        if not insight or not insight.panels:
            return self._build_blank_site_plan(address, today)

        # Use project-authoritative count first, then num_api_panels fallback,
        # then all API panels. This ensures the site plan panel count matches
        # the cover page and electrical calcs.
        _limit = total_panels or num_api_panels or 0
        panels = insight.panels[:_limit] if _limit else insight.panels
        mpp = self._meters_per_pixel(insight.lat)
        n_panels = len(panels)
        # Display kW from ProjectSpec when available so it matches cover page
        if self._project and self._project.num_panels and n_panels == self._project.num_panels:
            total_kw_display = round(self._project.system_dc_kw, 2)
        else:
            total_kw_display = round(n_panels * self.panel.kw, 2)

        # If we have a real satellite image, use the satellite overlay approach
        if sat_b64:
            return self._build_site_plan_satellite(
                insight, sat_b64, page_w, page_h, panels, mpp,
                n_panels, total_kw_display, address, today
            )

        # ══════════════════════════════════════════════════════════════
        # VECTOR SITE PLAN (no satellite image)
        # Professional architectural drawing on white paper
        # ══════════════════════════════════════════════════════════════
        VW, VH = 1280, 960
        svg = []

        # ── Defs: arrow markers, hatching patterns ─────────────────────
        svg.append('''<defs>
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
        </defs>''')

        # ── Page border ────────────────────────────────────────────────
        svg.append(f'<rect x="15" y="15" width="{VW-30}" height="{VH-30}" '
                   f'fill="none" stroke="#000" stroke-width="2"/>')

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

        # Building dimensions (estimate from roof segments or panel spread)
        bldg_w_m = 12.0  # typical house width
        bldg_h_m = 8.0   # typical house depth
        if insight.roof_segments:
            max_area = max(s.area_m2 for s in insight.roof_segments)
            # Estimate from largest roof segment
            bldg_w_m = max(10.0, math.sqrt(max_area * 2) * 1.2)
            bldg_h_m = max(7.0, math.sqrt(max_area * 2) * 0.8)

        # Property dimensions (typical suburban lot)
        lot_w_m = max(bldg_w_m + 8.0, 18.0)  # min 4m setback each side
        lot_h_m = max(bldg_h_m + 16.0, 30.0)  # front + back setbacks

        # ── Scale: fit the property into the drawing area ──────────────
        draw_area_w = VW - 120  # margins for labels/dimensions
        draw_area_h = VH - 200  # top margin + title block
        draw_cx = VW / 2
        draw_top = 80

        scale_x = draw_area_w / lot_w_m
        scale_y = draw_area_h / lot_h_m
        scale = min(scale_x, scale_y) * 0.85  # leave breathing room
        scale_label = f'1:{1/scale * 25.4:.0f}'  # approximate

        def m_to_px(mx, my):
            """Convert meters (relative to lot center) to SVG pixels."""
            return (draw_cx + mx * scale, draw_top + draw_area_h / 2 + my * scale)

        # ── Property boundary (dash-dot line) ──────────────────────────
        lot_x1, lot_y1 = m_to_px(-lot_w_m/2, -lot_h_m/2)
        lot_x2, lot_y2 = m_to_px(lot_w_m/2, lot_h_m/2)

        # Grass fill
        svg.append(f'<rect x="{lot_x1:.0f}" y="{lot_y1:.0f}" '
                   f'width="{lot_x2-lot_x1:.0f}" height="{lot_y2-lot_y1:.0f}" '
                   f'fill="url(#grass-hatch)" opacity="0.3"/>')

        # Property line
        svg.append(f'<rect x="{lot_x1:.0f}" y="{lot_y1:.0f}" '
                   f'width="{lot_x2-lot_x1:.0f}" height="{lot_y2-lot_y1:.0f}" '
                   f'fill="none" stroke="#000" stroke-width="1.5" '
                   f'stroke-dasharray="12,3,3,3"/>')

        # Property line label
        svg.append(f'<text x="{(lot_x1+lot_x2)/2:.0f}" y="{lot_y1 - 6:.0f}" '
                   f'text-anchor="middle" font-size="9" font-family="Arial" '
                   f'fill="#444" font-style="italic">PROPERTY LINE (TYP.)</text>')

        # ── Street at bottom ───────────────────────────────────────────
        street_y = lot_y2 + 20
        street_h = 50
        svg.append(f'<rect x="{lot_x1 - 40:.0f}" y="{street_y:.0f}" '
                   f'width="{lot_x2 - lot_x1 + 80:.0f}" height="{street_h:.0f}" '
                   f'fill="#e8e8e8" stroke="#000" stroke-width="0.5"/>')
        # Center line
        svg.append(f'<line x1="{lot_x1 - 40:.0f}" y1="{street_y + street_h/2:.0f}" '
                   f'x2="{lot_x2 + 40:.0f}" y2="{street_y + street_h/2:.0f}" '
                   f'stroke="#888" stroke-width="1" stroke-dasharray="15,10"/>')
        # Street name
        if self._project and self._project.street_name:
            street_name = self._project.street_name
        elif "," in address:
            import re as _re2
            _raw = address.split(",")[0].strip()
            street_name = _re2.sub(r"^\d+\s*", "", _raw).upper()
        else:
            street_name = "STREET"
        svg.append(f'<text x="{draw_cx:.0f}" y="{street_y + street_h/2 + 4:.0f}" '
                   f'text-anchor="middle" font-size="10" font-family="Arial" '
                   f'fill="#555" font-weight="600" letter-spacing="2">{street_name.upper()}</text>')

        # ── Sidewalk ───────────────────────────────────────────────────
        sw_y = street_y - 10
        svg.append(f'<rect x="{lot_x1 - 20:.0f}" y="{sw_y:.0f}" '
                   f'width="{lot_x2 - lot_x1 + 40:.0f}" height="10" '
                   f'fill="#f0f0f0" stroke="#999" stroke-width="0.3"/>')

        # ── Driveway ──────────────────────────────────────────────────
        drv_w = 3.5 * scale
        drv_x = lot_x1 + (lot_x2 - lot_x1) * 0.25
        svg.append(f'<rect x="{drv_x:.0f}" y="{lot_y2 - 2:.0f}" '
                   f'width="{drv_w:.0f}" height="{sw_y - lot_y2 + 12:.0f}" '
                   f'fill="#d8d8d8" stroke="#999" stroke-width="0.5"/>')
        svg.append(f'<text x="{drv_x + drv_w/2:.0f}" y="{lot_y2 + 15:.0f}" '
                   f'text-anchor="middle" font-size="7" font-family="Arial" fill="#777">DRVWY</text>')

        # ── Building footprint ─────────────────────────────────────────
        bldg_offset_y = -2.0  # building offset from lot center (slightly toward front)
        bx1, by1 = m_to_px(-bldg_w_m/2, bldg_offset_y - bldg_h_m/2)
        bx2, by2 = m_to_px(bldg_w_m/2, bldg_offset_y + bldg_h_m/2)

        svg.append(f'<rect x="{bx1:.0f}" y="{by1:.0f}" '
                   f'width="{bx2-bx1:.0f}" height="{by2-by1:.0f}" '
                   f'fill="#f5f3f0" stroke="#000" stroke-width="2"/>')

        # Building label
        svg.append(f'<text x="{(bx1+bx2)/2:.0f}" y="{(by1+by2)/2 + 4:.0f}" '
                   f'text-anchor="middle" font-size="11" font-family="Arial" '
                   f'fill="#333" font-weight="700">RESIDENCE</text>')
        svg.append(f'<text x="{(bx1+bx2)/2:.0f}" y="{(by1+by2)/2 + 18:.0f}" '
                   f'text-anchor="middle" font-size="9" font-family="Arial" fill="#666">'
                   f'{bldg_w_m:.1f}m × {bldg_h_m:.1f}m</text>')

        # ── Roof ridge line ────────────────────────────────────────────
        ridge_y = (by1 + by2) / 2
        svg.append(f'<line x1="{bx1:.0f}" y1="{ridge_y:.0f}" '
                   f'x2="{bx2:.0f}" y2="{ridge_y:.0f}" '
                   f'stroke="#000" stroke-width="1" stroke-dasharray="6,3"/>')
        svg.append(f'<text x="{bx2 + 6:.0f}" y="{ridge_y + 4:.0f}" '
                   f'font-size="8" font-family="Arial" fill="#555" font-style="italic">RIDGE</text>')

        # ── Eave lines ─────────────────────────────────────────────────
        eave_overhang = 0.5 * scale  # 0.5m overhang
        svg.append(f'<line x1="{bx1 - eave_overhang:.0f}" y1="{by1:.0f}" '
                   f'x2="{bx2 + eave_overhang:.0f}" y2="{by1:.0f}" '
                   f'stroke="#666" stroke-width="0.8" stroke-dasharray="3,2"/>')
        svg.append(f'<line x1="{bx1 - eave_overhang:.0f}" y1="{by2:.0f}" '
                   f'x2="{bx2 + eave_overhang:.0f}" y2="{by2:.0f}" '
                   f'stroke="#666" stroke-width="0.8" stroke-dasharray="3,2"/>')

        # ── Solar panel array (south side of ridge) ────────────────────
        # Place panels on the south (bottom) side of the building
        # Use actual panel positions relative to cluster center, mapped onto south roof
        array_cx = (bx1 + bx2) / 2
        array_cy = (ridge_y + by2) / 2  # center of south roof face

        # Map panel cluster to drawing coordinates
        if len(panel_positions_m) > 1:
            cluster_spread_x = max(p_xs) - min(p_xs) + insight.panel_height_m  # LANDSCAPE
            cluster_spread_y = max(p_ys) - min(p_ys) + insight.panel_width_m
        else:
            cluster_spread_x = insight.panel_height_m
            cluster_spread_y = insight.panel_width_m

        # Array bounding box
        arr_w = cluster_spread_x * scale
        arr_h = cluster_spread_y * scale
        arr_x1 = array_cx - arr_w / 2
        arr_y1 = array_cy - arr_h / 2
        arr_x2 = array_cx + arr_w / 2
        arr_y2 = array_cy + arr_h / 2

        # Array background fill
        svg.append(f'<rect x="{arr_x1:.0f}" y="{arr_y1:.0f}" '
                   f'width="{arr_w:.0f}" height="{arr_h:.0f}" '
                   f'fill="url(#panel-hatch)" stroke="none"/>')

        # Draw individual panels
        for idx, (pmx, pmy) in enumerate(panel_positions_m):
            # Position relative to cluster center
            rel_x = (pmx - cluster_cx_m) * scale
            rel_y = -(pmy - cluster_cy_m) * scale  # Y inverted

            p_obj = panels[idx]
            if p_obj.orientation == "LANDSCAPE":
                pw = insight.panel_height_m * scale  # long edge horizontal
                ph = insight.panel_width_m * scale
            else:
                pw = insight.panel_width_m * scale
                ph = insight.panel_height_m * scale

            pcx = array_cx + rel_x
            pcy = array_cy + rel_y

            # Panel rectangle
            svg.append(f'<rect x="{pcx - pw/2:.1f}" y="{pcy - ph/2:.1f}" '
                       f'width="{pw:.1f}" height="{ph:.1f}" '
                       f'fill="#ffffff" stroke="#000000" stroke-width="1"/>')
            # Cell grid (3 vertical lines)
            for ci in range(1, 3):
                gx = pcx - pw/2 + (pw / 3) * ci
                svg.append(f'<line x1="{gx:.1f}" y1="{pcy - ph/2:.1f}" '
                           f'x2="{gx:.1f}" y2="{pcy + ph/2:.1f}" '
                           f'stroke="#cccccc" stroke-width="0.5"/>')
            # Panel number
            svg.append(f'<text x="{pcx:.1f}" y="{pcy + 3:.1f}" text-anchor="middle" '
                       f'font-size="7" font-family="Arial" fill="#000000" font-weight="600">'
                       f'{idx+1}</text>')

        # Array outline (bold dashed)
        svg.append(f'<rect x="{arr_x1 - 3:.0f}" y="{arr_y1 - 3:.0f}" '
                   f'width="{arr_w + 6:.0f}" height="{arr_h + 6:.0f}" '
                   f'fill="none" stroke="#000000" stroke-width="1.5" stroke-dasharray="8,4"/>')

        # Array label with leader
        arr_label_x = arr_x2 + 40
        arr_label_y = arr_y1 + 10
        svg.append(f'<line x1="{arr_x2 + 3:.0f}" y1="{(arr_y1+arr_y2)/2:.0f}" '
                   f'x2="{arr_label_x:.0f}" y2="{arr_label_y:.0f}" '
                   f'stroke="#000" stroke-width="0.8"/>')
        svg.append(f'<circle cx="{arr_x2 + 3:.0f}" cy="{(arr_y1+arr_y2)/2:.0f}" r="2" fill="#000"/>')

        # Array callout box
        cb_w, cb_h = 180, 70
        svg.append(f'<rect x="{arr_label_x:.0f}" y="{arr_label_y - 10:.0f}" '
                   f'width="{cb_w}" height="{cb_h}" '
                   f'fill="#fff" stroke="#000" stroke-width="1"/>')
        svg.append(f'<text x="{arr_label_x + 8:.0f}" y="{arr_label_y + 4:.0f}" '
                   f'font-size="10" font-weight="700" font-family="Arial" fill="#000">'
                   f'PV ARRAY ({n_panels} PANELS)</text>')
        svg.append(f'<text x="{arr_label_x + 8:.0f}" y="{arr_label_y + 18:.0f}" '
                   f'font-size="9" font-family="Arial" fill="#333">'
                   f'{self.panel.name}</text>')
        svg.append(f'<text x="{arr_label_x + 8:.0f}" y="{arr_label_y + 31:.0f}" '
                   f'font-size="9" font-family="Arial" fill="#333">'
                   f'{total_kw_display:.2f} kW DC  |  {self.panel.wattage}W/panel</text>')
        _orient_label = (self._project.panel_orientation.upper()
                         if self._project and hasattr(self._project, 'panel_orientation')
                         else "PORTRAIT")
        svg.append(f'<text x="{arr_label_x + 8:.0f}" y="{arr_label_y + 44:.0f}" '
                   f'font-size="9" font-family="Arial" fill="#333">{_orient_label} orientation</text>')

        # ── Array dimension lines ──────────────────────────────────────
        # Bottom dimension (array width)
        dim_y = arr_y2 + 20
        svg.append(f'<line x1="{arr_x1:.0f}" y1="{arr_y2:.0f}" '
                   f'x2="{arr_x1:.0f}" y2="{dim_y + 5:.0f}" '
                   f'stroke="#000" stroke-width="0.5"/>')
        svg.append(f'<line x1="{arr_x2:.0f}" y1="{arr_y2:.0f}" '
                   f'x2="{arr_x2:.0f}" y2="{dim_y + 5:.0f}" '
                   f'stroke="#000" stroke-width="0.5"/>')
        svg.append(f'<line x1="{arr_x1:.0f}" y1="{dim_y:.0f}" '
                   f'x2="{arr_x2:.0f}" y2="{dim_y:.0f}" '
                   f'stroke="#000" stroke-width="0.7" '
                   f'marker-start="url(#dim-arrow-l)" marker-end="url(#dim-arrow-r)"/>')
        svg.append(f'<text x="{(arr_x1+arr_x2)/2:.0f}" y="{dim_y + 14:.0f}" '
                   f'text-anchor="middle" font-size="9" font-family="Arial" fill="#000">'
                   f'{cluster_spread_x:.2f} m</text>')

        # Right dimension (array depth)
        dim_x = arr_x1 - 20
        svg.append(f'<line x1="{arr_x1:.0f}" y1="{arr_y1:.0f}" '
                   f'x2="{dim_x - 5:.0f}" y2="{arr_y1:.0f}" '
                   f'stroke="#000" stroke-width="0.5"/>')
        svg.append(f'<line x1="{arr_x1:.0f}" y1="{arr_y2:.0f}" '
                   f'x2="{dim_x - 5:.0f}" y2="{arr_y2:.0f}" '
                   f'stroke="#000" stroke-width="0.5"/>')
        svg.append(f'<line x1="{dim_x:.0f}" y1="{arr_y1:.0f}" '
                   f'x2="{dim_x:.0f}" y2="{arr_y2:.0f}" '
                   f'stroke="#000" stroke-width="0.7" '
                   f'marker-start="url(#dim-arrow-l)" marker-end="url(#dim-arrow-r)"/>')
        svg.append(f'<text x="{dim_x - 5:.0f}" y="{(arr_y1+arr_y2)/2:.0f}" '
                   f'text-anchor="middle" font-size="9" font-family="Arial" fill="#000" '
                   f'transform="rotate(-90,{dim_x - 5:.0f},{(arr_y1+arr_y2)/2:.0f})">'
                   f'{cluster_spread_y:.2f} m</text>')

        # ── Property dimension lines ───────────────────────────────────
        # Top (lot width)
        pdim_y = lot_y1 - 18
        svg.append(f'<line x1="{lot_x1:.0f}" y1="{lot_y1:.0f}" '
                   f'x2="{lot_x1:.0f}" y2="{pdim_y - 3:.0f}" stroke="#000" stroke-width="0.5"/>')
        svg.append(f'<line x1="{lot_x2:.0f}" y1="{lot_y1:.0f}" '
                   f'x2="{lot_x2:.0f}" y2="{pdim_y - 3:.0f}" stroke="#000" stroke-width="0.5"/>')
        svg.append(f'<line x1="{lot_x1:.0f}" y1="{pdim_y:.0f}" '
                   f'x2="{lot_x2:.0f}" y2="{pdim_y:.0f}" '
                   f'stroke="#000" stroke-width="0.7" '
                   f'marker-start="url(#dim-arrow-l)" marker-end="url(#dim-arrow-r)"/>')
        svg.append(f'<text x="{(lot_x1+lot_x2)/2:.0f}" y="{pdim_y - 4:.0f}" '
                   f'text-anchor="middle" font-size="9" font-family="Arial" fill="#000">'
                   f'{lot_w_m:.1f} m</text>')

        # Left side (lot depth)
        pdim_x = lot_x1 - 18
        svg.append(f'<line x1="{lot_x1:.0f}" y1="{lot_y1:.0f}" '
                   f'x2="{pdim_x - 3:.0f}" y2="{lot_y1:.0f}" stroke="#000" stroke-width="0.5"/>')
        svg.append(f'<line x1="{lot_x1:.0f}" y1="{lot_y2:.0f}" '
                   f'x2="{pdim_x - 3:.0f}" y2="{lot_y2:.0f}" stroke="#000" stroke-width="0.5"/>')
        svg.append(f'<line x1="{pdim_x:.0f}" y1="{lot_y1:.0f}" '
                   f'x2="{pdim_x:.0f}" y2="{lot_y2:.0f}" '
                   f'stroke="#000" stroke-width="0.7" '
                   f'marker-start="url(#dim-arrow-l)" marker-end="url(#dim-arrow-r)"/>')
        svg.append(f'<text x="{pdim_x - 5:.0f}" y="{(lot_y1+lot_y2)/2:.0f}" '
                   f'text-anchor="middle" font-size="9" font-family="Arial" fill="#000" '
                   f'transform="rotate(-90,{pdim_x - 5:.0f},{(lot_y1+lot_y2)/2:.0f})">'
                   f'{lot_h_m:.1f} m</text>')

        # ── Building setback dimensions ────────────────────────────────
        # Front setback (building to property line at bottom)
        front_setback_m = (lot_h_m / 2) - (bldg_offset_y + bldg_h_m / 2)
        fs_y1 = by2
        fs_y2 = lot_y2
        fs_x = bx2 + 30
        svg.append(f'<line x1="{fs_x:.0f}" y1="{fs_y1:.0f}" '
                   f'x2="{fs_x:.0f}" y2="{fs_y2:.0f}" '
                   f'stroke="#cc0000" stroke-width="0.7" '
                   f'marker-start="url(#dim-arrow-l)" marker-end="url(#dim-arrow-r)"/>')
        svg.append(f'<text x="{fs_x + 5:.0f}" y="{(fs_y1+fs_y2)/2 + 3:.0f}" '
                   f'font-size="8" font-family="Arial" fill="#cc0000">'
                   f'{front_setback_m:.1f}m SETBACK</text>')

        # ── Equipment callout symbols (UM / MP / LC / INV / DCD) ──────────
        # Professional style: circle bubble with code + horizontal leader + description box

        def _equip_callout(cx, cy, code, label1, label2="", right=True, lw=185):
            """Return SVG string for a professional equipment callout symbol."""
            r = 12
            parts = []
            # Circle bubble with abbreviated code
            parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" '
                         f'fill="#ffffff" stroke="#000000" stroke-width="1.5"/>')
            parts.append(f'<text x="{cx:.1f}" y="{cy + 4:.1f}" text-anchor="middle" '
                         f'font-size="8" font-weight="700" font-family="Arial" fill="#000">{code}</text>')
            # Horizontal leader line
            lx1 = cx + (r if right else -r)
            lx2 = cx + (r + 22 if right else -(r + 22))
            parts.append(f'<line x1="{lx1:.1f}" y1="{cy:.1f}" x2="{lx2:.1f}" y2="{cy:.1f}" '
                         f'stroke="#000" stroke-width="0.8"/>')
            # Description box
            bx = lx2 if right else lx2 - lw
            bh = 26 if label2 else 18
            by_box = cy - bh / 2
            parts.append(f'<rect x="{bx:.1f}" y="{by_box:.1f}" width="{lw}" height="{bh}" '
                         f'fill="#f8f8f8" stroke="#000" stroke-width="0.8"/>')
            ty1 = cy + (-4 if label2 else 4)
            parts.append(f'<text x="{bx + 5:.1f}" y="{ty1:.1f}" '
                         f'font-size="8" font-weight="700" font-family="Arial" fill="#000">{label1}</text>')
            if label2:
                parts.append(f'<text x="{bx + 5:.1f}" y="{cy + 10:.1f}" '
                             f'font-size="7" font-family="Arial" fill="#555">{label2}</text>')
            return "\n".join(parts)

        # Get primary roof segment data (used here and by roof detail box below)
        _seg0  = insight.roof_segments[0] if insight.roof_segments else None
        _az_s  = round(_seg0.azimuth_deg) if _seg0 else 180
        _pit_s = round(_seg0.pitch_deg)   if _seg0 else 18

        # Equipment center positions (right side = JB/LC; left side = MP/UM)
        # Microinverter system: NO DCD (DC disconnect), NO separate INV box.
        # JB = Junction Box (NEMA 3R) where AC trunk cables from roof merge.
        _jb_cx  = bx2 + 38;  _jb_cy  = ridge_y + 28   # Junction box (AC trunk merge)
        _lc_cx  = bx2 + 38;  _lc_cy  = ridge_y + 80   # Load center / AC OCPD
        _mp_cx  = bx1 - 38;  _mp_cy  = (by1 + by2) * 0.55  # Main service panel
        _um_cx  = bx1 - 38;  _um_cy  = by2 + 35       # Utility meter

        # Draw equipment callout symbols (all AC — no DC disconnect in microinverter system)
        svg.append(_equip_callout(_jb_cx, _jb_cy, "JB",
                                  "JUNCTION BOX (NEMA 3R)",
                                  f"AC TRUNK MERGE — {self._code_prefix} {'300.10' if self._code_prefix == 'NEC' else '12-3000'}", right=True, lw=215))
        svg.append(_equip_callout(_lc_cx, _lc_cy, "LC",
                                  "LOAD CENTER / AC OCPD",
                                  f"30A 2P / 240V BACKFED — {self._code_prefix} {'705.12' if self._code_prefix == 'NEC' else '64-056'}", right=True, lw=215))
        svg.append(_equip_callout(_mp_cx, _mp_cy, "MP",
                                  "MAIN SERVICE PANEL",
                                  "200A / 240V — INTERIOR", right=False, lw=190))
        svg.append(_equip_callout(_um_cx, _um_cy, "UM",
                                  "UTILITY METER",
                                  "HYDRO-QU\u00c9BEC — BIDIRECTIONAL", right=False, lw=200))

        # ── Conduit runs (dashed lines connecting equipment) ──────────────
        # All conduit runs are AC in a microinverter system — no DC conduit.
        # AC trunk: Array right edge → JB (AC trunk cables exit roof at eave)
        svg.append(f'<line x1="{arr_x2:.1f}" y1="{(arr_y1 + arr_y2) / 2:.1f}" '
                   f'x2="{_jb_cx - 12:.1f}" y2="{_jb_cy:.1f}" '
                   f'stroke="#cc0000" stroke-width="1.5" stroke-dasharray="8,4"/>')
        # JB → LC (AC conduit through attic/wall)
        svg.append(f'<line x1="{_jb_cx - 12:.1f}" y1="{_jb_cy:.1f}" '
                   f'x2="{_lc_cx - 12:.1f}" y2="{_lc_cy:.1f}" '
                   f'stroke="#cc0000" stroke-width="1.5" stroke-dasharray="8,4"/>')
        # LC → MP (AC service conductors, horizontal run through wall)
        svg.append(f'<line x1="{_lc_cx - 12:.1f}" y1="{_lc_cy:.1f}" '
                   f'x2="{_mp_cx + 12:.1f}" y2="{_mp_cy:.1f}" '
                   f'stroke="#cc0000" stroke-width="1.5" stroke-dasharray="8,4"/>')
        # MP → UM (service entrance)
        svg.append(f'<line x1="{_mp_cx:.1f}" y1="{_mp_cy + 12:.1f}" '
                   f'x2="{_um_cx:.1f}" y2="{_um_cy - 12:.1f}" '
                   f'stroke="#cc0000" stroke-width="1.5" stroke-dasharray="8,4"/>')

        # ── System legend (left margin, top area) ────────────────────────
        leg_x, leg_y_s = 28, 175
        leg_w = 310
        legend_entries = [
            ("line", "#cc0000", "8,4", f'AC CONDUIT ({self._wire_type} IN \u00be" EMT)'),
            ("line", "#cc0000", "3,2", "FIRE SETBACK LINE (3\u2019-0\u201d TYP.)"),
            ("sym",  "UM",  "", "UTILITY METER"),
            ("sym",  "MP",  "", "MAIN SERVICE PANEL"),
            ("sym",  "JB",  "", "JUNCTION BOX (NEMA 3R)"),
            ("sym",  "LC",  "", "LOAD CENTER / AC OCPD"),
        ]
        leg_row_h = 18
        # +37px for the module/microinverter panel-icon entry appended after loop
        _mi_entry_h = 37
        leg_h_s = 18 + len(legend_entries) * leg_row_h + _mi_entry_h + 4
        svg.append(f'<rect x="{leg_x}" y="{leg_y_s}" width="{leg_w}" height="{leg_h_s}" '
                   f'fill="#fff" stroke="#000" stroke-width="1"/>')
        svg.append(f'<rect x="{leg_x}" y="{leg_y_s}" width="{leg_w}" height="18" '
                   f'fill="#d8d8d8" stroke="#000" stroke-width="1"/>')
        svg.append(f'<text x="{leg_x + leg_w // 2}" y="{leg_y_s + 13}" text-anchor="middle" '
                   f'font-size="9" font-weight="700" font-family="Arial" fill="#000">SYSTEM LEGEND</text>')
        for li, entry in enumerate(legend_entries):
            ily = leg_y_s + 18 + li * leg_row_h
            if li > 0:
                svg.append(f'<line x1="{leg_x + 1}" y1="{ily}" x2="{leg_x + leg_w - 1}" y2="{ily}" '
                           f'stroke="#ddd" stroke-width="0.5"/>')
            item_cy = ily + leg_row_h / 2
            if entry[0] == "line":
                _, col, dash, lbl = entry
                svg.append(f'<line x1="{leg_x + 8}" y1="{item_cy:.1f}" '
                           f'x2="{leg_x + 48}" y2="{item_cy:.1f}" '
                           f'stroke="{col}" stroke-width="1.5" stroke-dasharray="{dash}"/>')
                svg.append(f'<text x="{leg_x + 55}" y="{item_cy + 4:.1f}" font-size="8" '
                           f'font-family="Arial" fill="#000">{lbl}</text>')
            else:
                _, code, _, lbl = entry
                svg.append(f'<circle cx="{leg_x + 18}" cy="{item_cy:.1f}" r="9" '
                           f'fill="#fff" stroke="#000" stroke-width="1"/>')
                svg.append(f'<text x="{leg_x + 18}" y="{item_cy + 3:.1f}" text-anchor="middle" '
                           f'font-size="6" font-weight="700" font-family="Arial" fill="#000">{code}</text>')
                svg.append(f'<text x="{leg_x + 33}" y="{item_cy + 4:.1f}" font-size="8" '
                           f'font-family="Arial" fill="#000">{lbl}</text>')

        # ── Module / microinverter entry appended below equipment symbols ──────
        # Matches Cubillas PV-3 System Legend: small panel icon + model description.
        _vp_mi_y = leg_y_s + 18 + len(legend_entries) * leg_row_h + 4
        _vp_mi_icon_x = leg_x + 5
        _vp_mi_icon_w, _vp_mi_icon_h = 28, 16
        svg.append(f'<line x1="{leg_x + 1}" y1="{_vp_mi_y}" x2="{leg_x + leg_w - 1}" '
                   f'y2="{_vp_mi_y}" stroke="#ddd" stroke-width="0.5"/>')
        svg.append(f'<rect x="{_vp_mi_icon_x}" y="{_vp_mi_y + 2}" width="{_vp_mi_icon_w}" '
                   f'height="{_vp_mi_icon_h}" fill="#ffffff" stroke="#000000" stroke-width="1"/>')
        for _ci in range(1, 3):
            _gcx = _vp_mi_icon_x + _ci * _vp_mi_icon_w // 3
            svg.append(f'<line x1="{_gcx}" y1="{_vp_mi_y + 4}" '
                       f'x2="{_gcx}" y2="{_vp_mi_y + _vp_mi_icon_h - 2}" '
                       f'stroke="#aaaaaa" stroke-width="0.5"/>')
        svg.append(f'<line x1="{_vp_mi_icon_x + 2}" y1="{_vp_mi_y + _vp_mi_icon_h // 2 + 2}" '
                   f'x2="{_vp_mi_icon_x + _vp_mi_icon_w - 2}" '
                   f'y2="{_vp_mi_y + _vp_mi_icon_h // 2 + 2}" '
                   f'stroke="#aaaaaa" stroke-width="0.5"/>')
        _vp_mi_lines = [
            f"({n_panels}) {self.panel.name} [{self.panel.wattage}W]",
            f"WITH {self.INV_MODEL_SHORT} [240V]",
            "MICROINVERTERS MOUNTED UNDER EACH MODULE.",
        ]
        for _li, _lt in enumerate(_vp_mi_lines):
            svg.append(f'<text x="{leg_x + 38}" y="{_vp_mi_y + 8 + _li * 10}" '
                       f'font-size="6" font-family="Arial" fill="#000">{_lt}</text>')

        # ── Additional notes box (left margin, above scale bar) ─────────
        an_x, an_y = 28, VH - 290
        an_w = 440
        notes_items = [
            "1. CONDUIT PATH SHOWN DIAGRAMMATICALLY. FINAL ROUTING TO BE FIELD-VERIFIED BY INSTALLER.",
            f'2. ALL DC CONDUIT: \u00be" EMT MINIMUM, GROUNDED AND BONDED PER {self._code_prefix} {"690.43" if self._code_prefix == "NEC" else "64-100"}.',
            f'3. ALL AC CONDUIT: \u00be" EMT MINIMUM PER {"UL listed" if self._code_prefix == "NEC" else "CSA C22.2 No.211.2"}.',
            "4. CONDUIT PENETRATIONS THROUGH ROOF/WALLS TO BE SEALED WEATHERTIGHT.",
            "5. EQUIPMENT LOCATIONS SHOWN ARE APPROXIMATE — VERIFY ON SITE BEFORE INSTALLATION.",
        ]
        an_row_h = 14
        an_h = 18 + len(notes_items) * an_row_h + 6
        svg.append(f'<rect x="{an_x}" y="{an_y}" width="{an_w}" height="{an_h}" '
                   f'fill="#fff" stroke="#000" stroke-width="1"/>')
        svg.append(f'<rect x="{an_x}" y="{an_y}" width="{an_w}" height="18" '
                   f'fill="#d8d8d8" stroke="#000" stroke-width="1"/>')
        svg.append(f'<text x="{an_x + an_w // 2}" y="{an_y + 13}" text-anchor="middle" '
                   f'font-size="9" font-weight="700" font-family="Arial" fill="#000">ADDITIONAL NOTES</text>')
        for ni, note in enumerate(notes_items):
            ny = an_y + 18 + ni * an_row_h + 10
            svg.append(f'<text x="{an_x + 6}" y="{ny}" font-size="7.5" '
                       f'font-family="Arial" fill="#000">{note}</text>')

        # ── Fire setback annotation ────────────────────────────────────
        # 3ft (0.914m) from ridge per IFC
        fire_offset = 0.914 * scale
        fs_line_y = ridge_y + fire_offset
        svg.append(f'<line x1="{bx1:.0f}" y1="{fs_line_y:.0f}" '
                   f'x2="{bx2:.0f}" y2="{fs_line_y:.0f}" '
                   f'stroke="#cc0000" stroke-width="0.8" stroke-dasharray="4,2"/>')
        svg.append(f'<text x="{bx1 - 5:.0f}" y="{fs_line_y + 3:.0f}" '
                   f'text-anchor="end" font-size="7" font-family="Arial" fill="#cc0000">'
                   f'3\' FIRE SETBACK</text>')

        # ── Scale bar ──────────────────────────────────────────────────
        sb_x = 40
        sb_y = VH - 155
        scale_5m_px = 5.0 * scale
        svg.append(f'<line x1="{sb_x}" y1="{sb_y}" x2="{sb_x + scale_5m_px:.0f}" '
                   f'y2="{sb_y}" stroke="#000" stroke-width="1.5"/>')
        # Tick marks
        for i in range(6):
            tx = sb_x + i * scale
            svg.append(f'<line x1="{tx:.0f}" y1="{sb_y - 4}" x2="{tx:.0f}" y2="{sb_y + 4}" '
                       f'stroke="#000" stroke-width="1"/>')
            svg.append(f'<text x="{tx:.0f}" y="{sb_y + 14}" text-anchor="middle" '
                       f'font-size="7" font-family="Arial" fill="#000">{i}m</text>')

        # ── North arrow ────────────────────────────────────────────────
        na_x = VW - 80
        na_y = 65
        svg.append(f'<g transform="translate({na_x},{na_y})">'
                   f'<circle cx="0" cy="0" r="22" fill="#fff" stroke="#000" stroke-width="1.5"/>'
                   f'<polygon points="0,-18 -6,8 0,2 6,8" fill="#000"/>'
                   f'<polygon points="0,-18 6,8 0,2 -6,8" fill="none" stroke="#000" stroke-width="0.8"/>'
                   f'<text x="0" y="-24" text-anchor="middle" font-size="12" '
                   f'font-weight="700" font-family="Arial" fill="#000">N</text>'
                   f'<circle cx="0" cy="0" r="2" fill="#000"/>'
                   f'</g>')

        # ── Roof detail box (top-right, below north arrow) ──────────────
        rd_x  = VW - 270
        rd_y  = 100
        rd_w  = 255
        roof_detail_rows = [
            ("ROOF TYPE:",    "ASPHALT SHINGLES"),
            ("SECTION:",      "S-1 (PRIMARY SOUTH FACE)"),
            ("MODULE COUNT:", f"{n_panels} MODULES"),
            ("SYSTEM SIZE:",  f"{total_kw_display:.2f} kW DC"),
            ("AZIMUTH:",      f"{_az_s}\u00b0 ({self._azimuth_label(_az_s)})"),
            ("PITCH:",        f"{_pit_s}\u00b0"),
            ("SCALE:",        '1/8" = 1\'-0"'),
        ]
        rd_row_h = 16
        rd_h = 18 + len(roof_detail_rows) * rd_row_h + 2
        svg.append(f'<rect x="{rd_x}" y="{rd_y}" width="{rd_w}" height="{rd_h}" '
                   f'fill="#fff" stroke="#000" stroke-width="1"/>')
        svg.append(f'<rect x="{rd_x}" y="{rd_y}" width="{rd_w}" height="18" '
                   f'fill="#d8d8d8" stroke="#000" stroke-width="1"/>')
        svg.append(f'<text x="{rd_x + rd_w // 2}" y="{rd_y + 13}" text-anchor="middle" '
                   f'font-size="9" font-weight="700" font-family="Arial" fill="#000">ROOF DETAIL \u2014 SECTION S-1</text>')
        for ri, (k, v) in enumerate(roof_detail_rows):
            rry = rd_y + 18 + ri * rd_row_h
            if ri > 0:
                svg.append(f'<line x1="{rd_x + 1}" y1="{rry}" x2="{rd_x + rd_w - 1}" y2="{rry}" '
                           f'stroke="#ccc" stroke-width="0.5"/>')
            svg.append(f'<line x1="{rd_x + 108}" y1="{rry}" x2="{rd_x + 108}" y2="{rry + rd_row_h}" '
                       f'stroke="#ddd" stroke-width="0.5"/>')
            svg.append(f'<text x="{rd_x + 5}" y="{rry + 11}" font-size="8" font-weight="700" '
                       f'font-family="Arial" fill="#000">{k}</text>')
            svg.append(f'<text x="{rd_x + 113}" y="{rry + 11}" font-size="8" '
                       f'font-family="Arial" fill="#333">{v}</text>')

        # ── Title block ────────────────────────────────────────────────
        svg.append(self._svg_title_block(
            VW, VH, "PV-3", "Site Plan", "Aerial + Mercator Panels", "3 of 13",
            address, today
        ))

        content = "\n".join(svg)
        return (f'<div class="page">'
                f'<svg width="100%" height="100%" viewBox="0 0 {VW} {VH}" '
                f'xmlns="http://www.w3.org/2000/svg" style="background:#ffffff;">'
                f'{content}</svg></div>')

    def _build_site_plan_satellite(self, insight, sat_b64: str, page_w: int, page_h: int,
                                    panels, mpp: float, n_panels: int, total_kw_display: float,
                                    address: str, today: str) -> str:
        """PV-3: Professional satellite site plan — white engineering drawing standard.

        Layout: standard 1280×960 SVG coordinate space.
          Left 73%  = drawing area (satellite background + panel overlays + annotations).
          Right 27% = info column (SYSTEM LEGEND, ROOF DETAIL, ADDITIONAL NOTES).
          Bottom-right = standard title block (via _svg_title_block).

        Panels are rendered as white engineering rectangles (print-ready) over the
        satellite image.  Equipment callout symbols, DC/AC conduit runs, fire setback
        hatching, north arrow and scale bar match the Cubillas professional standard.
        """
        VW, VH = 1280, 960
        BORDER = 20

        # ── Layout zones ────────────────────────────────────────────────────
        DIVIDER_X = 935        # x where right column starts
        DRAW_X    = BORDER
        DRAW_Y    = 50         # below page title strip
        DRAW_W    = DIVIDER_X - BORDER - 5   # ≈ 910 px
        DRAW_H    = VH - DRAW_Y - BORDER - 10  # ≈ 880 px (title block overlaps bottom-right)
        RC_X      = DIVIDER_X + 8
        RC_W      = VW - DIVIDER_X - BORDER - 8  # ≈ 317 px

        # ── Panel data in satellite pixel space ──────────────────────────────
        panel_data = []
        for idx, p in enumerate(panels):
            px, py = self._latlng_to_pixel(
                p.center_lat, p.center_lng,
                insight.lat, insight.lng, mpp, page_w, page_h
            )
            w_m = insight.panel_width_m
            h_m = insight.panel_height_m
            if p.orientation == "LANDSCAPE":
                w_m, h_m = h_m, w_m
            w_px = w_m / mpp
            h_px = h_m / mpp
            seg_idx = getattr(p, 'segment_index', 0)
            seg = (insight.roof_segments[seg_idx]
                   if seg_idx < len(insight.roof_segments) else None)
            rotation = seg.azimuth_deg - 180 if seg else 0
            panel_data.append({'px': px, 'py': py, 'w': w_px, 'h': h_px,
                                'rot': rotation, 'idx': idx})

        # ── Cluster centre & zoom factor ─────────────────────────────────────
        all_sat_x = [pd['px'] for pd in panel_data]
        all_sat_y = [pd['py'] for pd in panel_data]
        cluster_cx = (min(all_sat_x) + max(all_sat_x)) / 2
        cluster_cy = (min(all_sat_y) + max(all_sat_y)) / 2
        cluster_span = max(
            max(all_sat_x) - min(all_sat_x) + max(pd['w'] for pd in panel_data) * 2,
            max(all_sat_y) - min(all_sat_y) + max(pd['h'] for pd in panel_data) * 2,
            1
        )

        # Panel cluster should span ~38 % of the smaller drawing dimension
        target_span = min(DRAW_W, DRAW_H) * 0.38
        sat_scale   = max(0.35, min(3.5, target_span / cluster_span))

        # Centre of drawing area in SVG coords (shift slightly up for room below)
        draw_cx_svg = DRAW_X + DRAW_W / 2
        draw_cy_svg = DRAW_Y + DRAW_H * 0.44

        # Transform: satellite pixel → SVG screen coordinate
        sat_tx = draw_cx_svg - cluster_cx * sat_scale
        sat_ty = draw_cy_svg - cluster_cy * sat_scale

        def _s(sat_x, sat_y):
            """Convert satellite pixel coordinate → SVG screen coordinate."""
            return sat_tx + sat_x * sat_scale, sat_ty + sat_y * sat_scale

        # ── Panel screen positions ────────────────────────────────────────────
        screen_panels = []
        for pd in panel_data:
            sx, sy = _s(pd['px'], pd['py'])
            sw = pd['w'] * sat_scale
            sh = pd['h'] * sat_scale
            screen_panels.append({'sx': sx, 'sy': sy, 'sw': sw, 'sh': sh,
                                   'rot': pd['rot'], 'idx': pd['idx']})

        # Array bounding box in screen space
        all_scr_x = [sp['sx'] for sp in screen_panels]
        all_scr_y = [sp['sy'] for sp in screen_panels]
        max_sw = max(sp['sw'] for sp in screen_panels)
        max_sh = max(sp['sh'] for sp in screen_panels)
        arr_xmin = min(all_scr_x) - max_sw / 2
        arr_xmax = max(all_scr_x) + max_sw / 2
        arr_ymin = min(all_scr_y) - max_sh / 2
        arr_ymax = max(all_scr_y) + max_sh / 2

        # Fire setback in screen pixels: 18 in = 0.457 m
        sb_scr = max(8.0, (0.457 / mpp) * sat_scale)

        # Roof segment info
        seg0      = insight.roof_segments[0] if insight.roof_segments else None
        az_deg    = round(seg0.azimuth_deg, 0) if seg0 else 180
        pitch_deg = round(seg0.pitch_deg,   0) if seg0 else 0

        AC_kw = self._calc_ac_kw(n_panels)  # n_panels × 384VA = proper AC capacity

        # ═══════════════════════════════════════════════════════════════════
        # BUILD SVG
        # ═══════════════════════════════════════════════════════════════════
        svg = []

        # ── Defs ─────────────────────────────────────────────────────────────
        svg.append('<defs>')
        svg.append(f'<clipPath id="pv3-clip">'
                   f'<rect x="{DRAW_X}" y="{DRAW_Y}" '
                   f'width="{DRAW_W}" height="{DRAW_H}"/></clipPath>')
        svg.append('<pattern id="pv3-fire" patternUnits="userSpaceOnUse" '
                   'width="7" height="7" patternTransform="rotate(45)">'
                   '<line x1="0" y1="0" x2="0" y2="7" stroke="#dd0000" '
                   'stroke-width="1.2" opacity="0.45"/></pattern>')
        svg.append('</defs>')

        # ── White page background ─────────────────────────────────────────────
        svg.append(f'<rect width="{VW}" height="{VH}" fill="#ffffff"/>')

        # ── Engineering border ────────────────────────────────────────────────
        svg.append(f'<rect x="{BORDER}" y="{BORDER}" '
                   f'width="{VW - 2 * BORDER}" height="{VH - 2 * BORDER}" '
                   f'fill="none" stroke="#000" stroke-width="1.5"/>')

        # ── Vertical divider: drawing area | right column ─────────────────────
        svg.append(f'<line x1="{DIVIDER_X}" y1="{BORDER}" '
                   f'x2="{DIVIDER_X}" y2="{VH - BORDER}" '
                   f'stroke="#000" stroke-width="0.8"/>')

        # ── Page title ────────────────────────────────────────────────────────
        svg.append(f'<text x="{DRAW_X + 8}" y="{BORDER + 16}" font-size="13" '
                   f'font-weight="700" font-family="Arial" fill="#000">'
                   f'PV-3: SITE PLAN \u2014 AERIAL &amp; PANELS</text>')
        svg.append(f'<text x="{DRAW_X + 8}" y="{BORDER + 29}" font-size="7.5" '
                   f'font-family="Arial" fill="#555">'
                   f'SCALE: 1/8&quot; = 1&apos;-0&quot;</text>')

        # ── Satellite image (clipped to drawing area) ─────────────────────────
        svg.append(f'<g clip-path="url(#pv3-clip)">')
        svg.append(f'<image href="data:image/png;base64,{sat_b64}" '
                   f'x="{sat_tx:.1f}" y="{sat_ty:.1f}" '
                   f'width="{page_w * sat_scale:.1f}" '
                   f'height="{page_h * sat_scale:.1f}" '
                   f'preserveAspectRatio="none"/>')

        # ── Fire setback hatched border (inside clip) ─────────────────────────
        fsb_x = arr_xmin - sb_scr
        fsb_y = arr_ymin - sb_scr
        fsb_w = arr_xmax - arr_xmin + 2 * sb_scr
        fsb_h = arr_ymax - arr_ymin + 2 * sb_scr
        svg.append(f'<rect x="{fsb_x:.1f}" y="{fsb_y:.1f}" '
                   f'width="{fsb_w:.1f}" height="{fsb_h:.1f}" '
                   f'fill="url(#pv3-fire)" stroke="#dd0000" '
                   f'stroke-width="1.2" stroke-dasharray="5,3" opacity="0.85"/>')

        # ── Panel overlays: white engineering style ───────────────────────────
        for sp in screen_panels:
            sx, sy, sw, sh = sp['sx'], sp['sy'], sp['sw'], sp['sh']
            rot, idx = sp['rot'], sp['idx']
            svg.append(f'<g transform="translate({sx:.1f},{sy:.1f}) rotate({rot:.1f})">')
            # White semi-transparent fill + black outline
            svg.append(f'<rect x="{-sw/2:.1f}" y="{-sh/2:.1f}" '
                       f'width="{sw:.1f}" height="{sh:.1f}" '
                       f'fill="rgba(255,255,255,0.82)" stroke="#000" stroke-width="1.4"/>')
            # 2 internal cell-column lines
            for ci in range(1, 3):
                gx = -sw / 2 + sw / 3 * ci
                svg.append(f'<line x1="{gx:.1f}" y1="{-sh/2:.1f}" '
                           f'x2="{gx:.1f}" y2="{sh/2:.1f}" '
                           f'stroke="#555" stroke-width="0.4"/>')
            # Panel number
            fsize = max(5, min(9, sh * 0.42))
            svg.append(f'<text x="0" y="{sh * 0.17:.1f}" text-anchor="middle" '
                       f'font-size="{fsize:.0f}" font-family="Arial" fill="#000" '
                       f'font-weight="600">{idx + 1}</text>')
            svg.append('</g>')

        svg.append('</g>')  # end pv3-clip

        # ── Setback dimension callout (screen space, outside clip) ────────────
        if DRAW_X + 5 < fsb_x < DRAW_X + DRAW_W - 5:
            sb_ann_x = fsb_x - 4
            sb_ann_y = arr_ymin - sb_scr - 6
            svg.append(f'<text x="{sb_ann_x:.0f}" y="{sb_ann_y:.0f}" '
                       f'text-anchor="end" font-size="7.5" font-weight="600" '
                       f'font-family="Arial" fill="#dd0000">1&apos;-6&quot; TYP.</text>')
            svg.append(f'<line x1="{fsb_x:.0f}" y1="{sb_ann_y + 1:.0f}" '
                       f'x2="{fsb_x:.0f}" y2="{arr_ymin:.0f}" '
                       f'stroke="#dd0000" stroke-width="0.8"/>')

        # ── Equipment callout symbols ─────────────────────────────────────────
        # Row of circles below the panel array (connected by dashed leader lines)
        # Microinverter system: NO DC disconnect, NO separate combiner box.
        # Equipment: UM (meter) → MP (main panel) → JB (junction box) → LC (load center)
        eq_row_y   = min(arr_ymax + sb_scr + 38, DRAW_Y + DRAW_H - 85)
        eq_row_y   = max(eq_row_y, arr_ymax + 30)
        equipment  = [
            ("UM",  "MAIN BILLING METER\nAND SERVICE POINT"),
            ("MP",  "MAIN SERVICE PANEL"),
            ("JB",  "JUNC. BOX\nNEMA 3R"),
            ("LC",  "125A RATED PV\nLOAD CENTER"),
        ]
        eq_spacing  = 76
        eq_total_w  = len(equipment) * eq_spacing
        eq_start_x  = max(DRAW_X + 20,
                          min(draw_cx_svg - eq_total_w / 2,
                              DRAW_X + DRAW_W - eq_total_w - 15))

        for i, (abbr, desc_raw) in enumerate(equipment):
            ex = eq_start_x + i * eq_spacing + 30
            ey = eq_row_y
            if ex < DRAW_X or ex > DRAW_X + DRAW_W - 10:
                continue

            # Dashed leader from array bottom to symbol
            anchor_x = min(max(ex, arr_xmin), arr_xmax)
            svg.append(f'<line x1="{anchor_x:.0f}" y1="{arr_ymax + sb_scr:.0f}" '
                       f'x2="{ex:.0f}" y2="{ey - 16:.0f}" '
                       f'stroke="#555" stroke-width="0.8" stroke-dasharray="4,2"/>')

            # Equipment circle with abbreviation
            svg.append(f'<circle cx="{ex:.0f}" cy="{ey:.0f}" r="13" '
                       f'fill="#fff" stroke="#000" stroke-width="1.5"/>')
            fz = "6.5" if len(abbr) > 2 else "8"
            svg.append(f'<text x="{ex:.0f}" y="{ey + 4:.0f}" text-anchor="middle" '
                       f'font-size="{fz}" font-weight="700" font-family="Arial" '
                       f'fill="#000">{abbr}</text>')

            # Description box below circle
            desc_lines = desc_raw.split("\n")
            box_w = 74
            box_h = len(desc_lines) * 11 + 8
            box_x = ex - box_w / 2
            box_y = ey + 16
            svg.append(f'<rect x="{box_x:.0f}" y="{box_y:.0f}" '
                       f'width="{box_w}" height="{box_h}" '
                       f'fill="#f8f8f8" stroke="#000" stroke-width="0.8"/>')
            for j, line in enumerate(desc_lines):
                svg.append(f'<text x="{ex:.0f}" y="{box_y + 9 + j * 11:.0f}" '
                           f'text-anchor="middle" font-size="6.5" '
                           f'font-family="Arial" fill="#000">{line}</text>')

        # ── Conduit runs ──────────────────────────────────────────────────────
        # All wiring is AC in a microinverter system — no DC conduit runs.
        # AC trunk cables: center of array → JB (junction box, index 2)
        jb_idx     = 2   # JB is the 3rd symbol (0-based index 2)
        jb_x       = eq_start_x + jb_idx * eq_spacing + 30
        ac_trunk_ax = min(max(jb_x, arr_xmin), arr_xmax)   # anchor at array bottom
        ac_trunk_sy = arr_ymax + sb_scr
        ac_trunk_ey = eq_row_y - 16

        svg.append(f'<line x1="{ac_trunk_ax:.0f}" y1="{ac_trunk_sy:.0f}" '
                   f'x2="{jb_x:.0f}" y2="{ac_trunk_ey:.0f}" '
                   f'fill="none" stroke="#cc0000" stroke-width="1.5" '
                   f'stroke-dasharray="8,5"/>')
        svg.append(f'<text x="{(ac_trunk_ax + jb_x) / 2 + 5:.0f}" '
                   f'y="{(ac_trunk_sy + ac_trunk_ey) / 2:.0f}" '
                   f'font-size="6.5" font-weight="700" font-family="Arial" '
                   f'fill="#cc0000">AC TRUNK</text>')

        # AC conduit (dashed red): LC position (index 3) → right of drawing area
        lc_idx     = 3   # LC is the 4th symbol (0-based index 3)
        ac_start_x = eq_start_x + lc_idx * eq_spacing + 30
        ac_start_y = eq_row_y
        ac_end_x   = min(ac_start_x + 110, DRAW_X + DRAW_W - 15)
        if ac_end_x > ac_start_x + 20:
            svg.append(f'<line x1="{ac_start_x:.0f}" y1="{ac_start_y:.0f}" '
                       f'x2="{ac_end_x:.0f}" y2="{ac_start_y:.0f}" '
                       f'fill="none" stroke="#cc0000" stroke-width="1.5" '
                       f'stroke-dasharray="8,5"/>')
            svg.append(f'<text x="{(ac_start_x + ac_end_x) / 2:.0f}" '
                       f'y="{ac_start_y - 5:.0f}" text-anchor="middle" '
                       f'font-size="7" font-weight="700" font-family="Arial" '
                       f'fill="#cc0000">AC</text>')

        # ── North arrow (top-right of drawing area) ───────────────────────────
        na_cx = DRAW_X + DRAW_W - 40
        na_cy = DRAW_Y + 48
        svg.append(f'<polygon points="{na_cx},{na_cy - 19} {na_cx - 7},{na_cy + 10} '
                   f'{na_cx},{na_cy + 4} {na_cx + 7},{na_cy + 10}" fill="#000"/>')
        svg.append(f'<polygon points="{na_cx},{na_cy + 4} {na_cx - 7},{na_cy + 10} '
                   f'{na_cx + 7},{na_cy + 10}" fill="#fff" stroke="#000" stroke-width="0.8"/>')
        svg.append(f'<text x="{na_cx}" y="{na_cy - 23}" text-anchor="middle" '
                   f'font-size="14" font-weight="700" font-family="Arial" fill="#000">N</text>')

        # ── Scale bar (bottom-left of drawing area) ───────────────────────────
        px_per_m    = (1.0 / mpp) * sat_scale
        bar_m       = 5
        bar_px      = px_per_m * bar_m
        sbar_x      = DRAW_X + 20
        sbar_y      = DRAW_Y + DRAW_H - 28
        # Alternating black/white segments
        svg.append(f'<rect x="{sbar_x:.0f}" y="{sbar_y - 6:.0f}" '
                   f'width="{bar_px / 2:.0f}" height="6" fill="#000"/>')
        svg.append(f'<rect x="{sbar_x + bar_px / 2:.0f}" y="{sbar_y - 6:.0f}" '
                   f'width="{bar_px / 2:.0f}" height="6" '
                   f'fill="#fff" stroke="#000" stroke-width="0.8"/>')
        svg.append(f'<line x1="{sbar_x:.0f}" y1="{sbar_y - 6:.0f}" '
                   f'x2="{sbar_x:.0f}" y2="{sbar_y:.0f}" '
                   f'stroke="#000" stroke-width="1"/>')
        svg.append(f'<line x1="{sbar_x + bar_px:.0f}" y1="{sbar_y - 6:.0f}" '
                   f'x2="{sbar_x + bar_px:.0f}" y2="{sbar_y:.0f}" '
                   f'stroke="#000" stroke-width="1"/>')
        svg.append(f'<text x="{sbar_x:.0f}" y="{sbar_y + 9:.0f}" font-size="7.5" '
                   f'font-family="Arial" fill="#000">0</text>')
        svg.append(f'<text x="{sbar_x + bar_px:.0f}" y="{sbar_y + 9:.0f}" '
                   f'text-anchor="end" font-size="7.5" font-family="Arial" '
                   f'fill="#000">{bar_m}m</text>')
        svg.append(f'<text x="{sbar_x + bar_px / 2:.0f}" y="{sbar_y - 9:.0f}" '
                   f'text-anchor="middle" font-size="7" font-family="Arial" '
                   f'fill="#555">SCALE BAR</text>')

        # ═══ RIGHT COLUMN ════════════════════════════════════════════════════
        RC_Y_TOP = BORDER + 8

        # ── SYSTEM LEGEND ─────────────────────────────────────────────────────
        sl_y = RC_Y_TOP
        sl_h = 335
        svg.append(f'<rect x="{RC_X}" y="{sl_y}" width="{RC_W}" height="{sl_h}" '
                   f'fill="#fff" stroke="#000" stroke-width="1.2"/>')
        svg.append(f'<rect x="{RC_X}" y="{sl_y}" width="{RC_W}" height="17" '
                   f'fill="#e8e8e8" stroke="#000" stroke-width="1"/>')
        svg.append(f'<text x="{RC_X + RC_W // 2}" y="{sl_y + 12}" '
                   f'text-anchor="middle" font-size="9" font-weight="700" '
                   f'font-family="Arial" fill="#000">SYSTEM LEGEND</text>')

        # System summary
        ly = sl_y + 23
        for txt, bold in [
            ("PHOTOVOLTAIC SYSTEM:", True),
            (f"DC SYSTEM SIZE: {total_kw_display:.2f} kW", False),
            (f"AC SYSTEM SIZE: {AC_kw:.2f} kW", False),
        ]:
            w700 = "700" if bold else "400"
            fsz  = "8.5" if bold else "8"
            svg.append(f'<text x="{RC_X + 6}" y="{ly}" font-size="{fsz}" '
                       f'font-weight="{w700}" font-family="Arial" fill="#000">{txt}</text>')
            ly += 13

        svg.append(f'<line x1="{RC_X + 4}" y1="{ly + 2}" '
                   f'x2="{RC_X + RC_W - 4}" y2="{ly + 2}" '
                   f'stroke="#ccc" stroke-width="0.6"/>')
        ly += 8

        # Equipment entries (small rectangle with abbreviation + description)
        # Microinverter system: NO DC disconnect, NO separate combiner box.
        eq_legend = [
            ("UM",  "MAIN BILLING METER AND SERVICE POINT"),
            ("MP",  "MAIN SERVICE PANEL"),
            ("JB",  "JUNCTION BOX (NEMA 3R) — AC TRUNK MERGE"),
            ("LC",  "125A RATED PV LOAD CENTER"),
        ]
        for abbr, desc in eq_legend:
            svg.append(f'<rect x="{RC_X + 5}" y="{ly - 1}" width="26" height="14" '
                       f'fill="#fff" stroke="#000" stroke-width="1"/>')
            fz2 = "6.5" if len(abbr) > 2 else "7.5"
            svg.append(f'<text x="{RC_X + 18}" y="{ly + 9}" text-anchor="middle" '
                       f'font-size="{fz2}" font-weight="700" font-family="Arial" '
                       f'fill="#000">{abbr}</text>')
            if len(desc) > 28:
                mid = desc.rfind(' ', 0, len(desc) // 2 + 5)
                l1, l2 = desc[:mid], desc[mid + 1:]
                svg.append(f'<text x="{RC_X + 36}" y="{ly + 5}" font-size="6.2" '
                           f'font-family="Arial" fill="#000">{l1}</text>')
                svg.append(f'<text x="{RC_X + 36}" y="{ly + 14}" font-size="6.2" '
                           f'font-family="Arial" fill="#000">{l2}</text>')
                ly += 22
            else:
                svg.append(f'<text x="{RC_X + 36}" y="{ly + 9}" font-size="7" '
                           f'font-family="Arial" fill="#000">{desc}</text>')
                ly += 17

        # ── Module / microinverter legend entry (Cubillas PV-3 standard) ────────
        # Shows a small panel icon + "(N) [MODULE MODEL] [W] WITH [INVERTER] [V]
        # MICROINVERTERS MOUNTED UNDER EACH MODULE." — matches the entry that
        # appears in the Cubillas PV-3 System Legend between the equipment symbols
        # and the conduit/fire-setback line style entries.
        _mi_icon_x = RC_X + 5
        _mi_icon_y = ly
        _mi_icon_w = 28
        _mi_icon_h = 16
        # Panel icon: white rectangle with internal grid lines (suggests a PV module)
        svg.append(f'<rect x="{_mi_icon_x}" y="{_mi_icon_y}" width="{_mi_icon_w}" '
                   f'height="{_mi_icon_h}" fill="#ffffff" stroke="#000000" stroke-width="1"/>')
        for _ci in range(1, 3):
            _gcx = _mi_icon_x + _ci * _mi_icon_w // 3
            svg.append(f'<line x1="{_gcx}" y1="{_mi_icon_y + 2}" '
                       f'x2="{_gcx}" y2="{_mi_icon_y + _mi_icon_h - 2}" '
                       f'stroke="#aaaaaa" stroke-width="0.5"/>')
        svg.append(f'<line x1="{_mi_icon_x + 2}" y1="{_mi_icon_y + _mi_icon_h // 2}" '
                   f'x2="{_mi_icon_x + _mi_icon_w - 2}" y2="{_mi_icon_y + _mi_icon_h // 2}" '
                   f'stroke="#aaaaaa" stroke-width="0.5"/>')
        # Module + microinverter description text (3 wrapped lines at font-size 6)
        _mi_lines = [
            f"({n_panels}) {self.panel.name} [{self.panel.wattage}W]",
            f"WITH {self.INV_MODEL_SHORT} [240V]",
            "MICROINVERTERS MOUNTED UNDER EACH MODULE.",
        ]
        for _li, _lt in enumerate(_mi_lines):
            svg.append(f'<text x="{RC_X + 38}" y="{ly + 7 + _li * 11}" '
                       f'font-size="6" font-family="Arial" fill="#000">{_lt}</text>')
        ly += max(_mi_icon_h + 4, len(_mi_lines) * 11 + 4)

        svg.append(f'<line x1="{RC_X + 4}" y1="{ly + 2}" '
                   f'x2="{RC_X + RC_W - 4}" y2="{ly + 2}" '
                   f'stroke="#ccc" stroke-width="0.6"/>')
        ly += 8

        # Line style entries
        # Microinverter system has no DC conduit — only AC conduit runs.
        for style, label in [
            ("red-dash",   "AC CONDUIT RUN"),
            ("hatch-fire", "FIRE CODE SETBACK\n(18\" MIN / 36\" MAX)"),
            ("gray-dash",  "CONDUIT RUN"),
        ]:
            lines_l = label.split("\n")
            if style == "red-dash":
                svg.append(f'<line x1="{RC_X + 5}" y1="{ly + 6}" '
                           f'x2="{RC_X + 32}" y2="{ly + 6}" '
                           f'stroke="#cc0000" stroke-width="2" stroke-dasharray="6,3"/>')
            elif style == "hatch-fire":
                svg.append(f'<rect x="{RC_X + 5}" y="{ly}" width="27" height="13" '
                           f'fill="url(#pv3-fire)" stroke="#dd0000" '
                           f'stroke-width="0.6" stroke-dasharray="3,2" opacity="0.85"/>')
            elif style == "gray-dash":
                svg.append(f'<line x1="{RC_X + 5}" y1="{ly + 6}" '
                           f'x2="{RC_X + 32}" y2="{ly + 6}" '
                           f'stroke="#666" stroke-width="1.5" stroke-dasharray="6,3"/>')
            for j_l, line_l in enumerate(lines_l):
                svg.append(f'<text x="{RC_X + 36}" y="{ly + 7 + j_l * 10}" '
                           f'font-size="7" font-family="Arial" fill="#000">{line_l}</text>')
            ly += max(14, len(lines_l) * 11)

        # ── Conduit routing paragraph (Cubillas PV-3 System Legend standard) ──
        # In Cubillas, this paragraph appears inside the System Legend box,
        # immediately after the "CONDUIT RUN" dashed-line entry — it explains
        # conduit routing rules to the permit reviewer without requiring them
        # to look elsewhere.  Our previous implementation put this text in
        # ADDITIONAL NOTES (wrong location); it belongs here, in the legend.
        svg.append(f'<line x1="{RC_X + 4}" y1="{ly + 3}" '
                   f'x2="{RC_X + RC_W - 4}" y2="{ly + 3}" '
                   f'stroke="#ccc" stroke-width="0.6"/>')
        ly += 9
        _conduit_para = [
            "CONDUIT TO BE RUN IN ATTIC IF POSSIBLE,",
            "OTHERWISE CONDUIT BLOCKS MIN. 1\"/MAX 6\"",
            "ABOVE ROOF SURFACE, CLOSE TO RIDGE LINES",
            "AND UNDER EAVES; TO BE PAINTED TO MATCH",
            "EXTERIOR/EXISTING BACKGROUND COLOUR;",
            "LABELED AT MAX 10\u2019 INTERVALS. CONDUIT RUNS",
            "ARE APPROXIMATE — FIELD DETERMINED.",
        ]
        for _pl in _conduit_para:
            svg.append(f'<text x="{RC_X + 6}" y="{ly + 9}" font-size="6" '
                       f'font-family="Arial" fill="#333">{_pl}</text>')
            ly += 10
        ly += 4  # bottom margin

        # ── ROOF DETAIL ───────────────────────────────────────────────────────
        rd_y = sl_y + sl_h + 8
        rd_h = 140
        svg.append(f'<rect x="{RC_X}" y="{rd_y}" width="{RC_W}" height="{rd_h}" '
                   f'fill="#fff" stroke="#000" stroke-width="1.2"/>')
        svg.append(f'<rect x="{RC_X}" y="{rd_y}" width="{RC_W}" height="17" '
                   f'fill="#e8e8e8" stroke="#000" stroke-width="1"/>')
        svg.append(f'<text x="{RC_X + RC_W // 2}" y="{rd_y + 12}" '
                   f'text-anchor="middle" font-size="9" font-weight="700" '
                   f'font-family="Arial" fill="#000">ROOF DETAIL</text>')
        # Section circle
        svg.append(f'<circle cx="{RC_X + RC_W - 22}" cy="{rd_y + rd_h // 2 + 10}" '
                   f'r="14" fill="#fff" stroke="#000" stroke-width="1.5"/>')
        svg.append(f'<text x="{RC_X + RC_W - 22}" y="{rd_y + rd_h // 2 + 16}" '
                   f'text-anchor="middle" font-size="15" font-weight="700" '
                   f'font-family="Arial" fill="#000">1</text>')
        rd_rows = [
            ("ROOF TYPE:",      "ASPHALT-SHINGLES"),
            ("ROOF SECTION 1:", f"{n_panels} MODULES"),
            ("AZIMUTH:",        f"{az_deg:.0f}\u00b0"),
            ("PITCH:",          f"{pitch_deg:.0f}\u00b0"),
            ("SCALE:",          '1/8" = 1\'-0"'),
        ]
        for i, (lbl, val) in enumerate(rd_rows):
            ry2 = rd_y + 22 + i * 22
            svg.append(f'<text x="{RC_X + 7}" y="{ry2}" font-size="7.5" '
                       f'font-weight="700" font-family="Arial" fill="#000">{lbl}</text>')
            svg.append(f'<text x="{RC_X + 7}" y="{ry2 + 13}" font-size="8" '
                       f'font-family="Arial" fill="#333">{val}</text>')

        # ── ADDITIONAL NOTES ──────────────────────────────────────────────────
        # Cubillas PV-3 standard: two specific fire/safety code notes only.
        # (The conduit routing paragraph has moved to the SYSTEM LEGEND above.)
        an_y = rd_y + rd_h + 8
        an_h = 60
        svg.append(f'<rect x="{RC_X}" y="{an_y}" width="{RC_W}" height="{an_h}" '
                   f'fill="#fff" stroke="#000" stroke-width="1.2"/>')
        svg.append(f'<rect x="{RC_X}" y="{an_y}" width="{RC_W}" height="17" '
                   f'fill="#e8e8e8" stroke="#000" stroke-width="1"/>')
        svg.append(f'<text x="{RC_X + RC_W // 2}" y="{an_y + 12}" '
                   f'text-anchor="middle" font-size="9" font-weight="700" '
                   f'font-family="Arial" fill="#000">ADDITIONAL NOTES</text>')
        # Two specific code-compliance safety notes (verbatim Cubillas PV-3 standard)
        add_notes = [
            ("NO CONDUIT SHALL PASS OVER FIREFIGHTER",   "ROOF ACCESS OR VENTILATION PATHS."),
            ("CONDUIT RUN IN THE ATTIC SHALL BE",        "MOUNTED 18\u2033 BELOW THE RIDGE."),
        ]
        _an_y = an_y + 24
        for _n1, _n2 in add_notes:
            svg.append(f'<text x="{RC_X + 7}" y="{_an_y}" '
                       f'font-size="6.5" font-family="Arial" fill="#333">{_n1}</text>')
            svg.append(f'<text x="{RC_X + 7}" y="{_an_y + 9}" '
                       f'font-size="6.5" font-family="Arial" fill="#333">{_n2}</text>')
            _an_y += 22

        # ── Standard title block ──────────────────────────────────────────────
        svg.append(self._svg_title_block(
            VW, VH,
            sheet_id="PV-3",
            sheet_title="SITE PLAN",
            subtitle="Aerial + Mercator Panels",
            page_of="3 of 13",
            address=address,
            today=today,
        ))

        content = "\n".join(svg)
        return (f'<div class="page">'
                f'<svg width="100%" height="100%" viewBox="0 0 {VW} {VH}" '
                f'xmlns="http://www.w3.org/2000/svg" style="background:#fff;">'
                f'{content}</svg></div>')

    def _build_blank_site_plan(self, address: str, today: str) -> str:
        """Fallback site plan when no API data."""
        return f"""<div class="page">
  <svg width="100%" height="100%" viewBox="0 0 1280 960" xmlns="http://www.w3.org/2000/svg" style="background:#fff;">
    <rect x="10" y="10" width="1260" height="940" fill="none" stroke="#000" stroke-width="2"/>
    <rect x="20" y="20" width="1240" height="820" fill="#f5f5f5"/>
    <text x="640" y="440" text-anchor="middle" font-size="14" font-family="Arial" fill="#999">Site plan data not available</text>

    <g transform="translate(750, 850)">
      <rect x="0" y="0" width="520" height="100" fill="#fff" stroke="#000" stroke-width="1"/>
      <text x="10" y="16" font-size="10" font-weight="700" font-family="Arial" fill="#000">{self.company}</text>
      <text x="320" y="20" font-size="11" font-weight="700" font-family="Arial" fill="#000">PV-3</text>
      <text x="320" y="55" font-size="9" font-family="Arial" fill="#666">2 of 8</text>
    </g>
  </svg>
</div>"""

    def _build_racking_plan_page(self, insight, num_api_panels: int,
                                address: str, today: str,
                                placements: List[PlacementResult] = None) -> str:
        """PV-3.1: Data-driven vector racking/framing plan.

        Uses actual roof segment areas from API to compute proportional rectangles.
        Shows individual panels at correct scale, fire setbacks with measurements,
        racking rails, and dimension annotations.
        """
        VW, VH = 1280, 960
        BORDER = 20
        TB_H = 100  # title block height at bottom
        DRAW_TOP = 195  # space for top info band (ROOF DETAIL + ROOF AREA table)
        DRAW_BOTTOM = 712  # bottom of main drawing; leaves room for bottom info band

        # Drawing area
        draw_x = BORDER + 10
        draw_y = DRAW_TOP
        draw_w = VW - 2 * BORDER - 20
        draw_h = DRAW_BOTTOM - DRAW_TOP

        # Scale: px per meter (compute from largest segment to fill drawing area)
        SETBACK_M = 0.914  # 36 inches (3 feet) in meters — California fire code setback (IFC 605.11.1 / CEC 690.12)
        PANEL_W_M = self.panel.width_ft * 0.3048  # convert ft → m
        PANEL_H_M = self.panel.height_ft * 0.3048
        GAP_M = 0.05  # 50mm gap between panels

        svg = []

        # Defs
        svg.append('<defs>')
        svg.append('<pattern id="hatch-sb" patternUnits="userSpaceOnUse" width="6" height="6" '
                   'patternTransform="rotate(45)">')
        svg.append('<line x1="0" y1="0" x2="0" y2="6" stroke="#cc0000" stroke-width="0.5" opacity="0.25"/>')
        svg.append('</pattern>')
        # Dimension arrow markers
        svg.append('<marker id="dim-l" markerWidth="6" markerHeight="6" refX="6" refY="3" orient="auto">'
                   '<polygon points="0,1 6,3 0,5" fill="#444"/></marker>')
        svg.append('<marker id="dim-r" markerWidth="6" markerHeight="6" refX="0" refY="3" orient="auto">'
                   '<polygon points="6,1 0,3 6,5" fill="#444"/></marker>')
        svg.append('</defs>')

        # White background
        svg.append(f'<rect width="{VW}" height="{VH}" fill="#ffffff"/>')

        # Light construction grid (1m spacing will be computed per segment)
        for gx in range(draw_x, draw_x + draw_w, 30):
            svg.append(f'<line x1="{gx}" y1="{draw_y}" x2="{gx}" y2="{DRAW_BOTTOM}" '
                       f'stroke="#f2f2f2" stroke-width="0.3"/>')
        for gy in range(draw_y, DRAW_BOTTOM, 30):
            svg.append(f'<line x1="{draw_x}" y1="{gy}" x2="{draw_x + draw_w}" y2="{gy}" '
                       f'stroke="#f2f2f2" stroke-width="0.3"/>')

        # Engineering border
        svg.append(f'<rect x="{BORDER}" y="{BORDER}" width="{VW-2*BORDER}" '
                   f'height="{VH-2*BORDER}" fill="none" stroke="#000" stroke-width="1.5"/>')

        # Page title
        svg.append(f'<text x="{BORDER+15}" y="{BORDER+18}" font-size="14" font-weight="700" '
                   f'font-family="Arial" fill="#000">A-102: RACKING AND FRAMING PLAN</text>')
        svg.append(f'<text x="{BORDER+15}" y="{BORDER+31}" font-size="8" '
                   f'font-family="Arial" fill="#555">SCALE: 1/8&quot; = 1&apos;-0&quot;</text>')

        # ── TOP INFO BAND (y=38 to y=188) ────────────────────────────────
        # Compute roof/array metrics from segments (drawn later, need first pass)
        SQFT_PER_M2 = 10.7639
        panel_area_sqft = round(self.panel.width_ft * self.panel.height_ft, 2)
        # Find first roof segment that has panels — independent lookup (panels_by_seg not yet built)
        _segs_with_panels = set()
        if insight and insight.panels and num_api_panels:
            for _pp in insight.panels[:num_api_panels]:
                _segs_with_panels.add(getattr(_pp, 'segment_index', 0))
        _first_seg = next((s for s in (insight.roof_segments if insight and insight.roof_segments else [])
                           if s.index in _segs_with_panels), None)
        if _first_seg is None and insight and insight.roof_segments:
            _first_seg = insight.roof_segments[0]
        # Use the project-authoritative panel count so every page is consistent.
        # When the placer places fewer panels than the design target (e.g. due to
        # API roof polygons being undersized), we still report the correct design
        # count — a building dept reviewer needs all pages to agree.
        _placed_count = sum(len(pr.panels) for pr in (placements or []))
        _proj_count = self._project.num_panels if (self._project and self._project.num_panels) else 0
        _total_panels_drawn = max(_placed_count, _proj_count) if _proj_count > 0 else (
            _placed_count or num_api_panels or 0)

        # Use total area of ALL roof segments so coverage % is realistic.
        # Using only the first segment produced a false "93% > 33%" alarm.
        _all_segs = insight.roof_segments if (insight and insight.roof_segments) else []
        _total_roof_sqft = sum(s.area_m2 * SQFT_PER_M2 for s in _all_segs) if _all_segs else (
            (_first_seg.area_m2 * SQFT_PER_M2) if _first_seg else 100.0)
        _roof_area_sqft  = round(_total_roof_sqft, 0)
        _array_area_sqft = round(_total_panels_drawn * panel_area_sqft, 2)
        _array_pct       = round((_array_area_sqft / _roof_area_sqft) * 100, 2) if _roof_area_sqft > 0 else 0
        _pitch_deg       = round(_first_seg.pitch_deg, 0) if _first_seg else 0
        _azimuth_deg     = round(_first_seg.azimuth_deg, 0) if _first_seg else 180
        _setback_note    = f"{_array_pct}% &lt; 33%, 18&quot; SETBACK IS VALID" if _array_pct < 33 else f"{_array_pct}% &gt; 33% — VERIFY SETBACK"

        # Pre-compute use_placements early so top info band can reference it
        use_placements = placements and any(pr.panels for pr in placements)

        # ── ROOF DETAIL block (top-left) ─────────────────────────────────
        rd_x, rd_y, rd_w, rd_h = BORDER + 10, 38, 260, 148
        svg.append(f'<rect x="{rd_x}" y="{rd_y}" width="{rd_w}" height="{rd_h}" '
                   f'fill="#fff" stroke="#000" stroke-width="1.2"/>')
        svg.append(f'<rect x="{rd_x}" y="{rd_y}" width="{rd_w}" height="16" '
                   f'fill="#e8e8e8" stroke="#000" stroke-width="1"/>')
        svg.append(f'<text x="{rd_x + rd_w//2}" y="{rd_y + 11}" text-anchor="middle" '
                   f'font-size="9" font-weight="700" font-family="Arial" fill="#000">ROOF DETAIL</text>')
        # Circled section number (1)
        svg.append(f'<circle cx="{rd_x + rd_w - 18}" cy="{rd_y + rd_h//2 + 12}" r="14" '
                   f'fill="#fff" stroke="#000" stroke-width="1.5"/>')
        svg.append(f'<text x="{rd_x + rd_w - 18}" y="{rd_y + rd_h//2 + 17}" text-anchor="middle" '
                   f'font-size="14" font-weight="700" font-family="Arial" fill="#000">1</text>')
        # Roof type row
        roof_mat = getattr(self._project, 'roof_material_display', 'ASPHALT-SHINGLES') if self._project else 'ASPHALT-SHINGLES'
        svg.append(f'<text x="{rd_x + 8}" y="{rd_y + 28}" font-size="9" font-weight="700" '
                   f'font-family="Arial" fill="#000">ROOF TYPE:</text>')
        svg.append(f'<text x="{rd_x + 8}" y="{rd_y + 40}" font-size="9" font-weight="400" '
                   f'font-family="Arial" fill="#333">{roof_mat.upper()}</text>')
        # Per-face detail rows from placements (or fallback to insight)
        _face_rows = []
        if use_placements:
            for _fi, _pr in enumerate(placements):
                if _pr.panels:
                    _rf = _pr.roof_face
                    _face_rows.append((
                        f"ROOF FACE {_fi + 1}: {len(_pr.panels)} MODULES",
                        f"AZM: {_rf.azimuth_deg:.0f}\u00b0 | TILT: {_rf.pitch_deg:.0f}\u00b0"
                        if _rf else "—"
                    ))
        if not _face_rows:
            _face_rows = [
                (f"ROOF SECTION 1: {_total_panels_drawn} MODULES",
                 f"AZM: {_azimuth_deg:.0f}\u00b0 | TILT: {_pitch_deg:.0f}\u00b0"),
            ]
        for _fi, (_face_lbl, _face_det) in enumerate(_face_rows):
            _fy = rd_y + 54 + _fi * 34
            svg.append(f'<text x="{rd_x + 8}" y="{_fy}" font-size="8.5" font-weight="700" '
                       f'font-family="Arial" fill="#000">{_face_lbl}</text>')
            svg.append(f'<text x="{rd_x + 8}" y="{_fy + 14}" font-size="8" font-weight="400" '
                       f'font-family="Arial" fill="#555">{_face_det}</text>')

        # ── ROOF AREA / SOLAR PANEL AREA table (top-center) ──────────────
        ra_x, ra_y, ra_w, ra_h = BORDER + 280, 38, 700, 70
        svg.append(f'<rect x="{ra_x}" y="{ra_y}" width="{ra_w}" height="{ra_h}" '
                   f'fill="#fff" stroke="#000" stroke-width="1.2"/>')
        # 3-column header
        ra_cols = [("ROOF AREA", 175), ("SOLAR PANEL AREA", 330), ("SOLAR % OF ROOF AREA", 195)]
        cx2 = ra_x
        for hdr, cw2 in ra_cols:
            svg.append(f'<rect x="{cx2}" y="{ra_y}" width="{cw2}" height="18" '
                       f'fill="#e8e8e8" stroke="#000" stroke-width="0.8"/>')
            svg.append(f'<text x="{cx2 + cw2//2}" y="{ra_y + 12}" text-anchor="middle" '
                       f'font-size="8" font-weight="700" font-family="Arial" fill="#000">{hdr}</text>')
            cx2 += cw2
        # Data row 1 (row headers)
        cx2 = ra_x
        subhdrs = [
            [f"{int(_roof_area_sqft)} SQ FT ROOF"],
            [f"{panel_area_sqft:.2f} SQ FT EACH", f"{_total_panels_drawn} PANELS", f"{_array_area_sqft:.2f} SQ FT ARRAY"],
            [f"{_setback_note}"],
        ]
        col_widths2 = [175, 330, 195]
        for ci_x, (vals, cw2) in enumerate(zip(subhdrs, col_widths2)):
            # Sub-columns for middle col
            if len(vals) == 3:
                sub_w = cw2 // 3
                for j, v in enumerate(vals):
                    scx = cx2 + j * sub_w
                    svg.append(f'<rect x="{scx}" y="{ra_y + 18}" width="{sub_w}" height="52" '
                               f'fill="#fafafa" stroke="#000" stroke-width="0.5"/>')
                    svg.append(f'<text x="{scx + sub_w//2}" y="{ra_y + 48}" text-anchor="middle" '
                               f'font-size="8" font-weight="600" font-family="Arial" fill="#000">{v}</text>')
            else:
                svg.append(f'<rect x="{cx2}" y="{ra_y + 18}" width="{cw2}" height="52" '
                           f'fill="#fafafa" stroke="#000" stroke-width="0.5"/>')
                svg.append(f'<text x="{cx2 + cw2//2}" y="{ra_y + 48}" text-anchor="middle" '
                           f'font-size="9" font-weight="600" font-family="Arial" fill="#000">{vals[0]}</text>')
            cx2 += cw2

        # ── SYSTEM LEGEND (top-right) ─────────────────────────────────────
        sl_x, sl_y, sl_w, sl_h = BORDER + 990, 38, 245, 148
        svg.append(f'<rect x="{sl_x}" y="{sl_y}" width="{sl_w}" height="{sl_h}" '
                   f'fill="#fff" stroke="#000" stroke-width="1.2"/>')
        svg.append(f'<rect x="{sl_x}" y="{sl_y}" width="{sl_w}" height="16" '
                   f'fill="#e8e8e8" stroke="#000" stroke-width="1"/>')
        svg.append(f'<text x="{sl_x + sl_w//2}" y="{sl_y + 11}" text-anchor="middle" '
                   f'font-size="9" font-weight="700" font-family="Arial" fill="#000">SYSTEM LEGEND</text>')
        leg_items_top = [
            ("dot",   "#1a6ea8","solid",  "ROOF ATTACHMENT POINT"),
            ("line",  "#d08020","solid",  "ROOF FRAMING (RAFTERS/TRUSS)"),
            ("line",  "#4a9e4a","solid",  "RACKING"),
            ("rect",  "#cc0000","hatch",  "FIRE CODE SETBACK (18\u2033 MIN / 36\u2033 MAX)"),
        ]
        for i, (sym, color, style, label) in enumerate(leg_items_top):
            iy = sl_y + 26 + i * 28
            if sym == "dot":
                svg.append(f'<circle cx="{sl_x + 14}" cy="{iy + 4}" r="4" '
                           f'fill="{color}" stroke="#000" stroke-width="0.8"/>')
            elif sym == "line":
                svg.append(f'<line x1="{sl_x + 4}" y1="{iy + 4}" x2="{sl_x + 24}" y2="{iy + 4}" '
                           f'stroke="{color}" stroke-width="2"/>')
            elif sym == "rect":
                svg.append(f'<rect x="{sl_x + 4}" y="{iy}" width="20" height="10" '
                           f'fill="url(#hatch-sb)" stroke="{color}" stroke-width="0.5"/>')
            svg.append(f'<text x="{sl_x + 32}" y="{iy + 9}" font-size="7.5" '
                       f'font-family="Arial" fill="#000">{label}</text>')

        # ── Draw roof faces and panels from placements data ──────────────
        # Default px_per_m for scale bar (updated below when segments available)
        px_per_m = 40

        if use_placements:
            # Layout each roof face in its own horizontal slot so all faces are
            # visible side by side regardless of their absolute coordinate positions.
            # Filter to faces that have a polygon; prefer faces with panels first.
            faces_to_draw = [pr for pr in placements
                             if pr.roof_face and pr.roof_face.polygon and pr.panels]
            if not faces_to_draw:
                faces_to_draw = [pr for pr in placements
                                 if pr.roof_face and pr.roof_face.polygon]

            num_faces = max(len(faces_to_draw), 1)
            slot_gap = 50  # px gap between face slots
            slot_w = (draw_w - (num_faces - 1) * slot_gap) / num_faces
            available_h = draw_h - 70  # reserve space for labels above/below

            # Estimate px_per_m from the largest face for the scale bar
            largest_pr2 = max(faces_to_draw, key=lambda pr: pr.roof_face.area_sqft
                              if pr.roof_face else 0)
            if largest_pr2.roof_face and largest_pr2.roof_face.area_sqft > 0:
                face_bb2 = largest_pr2.roof_face.polygon.bounds
                face_w2 = max(face_bb2[2] - face_bb2[0], 1.0)
                face_h2 = max(face_bb2[3] - face_bb2[1], 1.0)
                sc2 = min(slot_w * 0.8 / face_w2, available_h * 0.8 / face_h2)
                rf_area_sqft2 = largest_pr2.roof_face.area_sqft
                rf_diag_ft2 = math.sqrt(rf_area_sqft2 * 5.0)
                poly_diag_pts2 = math.hypot(face_w2, face_h2)
                pts_per_ft_est2 = poly_diag_pts2 / max(rf_diag_ft2, 1.0)
                px_per_m = sc2 * pts_per_ft_est2 * 3.281
                px_per_m = max(px_per_m, 8)

            # Draw each face in its allocated slot
            panel_num = 0
            for pri, pr in enumerate(faces_to_draw):
                rf = pr.roof_face
                face_bb = rf.polygon.bounds  # (minx, miny, maxx, maxy) in pts
                face_w = max(face_bb[2] - face_bb[0], 1.0)
                face_h = max(face_bb[3] - face_bb[1], 1.0)

                # Scale to fit slot with inner margin for annotations
                margin_inner = 30
                sc = min((slot_w - 2 * margin_inner) / face_w,
                         (available_h - 2 * margin_inner) / face_h) * 0.88

                # Slot x origin (left edge of this face's column)
                slot_x0 = draw_x + pri * (slot_w + slot_gap)

                # Center the face within the slot
                face_draw_w = face_w * sc
                face_draw_h = face_h * sc
                ox = slot_x0 + margin_inner + (slot_w - 2 * margin_inner - face_draw_w) / 2
                oy = draw_y + 30 + (available_h - face_draw_h) / 2

                def _make_pt2svg(ox_=ox, oy_=oy, sc_=sc, bb_=face_bb):
                    def pt2svg(px2, py2):
                        return (ox_ + (px2 - bb_[0]) * sc_,
                                oy_ + (py2 - bb_[1]) * sc_)
                    return pt2svg

                pt2svg = _make_pt2svg()

                # Face-local px_per_m for rafter spacing
                if rf.area_sqft > 0:
                    rf_diag_ft = math.sqrt(rf.area_sqft * 5.0)
                    poly_diag_pts = math.hypot(face_w, face_h)
                    pts_per_ft_est = poly_diag_pts / max(rf_diag_ft, 1.0)
                    face_px_per_m = sc * pts_per_ft_est * 3.281
                    face_px_per_m = max(face_px_per_m, 8)
                else:
                    face_px_per_m = px_per_m

                # Roof face outline
                coords = [pt2svg(x, y) for x, y in rf.polygon.exterior.coords]
                pts_str = " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
                svg.append(f'<polygon points="{pts_str}" fill="#fafafa" '
                           f'stroke="#000" stroke-width="2"/>')

                # Fire setback inner boundary (red dashed) from usable polygon
                if rf.usable_polygon and not rf.usable_polygon.is_empty:
                    try:
                        u_pts = " ".join(
                            f"{pt2svg(x, y)[0]:.1f},{pt2svg(x, y)[1]:.1f}"
                            for x, y in rf.usable_polygon.exterior.coords
                        )
                        svg.append(f'<polygon points="{u_pts}" fill="none" '
                                   f'stroke="#cc0000" stroke-width="1.2" '
                                   f'stroke-dasharray="6,3"/>')
                    except Exception:
                        pass

                # Rafter lines: orange vertical lines at 24" spacing across roof face
                RAFTER_M = 0.610
                rafter_px2 = RAFTER_M * face_px_per_m
                rf_sv_x0, rf_sv_y0 = pt2svg(face_bb[0], face_bb[1])
                rf_sv_x1, rf_sv_y1 = pt2svg(face_bb[2], face_bb[3])
                if rafter_px2 > 2:
                    ri = 0
                    while True:
                        rx2 = rf_sv_x0 + ri * rafter_px2
                        if rx2 > rf_sv_x1 + rafter_px2 * 0.1:
                            break
                        svg.append(f'<line x1="{rx2:.1f}" y1="{rf_sv_y0:.1f}" '
                                   f'x2="{rx2:.1f}" y2="{rf_sv_y1:.1f}" '
                                   f'stroke="#d08020" stroke-width="0.9" opacity="0.55"/>')
                        ri += 1

                # Draw panels
                for panel in pr.panels:
                    panel_num += 1
                    svg_cx, svg_cy = pt2svg(panel.center_x, panel.center_y)
                    pw2 = panel.width_pts * sc
                    ph2 = panel.height_pts * sc
                    rot = panel.rotation_deg

                    svg.append(
                        f'<g transform="translate({svg_cx:.1f},{svg_cy:.1f})'
                        f' rotate({rot:.1f})">'
                    )
                    svg.append(
                        f'<rect x="{-pw2/2:.1f}" y="{-ph2/2:.1f}" '
                        f'width="{pw2:.1f}" height="{ph2:.1f}" '
                        f'fill="#ffffff" stroke="#333" stroke-width="0.8"/>'
                    )
                    # Cell lines (3 subdivisions)
                    for ci2 in range(1, 3):
                        cell_y2 = -ph2/2 + ph2/3 * ci2
                        svg.append(
                            f'<line x1="{-pw2/2:.1f}" y1="{cell_y2:.1f}" '
                            f'x2="{pw2/2:.1f}" y2="{cell_y2:.1f}" '
                            f'stroke="#bbb" stroke-width="0.3"/>'
                        )
                    # Panel number
                    fs = max(5, min(8, int(pw2 * 0.35)))
                    svg.append(
                        f'<text x="0" y="{fs//2}" text-anchor="middle" '
                        f'font-size="{fs}" font-family="Arial" fill="#000">'
                        f'{panel_num}</text>'
                    )
                    svg.append('</g>')

                # Racking rails: green lines at top/bottom of each panel row
                if pr.panels:
                    # Group panels by approximate row (cluster by center_y)
                    panels_sorted = sorted(pr.panels, key=lambda p: p.center_y)
                    row_groups = []
                    current_row = [panels_sorted[0]]
                    for p in panels_sorted[1:]:
                        if abs(p.center_y - current_row[0].center_y) < p.height_pts * 0.8:
                            current_row.append(p)
                        else:
                            row_groups.append(current_row)
                            current_row = [p]
                    row_groups.append(current_row)

                    for row_panels in row_groups:
                        min_cx_pts = min(p.center_x for p in row_panels)
                        max_cx_pts = max(p.center_x for p in row_panels)
                        sample_p = row_panels[0]
                        half_w = sample_p.width_pts / 2
                        half_h = sample_p.height_pts / 2
                        rail_top_pts = sample_p.center_y - half_h + 2
                        rail_bot_pts = sample_p.center_y + half_h - 2
                        rx0, ry_t = pt2svg(min_cx_pts - half_w - 4, rail_top_pts)
                        rx1, _ = pt2svg(max_cx_pts + half_w + 4, rail_top_pts)
                        _, ry_b = pt2svg(min_cx_pts, rail_bot_pts)
                        svg.append(f'<line x1="{rx0:.1f}" y1="{ry_t:.1f}" '
                                   f'x2="{rx1:.1f}" y2="{ry_t:.1f}" '
                                   f'stroke="#4a9e4a" stroke-width="1.8"/>')
                        svg.append(f'<line x1="{rx0:.1f}" y1="{ry_b:.1f}" '
                                   f'x2="{rx1:.1f}" y2="{ry_b:.1f}" '
                                   f'stroke="#4a9e4a" stroke-width="1.8"/>')
                        # Attachment points at rail ends
                        for att_x_pts in [min_cx_pts - half_w, max_cx_pts + half_w]:
                            ax, _ = pt2svg(att_x_pts, rail_top_pts)
                            svg.append(f'<circle cx="{ax:.1f}" cy="{ry_t:.1f}" r="3" '
                                       f'fill="#1a6ea8" stroke="#000" stroke-width="0.5"/>')
                            svg.append(f'<circle cx="{ax:.1f}" cy="{ry_b:.1f}" r="3" '
                                       f'fill="#1a6ea8" stroke="#000" stroke-width="0.5"/>')

                # Segment label above polygon
                poly_cx2, _ = pt2svg(rf.polygon.centroid.x, rf.polygon.centroid.y)
                poly_top_svg = min(pt2svg(x, y)[1] for x, y in rf.polygon.exterior.coords)
                direction = self._azimuth_label(rf.azimuth_deg)
                svg.append(
                    f'<text x="{poly_cx2:.1f}" y="{poly_top_svg - 18:.0f}" '
                    f'text-anchor="middle" font-size="11" font-weight="700" '
                    f'font-family="Arial" fill="#000">ROOF #{pri+1}</text>'
                )
                svg.append(
                    f'<text x="{poly_cx2:.1f}" y="{poly_top_svg - 6:.0f}" '
                    f'text-anchor="middle" font-size="8" font-family="Arial" fill="#555">'
                    f'{direction} ({rf.azimuth_deg:.0f}°) — {rf.pitch_deg:.0f}° tilt'
                    f' — {len(pr.panels)} panels</text>'
                )

                # 3'-0" setback callout on right side of polygon
                poly_right_svg = max(pt2svg(x, y)[0] for x, y in rf.polygon.exterior.coords)
                sb_callout_px = SETBACK_M * face_px_per_m
                ann_x_r = poly_right_svg + 8
                ann_top = poly_top_svg
                svg.append(
                    f'<line x1="{ann_x_r:.1f}" y1="{ann_top:.1f}" '
                    f'x2="{ann_x_r:.1f}" y2="{ann_top + sb_callout_px:.1f}" '
                    f'stroke="#cc0000" stroke-width="1" '
                    f'marker-start="url(#dim-l)" marker-end="url(#dim-r)"/>'
                )
                svg.append(
                    f'<text x="{ann_x_r + 4:.1f}" y="{ann_top + sb_callout_px/2 + 3:.1f}" '
                    f'font-size="7.5" font-weight="700" font-family="Arial" fill="#cc0000">'
                    f'3\'-0&quot; TYP.</text>'
                )

        else:
            # ── Fallback: draw abstract segments when no placements available ──
            panels_by_seg = {}
            if insight and insight.panels and num_api_panels:
                for p in insight.panels[:num_api_panels]:
                    seg_idx = getattr(p, 'segment_index', 0)
                    panels_by_seg.setdefault(seg_idx, []).append(p)

            segments = insight.roof_segments if insight and insight.roof_segments else []
            num_segs = max(1, len([s for s in segments if s.index in panels_by_seg]))
            seg_gap = 60
            available_w_per_seg = (draw_w - (num_segs - 1) * seg_gap) / max(num_segs, 1)
            available_h = draw_h - 60

            if segments:
                largest_seg = max(segments, key=lambda s: s.area_m2)
                est_w = math.sqrt(largest_seg.area_m2 * 1.5)
                est_h = math.sqrt(largest_seg.area_m2 / 1.5)
                px_per_m = min(available_w_per_seg / est_w, available_h / est_h) * 0.85
            else:
                px_per_m = 40

            seg_x_cursor = draw_x + 40
            for seg in segments:
                seg_panels = panels_by_seg.get(seg.index, [])
                if not seg_panels and seg.index != 0:
                    continue
                direction = self._azimuth_label(seg.azimuth_deg)
                seg_w_m = math.sqrt(seg.area_m2 * 1.5)
                seg_h_m = math.sqrt(seg.area_m2 / 1.5)
                seg_w_px = seg_w_m * px_per_m
                seg_h_px = seg_h_m * px_per_m
                sb_px = SETBACK_M * px_per_m
                panel_w_px = PANEL_W_M * px_per_m
                panel_h_px = PANEL_H_M * px_per_m
                gap_px = GAP_M * px_per_m
                seg_x = seg_x_cursor
                seg_y = draw_y + (draw_h - seg_h_px) / 2

                svg.append(f'<rect x="{seg_x:.1f}" y="{seg_y:.1f}" width="{seg_w_px:.1f}" '
                           f'height="{seg_h_px:.1f}" fill="#fafafa" stroke="#000" stroke-width="2"/>')
                svg.append(f'<rect x="{seg_x + sb_px:.1f}" y="{seg_y + sb_px:.1f}" '
                           f'width="{seg_w_px - 2*sb_px:.1f}" height="{seg_h_px - 2*sb_px:.1f}" '
                           f'fill="none" stroke="#cc0000" stroke-width="1" stroke-dasharray="6,3"/>')

                usable_x = seg_x + sb_px + gap_px
                usable_y = seg_y + sb_px + gap_px
                usable_w = seg_w_px - 2 * sb_px - 2 * gap_px
                usable_h = seg_h_px - 2 * sb_px - 2 * gap_px
                pw, ph = panel_w_px, panel_h_px
                cols = max(1, int((usable_w + gap_px) / (pw + gap_px)))
                rows = max(1, int((usable_h + gap_px) / (ph + gap_px)))
                grid_w = cols * pw + (cols - 1) * gap_px
                grid_h = rows * ph + (rows - 1) * gap_px
                grid_x = usable_x + (usable_w - grid_w) / 2
                grid_y = usable_y + (usable_h - grid_h) / 2

                panel_count = 0
                max_to_draw = len(seg_panels) if seg_panels else cols * rows
                for r in range(rows):
                    for c in range(cols):
                        if panel_count >= max_to_draw:
                            break
                        px2 = grid_x + c * (pw + gap_px)
                        py2 = grid_y + r * (ph + gap_px)
                        svg.append(f'<rect x="{px2:.1f}" y="{py2:.1f}" width="{pw:.1f}" '
                                   f'height="{ph:.1f}" fill="#ffffff" stroke="#333" stroke-width="0.8"/>')
                        panel_count += 1

                svg.append(f'<text x="{seg_x + seg_w_px/2:.1f}" y="{seg_y - 18:.0f}" '
                           f'text-anchor="middle" font-size="12" font-weight="700" '
                           f'font-family="Arial" fill="#000">ROOF SEGMENT {seg.index+1}</text>')
                svg.append(f'<text x="{seg_x + seg_w_px/2:.1f}" y="{seg_y - 5:.0f}" '
                           f'text-anchor="middle" font-size="9" font-family="Arial" fill="#555">'
                           f'{direction} ({seg.azimuth_deg:.0f}°) — Pitch {seg.pitch_deg:.0f}° — '
                           f'{panel_count} panels</text>')
                seg_x_cursor += seg_w_px + seg_gap + 60

        # ── BOTTOM INFO BAND (y=DRAW_BOTTOM+4 to y=840) ──────────────────
        bot_band_y = DRAW_BOTTOM + 4
        bot_band_h = 125  # height of bottom info band

        # ── ELEVATION DETAIL cross-section (bottom-left, NTS) ────────────
        ev_x, ev_y, ev_w, ev_h = BORDER + 10, bot_band_y, 215, bot_band_h
        svg.append(f'<rect x="{ev_x}" y="{ev_y}" width="{ev_w}" height="{ev_h}" '
                   f'fill="#fff" stroke="#000" stroke-width="1"/>')
        svg.append(f'<rect x="{ev_x}" y="{ev_y}" width="{ev_w}" height="14" '
                   f'fill="#e8e8e8" stroke="#000" stroke-width="1"/>')
        svg.append(f'<text x="{ev_x + ev_w//2}" y="{ev_y + 10}" text-anchor="middle" '
                   f'font-size="8" font-weight="700" font-family="Arial" fill="#000">STRUCTURAL ATTACHMENT</text>')
        # Cross-section drawing (NTS)
        # Draw layers bottom→top in the box
        ed_lx, ed_rx = ev_x + 8, ev_x + 140
        ed_mid = (ed_lx + ed_rx) // 2
        # Truss / roof sheathing (bottom)
        ed_truss_y = ev_y + bot_band_h - 18
        svg.append(f'<rect x="{ed_lx}" y="{ed_truss_y - 8}" width="{ed_rx - ed_lx}" height="8" '
                   f'fill="#ddd" stroke="#555" stroke-width="0.8"/>')
        svg.append(f'<text x="{ed_rx + 4}" y="{ed_truss_y - 2}" font-size="6.5" '
                   f'font-family="Arial" fill="#333">TRUSS @24&quot; OC : 2&quot;x8&quot;</text>')
        # Asphalt shingles
        ed_shingle_y = ed_truss_y - 8
        svg.append(f'<rect x="{ed_lx}" y="{ed_shingle_y - 5}" width="{ed_rx - ed_lx}" height="5" '
                   f'fill="#999" stroke="#555" stroke-width="0.6"/>')
        svg.append(f'<text x="{ed_rx + 4}" y="{ed_shingle_y}" font-size="6.5" '
                   f'font-family="Arial" fill="#333">ASPHALT-SHINGLES</text>')
        # Structural attachment / L-foot
        ed_foot_y = ed_shingle_y - 5
        svg.append(f'<polygon points="{ed_mid - 6},{ed_foot_y} {ed_mid + 6},{ed_foot_y} '
                   f'{ed_mid + 4},{ed_foot_y - 12} {ed_mid - 4},{ed_foot_y - 12}" '
                   f'fill="#ccc" stroke="#444" stroke-width="0.8"/>')
        svg.append(f'<text x="{ed_rx + 4}" y="{ed_foot_y - 4}" font-size="6.5" '
                   f'font-family="Arial" fill="#333">STRUCTURAL ATTACHMENT</text>')
        # Rail
        ed_rail_y = ed_foot_y - 14
        svg.append(f'<rect x="{ed_lx + 10}" y="{ed_rail_y}" width="{ed_rx - ed_lx - 20}" height="5" '
                   f'fill="#aaa" stroke="#444" stroke-width="0.8"/>')
        # Module
        ed_mod_y = ed_rail_y - 5
        svg.append(f'<rect x="{ed_lx + 5}" y="{ed_mod_y - 14}" width="{ed_rx - ed_lx - 10}" height="14" '
                   f'fill="#ffffff" stroke="#000000" stroke-width="1.5"/>')
        svg.append(f'<text x="{ed_rx + 4}" y="{ed_mod_y - 6}" font-size="6.5" '
                   f'font-family="Arial" fill="#333">MODULE</text>')
        # NTS label
        svg.append(f'<text x="{ev_x + 8}" y="{ev_y + bot_band_h - 4}" font-size="7" '
                   f'font-weight="700" font-family="Arial" fill="#555">NTS</text>')
        svg.append(f'<text x="{ev_x + ev_w//2}" y="{ev_y + bot_band_h - 4}" text-anchor="middle" '
                   f'font-size="7" font-weight="700" font-family="Arial" fill="#000">ELEVATION DETAIL</text>')

        # ── MODULE MECHANICAL SPECIFICATIONS table ────────────────────────
        ms2_x, ms2_y, ms2_w = BORDER + 235, bot_band_y, 275
        ms2_col1, ms2_col2 = 185, 90
        _wind_snow = (self._jurisdiction.get_wind_snow_loads(city=self._project.municipality)
                      if hasattr(self._jurisdiction, 'get_wind_snow_loads')
                      else {"wind_mph": 105, "snow_psf": 40})
        ms2_rows = [
            ("DESIGN WIND SPEED",           f"{_wind_snow['wind_mph']} MPH"),
            ("DESIGN SNOW LOAD",            f"{_wind_snow['snow_psf']} PSF"),
            ("# OF STORIES",                "2"),
            ("ROOF PITCH",                  f"{_pitch_deg:.0f}\u00b0"),
            ("TOTAL ARRAY AREA (SQ. FT)",   f"{_array_area_sqft:.2f}"),
            ("TOTAL ROOF AREA (SQ. FT)",    f"{int(_roof_area_sqft)}"),
            ("ARRAY SQ. FT / TOTAL ROOF SQ. FT", f"{_array_pct:.2f}%"),
        ]
        ms2_row_h = 14
        ms2_total_h = 16 + len(ms2_rows) * ms2_row_h
        svg.append(f'<rect x="{ms2_x}" y="{ms2_y}" width="{ms2_w}" height="{ms2_total_h}" '
                   f'fill="#fff" stroke="#000" stroke-width="1"/>')
        svg.append(f'<rect x="{ms2_x}" y="{ms2_y}" width="{ms2_w}" height="16" '
                   f'fill="#e8e8e8" stroke="#000" stroke-width="1"/>')
        svg.append(f'<text x="{ms2_x + ms2_w//2}" y="{ms2_y + 11}" text-anchor="middle" '
                   f'font-size="8" font-weight="700" font-family="Arial" fill="#000">'
                   f'MODULE MECHANICAL SPECIFICATIONS</text>')
        for i, (lbl, val) in enumerate(ms2_rows):
            ry3 = ms2_y + 16 + i * ms2_row_h
            bg3 = "#fafafa" if i % 2 == 0 else "#fff"
            svg.append(f'<rect x="{ms2_x}" y="{ry3}" width="{ms2_col1}" height="{ms2_row_h}" '
                       f'fill="{bg3}" stroke="#000" stroke-width="0.4"/>')
            svg.append(f'<rect x="{ms2_x + ms2_col1}" y="{ry3}" width="{ms2_col2}" height="{ms2_row_h}" '
                       f'fill="{bg3}" stroke="#000" stroke-width="0.4"/>')
            svg.append(f'<text x="{ms2_x + 4}" y="{ry3 + 10}" font-size="7" '
                       f'font-family="Arial" fill="#000">{lbl}</text>')
            svg.append(f'<text x="{ms2_x + ms2_col1 + ms2_col2//2}" y="{ry3 + 10}" '
                       f'text-anchor="middle" font-size="7" font-weight="700" '
                       f'font-family="Arial" fill="#000">{val}</text>')

        # ── Scale bar + compass rose (bottom-center) ──────────────────────
        sc_x2, sc_y2 = ms2_x + ms2_w + 30, bot_band_y + 20
        sc_m = 2
        sc_px = sc_m * px_per_m
        svg.append(f'<line x1="{sc_x2}" y1="{sc_y2}" x2="{sc_x2 + sc_px:.0f}" y2="{sc_y2}" '
                   f'stroke="#000" stroke-width="1.5"/>')
        svg.append(f'<line x1="{sc_x2}" y1="{sc_y2 - 4}" x2="{sc_x2}" y2="{sc_y2 + 4}" '
                   f'stroke="#000" stroke-width="1.5"/>')
        svg.append(f'<line x1="{sc_x2 + sc_px:.0f}" y1="{sc_y2 - 4}" '
                   f'x2="{sc_x2 + sc_px:.0f}" y2="{sc_y2 + 4}" stroke="#000" stroke-width="1.5"/>')
        svg.append(f'<text x="{sc_x2 + sc_px / 2:.0f}" y="{sc_y2 + 14}" text-anchor="middle" '
                   f'font-size="8" font-family="Arial" fill="#000" font-weight="600">{sc_m} m</text>')
        svg.append(f'<text x="{sc_x2}" y="{sc_y2 - 10}" font-size="7" '
                   f'font-family="Arial" fill="#555">SCALE BAR</text>')

        # Compass rose (above scale bar)
        cr_x, cr_y2 = sc_x2 + int(sc_px) + 45, bot_band_y + 50
        svg.append(f'<g transform="translate({cr_x},{cr_y2})">'
                   f'<circle cx="0" cy="0" r="18" fill="none" stroke="#000" stroke-width="1"/>'
                   f'<polygon points="0,-15 -4,6 0,3 4,6" fill="#000"/>'
                   f'<polygon points="0,15 -4,-6 0,-3 4,-6" fill="#fff" stroke="#000" stroke-width="0.8"/>'
                   f'<text x="0" y="-20" text-anchor="middle" font-size="9" font-weight="700" '
                   f'font-family="Arial" fill="#000">N</text></g>')

        # ── Title block ──────────────────────────────────────────────
        svg.append(self._svg_title_block(VW, VH, "A-102", "Racking and Framing Plan",
                                          "Setback, Rails, Panels", "4 of 13",
                                          address, today))

        content = "\n".join(svg)
        return (f'<div class="page"><svg width="100%" height="100%" '
                f'viewBox="0 0 {VW} {VH}" xmlns="http://www.w3.org/2000/svg" '
                f'style="background:#fff;">{content}</svg></div>')

    def _build_string_plan_page(self, insight, total_panels: int,
                               address: str, today: str) -> str:
        """PV-7: Microinverter & Circuit Map — Cubillas-standard clean professional layout.

        Layout (1280×960):
          Top-left: CIRCUIT DETAIL box (Cubillas format: white swatches + "CIRCUIT # N: M MODULES")
          Main area: Panel array rotated to roof azimuth, white panels, green circuit lines
          Circuit labels: horizontal labels with leader lines (outside rotation)
          Footer: FOR INSTALLER USE ONLY
          Bottom-right: Standard _svg_title_block
          Bottom-right: Standard _svg_title_block
        """
        VW, VH = 1280, 960
        BORDER = 20

        # ── Circuit assignment ─────────────────────────────────────────────
        # Max inverter units per branch circuit — from catalog or default
        n_panels = max(total_panels, 1)
        MAX_PER_CIRCUIT = self._max_per_branch

        if n_panels <= MAX_PER_CIRCUIT:
            circuit_sizes = [n_panels]
        else:
            n_circ = math.ceil(n_panels / MAX_PER_CIRCUIT)
            base = n_panels // n_circ
            rem  = n_panels % n_circ
            circuit_sizes = [base + (1 if i < rem else 0) for i in range(n_circ)]
        # Note: with MAX_PER_CIRCUIT=7, 8+ panel systems naturally produce 2+ circuits.
        # No need to force-split; circuit sizes match PV-4 CIRCUIT-1/2 labels exactly.

        n_circuits = len(circuit_sizes)

        # ── Azimuth / rotation ─────────────────────────────────────────────
        azimuth = 175.0   # default: nearly south (Gatineau QC)
        if insight and insight.roof_segments:
            azimuth = insight.roof_segments[0].azimuth_deg
        # SVG rotation: azimuth − 180 so 180° (true south) = 0° (vertical column top-down)
        rot_deg = azimuth - 180.0

        # ── Panel / array dimensions ───────────────────────────────────────
        pw_m = self.panel.width_ft  * 0.3048   # short side (portrait)
        ph_m = self.panel.height_ft * 0.3048   # long side (portrait)
        gap_m     = 0.05                        # 5 cm gap between panels in column
        col_gap_m = pw_m * 0.25                 # gap between circuit columns

        # Array height = tallest column; width = all columns side-by-side
        max_rows   = max(circuit_sizes)
        array_h_m  = max_rows * ph_m + max(max_rows - 1, 0) * gap_m
        array_w_m  = n_circuits * pw_m + max(n_circuits - 1, 0) * col_gap_m

        # Scale to fit array in 65% of vertical drawing space (leaving room for title/header)
        avail_h = VH - 130 - 60   # minus title block (130) + top margin (60)
        avail_w = VW * 0.55        # use ~55% of width for array (labels on right)
        px_per_m = min(avail_h * 0.65 / array_h_m,
                       avail_w * 0.65 / array_w_m,
                       70.0)       # cap at 70 px/m

        pw_px     = pw_m     * px_per_m
        ph_px     = ph_m     * px_per_m
        gap_px    = gap_m    * px_per_m
        col_gap_px = col_gap_m * px_per_m

        # ── Drawing center (slightly left of page center to leave room for labels) ──
        draw_cx = VW * 0.46
        draw_cy = (60 + VH - 130) / 2      # vertically centered in drawing area

        # ── Pre-compute column layout in un-rotated space ──────────────────
        total_array_w_px = n_circuits * pw_px + max(n_circuits - 1, 0) * col_gap_px
        col_info: List[tuple] = []          # (col_x_left, col_y_top, col_height_px)
        for ci, sz in enumerate(circuit_sizes):
            col_x = draw_cx - total_array_w_px / 2 + ci * (pw_px + col_gap_px)
            col_h = sz * ph_px + max(sz - 1, 0) * gap_px
            col_y = draw_cy - col_h / 2
            col_info.append((col_x, col_y, col_h))

        # ── Rotation helper ────────────────────────────────────────────────
        _rot_rad = math.radians(rot_deg)
        _cos_r   = math.cos(_rot_rad)
        _sin_r   = math.sin(_rot_rad)
        def _rot(px: float, py: float):
            dx, dy = px - draw_cx, py - draw_cy
            return draw_cx + dx*_cos_r - dy*_sin_r, draw_cy + dx*_sin_r + dy*_cos_r

        # ── SVG pieces ────────────────────────────────────────────────────
        svg: List[str] = []

        # ── Defs: arrowhead marker ─────────────────────────────────────────
        svg.append('<defs>')
        svg.append(
            '<marker id="pv7arr" markerWidth="8" markerHeight="6" '
            'refX="0" refY="3" orient="auto" markerUnits="strokeWidth">'
            '<path d="M0,0 L0,6 L8,3 z" fill="#000"/></marker>'
        )
        svg.append('</defs>')

        # ── White background + engineering border ─────────────────────────
        svg.append(f'<rect width="{VW}" height="{VH}" fill="#ffffff"/>')

        svg.append(f'<rect x="{BORDER}" y="{BORDER}" width="{VW-2*BORDER}" height="{VH-2*BORDER}" '
                   f'fill="none" stroke="#000" stroke-width="1.5"/>')

        # ── CIRCUIT DETAIL BOX (top-left) — Cubillas style ─────────────────
        # Format: gray header "CIRCUIT DETAIL", sub-header "ARRAY CIRCUITS",
        # one row per circuit: white panel swatch + green line + "CIRCUIT # N: M MODULES"
        cd_x, cd_y = BORDER + 15, BORDER + 15
        cd_w       = 310
        cd_row_h   = 50
        cd_h       = 42 + n_circuits * cd_row_h

        # Outer box
        svg.append(f'<rect x="{cd_x}" y="{cd_y}" width="{cd_w}" height="{cd_h}" '
                   f'fill="#fff" stroke="#000" stroke-width="1.2"/>')
        # Gray title header
        svg.append(f'<rect x="{cd_x}" y="{cd_y}" width="{cd_w}" height="22" '
                   f'fill="#d0d0d0" stroke="#000" stroke-width="0.8"/>')
        svg.append(f'<text x="{cd_x + cd_w//2}" y="{cd_y + 15}" text-anchor="middle" '
                   f'font-size="12" font-weight="700" font-family="Arial" fill="#000">'
                   f'CIRCUIT DETAIL</text>')
        # Sub-header "ARRAY CIRCUITS"
        sub_y = cd_y + 22
        svg.append(f'<rect x="{cd_x}" y="{sub_y}" width="{cd_w}" height="20" '
                   f'fill="#ebebeb" stroke="#000" stroke-width="0.4"/>')
        svg.append(f'<text x="{cd_x + cd_w//2}" y="{sub_y + 14}" text-anchor="middle" '
                   f'font-size="10" font-weight="700" font-family="Arial" fill="#000">'
                   f'ARRAY CIRCUITS</text>')

        # One row per circuit
        for ci, sz in enumerate(circuit_sizes):
            ry   = cd_y + 42 + ci * cd_row_h
            bg   = "#ffffff" if ci % 2 == 0 else "#f9f9f9"
            svg.append(f'<rect x="{cd_x}" y="{ry}" width="{cd_w}" height="{cd_row_h}" '
                       f'fill="{bg}" stroke="#cccccc" stroke-width="0.5"/>')
            # White panel swatch (Cubillas style: white rect with black border)
            sw, sh = 56, 36
            swatch_x = cd_x + 12
            swatch_y = ry + 7
            svg.append(f'<rect x="{swatch_x}" y="{swatch_y}" width="{sw}" height="{sh}" '
                       f'fill="#ffffff" stroke="#000" stroke-width="1.5"/>')
            # Green circuit line through swatch vertical center
            slx = swatch_x + sw // 2
            svg.append(f'<line x1="{slx}" y1="{swatch_y}" x2="{slx}" y2="{swatch_y + sh}" '
                       f'stroke="#009900" stroke-width="2.0"/>')
            # "CIRCUIT # N: M MODULES" label
            svg.append(f'<text x="{cd_x + 82}" y="{ry + cd_row_h//2 + 5}" '
                       f'font-size="13" font-weight="700" font-family="Arial" fill="#000">'
                       f'CIRCUIT # {ci+1}:  {sz} MODULES</text>')

        # ── ROTATED PANEL ARRAY ────────────────────────────────────────────
        # All panels rendered inside a group rotated by (azimuth - 180°) around draw center.
        # This matches the Cubillas PV-7 style where the array is shown at the actual
        # roof orientation (north-up plan view).
        svg.append(f'<g transform="rotate({rot_deg:.1f},{draw_cx:.1f},{draw_cy:.1f})">')

        for ci, (col_x, col_y, col_h) in enumerate(col_info):
            sz = circuit_sizes[ci]

            # Green circuit trunk line (vertical, through horizontal center of column)
            lx = col_x + pw_px / 2
            svg.append(f'<line x1="{lx:.1f}" y1="{col_y - 8:.1f}" '
                       f'x2="{lx:.1f}" y2="{col_y + col_h + 8:.1f}" '
                       f'stroke="#009900" stroke-width="2.5" stroke-linecap="round"/>')

            # Individual panels: white fill, black border
            for pi in range(sz):
                px = col_x
                py = col_y + pi * (ph_px + gap_px)
                svg.append(f'<rect x="{px:.1f}" y="{py:.1f}" '
                           f'width="{pw_px:.1f}" height="{ph_px:.1f}" '
                           f'fill="#ffffff" stroke="#000000" stroke-width="1.5"/>')
                # Subtle mid-panel horizontal line (like cell grid in Cubillas)
                mid_y = py + ph_px * 0.5
                svg.append(f'<line x1="{px:.1f}" y1="{mid_y:.1f}" '
                           f'x2="{px + pw_px:.1f}" y2="{mid_y:.1f}" '
                           f'stroke="#cccccc" stroke-width="0.4"/>')

        svg.append('</g>')   # end rotation group

        # ── CIRCUIT LABELS (horizontal text, outside rotation) ─────────────
        # For each circuit column: compute rotated center of column, draw leader line
        # and horizontal label to the right of the array.
        lbl_area_x = int(draw_cx + total_array_w_px * 0.7 + 80)
        lbl_area_x = min(lbl_area_x, VW - BORDER - 180)  # keep inside page

        for ci, (col_x, col_y, col_h) in enumerate(col_info):
            # Mid-point of right edge of this column (unrotated)
            anchor_ux = col_x + pw_px
            anchor_uy = col_y + col_h / 2
            # Rotate to get screen position
            arx, ary = _rot(anchor_ux, anchor_uy)
            arx = float(arx); ary = float(ary)

            # Label y: spread circuits vertically around draw_cy
            lbl_y = draw_cy + (ci - (n_circuits - 1) / 2.0) * 45
            lbl_y = max(70.0, min(float(VH - 150), lbl_y))

            # Leader line: from rotated anchor to label box left edge
            lbl_box_x = float(lbl_area_x)
            svg.append(f'<line x1="{arx:.1f}" y1="{ary:.1f}" '
                       f'x2="{lbl_box_x:.1f}" y2="{lbl_y:.1f}" '
                       f'stroke="#000000" stroke-width="0.8"/>')
            # Small dot at anchor
            svg.append(f'<circle cx="{arx:.1f}" cy="{ary:.1f}" r="3.5" '
                       f'fill="#000000"/>')
            # Label text "CIRCUIT - N"
            svg.append(f'<text x="{lbl_box_x + 5:.1f}" y="{lbl_y + 5:.1f}" '
                       f'font-size="13" font-weight="700" font-family="Arial" fill="#000">'
                       f'CIRCUIT - {ci+1}</text>')

        # ── FOR INSTALLER USE ONLY footer (bottom-left) ────────────────────
        svg.append(f'<text x="{BORDER + 15}" y="{VH - 140}" '
                   f'font-size="11" font-weight="700" font-style="italic" '
                   f'font-family="Arial" fill="#555">FOR INSTALLER USE ONLY</text>')

        # ── Title block ────────────────────────────────────────────────────
        svg.append(self._svg_title_block(
            VW, VH, "A-103", "STRING PLAN", "Array Branch Circuit Assignment",
            "10 of 13", address, today
        ))

        svg_content = "\n".join(svg)
        return (
            f'<div class="page"><svg width="100%" height="100%" '
            f'viewBox="0 0 {VW} {VH}" xmlns="http://www.w3.org/2000/svg" '
            f'style="background:#fff;">{svg_content}</svg></div>'
        )

    def _build_single_line_diagram(self, total_panels: int, total_kw: float,
                                   address: str, today: str) -> str:
        """PV-4: Single-line diagram — full permit-ready layout.

        Layout (1280×960 SVG):
          Top (y=60-300):   Compressed circuit flow (left 68%) + String Data / 120% Rule (right 32%)
          Middle (y=308-498): Conductor & Conduit Schedule (left) + PV Module Spec Table (right)
          Lower (y=506-660):  Inverter Spec Table (left) + OCPD Calculations Table (right)
          Bottom (y=668-830): Numbered electrical notes (9 items, 2 columns)
        """
        svg_parts = []

        # Jurisdiction-aware code references
        _cp = self._code_prefix
        _is_nec = (_cp == "NEC")

        # ── Electrical calculations ──────────────────────────────────────
        # Panel electrical specs — from ProjectSpec/catalog or legacy defaults
        voc_per_panel = self._panel_voc
        vmp_per_panel = self._panel_vmp
        isc_per_panel = self._panel_isc
        imp_per_panel = self._panel_imp
        temp_coeff_voc = self._panel_temp_coeff_voc
        panel_efficiency = self._project.panel.efficiency_pct if self._project else 22.5

        # ── Microinverter branch circuit calculations (Enphase IQ8A) ──────────
        # Each panel has its own microinverter; circuits are AC branch groups.
        # IQ8A: 1.6 A per unit @ 240 V.  15 A 2P breakers → max 7 per branch
        #   (7 × 1.6 A × 1.25 = 14.0 A ≤ 15 A ✓)  matching Cubillas reference.
        MAX_PER_BRANCH   = self._max_per_branch
        BRANCH_BREAKER_A = 15           # 2P-15A branch breaker

        n_branches = max(1, math.ceil(total_panels / MAX_PER_BRANCH))
        # Split panels across branches (front-heavy ceiling split)
        branch_sizes: list = []
        _remaining = total_panels
        for _bi in range(n_branches):
            _sz = math.ceil(_remaining / (n_branches - _bi))
            branch_sizes.append(_sz)
            _remaining -= _sz

        # AC current per branch and system total
        max_branch_current = max(branch_sizes) * self.INV_AC_AMPS_PER_UNIT  # A
        total_ac_current   = total_panels * self.INV_AC_AMPS_PER_UNIT        # A (13×1.6=20.8)

        # Wire sizing helpers
        def _wire_gauge(amps):
            if amps <= 15:  return "#14 AWG"
            if amps <= 20:  return "#12 AWG"
            if amps <= 30:  return "#10 AWG"
            if amps <= 40:  return "#8 AWG"
            if amps <= 55:  return "#6 AWG"
            if amps <= 70:  return "#4 AWG"
            return "#2 AWG"

        def _conduit_size(amps):
            if amps <= 30:  return '3/4"'
            if amps <= 55:  return '1"'
            return '1-1/4"'

        def _egc_gauge(ocpd_a):
            """Minimum EGC copper wire size per jurisdiction EGC table"""
            if ocpd_a <= 15:   return "#14 AWG"
            if ocpd_a <= 20:   return "#12 AWG"
            if ocpd_a <= 60:   return "#10 AWG"
            if ocpd_a <= 100:  return "#8 AWG"
            if ocpd_a <= 200:  return "#6 AWG"
            return "#4 AWG"

        branch_ac_wire    = _wire_gauge(max_branch_current * 1.25)     # branch circuit
        branch_ac_conduit = _conduit_size(max_branch_current * 1.25)
        sys_ac_wire       = _wire_gauge(total_ac_current * 1.25)       # load-center output
        sys_ac_conduit    = _conduit_size(total_ac_current * 1.25)
        egc_wire          = sys_ac_wire                                 # EGC follows system wire
        # Per-segment EGC wire: branch_egc computed now; sys_egc computed after system_ocpd
        branch_egc_wire   = _egc_gauge(BRANCH_BREAKER_A)               # 15A branch → #14 AWG

        # System OCPD: 125% × total AC continuous output (NEC 690.8 / CEC Rule 4-004)
        system_ocpd = math.ceil(total_ac_current * 1.25 / 5) * 5      # 26 A → 30 A
        sys_egc_wire      = _egc_gauge(system_ocpd)                    # 30A system → #10 AWG

        # 120% rule (NEC 705.12 / CEC 64-056)
        # North American 200A residential panels (Square D QO, Eaton, etc.) have a
        # 225A rated bus bar — the bus rating is higher than the main breaker rating.
        # Cubillas PV-4 shows MAIN BUS RATING: 225A / MAIN DISCONNECT: 200A.
        # Using 225A for the bus (per panel label) is more technically accurate.
        main_breaker  = self._main_breaker_a
        bus_rating    = self._bus_rating_a
        total_ocpd    = system_ocpd + main_breaker                     # 30 + 200 = 230
        rule_120_lim  = int(bus_rating * 1.2)                          # 270
        rule_120_pass = (total_ocpd <= rule_120_lim)                   # 230 ≤ 270 ✓

        # Keep legacy names so downstream code (120% rule box) still works
        ac_breaker  = system_ocpd
        ac_wire     = sys_ac_wire
        ac_conduit  = sys_ac_conduit
        inv_amps_ac = total_ac_current

        inv_kw = self._calc_ac_kw(total_panels)  # total_panels × 384VA

        # ── SVG canvas & border ──────────────────────────────────────────
        svg_parts.append('<rect width="1280" height="960" fill="#ffffff"/>')
        svg_parts.append('<rect x="20" y="20" width="1240" height="820" fill="none" stroke="#000" stroke-width="2"/>')

        # Page title strip
        svg_parts.append('<rect x="20" y="20" width="1240" height="26" fill="#e8e8e8" stroke="#000" stroke-width="1"/>')
        svg_parts.append('<text x="640" y="37" text-anchor="middle" font-size="12" font-weight="700" font-family="Arial" fill="#000">SINGLE-LINE DIAGRAM — PV-4</text>')

        # ── SVG defs ─────────────────────────────────────────────────────
        svg_parts.append('''<defs>
  <marker id="arr-dc" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
    <polygon points="0,0 8,3 0,6" fill="#0066cc"/>
  </marker>
  <marker id="arr-ac" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
    <polygon points="0,0 8,3 0,6" fill="#cc0000"/>
  </marker>
</defs>''')

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
            f'<rect x="{nb_x}" y="{nb_y}" width="{nb_w}" height="13" '
            f'fill="#e8e8e8" stroke="#000" stroke-width="1"/>'
        )
        svg_parts.append(
            f'<text x="{nb_x + 8}" y="{nb_y + 9}" '
            f'font-size="8" font-weight="700" font-family="Arial" fill="#000">NOTES:</text>'
        )
        svg_parts.append(
            f'<line x1="{nb_x}" y1="{nb_y + 13}" x2="{nb_x + nb_w}" y2="{nb_y + 13}" '
            f'stroke="#000" stroke-width="0.8"/>'
        )
        _cp = self._code_prefix
        _is_nec = (_cp == "NEC")
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
        _col2_start = nb_x + nb_w // 2 + 4
        _half = (len(_sld_notes) + 1) // 2   # 5 notes left, 4 right
        for _ni, _note in enumerate(_sld_notes):
            _col = _ni // _half
            _row = _ni % _half
            _nx  = _col2_start if _col else nb_x + 8
            _ny  = nb_y + 17 + _row * 12
            svg_parts.append(
                f'<text x="{_nx}" y="{_ny}" font-size="5" font-family="Arial" fill="#222">'
                f'{_ni + 1}. {_note}</text>'
            )

        # ── TOP: CONDUCTOR AND CONDUIT SCHEDULE (x=460..880, y=47..127) ────
        # Placed immediately to the right of the NOTES box — matches Cubillas
        # PV-4 layout where the conductor schedule is the first thing visible
        # to a permit reviewer, right alongside the safety notes.
        cs_x, cs_y, cs_w, cs_h = 460, 47, 420, 106
        # 6 columns matching Cubillas PV-4 exactly (no CIRCUIT DESCRIPTION column)
        # TAG | WIRE TYPE | WIRE SIZE | # CONDUCTORS | CONDUIT TYPE | MIN. SIZE
        cs_cols = [36, 95, 68, 70, 75, 76]   # sums to 420
        cs_hdrs = ["TAG", "WIRE TYPE", "WIRE SIZE", "# CONDUCTORS",
                   "CONDUIT TYPE", "MIN. SIZE"]

        # Outer border
        svg_parts.append(
            f'<rect x="{cs_x}" y="{cs_y}" width="{cs_w}" height="{cs_h}" '
            f'fill="#ffffff" stroke="#000" stroke-width="1.2"/>'
        )
        # Title bar
        svg_parts.append(
            f'<rect x="{cs_x}" y="{cs_y}" width="{cs_w}" height="12" '
            f'fill="#e8e8e8" stroke="#000" stroke-width="1"/>'
        )
        svg_parts.append(
            f'<text x="{cs_x + cs_w//2}" y="{cs_y + 9}" '
            f'text-anchor="middle" font-size="7.5" font-weight="700" '
            f'font-family="Arial" fill="#000">CONDUCTOR AND CONDUIT SCHEDULE</text>'
        )
        # Column headers (y=59..70)
        csh_x = cs_x
        for _cw, _ch in zip(cs_cols, cs_hdrs):
            svg_parts.append(
                f'<rect x="{csh_x}" y="{cs_y+12}" width="{_cw}" height="11" '
                f'fill="#f2f2f2" stroke="#000" stroke-width="0.8"/>'
            )
            svg_parts.append(
                f'<text x="{csh_x + _cw//2}" y="{cs_y+20}" '
                f'text-anchor="middle" font-size="5.5" font-weight="700" '
                f'font-family="Arial" fill="#000">{_ch}</text>'
            )
            csh_x += _cw

        # Data rows: 11 rows × 7px = 77px; starts at y=70, ends at y=147 (within 106px box)
        # Conductor count notation matches Cubillas PV-4 standard:
        #   - 240V branch circuits (no neutral): "N - L1 L2"
        #   - System run past load center (120/240V service with neutral): "3 - L1 L2 N"
        #   - Each conduit segment has a paired EGC sub-row sharing the same tag (Cubillas standard)
        #   - Trunk (row 2) sized for combined system current (sys_ac_wire = #10 AWG)
        #     not branch_ac_wire — the trunk carries all branches' combined output
        _trunk_cond = f"{2 * n_branches} - L1 L2"   # e.g. "4 - L1 L2" for 2-circuit trunk
        # Enphase microinverter AC wiring topology:
        #   Tag 1 = AC trunk cable running in FREE AIR along module racking (Enphase Q Cable
        #           assembly). Carries combined output of all branch circuits from modules to
        #           junction box. Sized for total system current (sys_ac_wire).
        #           Matching Cubillas PV-4: "TRUNK CABLE / FREE AIR / N/A"
        #   Tag 2 = From junction box to PV load center — THWN-2 in EMT conduit
        #   Tags 3–5 = Downstream of load center — THWN-2 in EMT conduit
        #   EGC notation: "1 - GND" (matching Cubillas PV-4 verbatim)
        _wt = self._wire_type  # "THWN-2" for US, "RW90-XLPE" for CA
        cs_rows = [
            # tag, description, wire_type, wire_size, conductors, conduit_type, conduit_size, is_egc
            ("1", "AC TRUNK: MODULES \u2192 J-BOX (FREE AIR)", "TRUNK CABLE",   sys_ac_wire,  _trunk_cond,   "FREE AIR", "N/A",         False),
            ("1", "Trunk Bare Cu EGC (Free Air)",               "BARE COPPER",   "#6 AWG",     "1 - BARE",    "FREE AIR", "N/A",         True),
            ("2", "J-BOX \u2192 PV Load Center",
                                                       _wt,              sys_ac_wire,     _trunk_cond,   "EMT",      sys_ac_conduit,    False),
            ("2", "J-BOX \u2192 Load Ctr EGC",        f"{_wt} EGC",     sys_egc_wire,    "1 - GND",     "EMT",      sys_ac_conduit,    True),
            ("3", "Load Center \u2192 AC OCPD",        _wt,              sys_ac_wire,     "3 - L1 L2 N", "EMT",      sys_ac_conduit,    False),
            ("3", "Load Center \u2192 OCPD EGC",       f"{_wt} EGC",     sys_egc_wire,    "1 - GND",     "EMT",      sys_ac_conduit,    True),
            ("4", "AC OCPD \u2192 Main Service Panel", _wt,              sys_ac_wire,     "3 - L1 L2 N", "EMT",      sys_ac_conduit,    False),
            ("4", "OCPD \u2192 Main Panel EGC",        f"{_wt} EGC",     sys_egc_wire,    "1 - GND",     "EMT",      sys_ac_conduit,    True),
            ("5", "Main Panel \u2192 Utility Meter",   _wt,              sys_ac_wire,     "3 - L1 L2 N", "EMT",      sys_ac_conduit,    False),
            ("5", "Main Panel \u2192 Meter EGC",       f"{_wt} EGC",     sys_egc_wire,    "1 - GND",     "EMT",      sys_ac_conduit,    True),
            ("G", "GEC: Grounding Electrode Cond.",    "Bare Cu",        "#6 AWG",        "1 - GEC",     "FREE AIR", "N/A",             False),
        ]
        cs_row_y = cs_y + 23
        for _ri, _row in enumerate(cs_rows):
            _tag, _desc, _wtype, _wsize, _ncond, _ctype, _csize, _is_egc = _row
            # EGC sub-rows: light gray; main rows: white/near-white alternating
            if _is_egc:
                _bg = "#f0f0f0"
            else:
                _bg = "#fff" if (_ri // 2) % 2 == 0 else "#f8f8f8"
            _row_data = (_tag, _wtype, _wsize, _ncond, _ctype, _csize)  # _desc intentionally omitted (not in Cubillas)
            csr_x = cs_x
            for _ci, (_cw, _val) in enumerate(zip(cs_cols, _row_data)):
                svg_parts.append(
                    f'<rect x="{csr_x}" y="{cs_row_y}" width="{_cw}" height="7" '
                    f'fill="{_bg}" stroke="#000" stroke-width="0.6"/>'
                )
                # TAG column: bold for main rows, regular for EGC (share same tag visually)
                _fw = "700" if (_ci == 0 and not _is_egc) else "400"
                _fill = "#555" if _is_egc else "#000"
                svg_parts.append(
                    f'<text x="{csr_x + _cw//2}" y="{cs_row_y + 5}" '
                    f'text-anchor="middle" font-size="5" font-weight="{_fw}" '
                    f'font-family="Arial" fill="{_fill}">{_val}</text>'
                )
                csr_x += _cw
            cs_row_y += 7

        # ── TOP-RIGHT: PHOTOVOLTAIC SYSTEM SUMMARY (x=884..1260, y=47..153) ────
        # In Cubillas PV-4, the PHOTOVOLTAIC SYSTEM: summary box occupies the
        # top-right column alongside NOTES (left) and Conductor Schedule (center).
        # This matches the Cubillas layout exactly.
        pvsys_x, pvsys_y = 884, 47
        pvsys_w, pvsys_h = 376, 106
        svg_parts.append(
            f'<rect x="{pvsys_x}" y="{pvsys_y}" width="{pvsys_w}" height="{pvsys_h}" '
            f'fill="#ffffff" stroke="#000" stroke-width="1.2"/>'
        )
        svg_parts.append(
            f'<rect x="{pvsys_x}" y="{pvsys_y}" width="{pvsys_w}" height="13" '
            f'fill="#e8e8e8" stroke="#000" stroke-width="1"/>'
        )
        svg_parts.append(
            f'<text x="{pvsys_x + pvsys_w//2}" y="{pvsys_y + 9}" '
            f'text-anchor="middle" font-size="8" font-weight="700" '
            f'font-family="Arial" fill="#000">PHOTOVOLTAIC SYSTEM:</text>'
        )
        _pvs_rows = [
            ("DC SYSTEM SIZE:", f"{total_kw:.2f} kW"),
            ("AC SYSTEM SIZE:", f"{inv_kw:.2f} kW"),
            ("MODULE:", f"({total_panels}) {self.panel.name} [{self.panel.wattage}W]"),
            ("", f"WITH INTEGRATED MICROINVERTERS {self.INV_MODEL_SHORT}"),
            ("MONITORING:", "ENPHASE ENVOY (AC GATEWAY)"),
        ]
        _pvs_y = pvsys_y + 23
        for _pvl, _pvv in _pvs_rows:
            if _pvl:
                svg_parts.append(
                    f'<text x="{pvsys_x + 8}" y="{_pvs_y}" '
                    f'font-size="7" font-weight="700" font-family="Arial" fill="#000">{_pvl}</text>'
                )
            svg_parts.append(
                f'<text x="{pvsys_x + 108}" y="{_pvs_y}" '
                f'font-size="7" font-family="Arial" fill="#000">{_pvv}</text>'
            )
            _pvs_y += 14

        # ── Compressed circuit layout (x=28..875, y=55..295) ─────────────
        bus_y = 205
        cx_pv      = 75
        cx_dc_disc = 200
        cx_inv     = 345
        cx_ac_ocpd = 478
        cx_main    = 620
        cx_meter   = 745
        cx_grid    = 855

        # ── Helpers ──────────────────────────────────────────────────────
        def _ground(gx, gy):
            p = [f'<line x1="{gx}" y1="{gy}" x2="{gx}" y2="{gy+13}" stroke="#00aa00" stroke-width="1.5"/>']
            for j in range(3):
                hw = 7 - j*2
                yy = gy + 13 + j*4
                p.append(f'<line x1="{gx-hw}" y1="{yy}" x2="{gx+hw}" y2="{yy}" stroke="#00aa00" stroke-width="1.5"/>')
            return "\n".join(p)

        def _switch(sx, sy, label):
            sw = 25
            p = [
                f'<circle cx="{sx}" cy="{sy}" r="3" fill="#000"/>',
                f'<line x1="{sx}" y1="{sy}" x2="{sx+sw}" y2="{sy-11}" stroke="#000" stroke-width="2"/>',
                f'<circle cx="{sx+sw+2}" cy="{sy}" r="3" fill="none" stroke="#000" stroke-width="1.5"/>',
            ]
            if label:
                p.append(f'<text x="{sx+sw//2}" y="{sy+17}" text-anchor="middle" '
                         f'font-size="7" font-weight="700" font-family="Arial" fill="#000">{label}</text>')
            return "\n".join(p)

        # ── 1. PV ARRAY — per-string circuit detail ───────────────────────
        # Layout: expanded box showing each string as a series chain of
        # panel icons, with a combiner bus bar on the right side for
        # multi-string systems. Output exits at bus_y (horizontal centre).
        max_icons_per_str = 6          # compact panel icons rendered per row
        icon_w  = 10                   # panel icon width  (px)
        icon_h  = 8                    # panel icon height (px)
        icon_gap = 1                   # gap between consecutive icons
        str_row_h = 24                 # total height per string row (label + icons)

        pv_box_x = 28
        pv_box_w = 116
        # Height: 14 (header) + n_branches*(str_row_h+3) + 10 (footer pad)
        pv_box_inner_h = 14 + n_branches * (str_row_h + 3) + 10
        pv_box_h = max(68, pv_box_inner_h)
        pv_box_y = bus_y - pv_box_h // 2

        # Outer box
        svg_parts.append(f'<rect x="{pv_box_x}" y="{pv_box_y}" width="{pv_box_w}" height="{pv_box_h}" '
                         f'fill="#ffffff" stroke="#000" stroke-width="2"/>')
        # Header bar
        svg_parts.append(f'<rect x="{pv_box_x}" y="{pv_box_y}" width="{pv_box_w}" height="14" '
                         f'fill="#e8e8e8" stroke="#000" stroke-width="1"/>')
        svg_parts.append(f'<text x="{pv_box_x + pv_box_w//2}" y="{pv_box_y + 10}" text-anchor="middle" '
                         f'font-size="7.5" font-weight="700" font-family="Arial" fill="#000">PV ARRAY</text>')

        # Sun-ray icon in header (decorative, shows it is a PV source)
        sx0 = pv_box_x + 8
        sy0 = pv_box_y + 7
        for _ang in [0, 45, 90, 135]:
            import math as _m
            dx, dy = _m.cos(_m.radians(_ang))*5, _m.sin(_m.radians(_ang))*5
            svg_parts.append(f'<line x1="{sx0+dx:.0f}" y1="{sy0+dy:.0f}" x2="{sx0+dx*1.9:.0f}" y2="{sy0+dy*1.9:.0f}" '
                             f'stroke="#ffaa00" stroke-width="1"/>')
        svg_parts.append(f'<circle cx="{sx0}" cy="{sy0}" r="2.5" fill="#ffcc00" stroke="none"/>')

        # Per-circuit rows (AC branch circuits for microinverter system)
        str_mid_ys = []          # y-centre of each circuit's icon row (used for wiring)
        collect_x = pv_box_x + pv_box_w - 14   # x of internal collection bar

        for si in range(n_branches):
            str_panels_i = branch_sizes[si]
            row_top = pv_box_y + 16 + si * (str_row_h + 3)
            label_y  = row_top + 9
            icons_y  = row_top + 12          # top of icon row
            mid_y    = icons_y + icon_h // 2 # vertical centre of icon row
            str_mid_ys.append(mid_y)

            show_count = min(max_icons_per_str, str_panels_i)
            icons_start_x = pv_box_x + 6

            # Circuit label (AC branch circuit — not a DC string)
            svg_parts.append(f'<text x="{icons_start_x}" y="{label_y}" '
                             f'font-size="6.5" font-weight="700" font-family="Arial" fill="#333">'
                             f'CIRCUIT-{si+1}  ({str_panels_i} MODULES)</text>')

            # Wire behind icons (AC wire — black/dark)
            wire_end_x = icons_start_x + show_count * (icon_w + icon_gap) + \
                         (10 if str_panels_i > max_icons_per_str else 0)
            svg_parts.append(f'<line x1="{icons_start_x}" y1="{mid_y}" '
                             f'x2="{collect_x}" y2="{mid_y}" '
                             f'stroke="#cc0000" stroke-width="0.8"/>')

            # Panel icons — white fill with black outline (AC module / microinverter style)
            for pi in range(show_count):
                px = icons_start_x + pi * (icon_w + icon_gap)
                svg_parts.append(f'<rect x="{px}" y="{icons_y}" width="{icon_w}" height="{icon_h}" '
                                 f'fill="#fff" stroke="#000" stroke-width="0.8"/>')
                # Horizontal cell divider (light gray)
                svg_parts.append(f'<line x1="{px+1}" y1="{icons_y+icon_h//2}" '
                                 f'x2="{px+icon_w-1}" y2="{icons_y+icon_h//2}" '
                                 f'stroke="#aaa" stroke-width="0.4"/>')
                # Microinverter dot below each panel (shows module-level electronics)
                svg_parts.append(f'<circle cx="{px + icon_w//2}" cy="{icons_y + icon_h + 2}" '
                                 f'r="1.5" fill="#cc0000" stroke="none"/>')

            # Truncation label "+N more" when panels exceed max icons
            if str_panels_i > max_icons_per_str:
                px_extra = icons_start_x + max_icons_per_str * (icon_w + icon_gap)
                svg_parts.append(f'<text x="{px_extra+1}" y="{icons_y + icon_h - 1}" '
                                 f'font-size="5.5" font-weight="700" font-family="Arial" '
                                 f'fill="#555">+{str_panels_i - max_icons_per_str}</text>')

            # AC output marker (no +/− polarity — microinverter outputs are AC)
            svg_parts.append(f'<text x="{wire_end_x - 1}" y="{mid_y + 3}" '
                             f'font-size="7" font-weight="700" font-family="Arial" fill="#cc0000">~</text>')

        # ── Combiner bus / collection bar (right side of PV box) ─────────
        # For all systems: a vertical bar at collect_x collects string outputs.
        # Multi-string: vertical bar is labelled "CB" (DC Combiner Box).
        # Single-string: acts as a simple output terminal.
        bar_top = str_mid_ys[0]
        bar_bot = str_mid_ys[-1]
        svg_parts.append(f'<line x1="{collect_x}" y1="{bar_top}" x2="{collect_x}" y2="{bar_bot}" '
                         f'stroke="#000" stroke-width="1.8"/>')
        # Output stub to box right edge at bus_y
        svg_parts.append(f'<line x1="{collect_x}" y1="{bus_y}" '
                         f'x2="{pv_box_x + pv_box_w}" y2="{bus_y}" '
                         f'stroke="#000" stroke-width="1.8"/>')

        if n_branches > 1:
            # Branch collection bar label — "LC" (load-center input bus)
            cb_label_y = (bar_top + bar_bot) // 2
            svg_parts.append(f'<rect x="{collect_x - 9}" y="{cb_label_y - 8}" width="18" height="16" '
                             f'fill="#fff" stroke="#555" stroke-width="0.8" rx="2"/>')
            svg_parts.append(f'<text x="{collect_x}" y="{cb_label_y + 2}" text-anchor="middle" '
                             f'font-size="6" font-weight="700" font-family="Arial" fill="#cc0000">AC</text>')
            # Small AC node dots where branches join collection bar
            for sy in str_mid_ys:
                svg_parts.append(f'<circle cx="{collect_x}" cy="{sy}" r="2" '
                                 f'fill="#cc0000" stroke="none"/>')

        # System summary below box
        pv_cx_new = pv_box_x + pv_box_w // 2
        svg_parts.append(f'<text x="{pv_cx_new}" y="{pv_box_y + pv_box_h + 9}" text-anchor="middle" '
                         f'font-size="6" font-family="Arial" fill="#333">'
                         f'{total_panels}× {self.panel.wattage}W = {total_kw:.2f} kW DC</text>')

        # ── Supplemental ground rod at PV array (NEC 690.47 / CEC 64-104) ──
        # A supplemental grounding electrode (driven rod) is required adjacent to the
        # PV array and connected via GEC to the system grounding electrode conductor.
        # Symbol is drawn so its bottom aligns with the EGC bus at egc_y (bus_y+82).
        # The EGC bus is extended leftward to connect at this point (see Change 3).
        # Only rendered when there is sufficient vertical space between the PV array
        # box bottom and the EGC bus level (i.e., for typical 1–3 branch systems).
        _gec_rod_y = (bus_y + 82) - 25   # ground symbol occupies y → y+25; bottom = egc_y
        if _gec_rod_y >= pv_box_y + pv_box_h + 10:
            svg_parts.append(_ground(pv_cx_new, _gec_rod_y))
            svg_parts.append(
                f'<text x="{pv_cx_new + 11}" y="{_gec_rod_y + 8}" '
                f'font-size="6" font-weight="700" font-family="Arial" fill="#00aa00">'
                f'SUPP. GND ROD</text>'
            )
            svg_parts.append(
                f'<text x="{pv_cx_new + 11}" y="{_gec_rod_y + 17}" '
                f'font-size="5.5" font-family="Arial" fill="#00aa00">'
                f'GEC \u2014 #6 AWG CU</text>'
            )
            svg_parts.append(
                f'<text x="{pv_cx_new + 11}" y="{_gec_rod_y + 25}" '
                f'font-size="5.5" font-family="Arial" fill="#00aa00">'
                f'[{_cp} {"690.47" if _is_nec else "64-104"}]</text>'
            )

        pv_right_edge = pv_box_x + pv_box_w   # = 144

        # Tag circle 1 (matches Conductor & Conduit Schedule Tag 1: TRUNK CABLE, FREE AIR)
        tag_ax = (pv_right_edge + cx_dc_disc - 13) // 2   # ≈ midpoint
        svg_parts.append(f'<circle cx="{tag_ax}" cy="{bus_y-28}" r="8" fill="#fff" stroke="#000" stroke-width="1"/>')
        svg_parts.append(f'<text x="{tag_ax}" y="{bus_y-24}" text-anchor="middle" font-size="8" font-weight="700" font-family="Arial" fill="#000">1</text>')

        # PV array → junction box (AC output from microinverters — all red/AC)
        svg_parts.append(f'<line x1="{pv_right_edge}" y1="{bus_y}" x2="{cx_dc_disc-15}" y2="{bus_y}" stroke="#cc0000" stroke-width="2.5" marker-end="url(#arr-ac)"/>')
        svg_parts.append(f'<text x="{tag_ax}" y="{bus_y-12}" text-anchor="middle" font-size="6" font-family="Arial" fill="#cc0000">TRUNK CABLE (FREE AIR)</text>')

        # ── 2. AC JUNCTION BOX (branch circuits combine here → PV load center) ──
        # Small box symbol for NEMA 3R junction box
        jb_sz = 22
        jb_x, jb_y = cx_dc_disc - jb_sz//2, bus_y - jb_sz//2
        svg_parts.append(f'<rect x="{jb_x}" y="{jb_y}" width="{jb_sz}" height="{jb_sz}" '
                         f'fill="#fff" stroke="#000" stroke-width="1.5"/>')
        svg_parts.append(f'<text x="{cx_dc_disc}" y="{bus_y - 1}" text-anchor="middle" '
                         f'font-size="5.5" font-weight="700" font-family="Arial" fill="#000">JB</text>')
        svg_parts.append(f'<text x="{cx_dc_disc}" y="{bus_y + 8}" text-anchor="middle" '
                         f'font-size="5" font-family="Arial" fill="#555">NEMA 3R</text>')
        svg_parts.append(f'<text x="{cx_dc_disc}" y="{bus_y+28}" text-anchor="middle" font-size="6" font-family="Arial" fill="#333">JUNC. BOX</text>')

        # Junction box → PV load center  (AC wire)
        svg_parts.append(f'<line x1="{cx_dc_disc + jb_sz//2}" y1="{bus_y}" x2="{cx_inv-33}" y2="{bus_y}" stroke="#cc0000" stroke-width="2.5" marker-end="url(#arr-ac)"/>')

        # ── 3. PV LOAD CENTER (125A — combines AC branch circuits) ────────────
        inv_w, inv_h = 60, 44
        inv_x, inv_y = cx_inv - inv_w//2, bus_y - inv_h//2
        svg_parts.append(f'<rect x="{inv_x}" y="{inv_y}" width="{inv_w}" height="{inv_h}" fill="#f5f5f5" stroke="#000" stroke-width="2"/>')
        # "LC" symbol — two vertical bus bars inside box
        for _bi in range(2):
            _bx = inv_x + 16 + _bi * 22
            svg_parts.append(f'<line x1="{_bx}" y1="{inv_y+6}" x2="{_bx}" y2="{inv_y+inv_h-6}" stroke="#000" stroke-width="2"/>')
            for _ti in range(3):
                _ty = inv_y + 12 + _ti * 8
                svg_parts.append(f'<line x1="{_bx-4}" y1="{_ty}" x2="{_bx+4}" y2="{_ty}" stroke="#000" stroke-width="1"/>')
        svg_parts.append(f'<text x="{cx_inv}" y="{bus_y+inv_h//2+12}" text-anchor="middle" font-size="7" font-weight="700" font-family="Arial" fill="#000">PV LOAD CTR</text>')
        svg_parts.append(f'<text x="{cx_inv}" y="{bus_y+inv_h//2+21}" text-anchor="middle" font-size="6" font-family="Arial" fill="#333">125A / 240V 1φ</text>')
        svg_parts.append(_ground(cx_inv, inv_y + inv_h))

        # Tag circle 2 (matches Conductor & Conduit Schedule Tag 2: J-BOX → PV Load Center)
        tag_2x = (cx_dc_disc + jb_sz//2 + cx_inv - inv_w//2) // 2
        svg_parts.append(f'<circle cx="{tag_2x}" cy="{bus_y-28}" r="8" fill="#fff" stroke="#000" stroke-width="1"/>')
        svg_parts.append(f'<text x="{tag_2x}" y="{bus_y-24}" text-anchor="middle" font-size="8" font-weight="700" font-family="Arial" fill="#000">2</text>')
        svg_parts.append(f'<text x="{tag_2x}" y="{bus_y-12}" text-anchor="middle" font-size="6" font-family="Arial" fill="#cc0000">{sys_ac_wire} {self._wire_type}</text>')

        # Tag circle 3 (matches Conductor & Conduit Schedule Tag 3: Load Center → AC OCPD)
        tag_bx = (cx_inv + inv_w//2 + cx_ac_ocpd - 14) // 2
        svg_parts.append(f'<circle cx="{tag_bx}" cy="{bus_y-26}" r="8" fill="#fff" stroke="#000" stroke-width="1"/>')
        svg_parts.append(f'<text x="{tag_bx}" y="{bus_y-22}" text-anchor="middle" font-size="8" font-weight="700" font-family="Arial" fill="#000">3</text>')

        # Load center → AC OCPD
        svg_parts.append(f'<line x1="{cx_inv+inv_w//2}" y1="{bus_y}" x2="{cx_ac_ocpd-15}" y2="{bus_y}" stroke="#cc0000" stroke-width="2.5" marker-end="url(#arr-ac)"/>')
        svg_parts.append(f'<text x="{tag_bx}" y="{bus_y-11}" text-anchor="middle" font-size="6" font-family="Arial" fill="#cc0000">{sys_ac_wire} {self._wire_type}</text>')

        # ── 4. AC OCPD ───────────────────────────────────────────────────
        osz = 24
        ox, oy = cx_ac_ocpd - osz//2, bus_y - osz//2
        svg_parts.append(f'<rect x="{ox}" y="{oy}" width="{osz}" height="{osz}" fill="#fff" stroke="#000" stroke-width="2"/>')
        svg_parts.append(f'<line x1="{ox}" y1="{oy}" x2="{ox+osz}" y2="{oy+osz}" stroke="#000" stroke-width="1.5"/>')
        svg_parts.append(f'<line x1="{ox+osz}" y1="{oy}" x2="{ox}" y2="{oy+osz}" stroke="#000" stroke-width="1.5"/>')
        svg_parts.append(f'<text x="{cx_ac_ocpd}" y="{bus_y+osz//2+11}" text-anchor="middle" font-size="7" font-weight="700" font-family="Arial" fill="#000">AC OCPD</text>')
        svg_parts.append(f'<text x="{cx_ac_ocpd}" y="{bus_y+osz//2+21}" text-anchor="middle" font-size="6" font-family="Arial" fill="#333">{ac_breaker}A 2P</text>')

        # AC OCPD → main panel
        svg_parts.append(f'<line x1="{cx_ac_ocpd+osz//2}" y1="{bus_y}" x2="{cx_main-33}" y2="{bus_y}" stroke="#cc0000" stroke-width="2.5" marker-end="url(#arr-ac)"/>')

        # ── 5. MAIN PANEL ────────────────────────────────────────────────
        mp_w, mp_h = 58, 66
        mp_x, mp_y = cx_main - mp_w//2, bus_y - mp_h//2
        svg_parts.append(f'<rect x="{mp_x}" y="{mp_y}" width="{mp_w}" height="{mp_h}" fill="#f5f5f5" stroke="#000" stroke-width="2"/>')
        for bi in range(2):
            bx = mp_x + 16 + bi*24
            svg_parts.append(f'<line x1="{bx}" y1="{mp_y+6}" x2="{bx}" y2="{mp_y+mp_h-6}" stroke="#000" stroke-width="2"/>')
            for ti in range(4):
                ty = mp_y + 14 + ti*11
                svg_parts.append(f'<line x1="{bx-5}" y1="{ty}" x2="{bx+5}" y2="{ty}" stroke="#000" stroke-width="1"/>')
        svg_parts.append(f'<text x="{cx_main}" y="{bus_y+mp_h//2+12}" text-anchor="middle" font-size="7" font-weight="700" font-family="Arial" fill="#000">MAIN PANEL</text>')
        svg_parts.append(f'<text x="{cx_main}" y="{bus_y+mp_h//2+21}" text-anchor="middle" font-size="6" font-family="Arial" fill="#333">{main_breaker}A / {bus_rating}A BUS</text>')
        svg_parts.append(_ground(cx_main, mp_y + mp_h))

        # Tag circle 4 (matches Conductor & Conduit Schedule Tag 4: AC OCPD → Main Service Panel)
        tag_4x = (cx_ac_ocpd + osz//2 + cx_main - mp_w//2) // 2
        svg_parts.append(f'<circle cx="{tag_4x}" cy="{bus_y-28}" r="8" fill="#fff" stroke="#000" stroke-width="1"/>')
        svg_parts.append(f'<text x="{tag_4x}" y="{bus_y-24}" text-anchor="middle" font-size="8" font-weight="700" font-family="Arial" fill="#000">4</text>')
        svg_parts.append(f'<text x="{tag_4x}" y="{bus_y-12}" text-anchor="middle" font-size="6" font-family="Arial" fill="#cc0000">{sys_ac_wire} {self._wire_type}</text>')

        # Main panel → meter
        svg_parts.append(f'<line x1="{cx_main+mp_w//2}" y1="{bus_y}" x2="{cx_meter-21}" y2="{bus_y}" stroke="#cc0000" stroke-width="2.5" marker-end="url(#arr-ac)"/>')

        # ── 6. METER ─────────────────────────────────────────────────────
        mr = 19
        svg_parts.append(f'<circle cx="{cx_meter}" cy="{bus_y}" r="{mr}" fill="#fff" stroke="#000" stroke-width="2"/>')
        svg_parts.append(f'<text x="{cx_meter}" y="{bus_y+4}" text-anchor="middle" font-size="8" font-weight="700" font-family="Arial" fill="#000">Wh</text>')
        svg_parts.append(f'<text x="{cx_meter}" y="{bus_y+mr+12}" text-anchor="middle" font-size="7" font-weight="700" font-family="Arial" fill="#000">METER</text>')
        svg_parts.append(f'<text x="{cx_meter}" y="{bus_y+mr+21}" text-anchor="middle" font-size="6" font-family="Arial" fill="#333">BI-DIR.</text>')

        # Tag circle 5 (matches Conductor & Conduit Schedule Tag 5: Main Panel → Utility Meter)
        tag_5x = (cx_main + mp_w//2 + cx_meter - mr) // 2
        svg_parts.append(f'<circle cx="{tag_5x}" cy="{bus_y-28}" r="8" fill="#fff" stroke="#000" stroke-width="1"/>')
        svg_parts.append(f'<text x="{tag_5x}" y="{bus_y-24}" text-anchor="middle" font-size="8" font-weight="700" font-family="Arial" fill="#000">5</text>')
        svg_parts.append(f'<text x="{tag_5x}" y="{bus_y-12}" text-anchor="middle" font-size="6" font-family="Arial" fill="#cc0000">{sys_ac_wire} {self._wire_type}</text>')

        # Meter → grid
        svg_parts.append(f'<line x1="{cx_meter+mr}" y1="{bus_y}" x2="{cx_grid-18}" y2="{bus_y}" stroke="#cc0000" stroke-width="2.5" marker-end="url(#arr-ac)"/>')

        # ── 7. GRID ──────────────────────────────────────────────────────
        gw = 34
        for gi in range(5):
            gwi = gw - gi*5
            gxi = cx_grid - gwi//2
            svg_parts.append(f'<line x1="{gxi}" y1="{bus_y-11+gi*5}" x2="{gxi+gwi}" y2="{bus_y-11+gi*5}" stroke="#000" stroke-width="1.8"/>')
        svg_parts.append(f'<text x="{cx_grid}" y="{bus_y+22}" text-anchor="middle" font-size="7" font-weight="700" font-family="Arial" fill="#000">GRID</text>')
        svg_parts.append(f'<text x="{cx_grid}" y="{bus_y+31}" text-anchor="middle" font-size="6" font-family="Arial" fill="#333">UTILITY 240V 1φ</text>')

        # ── EGC bus ──────────────────────────────────────────────────────
        # Bus extended left to pv_cx_new (= PV array center = 86) so it connects
        # to the supplemental ground rod symbol rendered below the PV array box.
        # This shows that the PV array equipment ground ties into the same EGC
        # that runs to the main panel — matching the Cubillas SLD grounding path.
        egc_y = bus_y + 82
        egc_x_left = pv_cx_new   # = pv_box_x + pv_box_w // 2 = 86
        svg_parts.append(f'<line x1="{egc_x_left}" y1="{egc_y}" x2="{cx_main}" y2="{egc_y}" stroke="#00aa00" stroke-width="1.5" stroke-dasharray="5,3"/>')
        svg_parts.append(f'<text x="{(egc_x_left+cx_main)//2}" y="{egc_y+11}" text-anchor="middle" font-size="6.5" font-family="Arial" fill="#00aa00">EGC — {egc_wire} CU BARE</text>')

        # ── Conductor legend (inline, bottom of circuit area) ─────────────
        lg_x = 30
        lg_y = 266
        svg_parts.append(f'<line x1="{lg_x}" y1="{lg_y}" x2="{lg_x+32}" y2="{lg_y}" stroke="#cc0000" stroke-width="2.5"/>')
        svg_parts.append(f'<text x="{lg_x+37}" y="{lg_y+4}" font-size="6.5" font-family="Arial" fill="#333">AC (MICROINVERTER OUTPUT)</text>')
        svg_parts.append(f'<line x1="{lg_x+185}" y1="{lg_y}" x2="{lg_x+217}" y2="{lg_y}" stroke="#00aa00" stroke-width="1.5" stroke-dasharray="4,2"/>')
        svg_parts.append(f'<text x="{lg_x+222}" y="{lg_y+4}" font-size="6.5" font-family="Arial" fill="#333">EGC</text>')

        # ── RIGHT COLUMN: ELECTRICAL NOTES ──────────────────────────────
        # In Cubillas PV-4, the right column below the PHOTOVOLTAIC SYSTEM
        # summary contains the numbered ELECTRICAL NOTES — not BRANCH CIRCUIT
        # DATA.  Moving notes here matches the Cubillas reference exactly.
        # BRANCH CIRCUIT DATA has moved to the bottom-left (alongside OCPD).
        en_x, en_y, en_w = 884, 158, 376
        _elec_notes_col = [
            f"All conductors shall be copper, 90\u00b0C rated min. [{_cp} {'310.16' if _is_nec else 'Rule 12-100'}]",
            f"PV output conductors: {self._wire_type} or USE-2, sunlight-resistant. [{_cp} {'690.31' if _is_nec else '64-058'}]",
            f"All DC conductors enclosed in conduit unless listed as PV wire. [{_cp} {'690.31' if _is_nec else '12-1010'}]",
            f"Conductors identified at every junction, pull box, termination. [{_cp} {'690.31(G)' if _is_nec else '64-214'}]",
            f"All metallic raceways bonded to grounding electrode system. [{_cp} {'250.96' if _is_nec else 'Rule 10-900'}]",
            f"AC OCPD rated \u2265125% of inverter max continuous output current. [{_cp} {'690.8' if _is_nec else '64-100'}]",
            f"Backfed PV breaker at opposite end of bus from main breaker. [{_cp} {'705.12' if _is_nec else '64-056'}]",
            f"Rapid shutdown: array \u226430 V within 30 s of initiating signal. [{_cp} {'690.12' if _is_nec else '64-218'}]",
            f"Disconnect locations marked with lamacoid labels. [{_cp} {'690.13' if _is_nec else '2-308'}]",
        ]
        _ln_h = 15   # line height per note
        en_h = 16 + len(_elec_notes_col) * _ln_h + 6
        svg_parts.append(f'<rect x="{en_x}" y="{en_y}" width="{en_w}" height="{en_h}" fill="#ffffff" stroke="#000" stroke-width="1.2"/>')
        svg_parts.append(f'<rect x="{en_x}" y="{en_y}" width="{en_w}" height="13" fill="#e8e8e8" stroke="#000" stroke-width="1"/>')
        svg_parts.append(f'<text x="{en_x+8}" y="{en_y+9}" font-size="8" font-weight="700" font-family="Arial" fill="#000">ELECTRICAL NOTES:</text>')
        for _ei, _en in enumerate(_elec_notes_col):
            _eny = en_y + 16 + (_ei + 1) * _ln_h - 3
            svg_parts.append(f'<text x="{en_x+8}" y="{_eny}" font-size="6.5" font-family="Arial" fill="#333">{_ei+1}. {_en}</text>')

        # ═══════════════════════════════════════════════════════════════
        # DIVIDER 1
        # ═══════════════════════════════════════════════════════════════
        div1 = 306
        # Divider stops at x=880 — right column (x=884..1260) holds the
        # ELECTRICAL NOTES box which spans past this y-level without interruption.
        svg_parts.append(f'<line x1="20" y1="{div1}" x2="880" y2="{div1}" stroke="#aaa" stroke-width="0.8" stroke-dasharray="4,4"/>')

        # ═══════════════════════════════════════════════════════════════
        # TABLE 2: PV MODULE ELECTRICAL SPECIFICATIONS  (left half)
        # Moved from right (x=654) to left (x=25) — matching Cubillas PV-4
        # which places module specs bottom-left alongside inverter specs
        # center-right. The PHOTOVOLTAIC SYSTEM summary has moved to the
        # top-right column (alongside NOTES and Conductor Schedule).
        # ═══════════════════════════════════════════════════════════════
        ms_x, ms_y, ms_w = 25, 312, 601
        ms_cw = [ms_w - 160, 160]

        svg_parts.append(f'<rect x="{ms_x}" y="{ms_y}" width="{ms_w}" height="14" fill="#e8e8e8" stroke="#000" stroke-width="1"/>')
        svg_parts.append(f'<text x="{ms_x+ms_w//2}" y="{ms_y+10}" text-anchor="middle" font-size="8" font-weight="700" font-family="Arial" fill="#000">PV MODULE ELECTRICAL SPECIFICATIONS</text>')

        # Header
        mx = ms_x
        for cw, ch in zip(ms_cw, ["PARAMETER", "VALUE"]):
            svg_parts.append(f'<rect x="{mx}" y="{ms_y+14}" width="{cw}" height="13" fill="#f2f2f2" stroke="#000" stroke-width="0.8"/>')
            svg_parts.append(f'<text x="{mx+cw//2}" y="{ms_y+14+9}" text-anchor="middle" font-size="6.5" font-weight="700" font-family="Arial" fill="#000">{ch}</text>')
            mx += cw

        mod_rows = [
            ("Module Model",                  self.panel.name),
            ("Rated Power (Pmax @ STC)",      f"{self.panel.wattage} W"),
            ("Open Circuit Voltage (Voc)",    f"{voc_per_panel:.1f} V"),
            ("Short Circuit Current (Isc)",   f"{isc_per_panel:.1f} A"),
            ("Voltage at Pmax (Vmp)",         f"{vmp_per_panel:.1f} V"),
            ("Current at Pmax (Imp)",         f"{imp_per_panel:.1f} A"),
            ("Module Efficiency",             f"{panel_efficiency} %"),
            ("Temp. Coefficient (Voc)",       f"{temp_coeff_voc*100:.2f} %/°C"),
            ("Max System Voltage",            "1000 V DC"),
            ("Max Series Fuse Rating",        "20 A"),
        ]
        mry = ms_y + 27
        for mi, (param, val) in enumerate(mod_rows):
            bg = "#fff" if mi % 2 == 0 else "#f8f8f8"
            mx = ms_x
            svg_parts.append(f'<rect x="{mx}" y="{mry}" width="{ms_cw[0]}" height="12" fill="{bg}" stroke="#000" stroke-width="0.7"/>')
            svg_parts.append(f'<text x="{mx+5}" y="{mry+9}" font-size="6.5" font-family="Arial" fill="#333">{param}</text>')
            mx += ms_cw[0]
            svg_parts.append(f'<rect x="{mx}" y="{mry}" width="{ms_cw[1]}" height="12" fill="{bg}" stroke="#000" stroke-width="0.7"/>')
            svg_parts.append(f'<text x="{mx+5}" y="{mry+9}" font-size="6.5" font-weight="600" font-family="Arial" fill="#000">{val}</text>')
            mry += 12

        # ═══════════════════════════════════════════════════════════════
        # DIVIDER 2
        # ═══════════════════════════════════════════════════════════════
        div2 = 504
        svg_parts.append(f'<line x1="20" y1="{div2}" x2="1260" y2="{div2}" stroke="#aaa" stroke-width="0.8" stroke-dasharray="4,4"/>')

        # ═══════════════════════════════════════════════════════════════
        # TABLE 3: INVERTER ELECTRICAL SPECIFICATIONS  (right half)
        # Moved from (x=25, y=510) to (x=635, y=312) — now placed alongside
        # MODULE ELECTRICAL SPECS to match Cubillas PV-4 bottom layout:
        # MODULE SPECS (left) | INVERTER SPECS (right) at same vertical level.
        # ═══════════════════════════════════════════════════════════════
        is_x, is_y, is_w = 635, 312, 620
        is_cw = [is_w - 175, 175]

        svg_parts.append(f'<rect x="{is_x}" y="{is_y}" width="{is_w}" height="14" fill="#e8e8e8" stroke="#000" stroke-width="1"/>')
        svg_parts.append(f'<text x="{is_x+is_w//2}" y="{is_y+10}" text-anchor="middle" font-size="8" font-weight="700" font-family="Arial" fill="#000">INVERTER ELECTRICAL SPECIFICATIONS</text>')

        ix = is_x
        for cw, ch in zip(is_cw, ["PARAMETER", "VALUE"]):
            svg_parts.append(f'<rect x="{ix}" y="{is_y+14}" width="{cw}" height="13" fill="#f2f2f2" stroke="#000" stroke-width="0.8"/>')
            svg_parts.append(f'<text x="{ix+cw//2}" y="{is_y+14+9}" text-anchor="middle" font-size="6.5" font-weight="700" font-family="Arial" fill="#000">{ch}</text>')
            ix += cw

        inv_rows_data = [
            ("Inverter Type",                   "Microinverter (Module-Level Power Electronics)"),
            ("Microinverter Model",              self.INV_MODEL_SHORT),
            ("AC Output Power (per unit)",       f"{self.INV_AC_WATTS_PER_UNIT} VA  ({self.INV_AC_AMPS_PER_UNIT:.1f} A @ 240 V)"),
            ("Total System AC Power",            f"{inv_kw:.2f} kW  ({total_panels} units × {self.INV_AC_WATTS_PER_UNIT} VA)"),
            ("AC Output Voltage / Freq.",        "240 V, 1-Phase, 60 Hz"),
            ("Total Continuous AC Current",      f"{total_ac_current:.1f} A"),
            ("DC Input Voltage Range",           "16 – 60 V DC"),
            ("CEC Weighted Efficiency",          "97.0 %"),
            ("Max Units per 15 A Branch",        f"{MAX_PER_BRANCH}"),
            ("Operating Temp. Range",            "−40°C to +65°C"),
        ]
        iry = is_y + 27
        for ii2, (param, val) in enumerate(inv_rows_data):
            bg = "#fff" if ii2 % 2 == 0 else "#f8f8f8"
            ix = is_x
            svg_parts.append(f'<rect x="{ix}" y="{iry}" width="{is_cw[0]}" height="12" fill="{bg}" stroke="#000" stroke-width="0.7"/>')
            svg_parts.append(f'<text x="{ix+5}" y="{iry+9}" font-size="6.5" font-family="Arial" fill="#333">{param}</text>')
            ix += is_cw[0]
            svg_parts.append(f'<rect x="{ix}" y="{iry}" width="{is_cw[1]}" height="12" fill="{bg}" stroke="#000" stroke-width="0.7"/>')
            svg_parts.append(f'<text x="{ix+5}" y="{iry+9}" font-size="6.5" font-weight="600" font-family="Arial" fill="#000">{val}</text>')
            iry += 12

        # ═══════════════════════════════════════════════════════════════
        # BRANCH CIRCUIT DATA — bottom-left (x=25, y=510)
        # Moved from right column; Cubillas has ELECTRICAL NOTES there instead.
        # Side-by-side with OCPD/BUSBAR tables on the right half.
        # ═══════════════════════════════════════════════════════════════
        bcd_x, bcd_y, bcd_w = 25, 510, 601
        _bcd_rows = [
            ("No. of Circuits:", f"{n_branches}", "Modules/Circuit:", f"max {MAX_PER_BRANCH}"),
            ("Branch Breaker:", f"{BRANCH_BREAKER_A}A 2P", "Sys. OCPD:", f"{system_ocpd}A 2P"),
            ("Max Branch Current:", f"{max_branch_current:.1f} A", "Total AC:", f"{total_ac_current:.1f} A"),
            ("Branch Wire:", branch_ac_wire, "System Wire:", sys_ac_wire),
            ("Branch Conduit:", branch_ac_conduit + " EMT", "Sys. Conduit:", sys_ac_conduit + " EMT"),
            ("Inverter (per panel):", self.INV_MODEL_SHORT, "CEC Eff.:", "97.0 %"),
        ]
        bcd_h = 16 + len(_bcd_rows) * 17 + 4
        svg_parts.append(f'<rect x="{bcd_x}" y="{bcd_y}" width="{bcd_w}" height="{bcd_h}" fill="#ffffff" stroke="#000" stroke-width="1.2"/>')
        svg_parts.append(f'<rect x="{bcd_x}" y="{bcd_y}" width="{bcd_w}" height="13" fill="#e8e8e8" stroke="#000" stroke-width="1"/>')
        svg_parts.append(f'<text x="{bcd_x+bcd_w//2}" y="{bcd_y+9}" text-anchor="middle" font-size="8" font-weight="700" font-family="Arial" fill="#000">BRANCH CIRCUIT DATA</text>')
        bcd_dy = bcd_y + 27
        for _bll, _blv, _brl, _brv in _bcd_rows:
            svg_parts.append(f'<text x="{bcd_x+8}" y="{bcd_dy}" font-size="7" font-family="Arial" fill="#555">{_bll}</text>')
            svg_parts.append(f'<text x="{bcd_x+170}" y="{bcd_dy}" font-size="7" font-weight="600" font-family="Arial" fill="#000">{_blv}</text>')
            svg_parts.append(f'<text x="{bcd_x+305}" y="{bcd_dy}" font-size="7" font-family="Arial" fill="#555">{_brl}</text>')
            svg_parts.append(f'<text x="{bcd_x+470}" y="{bcd_dy}" font-size="7" font-weight="600" font-family="Arial" fill="#000">{_brv}</text>')
            bcd_dy += 17

        # ═══════════════════════════════════════════════════════════════
        # TABLE 4: SYSTEM OVER-CURRENT PROTECTION DEVICE (OCPD) CALCULATIONS
        # Cubillas compact format: 3 columns, 1 data row with inline formula
        # Columns: INVERTER TYPE | # OF INVERTERS / MAX CONT. OUTPUT CURRENT | OCPD RATING
        # ═══════════════════════════════════════════════════════════════
        oc_x, oc_y, oc_w = 638, 510, 617
        oc_title_h, oc_hdr_h, oc_row_h = 14, 13, 20
        oc_cw = [230, 200, 187]   # sums to 617
        oc_hdr = ["INVERTER TYPE",
                  "# OF INVERTERS / MAX CONT. OUTPUT CURRENT",
                  "OCPD RATING"]

        # Title bar
        svg_parts.append(
            f'<rect x="{oc_x}" y="{oc_y}" width="{oc_w}" height="{oc_title_h}" '
            f'fill="#e8e8e8" stroke="#000" stroke-width="1"/>'
        )
        svg_parts.append(
            f'<text x="{oc_x + oc_w//2}" y="{oc_y + 10}" text-anchor="middle" '
            f'font-size="7.5" font-weight="700" font-family="Arial" fill="#000">'
            f'SYSTEM OVER-CURRENT PROTECTION DEVICE (OCPD) CALCULATIONS</text>'
        )
        # Column headers
        ox2 = oc_x
        for cw, ch in zip(oc_cw, oc_hdr):
            svg_parts.append(
                f'<rect x="{ox2}" y="{oc_y + oc_title_h}" width="{cw}" height="{oc_hdr_h}" '
                f'fill="#f2f2f2" stroke="#000" stroke-width="0.8"/>'
            )
            svg_parts.append(
                f'<text x="{ox2 + cw//2}" y="{oc_y + oc_title_h + 9}" '
                f'text-anchor="middle" font-size="5.5" font-weight="700" '
                f'font-family="Arial" fill="#000">{ch}</text>'
            )
            ox2 += cw

        # Single data row  — inverter description | count / current | formula + result
        oc_data_y = oc_y + oc_title_h + oc_hdr_h
        inv_type_str  = f"{self.panel.name}  WITH  {self.INV_MODEL_SHORT} MICROINVERTERS [240V]"
        inv_curr_str  = f"{total_panels} / {self.INV_AC_AMPS_PER_UNIT:.1f} A"
        ocpd_calc_str = (
            f"({total_panels} \u00d7 {self.INV_AC_AMPS_PER_UNIT:.1f}A \u00d7 1.25)"
            f" = {total_ac_current * 1.25:.2f}A  \u2264  {system_ocpd}A  OK"
        )
        oc_row_data = [(inv_type_str, oc_cw[0]),
                       (inv_curr_str, oc_cw[1]),
                       (ocpd_calc_str, oc_cw[2])]
        ox2 = oc_x
        for val, cw in oc_row_data:
            svg_parts.append(
                f'<rect x="{ox2}" y="{oc_data_y}" width="{cw}" height="{oc_row_h}" '
                f'fill="#ffffff" stroke="#000" stroke-width="0.7"/>'
            )
            fs = "5.5" if len(val) > 35 else "7"
            svg_parts.append(
                f'<text x="{ox2 + 4}" y="{oc_data_y + 13}" '
                f'font-size="{fs}" font-family="Arial" fill="#000">{val}</text>'
            )
            ox2 += cw

        # ═══════════════════════════════════════════════════════════════
        # BUSBAR CALCULATIONS - PV BREAKER - 120% RULE  (Cubillas standard)
        # Format: 3-column header row (bus / main_disc / pv_breaker) showing
        # ratings, then formula row, then colour-coded calculation + result.
        # Matches Cubillas PV-4 "BUSBAR CALCULATIONS" table exactly.
        # ═══════════════════════════════════════════════════════════════
        bus_gap   = 4
        bus_x     = oc_x
        bus_y_top = oc_data_y + oc_row_h + bus_gap
        bus_w     = oc_w
        bb_cw     = [bus_w // 3, bus_w // 3, bus_w - 2 * (bus_w // 3)]  # 3 equal cols
        bb_hdr    = ["MAIN BUS RATING", "MAIN DISCONNECT RATING", "PV BREAKER RATING"]
        bus_title_h, bus_hdr_h = 14, 13
        bus_val_h, bus_form_h, bus_res_h = 18, 14, 16
        bc_color  = "#00aa00" if rule_120_pass else "#cc0000"

        # Title bar
        svg_parts.append(
            f'<rect x="{bus_x}" y="{bus_y_top}" width="{bus_w}" height="{bus_title_h}" '
            f'fill="#e8e8e8" stroke="#000" stroke-width="1"/>'
        )
        svg_parts.append(
            f'<text x="{bus_x + bus_w//2}" y="{bus_y_top + 10}" text-anchor="middle" '
            f'font-size="7.5" font-weight="700" font-family="Arial" fill="#000">'
            f'BUSBAR CALCULATIONS - PV BREAKER - 120% RULE</text>'
        )
        # Column headers
        bx2 = bus_x
        for cw, ch in zip(bb_cw, bb_hdr):
            svg_parts.append(
                f'<rect x="{bx2}" y="{bus_y_top + bus_title_h}" width="{cw}" '
                f'height="{bus_hdr_h}" fill="#f2f2f2" stroke="#000" stroke-width="0.8"/>'
            )
            svg_parts.append(
                f'<text x="{bx2 + cw//2}" y="{bus_y_top + bus_title_h + 9}" '
                f'text-anchor="middle" font-size="6.5" font-weight="700" '
                f'font-family="Arial" fill="#000">{ch}</text>'
            )
            bx2 += cw

        # Values row: bus rating | main disconnect | PV breaker
        bv_y = bus_y_top + bus_title_h + bus_hdr_h
        bx2  = bus_x
        for val, cw in zip([f"{bus_rating}", f"{main_breaker}", f"{system_ocpd}A 2P"],
                            bb_cw):
            svg_parts.append(
                f'<rect x="{bx2}" y="{bv_y}" width="{cw}" height="{bus_val_h}" '
                f'fill="#ffffff" stroke="#000" stroke-width="0.7"/>'
            )
            svg_parts.append(
                f'<text x="{bx2 + cw//2}" y="{bv_y + 13}" text-anchor="middle" '
                f'font-size="10" font-weight="700" font-family="Arial" fill="#000">{val}</text>'
            )
            bx2 += cw

        # Formula row — spans full width (grey background)
        form_y      = bv_y + bus_val_h
        formula_str = (
            "(MAIN BUS RATING \u00d7 1.2) \u2212 MAIN DISCONNECT RATING"
            " \u2265 OCPD RATING"
        )
        svg_parts.append(
            f'<rect x="{bus_x}" y="{form_y}" width="{bus_w}" height="{bus_form_h}" '
            f'fill="#f8f8f8" stroke="#000" stroke-width="0.7"/>'
        )
        svg_parts.append(
            f'<text x="{bus_x + bus_w//2}" y="{form_y + 10}" text-anchor="middle" '
            f'font-size="6.5" font-style="italic" font-family="Arial" fill="#444">'
            f'{formula_str}</text>'
        )

        # Calculation + PASS/FAIL row — colour-coded
        headroom = rule_120_lim - main_breaker   # e.g. 270 − 200 = 70
        calc_str = (
            f"({bus_rating}A \u00d7 1.2) \u2212 {main_breaker}A"
            f" = {rule_120_lim}A \u2212 {main_breaker}A"
            f" = {headroom}A \u2265 {system_ocpd}A"
        )
        pass_str = "  \u2714 OK" if rule_120_pass else "  \u2718 FAIL \u2014 UPGRADE PANEL OR REDUCE INVERTER"
        res_y  = form_y + bus_form_h
        res_bg = "#ddf0dd" if rule_120_pass else "#ffdede"
        svg_parts.append(
            f'<rect x="{bus_x}" y="{res_y}" width="{bus_w}" height="{bus_res_h}" '
            f'fill="{res_bg}" stroke="{bc_color}" stroke-width="1"/>'
        )
        svg_parts.append(
            f'<text x="{bus_x + bus_w//2}" y="{res_y + 11}" text-anchor="middle" '
            f'font-size="7" font-weight="700" font-family="Arial" fill="{bc_color}">'
            f'{calc_str}{pass_str}</text>'
        )

        # (ELECTRICAL NOTES moved to right column — see en_x/en_y block above)
        # (DIVIDER 3 removed — bottom zone freed now that notes are in right column)

        # Supplemental ground rod specification text block (matches Cubillas PV-4)
        # Positioned bottom-left, to the left of the rapid shutdown callout.
        # Supplemental electrode adjacent to the array (NEC 690.47 / CEC 64-104).
        gr_x, gr_y, gr_w, gr_h = 640, 790, 310, 32
        _grd_ref = f"{_cp} {'250.68(C)(1)' if _is_nec else '64-104'}"
        grd_lines = [
            "**SUPPLEMENTAL GROUND ROD SHALL BE 10' LONG \u00d7 5/8\" IN DIAMETER.",
            f"ROD IS TO BE EMBEDDED A MIN 8\" INTO DIRECT SOIL [{_cp} {'250.53(D)' if _is_nec else '10-706(3)'}],",
            "MIN 5 FT APART. CONNECTION TO INTERIOR METAL WATER PIPING",
            f"SHALL BE WITHIN 5 FT OF ENTRY POINT. [{_grd_ref}]",
        ]
        svg_parts.append(f'<rect x="{gr_x}" y="{gr_y}" width="{gr_w}" height="{gr_h}" '
                         f'fill="#ffffff" stroke="#000" stroke-width="0.8"/>')
        for gi, gl in enumerate(grd_lines):
            # Strip leading ** bold marker for SVG text (no SVG bold spans here)
            gl_clean = gl.lstrip('*')
            fw = "700" if gl.startswith("**") else "400"
            svg_parts.append(
                f'<text x="{gr_x+4}" y="{gr_y + 8 + gi*7}" '
                f'font-size="5.5" font-weight="{fw}" font-family="Arial" fill="#000">{gl_clean}</text>'
            )

        # Rapid shutdown callout box
        rs_x2 = 960
        rs_y2 = 790
        svg_parts.append(f'<rect x="{rs_x2}" y="{rs_y2}" width="290" height="32" fill="#fff5f5" stroke="#cc0000" stroke-width="1" rx="2"/>')
        svg_parts.append(f'<text x="{rs_x2+10}" y="{rs_y2+13}" font-size="7.5" font-weight="700" font-family="Arial" fill="#cc0000">\u26a1 RAPID SHUTDOWN ({_cp} {"690.12" if _is_nec else "64-218"})</text>')
        svg_parts.append(f'<text x="{rs_x2+10}" y="{rs_y2+26}" font-size="7" font-family="Arial" fill="#333">Array ≤30 V within 30 s of initiating signal.</text>')

        # ── Title block ──────────────────────────────────────────────────
        svg_parts.append(self._svg_title_block(
            1280, 960, "PV-4", "Single-Line Diagram",
            f"{total_kw:.2f} kW DC / {inv_kw:.2f} kW AC",
            "5 of 13", address, today
        ))

        svg_content = "\n".join(svg_parts)
        return f'<div class="page"><svg width="100%" height="100%" viewBox="0 0 1280 960" xmlns="http://www.w3.org/2000/svg" style="background:#fff;">{svg_content}</svg></div>'

    def _build_electrical_calcs_page(self, total_panels: int, total_kw: float,
                                    address: str, today: str) -> str:
        """PV-4.1: Electrical calculation worksheet (jurisdiction-aware).

        Microinverter system: each panel drives its own inverter.
        DC circuit = one panel → one microinverter (no series strings).
        AC circuit = branch of N microinverters sharing a breaker.

        Wire sizing: DC conductor ×1.56 (Isc), AC continuous ×1.25.
        Code references and design temperatures come from the jurisdiction engine.
        """
        VW, VH = 1280, 960
        svg: list = []

        # Jurisdiction-aware code references
        _cp = self._code_prefix
        _is_nec = (_cp == "NEC")

        # ── Module specs — from ProjectSpec/catalog ─────────────────────────
        voc_stc        = self._panel_voc
        vmp_stc        = self._panel_vmp
        isc_stc        = self._panel_isc
        imp_stc        = self._panel_imp
        pmax_stc       = self._panel_wattage
        temp_coeff_voc = self._panel_temp_coeff_voc
        temp_coeff_isc = self._panel_temp_coeff_isc

        # ── Inverter specs — from ProjectSpec/catalog ───────────────────────
        inv_ac_amps_per_unit = self.INV_AC_AMPS_PER_UNIT
        inv_ac_voltage       = self._project.inverter.ac_voltage_v if self._project else 240
        max_per_branch       = self._max_per_branch
        inv_output_va        = self.INV_AC_WATTS_PER_UNIT

        # ── Design temperatures (from jurisdiction engine) ─────────────────
        _temps = self._design_temps
        t_cold_c   = float(_temps.get("cold_c", -25))
        t_stc_c    = float(_temps.get("stc_c", 25))
        t_hot_c    = float(_temps.get("hot_module_c", 70))

        # ── DC circuit calculations (per panel) ──────────────────────────────
        # Temperature-corrected open-circuit voltage (worst-case = coldest morning)
        voc_cold = voc_stc * (1.0 + temp_coeff_voc * (t_cold_c - t_stc_c))
        # Temperature-corrected Isc (hot roof, for wire ampacity check)
        isc_hot  = isc_stc * (1.0 + temp_coeff_isc * (t_hot_c  - t_stc_c))
        # DC conductor minimum ampacity: NEC 690.8 / CEC 14-100 → 1.56 × Isc
        dc_min_amps = isc_stc * 1.56
        # Select conductor gauge
        def _wire_gauge(amps):
            if amps <= 15: return "#14 AWG"
            if amps <= 20: return "#12 AWG"
            if amps <= 30: return "#10 AWG"
            if amps <= 40: return "#8 AWG"
            if amps <= 55: return "#6 AWG"
            if amps <= 70: return "#4 AWG"
            return "#2 AWG"
        dc_wire = _wire_gauge(dc_min_amps)
        dc_ocpd = math.ceil(isc_stc * 1.56 / 5) * 5  # round up to nearest 5 A fuse

        # ── AC branch circuit calculations ────────────────────────────────────
        # Assign panels to branch circuits (sequential, ≤ max_per_branch each)
        n = max(total_panels, 1)
        if n <= max_per_branch:
            branch_sizes = [n]
        else:
            nb = math.ceil(n / max_per_branch)
            base_sz = n // nb
            rem     = n % nb
            branch_sizes = [base_sz + (1 if i < rem else 0) for i in range(nb)]
        # Note: with max_per_branch=7, systems of 1–7 panels naturally produce
        # 1 branch, and 8+ panels produce 2+ branches — consistent with PV-4 and PV-7.
        n_branches = len(branch_sizes)

        # AC continuous current per branch
        branch_ac_amps = [sz * inv_ac_amps_per_unit for sz in branch_sizes]
        # Wire sizing: NEC 690.8 / CEC 4-004 — continuous load × 1.25
        branch_wire_amps = [a * 1.25 for a in branch_ac_amps]
        branch_wire = [_wire_gauge(a) for a in branch_wire_amps]
        branch_ocpd = [math.ceil(a / 5) * 5 for a in branch_wire_amps]

        # Total system AC current
        total_ac_amps = n * inv_ac_amps_per_unit
        total_ac_wire_amps = total_ac_amps * 1.25
        total_ac_wire = _wire_gauge(total_ac_wire_amps)
        total_ac_ocpd = math.ceil(total_ac_wire_amps / 5) * 5

        # 120 % rule (NEC 705.12 / CEC 64-056)
        # 200A residential panels have a 225A rated bus bar (matches Cubillas PV-4).
        main_breaker = self._main_breaker_a
        bus_rating   = self._bus_rating_a
        rule_120_lim = int(bus_rating * 1.2)
        rule_120_pass = (total_ac_ocpd + main_breaker) <= rule_120_lim

        # ── SVG canvas ────────────────────────────────────────────────────────
        svg.append(f'<rect width="{VW}" height="{VH}" fill="#ffffff"/>')
        svg.append(f'<rect x="20" y="20" width="{VW-40}" height="{VH-40}" fill="none" stroke="#000" stroke-width="2"/>')

        # ── Page title strip ──────────────────────────────────────────────────
        svg.append(f'<rect x="20" y="20" width="{VW-40}" height="26" fill="#e8e8e8" stroke="#000" stroke-width="1"/>')
        svg.append(f'<text x="{VW//2}" y="38" text-anchor="middle" font-size="13" font-weight="700" '
                   f'font-family="Arial" fill="#000">PV-4.1 — ELECTRICAL CALCULATIONS</text>')

        # ── Helper to draw a titled table ─────────────────────────────────────
        def _table(x, y, title, headers_list, rows, col_widths, row_h=22, hdr_fill="#e8e8e8"):
            """Draw a titled table. Returns next y after the table."""
            parts = []
            # Section title
            parts.append(f'<rect x="{x}" y="{y}" width="{sum(col_widths)}" height="18" '
                         f'fill="#444" stroke="#000" stroke-width="1"/>')
            parts.append(f'<text x="{x + sum(col_widths)//2}" y="{y + 13}" text-anchor="middle" '
                         f'font-size="9" font-weight="700" font-family="Arial" fill="#fff">{title}</text>')
            y += 18
            # Column headers
            cx = x
            for i, hdr in enumerate(headers_list):
                parts.append(f'<rect x="{cx}" y="{y}" width="{col_widths[i]}" height="{row_h}" '
                             f'fill="{hdr_fill}" stroke="#000" stroke-width="0.8"/>')
                parts.append(f'<text x="{cx + col_widths[i]//2}" y="{y + row_h - 7}" text-anchor="middle" '
                             f'font-size="8" font-weight="700" font-family="Arial" fill="#000">{hdr}</text>')
                cx += col_widths[i]
            y += row_h
            # Data rows
            for ri, row in enumerate(rows):
                bg = "#f9f9f9" if ri % 2 == 0 else "#ffffff"
                cx = x
                highlight = row[0].startswith("★")
                row_fill  = "#fffbe6" if highlight else bg
                for i, cell in enumerate(row):
                    cell_text = cell.lstrip("★")
                    parts.append(f'<rect x="{cx}" y="{y}" width="{col_widths[i]}" height="{row_h}" '
                                 f'fill="{row_fill}" stroke="#ccc" stroke-width="0.5"/>')
                    weight = "700" if highlight else "400"
                    parts.append(f'<text x="{cx + 4}" y="{y + row_h - 7}" '
                                 f'font-size="8" font-weight="{weight}" font-family="Arial" fill="#000">{cell_text}</text>')
                    cx += col_widths[i]
                y += row_h
            return "".join(parts), y

        # ══════════════════════════════════════════════════════════════════════
        # LEFT COLUMN (x=30 … 640)
        # ══════════════════════════════════════════════════════════════════════
        lx, ly = 30, 54

        # ── 1. System Overview ────────────────────────────────────────────────
        overview_rows = [
            ("System Type",          "Microinverter (no DC series strings)"),
            ("Module",               f"{self._panel_model_full}   {pmax_stc} W"),
            ("Microinverter" if (self._project and self._project.inverter.is_micro) or not self._project else "Inverter",
                                     f"{self.INV_MODEL_SHORT}  [{self._project.inverter.ac_voltage_v if self._project else 240} V / 1φ]"),
            ("# Modules",            f"{total_panels}"),
            ("DC System Size",       f"{total_kw:.2f} kW DC"),
            ("AC System Size",       f"{self._calc_ac_kw(total_panels):.2f} kW AC"),
        ]
        tbl_svg, ly = _table(lx, ly, "SYSTEM OVERVIEW", ["Parameter", "Value"],
                             overview_rows, [210, 390], row_h=22)
        svg.append(tbl_svg)
        ly += 8

        # ── 2. Module DC Electrical Specs (STC) ─────────────────────────────
        dc_rows = [
            ("Rated Power (Pmax @ STC)",           f"{pmax_stc} W"),
            ("Open-Circuit Voltage  Voc @ STC",    f"{voc_stc:.1f} V"),
            ("Voltage at Pmax       Vmp @ STC",    f"{vmp_stc:.1f} V"),
            ("Short-Circuit Current Isc @ STC",    f"{isc_stc:.1f} A"),
            ("Current at Pmax       Imp @ STC",    f"{imp_stc:.1f} A"),
            ("Temp. Coeff. Voc",                   f"{temp_coeff_voc*100:+.2f} %/°C"),
            ("Temp. Coeff. Isc",                   f"{temp_coeff_isc*100:+.3f} %/°C"),
        ]
        tbl_svg, ly = _table(lx, ly, "MODULE ELECTRICAL SPECIFICATIONS @ STC",
                             ["Parameter", "Value"], dc_rows, [310, 290], row_h=21)
        svg.append(tbl_svg)
        ly += 8

        # ── 3. DC Temperature Corrections ───────────────────────────────────
        _city = self._project.municipality if self._project else ""
        _temp_label = f"{_city} design temp (ASHRAE 2 %)" if _city else "Design temp (ASHRAE 2 %)"
        temp_rows = [
            (_temp_label,                             f"{t_cold_c:.0f} °C"),
            ("\u0394T below STC",                          f"{t_cold_c - t_stc_c:.0f} °C"),
            ("Voc correction factor",                 f"1 + ({temp_coeff_voc*100:+.2f}%/°C \u00d7 {t_cold_c-t_stc_c:.0f}\u00b0C) = "
                                                      f"{1 + temp_coeff_voc*(t_cold_c - t_stc_c):.4f}"),
            (f"\u2605Voc @ {t_cold_c:.0f} \u00b0C  (design Voc)",           f"{voc_cold:.1f} V  (<600 V {_cp} limit \u2713)"),
            ("Hot-roof temp (summer)",                f"{t_hot_c:.0f} \u00b0C"),
            (f"\u2605Isc @ +{t_hot_c:.0f} \u00b0C  (hot-roof)",             f"{isc_hot:.2f} A  (used for ampacity check)"),
        ]
        _dc_temp_rule = f"{_cp} {'690.8 / NEC Table 690.7' if _is_nec else 'Rule 14-100 / Annex D'}"
        tbl_svg, ly = _table(lx, ly, f"DC TEMPERATURE CORRECTIONS  [{_dc_temp_rule}]",
                             ["Parameter", "Value"], temp_rows, [250, 350], row_h=21)
        svg.append(tbl_svg)
        ly += 8

        # ── 4. DC Wire Sizing (per panel) ────────────────────────────────────
        _dc_sizing_rule = f"{_cp} {'690.8' if _is_nec else 'Rule 14-100'}"
        dc_wire_rows = [
            ("Isc @ STC",                         f"{isc_stc:.1f} A"),
            (f"{_dc_sizing_rule} factor",         "\u00d71.56"),
            (f"\u2605Min. DC conductor ampacity",        f"{dc_min_amps:.1f} A  \u2192 {dc_wire} {self._wire_type}  \u2713"),
            ("DC OCPD (fuse)",                    f"{dc_ocpd} A"),
            ("Conduit / raceway",                 "EMT  (exterior)" ),
        ]
        tbl_svg, ly = _table(lx, ly, f"DC CONDUCTOR SIZING \u2014 PER PANEL  [{_dc_sizing_rule}]",
                             ["Parameter", "Value"], dc_wire_rows, [250, 350], row_h=21)
        svg.append(tbl_svg)
        ly += 8

        # ── 5. String Configuration ───────────────────────────────────────────
        if self._project:
            try:
                _str_cfg = calculate_string_config(
                    self._project.panel, self._project.inverter, total_panels)
            except Exception:
                _str_cfg = None
        else:
            _str_cfg = None

        if _str_cfg and _str_cfg.get('type') == 'microinverter':
            _br_a = _str_cfg.get('branch_current_a', 0.0)
            _br_wire = _wire_gauge(_br_a)
            str_rows = [
                ("Configuration",          f"{_str_cfg['num_branches']} \u00d7 1-module branch circuits"),
                ("Branch circuit current",  f"1.25 \u00d7 Isc = {_br_a:.2f} A  \u2192  {_br_wire} {self._wire_type}"),
                ("System voltage (Voc)",   f"{_str_cfg.get('system_voltage_v', 0):.1f} V"),
            ]
            _str_rule = f"{_cp} {'690.8' if _is_nec else 'Rule 14-100'}"
            tbl_svg, ly = _table(lx, ly, f"STRING CONFIGURATION  [{_str_rule}]",
                                 ["Parameter", "Value"], str_rows, [250, 350], row_h=21)
            svg.append(tbl_svg)
        elif _str_cfg and _str_cfg.get('type') == 'string':
            str_rows = [
                ("Panels per string",       f"{_str_cfg.get('string_length', 0)}"),
                ("Number of strings",       f"{_str_cfg.get('num_strings', 0)}"),
                ("String Voc",             f"{_str_cfg.get('string_voc_v', 0):.1f} V"),
                ("String Vmp",             f"{_str_cfg.get('string_vmp_v', 0):.1f} V"),
            ]
            tbl_svg, ly = _table(lx, ly, "STRING CONFIGURATION",
                                 ["Parameter", "Value"], str_rows, [250, 350], row_h=21)
            svg.append(tbl_svg)

        # ══════════════════════════════════════════════════════════════════════
        # RIGHT COLUMN (x=650 … 1240)
        # ══════════════════════════════════════════════════════════════════════
        rx, ry = 655, 54

        # ── 5. AC Branch Circuit Table ───────────────────────────────────────
        branch_hdr = ["Branch", "Modules", "AC Current (A)", "×1.25 (A)", "Wire", "OCPD"]
        branch_rows = []
        for bi, (sz, ia, iw, wg, oc) in enumerate(
                zip(branch_sizes, branch_ac_amps, branch_wire_amps, branch_wire, branch_ocpd)):
            branch_rows.append([
                f"Branch {bi+1}",
                f"{sz}",
                f"{ia:.1f}",
                f"{iw:.1f}",
                wg,
                f"{oc} A  2P",
            ])
        # Totals row
        branch_rows.append([
            "★TOTAL",
            f"{n}",
            f"{total_ac_amps:.1f}",
            f"{total_ac_wire_amps:.1f}",
            total_ac_wire,
            f"{total_ac_ocpd} A  2P",
        ])
        _ac_rule = f"{_cp} {'210.20 / 705.12' if _is_nec else 'Rule 4-004 / Rule 64-056'}"
        tbl_svg, ry = _table(rx, ry,
                             f"AC BRANCH CIRCUIT CALCULATIONS  [{_ac_rule}]",
                             branch_hdr, branch_rows, [75, 60, 105, 80, 80, 85+15], row_h=22)
        svg.append(tbl_svg)
        ry += 8

        # ── 6. 120 % Rule ─────────────────────────────────────────────────────
        pass_fail_color = "#008800" if rule_120_pass else "#cc0000"
        pass_fail_text  = "PASS ✓" if rule_120_pass else "FAIL ✗"
        rule_rows = [
            ("Main bus rating",               f"{bus_rating} A"),
            ("120 % of bus",                  f"{rule_120_lim} A"),
            ("Main breaker (existing)",        f"{main_breaker} A"),
            ("PV backfed OCPD",               f"{total_ac_ocpd} A"),
            ("Sum (main + PV OCPD)",           f"{main_breaker + total_ac_ocpd} A"),
            (f"★{pass_fail_text}  ({main_breaker + total_ac_ocpd} ≤ {rule_120_lim})",
             f"{main_breaker + total_ac_ocpd} ≤ {rule_120_lim}  {pass_fail_text}"),
        ]
        _120_rule = f"{_cp} {'705.12' if _is_nec else 'Rule 64-056'}"
        tbl_svg, ry = _table(rx, ry,
                             f"BUSBAR CALCULATIONS \u2014 120 % RULE  [{_120_rule}]",
                             ["Parameter", "Value"], rule_rows, [300, 245], row_h=22)
        svg.append(tbl_svg)
        ry += 8

        # ── 7. Microinverter AC Specs ─────────────────────────────────────────
        inv_rows = [
            ("Model",                          self.INV_MODEL_SHORT),
            ("Output voltage",                 f"{inv_ac_voltage} V  1φ"),
            ("Max continuous output current",  f"{inv_ac_amps_per_unit:.1f} A"),
            ("Max output apparent power",      f"{inv_output_va} VA"),
            ("Max modules per branch circuit", f"{max_per_branch}  (for 15 A 2P OCPD)"),
            ("DC input voltage range",         "16–60 V  (per panel)"),
        ]
        tbl_svg, ry = _table(rx, ry,
                             "MICROINVERTER AC ELECTRICAL SPECIFICATIONS",
                             ["Parameter", "Value"], inv_rows, [295, 250], row_h=22)
        svg.append(tbl_svg)
        ry += 8

        # ── 8. Applicable Codes ──────────────────────────────────────────────
        _utility_info = self._utility_info
        _utility_nm_kw = _utility_info.get("net_metering_max_kw", 50)
        if _is_nec:
            code_rows = [
                ("NEC 705.12",       "Interconnection of PV systems"),
                ("NEC 690.8",        "DC conductor ampacity (\u00d71.56 factor)"),
                ("NEC 210.20",       "AC continuous load sizing (\u00d71.25 factor)"),
                ("NEC 690.31",       "PV output circuit conductors"),
                ("NEC 2020 / CEC",   self._code_edition),
                ("IEC 62109",        "Safety of power converters for PV systems"),
                (self._utility_name, f"Net metering \u2264 {_utility_nm_kw} kW \u2014 single-phase"),
            ]
        else:
            code_rows = [
                ("CEC Rule 64-056",  "Interconnection of PV systems"),
                ("CEC Rule 14-100",  "DC conductor ampacity (\u00d71.56 factor)"),
                ("CEC Rule 4-004",   "AC continuous load sizing (\u00d71.25 factor)"),
                ("CEC Rule 64-050",  "PV output circuit conductors"),
                ("CSA C22.1-2021",   "Canadian Electrical Code, Part I"),
                ("IEC 62109",        "Safety of power converters for PV systems"),
                (self._utility_name, f"Net metering \u2264 {_utility_nm_kw} kW \u2014 single-phase"),
            ]
        tbl_svg, ry = _table(rx, ry,
                             "APPLICABLE CODES & STANDARDS",
                             ["Code / Rule", "Description"], code_rows, [145, 400], row_h=21)
        svg.append(tbl_svg)
        ry += 8

        # ── 9. Formula notes strip (bottom, full width) ──────────────────────
        notes_y = max(ly, ry) + 10
        _dc_rule_label = f"{_cp} {'690.8' if _is_nec else 'Rule 14-100'}"
        _ac_rule_label = f"{_cp} {'210.20' if _is_nec else 'Rule 4-004'}"
        note_lines = [
            "FORMULAS:   "
            "Voc_cold = Voc_STC \u00d7 [1 + \u03b1_Voc \u00d7 (T_design \u2212 25)]     "
            f"where \u03b1_Voc = \u22120.24 %/\u00b0C,  T_design = {t_cold_c:.0f} \u00b0C ({_city or 'local'} ASHRAE 2 % heating)     "
            f"DC ampacity = Isc \u00d7 1.56  [{_dc_rule_label}]     "
            f"AC ampacity = I_branch_total \u00d7 1.25  [{_ac_rule_label} continuous load]",
        ]
        svg.append(f'<rect x="30" y="{notes_y}" width="{VW-60}" height="22" '
                   f'fill="#f4f4f4" stroke="#aaa" stroke-width="0.8"/>')
        svg.append(f'<text x="36" y="{notes_y + 14}" font-size="7.5" '
                   f'font-family="Arial" fill="#333">{note_lines[0]}</text>')

        # ── Title block ───────────────────────────────────────────────────────
        svg.append(self._svg_title_block(
            VW, VH, "PV-4.1", "Electrical Calculations",
            self._code_edition, "6 of 13",
            address, today
        ))

        svg_content = "\n".join(svg)
        return (f'<div class="page"><svg width="100%" height="100%" '
                f'viewBox="0 0 {VW} {VH}" xmlns="http://www.w3.org/2000/svg" '
                f'style="background:#fff;">{svg_content}</svg></div>')

    def _build_signage_page(self, address: str, today: str) -> str:
        """PV-6: Required warning labels and placards — 14 items, ANSI Z535."""
        VW, VH = 1280, 960
        svg_parts = []

        # Background & border
        svg_parts.append(f'<rect width="{VW}" height="{VH}" fill="#ffffff"/>')
        svg_parts.append(f'<rect x="20" y="20" width="{VW-40}" height="{VH-40}" '
                         f'fill="none" stroke="#000" stroke-width="1.5"/>')

        # Page header
        svg_parts.append('<text x="40" y="52" font-size="15" font-weight="700" '
                         'font-family="Arial" fill="#000">PV-6: ELECTRICAL LABELS</text>')
        _cp = self._code_prefix
        _is_nec = (_cp == "NEC")
        _code_ref = f"{'NEC 690 / California Electrical Code' if _is_nec else 'CEC Section 64 (CSA C22.1-21)'}"
        svg_parts.append(f'<text x="40" y="68" font-size="9" font-family="Arial" fill="#555">'
                         f'Required warning labels per {_code_ref}, ANSI Z535.4 — '
                         f'install at indicated locations prior to utility energization</text>')
        svg_parts.append('<line x1="30" y1="76" x2="1250" y2="76" stroke="#ccc" stroke-width="0.7"/>')

        # ── ANSI Z535 colour constants ─────────────────────────────────
        ANSI_RED    = "#C62828"   # DANGER
        ANSI_ORANGE = "#E65100"   # WARNING
        ANSI_YELLOW = "#F9A825"   # CAUTION
        ANSI_BLUE   = "#1565C0"   # INFO / directive
        WHITE = "#FFFFFF"
        BLACK = "#000000"

        # ── 14 label definitions ───────────────────────────────────────
        # (label_num, level, header_color, text_color, title, [lines], code_ref, location)
        _un = self._utility_name
        _safety_listing = f"{'UL 1741 LISTED' if _is_nec else 'CSA C22.2 No. 107.1 LISTED'}"
        def _lr(nec_ref, cec_ref):
            """Return the appropriate label code ref for the jurisdiction."""
            return f"NEC {nec_ref}" if _is_nec else f"CEC Rule {cec_ref}"

        labels = [
            # DANGER x 2
            ("L-01", "DANGER",  ANSI_RED,    WHITE,
             "ELECTRIC SHOCK HAZARD",
             ["TERMINALS ON BOTH LINE AND LOAD",
              "SIDES MAY BE ENERGIZED IN THE",
              "OPEN POSITION \u2014 DO NOT TOUCH."],
             _lr("690.17", "64-218"),
             "On or adjacent to each DC disconnect"),

            ("L-02", "DANGER",  ANSI_RED,    WHITE,
             "HIGH DC VOLTAGE \u2014 DO NOT TOUCH",
             ["SOLAR PANELS PRODUCE LETHAL",
              "VOLTAGE WHEN EXPOSED TO LIGHT.",
              "RISK OF FATAL ELECTRICAL SHOCK."],
             _lr("690.5", "64-218"),
             "Roof surface near array / array combiner box"),

            # WARNING x 5
            ("L-03", "WARNING", ANSI_ORANGE, WHITE,
             "DUAL POWER SOURCES",
             ["THIS EQUIPMENT IS FED FROM TWO",
              "SEPARATE SOURCES \u2014 DISCONNECT",
              "BOTH BEFORE SERVICING."],
             _lr("705.12", "64-218"),
             "Main electrical panel exterior"),

            ("L-04", "WARNING", ANSI_ORANGE, WHITE,
             "BACKFED CIRCUIT \u2014 DO NOT RELOCATE",
             ["PHOTOVOLTAIC SYSTEM BACKFED",
              "BREAKER MUST REMAIN AT THIS",
              "LOCATION IN THE LOAD CENTER."],
             _lr("705.12(B)(4)", "64-218"),
             "Adjacent to PV backfed breaker in load center"),

            ("L-05", "WARNING", ANSI_ORANGE, WHITE,
             "RAPID SHUTDOWN EQUIPPED",
             ["PHOTOVOLTAIC SYSTEM EQUIPPED",
              "WITH RAPID SHUTDOWN \u2014 PRESS",
              "SWITCH TO DE-ENERGIZE ARRAY."],
             _lr("690.12", "64-218"),
             "Service entrance / main panel exterior"),

            ("L-06", "WARNING", ANSI_ORANGE, WHITE,
             "INVERTER OUTPUT \u2014 SHOCK RISK",
             ["INVERTER OUTPUT REMAINS ENERGIZED",
              "AFTER AC DISCONNECT IS OPENED.",
              "WAIT 5 MINUTES BEFORE SERVICING."],
             _lr("690.13", "64-218"),
             "On inverter housing / enclosure"),

            ("L-07", "WARNING", ANSI_ORANGE, WHITE,
             "RAPID SHUTDOWN SWITCH",
             ["SOLAR PHOTOVOLTAIC SYSTEM \u2014",
              "PRESS TO DE-ENERGIZE ROOF",
              "CONDUCTORS WITHIN 30 SECONDS."],
             _lr("690.12(B)(1)", "64-218"),
             "At rapid shutdown initiator / RSM switch"),

            # CAUTION x 4
            ("L-08", "CAUTION", ANSI_YELLOW, BLACK,
             "PHOTOVOLTAIC DC CIRCUITS",
             ["SOLAR CIRCUIT \u2014 DO NOT INTERRUPT",
              "UNDER LOAD. MAXIMUM 600 V DC.",
              "LABEL EVERY 3 m (10 ft) OF CONDUIT."],
             _lr("690.31(G)", "64-214"),
             "All DC conduit runs \u2014 every 3 m and at junctions"),

            ("L-09", "CAUTION", ANSI_YELLOW, BLACK,
             "PHOTOVOLTAIC AC CIRCUITS",
             ["SOLAR CIRCUIT \u2014 MAXIMUM 240 V AC.",
              "ENERGIZED FROM INVERTER AND",
              "UTILITY GRID SIMULTANEOUSLY."],
             _lr("690.31", "64-214"),
             "All AC conduit between inverter and load center"),

            ("L-10", "CAUTION", ANSI_YELLOW, BLACK,
             "DISCONNECT BEFORE SERVICING",
             ["OPEN BOTH DC DISCONNECT AND",
              "AC DISCONNECT BEFORE SERVICING",
              "ANY PART OF THIS SYSTEM."],
             _lr("690.13", "84-030"),
             "On each piece of electrical equipment"),

            ("L-11", "CAUTION", ANSI_YELLOW, BLACK,
             "JUNCTION BOX \u2014 PV CIRCUIT INSIDE",
             ["ALL JUNCTION AND PULL BOXES ON",
              "THIS CIRCUIT SHALL BE LABELED AT",
              "EVERY POINT OF ACCESS PER CODE."],
             _lr("690.31(G)(3)", "64-214"),
             "At all PV junction boxes and pull boxes"),

            # INFO x 3
            ("L-12", "INFO",    ANSI_BLUE,   WHITE,
             "PHOTOVOLTAIC SYSTEM DISCONNECT",
             ["DC DISCONNECTING MEANS.",
              "MAXIMUM SYSTEM VOLTAGE: 600 V DC.",
              f"{_safety_listing}."],
             _lr("690.17", "84-030"),
             "On DC disconnect switch or enclosure cover"),

            ("L-13", "INFO",    ANSI_BLUE,   WHITE,
             "POINT OF INTERCONNECTION",
             ["PHOTOVOLTAIC SYSTEM INTERACTIVE",
              "WITH UTILITY GRID.",
              f"{_un} NET METERING."],
             _lr("705.10", "84-030"),
             "On load center at grid interconnection point"),

            ("L-14", "INFO",    ANSI_BLUE,   WHITE,
             "BI-DIRECTIONAL UTILITY METER",
             [f"NET METERING \u2014 {_un}.",
              "RECORDS ENERGY EXPORTED TO AND",
              "IMPORTED FROM THE UTILITY GRID."],
             f"{_un} {'NEM 3.0' if _is_nec else 'Distribution Tariff D'}",
             "Adjacent to utility revenue meter"),
        ]

        # ── Grid layout (3 cols × 5 rows; notes in right-column panel) ─
        col_count = 3
        label_w   = 309   # (959 - 2×16) / 3 — leaves 243 px for right notes col
        col_gap   = 16
        card_h    = 120   # header(26) + title(26) + body(48) + footer(20)
        header_h  = 26
        footer_h  = 20
        row_gap   = 12    # gap between bottom of location text and next card
        loc_h     = 13    # height reserved for location text line
        row_h     = card_h + loc_h + row_gap   # = 145 px per row

        start_x   = 33
        start_y   = 85

        col_x = [start_x + i * (label_w + col_gap) for i in range(col_count)]
        row_y = [start_y + i * row_h for i in range(5)]

        for idx, (lnum, level, color, tcolor, title, lines, code, location) in enumerate(labels):
            col = idx % col_count
            row = idx // col_count
            x   = col_x[col]
            y   = row_y[row]

            # Card outline (white fill)
            svg_parts.append(
                f'<rect x="{x}" y="{y}" width="{label_w}" height="{card_h}" '
                f'fill="#ffffff" stroke="#444" stroke-width="1.2" rx="2"/>'
            )

            # ── Coloured header bar ──────────────────────────────────
            svg_parts.append(
                f'<rect x="{x}" y="{y}" width="{label_w}" height="{header_h}" '
                f'fill="{color}" rx="2" stroke="none"/>'
            )
            # Square the bottom corners of the header
            svg_parts.append(
                f'<rect x="{x}" y="{y + header_h - 3}" width="{label_w}" height="3" '
                f'fill="{color}" stroke="none"/>'
            )

            # Safety triangle icon (for DANGER/WARNING/CAUTION)
            if level in ("DANGER", "WARNING", "CAUTION"):
                tx = x + 16
                ty = y + header_h // 2
                ts = 8
                tri_pts = (f"{tx:.1f},{ty - ts:.1f} "
                           f"{tx - ts * 0.866:.1f},{ty + ts * 0.5:.1f} "
                           f"{tx + ts * 0.866:.1f},{ty + ts * 0.5:.1f}")
                svg_parts.append(
                    f'<polygon points="{tri_pts}" fill="white" stroke="{color}" '
                    f'stroke-width="0.5" opacity="0.92"/>'
                )
                svg_parts.append(
                    f'<text x="{tx}" y="{ty + 4}" text-anchor="middle" '
                    f'font-size="8" font-weight="900" font-family="Arial" '
                    f'fill="{color}">!</text>'
                )
            else:
                # Info circle "i"
                svg_parts.append(
                    f'<circle cx="{x + 14}" cy="{y + header_h // 2}" r="7" '
                    f'fill="white" opacity="0.9"/>'
                )
                svg_parts.append(
                    f'<text x="{x + 14}" y="{y + header_h // 2 + 4}" '
                    f'text-anchor="middle" font-size="9" font-weight="900" '
                    f'font-family="Arial" fill="{color}">i</text>'
                )

            # Level text (centred in header, offset right of icon)
            mid_x = x + label_w // 2 + 10
            mid_y = y + header_h // 2 + 5
            svg_parts.append(
                f'<text x="{mid_x}" y="{mid_y}" text-anchor="middle" '
                f'font-size="11" font-weight="900" font-family="Arial" '
                f'fill="{tcolor}" letter-spacing="2">{level}</text>'
            )

            # Label number badge (top-right corner of header)
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
                f'<line x1="{x}" y1="{foot_y}" x2="{x + label_w}" y2="{foot_y}" '
                f'stroke="#ccc" stroke-width="0.7"/>'
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
        # Column geometry: x=1007, w=243, spans from page header to below label grid
        nc_x = 1007   # 33 + 3×(309+16) - 16 + 15 = 33 + 959 + 15 = 1007
        nc_y = 75
        nc_w = 243    # 1280 - 30 - 1007
        nc_h = 735    # from y=75 to y=810 (= start_y + 5×row_h)

        # Column border
        svg_parts.append(
            f'<rect x="{nc_x}" y="{nc_y}" width="{nc_w}" height="{nc_h}" '
            f'fill="#ffffff" stroke="#000" stroke-width="1.2"/>'
        )
        # Header bar
        svg_parts.append(
            f'<rect x="{nc_x}" y="{nc_y}" width="{nc_w}" height="22" '
            f'fill="#e8e8e8" stroke="none"/>'
        )
        svg_parts.append(
            f'<line x1="{nc_x}" y1="{nc_y+22}" x2="{nc_x+nc_w}" y2="{nc_y+22}" '
            f'stroke="#000" stroke-width="0.8"/>'
        )
        svg_parts.append(
            f'<text x="{nc_x + nc_w//2}" y="{nc_y+15}" text-anchor="middle" '
            f'font-size="9" font-weight="700" font-family="Arial" fill="#000">'
            f'LABELING NOTES</text>'
        )

        # Text rendering helpers
        _nc_ty = [nc_y + 34]   # mutable y cursor
        nc_lx = nc_x + 8

        def _nc(text, bold=False, fill="#000", size=7.0):
            fw = "700" if bold else "400"
            svg_parts.append(
                f'<text x="{nc_lx}" y="{_nc_ty[0]}" font-size="{size}" '
                f'font-weight="{fw}" font-family="Arial" fill="{fill}">'
                f'{text}</text>'
            )
            _nc_ty[0] += 12.0

        def _nc_gap(px=6):
            _nc_ty[0] += px

        def _nc_divider():
            svg_parts.append(
                f'<line x1="{nc_x+5}" y1="{_nc_ty[0]}" '
                f'x2="{nc_x+nc_w-5}" y2="{_nc_ty[0]}" '
                f'stroke="#ccc" stroke-width="0.6"/>'
            )
            _nc_ty[0] += 8

        # ── Block 1: Hand-written labels prohibited ────────────────────
        _pc = self._code_prefix
        _pn = (_pc == "NEC")
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
        _nc("1.4 MIN LETTER HEIGHT: 3/8\"")
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
            f'NOTE:- *ALL PLAQUES AND SIGNAGE WILL BE INSTALLED OR REFLECTIVE '
            f'ADHESIVE LABEL AS REQUIRED BY THE {_code_name}*'
            f'</text>'
        )

        # ── Title block ───────────────────────────────────────────────
        svg_parts.append(self._svg_title_block(
            VW, VH,
            sheet_id="PV-6",
            sheet_title="Electrical Labels",
            subtitle=f"{_cp} {'690 / NEC' if _is_nec else 'Rule 64'} | ANSI Z535.4",
            page_of="8 of 13",
            address=address,
            today=today,
        ))

        svg_content = "\n".join(svg_parts)
        return (f'<div class="page"><svg width="100%" height="100%" '
                f'viewBox="0 0 {VW} {VH}" xmlns="http://www.w3.org/2000/svg" '
                f'style="background:#fff;">{svg_content}</svg></div>')

    def _build_placard_house_page(self, address: str, today: str) -> str:
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
        svg_parts.append('<text x="640" y="34" text-anchor="middle" font-size="14" font-weight="700" font-family="Arial" fill="#000">! CAUTION !</text>')

        # ── "Power supplied from following sources" notice ────────────────
        svg_parts.append('<rect x="20" y="58" width="1240" height="30" fill="#f5f5f5" stroke="#000" stroke-width="1"/>')
        svg_parts.append(
            '<text x="640" y="71" text-anchor="middle" font-size="9" font-weight="700" font-family="Arial" fill="#000">'
            'POWER TO THIS BUILDING IS SUPPLIED FROM THE FOLLOWING SOURCES WITH DISCONNECTS LOCATED AS SHOWN'
            '</text>'
        )
        svg_parts.append(
            '<text x="640" y="82" text-anchor="middle" font-size="8" font-family="Arial" fill="#333">'
            'SERVICE 1 OF 1 — NEW ROOF MOUNT SOLAR PV ARRAY (MICROINVERTER SYSTEM — ALL AC OUTPUT)'
            '</text>'
        )

        # ── House geometry ────────────────────────────────────────────────
        # Centered house elevation with equipment on sides
        house_x = 370        # left wall x
        roof_peak_y = 150    # top of roof
        roof_base_y = 255    # eave line (roof meets walls)
        wall_bottom_y = 490  # ground line
        house_w = 290
        roof_overhang = 22   # eaves extend past walls

        # ── Ground line ───────────────────────────────────────────────────
        svg_parts.append(
            f'<line x1="80" y1="{wall_bottom_y}" x2="950" y2="{wall_bottom_y}" '
            f'stroke="#000" stroke-width="1.5" stroke-dasharray="8,4"/>'
        )
        svg_parts.append(
            f'<text x="960" y="{wall_bottom_y + 4}" font-size="8" font-family="Arial" fill="#666">GRADE</text>'
        )

        # ── Roof (gable) ──────────────────────────────────────────────────
        roof_left  = house_x - roof_overhang
        roof_right = house_x + house_w + roof_overhang
        roof_cx    = house_x + house_w / 2
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
                f'<rect x="{px - panel_w/2:.0f}" y="{py - panel_h:.0f}" '
                f'width="{panel_w}" height="{panel_h}" '
                f'fill="#ffffff" stroke="#000000" stroke-width="0.9" '
                f'transform="rotate({angle},{px:.0f},{py - panel_h/2:.0f})"/>'
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
            f'<circle cx="{door_x + door_w - 9:.0f}" cy="{door_y + door_h/2:.0f}" r="3" '
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
                f'<line x1="{wx + win_w/2:.0f}" y1="{wy}" x2="{wx + win_w/2:.0f}" '
                f'y2="{wy + win_h}" stroke="#000" stroke-width="0.5"/>'
            )
            svg_parts.append(
                f'<line x1="{wx:.0f}" y1="{wy + win_h/2:.0f}" x2="{wx + win_w:.0f}" '
                f'y2="{wy + win_h/2:.0f}" stroke="#000" stroke-width="0.5"/>'
            )

        # ── RIGHT SIDE equipment: JUNC. BOX + PV LOAD CTR ────────────────
        # Microinverter system: AC trunk cables come off roof to junction box,
        # then to PV Load Center. NO DC disconnect. NO central inverter.
        eq_x = house_x + house_w + 35  # right of house

        # Junction Box (NEMA 3R) — where AC trunk cables from roof merge
        jb_y = roof_base_y + 18
        svg_parts.append(
            f'<rect x="{eq_x}" y="{jb_y}" width="90" height="52" '
            f'fill="#ffffff" stroke="#000" stroke-width="1.8"/>'
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

        # PV Load Center (125A/240V) — backfed breaker panel
        pvlc_y = jb_y + 80
        svg_parts.append(
            f'<rect x="{eq_x}" y="{pvlc_y}" width="90" height="60" '
            f'fill="#ffffff" stroke="#000" stroke-width="1.8"/>'
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
            f'<rect x="{mp_x}" y="{mp_y}" width="72" height="88" '
            f'fill="#f0f0f0" stroke="#000" stroke-width="1.8"/>'
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
            f'<circle cx="{meter_x + 36}" cy="{meter_y + 28}" r="26" '
            f'fill="#f8f8f8" stroke="#000" stroke-width="1.8"/>'
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
            f'{eq_x + 45},{wall_bottom_y - 12} '
            f'{mp_x + 72},{wall_bottom_y - 12} '
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
        # Numbered circles at equipment locations with leader lines + label boxes
        callouts = [
            {
                "num": "1",
                "label": "ROOF ARRAY (13 MODULES)",
                "sublabel": "13x ENPHASE IQ8A MICROINVERTERS",
                "dot_x": roof_cx + 0.45 * (roof_right - roof_cx),
                "dot_y": roof_peak_y + 0.45 * (roof_base_y - roof_peak_y),
                "box_x": 710, "box_y": 100,
            },
            {
                "num": "2",
                "label": "JUNCTION BOX (NEMA 3R)",
                "sublabel": "AC BRANCH CIRCUIT MERGE POINT",
                "dot_x": eq_x + 45, "dot_y": jb_y + 26,
                "box_x": 760, "box_y": 205,
            },
            {
                "num": "3",
                "label": "PV LOAD CENTER",
                "sublabel": "125A/240V — 30A 2P RAPID SHUTDOWN",
                "dot_x": eq_x + 45, "dot_y": pvlc_y + 30,
                "box_x": 760, "box_y": 310,
            },
            {
                "num": "4",
                "label": "MAIN SERVICE PANEL",
                "sublabel": "200A/240V — DUAL POWER SOURCE",
                "dot_x": mp_x + 36, "dot_y": mp_y + 44,
                "box_x": 55, "box_y": 205,
            },
            {
                "num": "5",
                "label": "MAIN BILLING METER",
                "sublabel": "BI-DIRECTIONAL (NET METERING)",
                "dot_x": meter_x + 36, "dot_y": meter_y + 28,
                "box_x": 55, "box_y": 380,
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
            svg_parts.append(
                f'<circle cx="{c["box_x"] + 18}" cy="{c["box_y"] + 24}" r="11" '
                f'fill="#000000"/>'
            )
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
            ("#cc0000", "●",  "Enphase IQ8A microinverter (one under each panel, AC output only)"),
            ("#000000", "①",  "Callout number — matches equipment location on building"),
        ]
        for li, (lc, sym, txt) in enumerate(legend_items):
            ly2 = leg_y + 18 + li * 16
            svg_parts.append(
                f'<text x="60" y="{ly2}" font-size="9" font-family="Arial" fill="{lc}">{sym}</text>'
            )
            svg_parts.append(
                f'<text x="80" y="{ly2}" font-size="8" font-family="Arial" fill="#333">{txt}</text>'
            )

        # ── Notes ─────────────────────────────────────────────────────────
        notes_y = leg_y + 80
        svg_parts.append(
            f'<text x="50" y="{notes_y}" font-size="9" font-weight="700" font-family="Arial" fill="#000">NOTES</text>'
        )
        notes = [
            "This system uses MICROINVERTERS — there is NO DC conduit and NO central inverter on this property.",
            "All conductors from the PV array to the load center are AC. Rapid shutdown is at the PV Load Center.",
            f"All labels must be permanently attached, weather/UV-resistant, min. 3/8\" letter height ({self._code_prefix} {'690.31(G)' if self._code_prefix == 'NEC' else '64-060'}).",
            "Labels on roof and equipment must remain visible during inspection walk-through.",
            f"Bi-directional meter required for {self._utility_name} net metering (max {int(self._utility_info.get('net_metering_max_kw', 25))} kW single-phase).",
        ]
        for ni, note in enumerate(notes):
            svg_parts.append(
                f'<text x="60" y="{notes_y + 15 + ni * 15}" font-size="7.5" font-family="Arial" fill="#333">{ni+1}. {note}</text>'
            )

        # ── Title block ───────────────────────────────────────────────────
        svg_parts.append(self._svg_title_block(
            1280, 960, "PV-6.1", "Placard House",
            "Disconnect Locations — Microinverter System", "9 of 13",
            address, today
        ))

        svg_content = "\n".join(svg_parts)
        return f'<div class="page"><svg width="100%" height="100%" viewBox="0 0 1280 960" xmlns="http://www.w3.org/2000/svg" style="background:#fff;">{svg_content}</svg></div>'

    def _build_mounting_details_page(self, total_panels: int, total_kw: float,
                                     address: str, today: str, insight) -> str:
        """PV-5: Mounting Details and Bill of Materials (Cubillas PV-5 equivalent).

        Layout (1280×960 landscape) — matches Cubillas PV-5 standard:
          Left column  (x=30–490):  Attachment elevation cross-section +
                                    4 clamp detail drawings (2×2 grid, generous height)
          Center column (x=510–1040): Large attachment spec text (17pt) + BOM table
          Far right: standard title block
        """
        svg = []

        # ── Background & border ──────────────────────────────────────────
        svg.append('<rect width="1280" height="960" fill="#ffffff"/>')
        svg.append('<rect x="20" y="20" width="1240" height="820" fill="none" stroke="#000" stroke-width="2"/>')

        # Vertical divider: left column | center column
        svg.append('<line x1="490" y1="28" x2="490" y2="838" stroke="#000" stroke-width="1"/>')

        # ─────────────────────────────────────────────────────────────────
        # PANEL DIMENSIONS — from ProjectSpec/catalog (consistent with PV-8.1 datasheet)
        if self._project:
            _p = self._project.panel
            panel_h_m = _p.dimensions.length_mm / 1000
            panel_w_m = _p.dimensions.width_mm / 1000
            panel_weight_lbs = _p.weight_lbs
        else:
            panel_h_m = 1.800
            panel_w_m = 1.134
            panel_weight_lbs = 58.4

        panel_h_in = panel_h_m / 0.0254
        panel_w_in = panel_w_m / 0.0254
        panel_h_str = f"{int(panel_h_in // 12)}'-{int(panel_h_in % 12):02d}\""
        panel_w_str = f"{int(panel_w_in // 12)}'-{int(panel_w_in % 12):02d}\""
        panel_area_sqft = (panel_h_m * panel_w_m) / (0.3048 ** 2)
        panel_weight_per_sqft = panel_weight_lbs / panel_area_sqft if panel_area_sqft > 0 else 0

        pitch_deg = "19\u00b0"
        if insight and insight.roof_segments:
            pitch_deg = f"{insight.roof_segments[0].pitch_deg:.0f}\u00b0"

        n = total_panels
        if HAS_PROJECT_SPEC and self._project:
            _bom = {item.equipment: item.qty for item in calculate_bom(self._project)}
            n_rails      = _bom.get("MOUNTING RAIL", max(4, round(n * 0.77)))
            n_end_clamps = _bom.get("END CLAMP",     n_rails * 2)
            n_mid_clamps = _bom.get("MID CLAMP",     max(4, round(n * 1.85)))
            n_mounts     = _bom.get("MOUNTING POINT", max(8, round(n * 1.38)))
            # Inverter count: 1-per-panel for micro, 1 for string
            if self._project.inverter.is_micro:
                n_inverters      = _bom.get("MICROINVERTER", n)
                inverter_row_label = "MICROINVERTERS"
            else:
                n_inverters      = _bom.get("STRING INVERTER", 1)
                inverter_row_label = "STRING INVERTER"
        else:
            n_rails      = max(4, round(n * 0.77))
            n_end_clamps = n_rails * 2
            n_mid_clamps = max(4, round(n * 1.85))
            n_mounts     = max(8, round(n * 1.38))
            n_inverters      = n
            inverter_row_label = "MICROINVERTERS"
        total_ac_current_bom = n * self.INV_AC_AMPS_PER_UNIT
        system_ocpd_bom = math.ceil(total_ac_current_bom * 1.25 / 5) * 5

        # ════════════════════════════════════════════════════════════════
        # LEFT COLUMN: Elevation Drawing + Clamp Details
        # Column: x=30–490, width=460
        # ════════════════════════════════════════════════════════════════

        # ── Section header ──────────────────────────────────────────────
        svg.append('<text x="40" y="48" font-size="12" font-weight="700" font-family="Arial" fill="#000">ATTACHMENT DETAILS</text>')
        svg.append('<circle cx="265" cy="43" r="9" fill="none" stroke="#000" stroke-width="1.5"/>')
        svg.append('<text x="265" y="47" text-anchor="middle" font-size="9" font-weight="700" font-family="Arial" fill="#000">1</text>')
        svg.append('<text x="278" y="47" font-size="9" font-family="Arial" fill="#555">(N.T.S.)</text>')
        svg.append('<line x1="30" y1="55" x2="488" y2="55" stroke="#000" stroke-width="1"/>')

        # ── Elevation Cross-Section Drawing ──────────────────────────────
        # Side profile: PV MODULE → MID-CLAMP → XR-10 RAIL → FLASHFOOT2 → SHINGLES → RAFTER
        ex, ey = 35, 65
        dw, dh = 455, 255
        cx_drw = ex + dw // 2

        # Drawing area background (white engineering standard)
        svg.append(f'<rect x="{ex}" y="{ey}" width="{dw}" height="{dh}" fill="#ffffff" stroke="#000" stroke-width="0.8"/>')

        # ── Horizontal Rail Elevation Drawing (Cubillas PV-5 standard) ──────────
        # Shows the IronRidge XR-10 rail running LEFT-TO-RIGHT across the drawing
        # with three FlashFoot2 attachment points at rafter positions — matching the
        # Cubillas PV-5 left-column elevation drawing style exactly.
        #
        # Component y-positions (top-down, centered in the 255px drawing area):
        #   Stack: module(42) + clamp(11) + rail(18) + FF2(22) + shingles(9) + rafter(18) = 120px
        #   Vertical offset: (255 - 120) // 2 = 67px
        #   Module top at: ey + 67
        _el_mod_y0    = ey + 67        # top of module panels
        _el_mod_h     = 42             # module height (portrait short-side from side)
        _el_rail_y0   = _el_mod_y0 + _el_mod_h + 11   # +11 for clamp thickness
        _el_rail_h    = 18
        _el_ff2_y0    = _el_rail_y0 + _el_rail_h
        _el_ff2_h     = 22
        _el_shingle_y = _el_ff2_y0 + _el_ff2_h
        _el_shingle_h = 9
        _el_rafter_y  = _el_shingle_y + _el_shingle_h
        _el_rafter_h  = 18

        # Horizontal extents: drawing content x=52..325, label area x=335..488
        _el_lx = ex + 17    # left edge of content  (x = 52)
        _el_rx = ex + 290   # right edge of content (x = 325)
        _el_lbl_x = ex + 300  # label text start    (x = 335)

        # ── XR-10 Rail (full-width horizontal bar) ────────────────────────────
        # Rail fill: same green (#4a9e4a) used for racking rails on PV-3.1,
        # maintaining visual consistency across all pages of the planset.
        # Previous gray (#b8c4d0) created a visual inconsistency — a reviewer
        # seeing PV-3.1 green racking rails and then PV-5 gray rails in the
        # elevation would not immediately recognize them as the same component.
        _el_rl_x = _el_lx - 6
        _el_rl_w = _el_rx - _el_lx + 12
        svg.append(f'<rect x="{_el_rl_x}" y="{_el_rail_y0}" width="{_el_rl_w}" '
                   f'height="{_el_rail_h}" fill="#4a9e4a" stroke="#000" stroke-width="1.5"/>')
        # C-channel inner profile lines (XR-10 cross-section detail) — darker green
        svg.append(f'<line x1="{_el_rl_x+2}" y1="{_el_rail_y0+5}" '
                   f'x2="{_el_rl_x+_el_rl_w-2}" y2="{_el_rail_y0+5}" '
                   f'stroke="#2d7a2d" stroke-width="0.5"/>')
        svg.append(f'<line x1="{_el_rl_x+2}" y1="{_el_rail_y0+_el_rail_h-5}" '
                   f'x2="{_el_rl_x+_el_rl_w-2}" y2="{_el_rail_y0+_el_rail_h-5}" '
                   f'stroke="#2d7a2d" stroke-width="0.5"/>')

        # ── FlashFoot2 bases (3 attachment points at 1/4, 1/2, 3/4 of span) ──
        _el_span = _el_rx - _el_lx           # = 273px
        _el_ff2_xs = [
            _el_lx + _el_span // 4,          # ≈ x=120
            _el_lx + _el_span // 2,          # ≈ x=188
            _el_lx + 3 * _el_span // 4,      # ≈ x=257
        ]
        for _fx in _el_ff2_xs:
            # Flashing plate cap (sits directly below rail, above shingles)
            svg.append(f'<rect x="{_fx-15}" y="{_el_ff2_y0}" width="30" height="10" '
                       f'fill="#c8c8c8" stroke="#000" stroke-width="1"/>')
            # Lag bolt/post penetrating shingles down to rafter
            svg.append(f'<line x1="{_fx}" y1="{_el_ff2_y0+10}" '
                       f'x2="{_fx}" y2="{_el_rafter_y + _el_rafter_h - 3}" '
                       f'stroke="#555" stroke-width="2.0"/>')
            # Bolt tip
            svg.append(f'<polygon points="{_fx-3},{_el_rafter_y+_el_rafter_h-3} '
                       f'{_fx+3},{_el_rafter_y+_el_rafter_h-3} '
                       f'{_fx},{_el_rafter_y+_el_rafter_h+3}" fill="#555"/>')

        # ── Shingles (gray with horizontal lap-texture lines) ─────────────────
        svg.append(f'<rect x="{_el_rl_x-8}" y="{_el_shingle_y}" '
                   f'width="{_el_rl_w+16}" height="{_el_shingle_h}" '
                   f'fill="#888888" stroke="#555" stroke-width="0.8"/>')
        for _sxi in range(_el_rl_x - 8, _el_rl_x + _el_rl_w + 20, 30):
            svg.append(f'<rect x="{_sxi}" y="{_el_shingle_y}" width="30" height="5" '
                       f'fill="none" stroke="#555" stroke-width="0.35"/>')

        # ── Rafters (brown/wood, 3 of them at FlashFoot2 x-positions) ─────────
        for _fx in _el_ff2_xs:
            svg.append(f'<rect x="{_fx-13}" y="{_el_rafter_y}" width="26" '
                       f'height="{_el_rafter_h}" fill="#d4b896" stroke="#000" stroke-width="1.2"/>')
            for _gx in range(_fx - 11, _fx + 13, 5):
                svg.append(f'<line x1="{_gx}" y1="{_el_rafter_y+2}" '
                           f'x2="{_gx}" y2="{_el_rafter_y+_el_rafter_h-2}" '
                           f'stroke="#b8936a" stroke-width="0.4"/>')

        # ── Two PV modules (landscape orientation side view, white) ───────────
        _el_mod_gap = 10
        _el_mod_w   = (_el_rx - _el_lx - _el_mod_gap) // 2   # ≈ 131px each
        for _mi in range(2):
            _mx = _el_lx + _mi * (_el_mod_w + _el_mod_gap)
            svg.append(f'<rect x="{_mx}" y="{_el_mod_y0}" '
                       f'width="{_el_mod_w}" height="{_el_mod_h}" '
                       f'fill="#ffffff" stroke="#000000" stroke-width="1.5"/>')
            # Vertical cell grid lines
            for _ci in range(1, 5):
                _gcx = _mx + _ci * _el_mod_w // 5
                svg.append(f'<line x1="{_gcx}" y1="{_el_mod_y0+2}" '
                           f'x2="{_gcx}" y2="{_el_mod_y0+_el_mod_h-2}" '
                           f'stroke="#cccccc" stroke-width="0.4"/>')
            # Horizontal cell grid lines
            for _ri in range(1, 3):
                svg.append(f'<line x1="{_mx+2}" y1="{_el_mod_y0+_ri*_el_mod_h//3}" '
                           f'x2="{_mx+_el_mod_w-2}" y2="{_el_mod_y0+_ri*_el_mod_h//3}" '
                           f'stroke="#cccccc" stroke-width="0.4"/>')

        # ── End clamps (outer module edges) ───────────────────────────────────
        _el_ec_w = 9
        svg.append(f'<rect x="{_el_lx-_el_ec_w}" y="{_el_mod_y0+6}" '
                   f'width="{_el_ec_w}" height="28" fill="#c8c8c8" stroke="#000" stroke-width="1.2"/>')
        svg.append(f'<rect x="{_el_rx}" y="{_el_mod_y0+6}" '
                   f'width="{_el_ec_w}" height="28" fill="#c8c8c8" stroke="#000" stroke-width="1.2"/>')

        # ── Mid clamp (between modules, with fastening bolt circle) ───────────
        _el_mc_cx = _el_lx + _el_mod_w + _el_mod_gap // 2
        svg.append(f'<rect x="{_el_mc_cx-8}" y="{_el_mod_y0+6}" width="16" height="28" '
                   f'fill="#c8c8c8" stroke="#000" stroke-width="1.2"/>')
        svg.append(f'<circle cx="{_el_mc_cx}" cy="{_el_mod_y0+20}" r="3.5" '
                   f'fill="#888" stroke="#555" stroke-width="0.8"/>')

        # ── Component labels (right side, with short dashed leader lines) ──────
        _el_leader_x = _el_rx + 5   # start of leader (right edge of content + 5)
        _el_lbl_items = [
            (_el_mod_y0 + _el_mod_h // 2,        "PV MODULE FRAME"),
            (_el_rail_y0 + _el_rail_h // 2,      "{self._racking_full} RAIL"),
            (_el_ff2_y0 + _el_ff2_h // 2,        "{self._attachment_full}"),
            (_el_shingle_y + _el_shingle_h // 2, "ASPHALT SHINGLES"),
            (_el_rafter_y + _el_rafter_h // 2,   'RAFTER @ 24" O.C.'),
        ]
        for _ly, _lt in _el_lbl_items:
            # Short horizontal dashed leader line → label text
            svg.append(f'<line x1="{_el_leader_x}" y1="{_ly}" '
                       f'x2="{_el_lbl_x - 4}" y2="{_ly}" '
                       f'stroke="#555" stroke-width="0.8" stroke-dasharray="4,2"/>')
            svg.append(f'<text x="{_el_lbl_x}" y="{_ly + 3}" '
                       f'font-size="7.5" font-family="Arial" fill="#000">{_lt}</text>')

        # ── 4 Clamp Detail Drawings (2×2 grid) ──────────────────────────
        # Now has generous vertical space: ~498px for 4 drawings (was ~340px)
        cd_start_y = ey + dh + 10   # 65+255+10 = 330
        cd_area_h  = 838 - cd_start_y - 10   # 498
        cd_col_w   = (490 - 30) // 2          # 230 per column
        cd_row_h   = cd_area_h // 2 - 8       # ~241 per row

        def _clamp_lbl(text, cx2, cy2):
            svg.append(f'<text x="{cx2}" y="{cy2}" text-anchor="middle" '
                       f'font-size="8.5" font-weight="700" font-family="Arial" fill="#000">{text}</text>')

        row0_top = cd_start_y
        row1_top = cd_start_y + cd_row_h + 16

        # ── MID CLAMP — PLAN VIEW (row 0, col 0) ─────────────────────
        mc_px = 30 + cd_col_w // 2
        mc_py = row0_top + cd_row_h // 2 + 8
        _clamp_lbl("DETAIL, MID CLAMP — PLAN VIEW", mc_px, row0_top + 12)

        mf_w, mf_h = 85, 55
        mf_y = mc_py - mf_h // 2
        m_gap = 10
        for mx_off in [mc_px - mf_w - m_gap // 2, mc_px + m_gap // 2]:
            svg.append(f'<rect x="{mx_off}" y="{mf_y}" width="{mf_w}" height="{mf_h}" fill="#ffffff" stroke="#000000" stroke-width="2"/>')
            svg.append(f'<text x="{mx_off+mf_w//2}" y="{mf_y+mf_h//2+4}" text-anchor="middle" font-size="7" font-family="Arial" fill="#000000">PV MODULE FRAME</text>')

        rail_plan_y = mc_py - 7
        svg.append(f'<rect x="{mc_px-mf_w-m_gap//2-8}" y="{rail_plan_y}" width="{2*mf_w+m_gap+16}" height="13" fill="#4a9e4a" stroke="#000" stroke-width="1"/>')
        svg.append(f'<text x="{mc_px-mf_w-m_gap//2-8}" y="{rail_plan_y+22}" font-size="7" font-family="Arial" fill="#000">{self._racking_full} RAIL</text>')

        svg.append(f'<rect x="{mc_px-8}" y="{mc_py-18}" width="16" height="36" fill="#c8c8c8" stroke="#000" stroke-width="1.5"/>')
        svg.append(f'<circle cx="{mc_px}" cy="{mc_py}" r="5" fill="#888" stroke="#000" stroke-width="1"/>')
        svg.append(f'<text x="{mc_px+18}" y="{mc_py+4}" font-size="7" font-family="Arial" fill="#000">{self._racking_manufacturer} CLAMP</text>')
        svg.append(f'<text x="{mc_px+18}" y="{mc_py+13}" font-size="7" font-family="Arial" fill="#000">FASTENING OBJECT</text>')

        # ── MID CLAMP — FRONT VIEW (row 0, col 1) ─────────────────────
        mc_fx = 30 + cd_col_w + cd_col_w // 2
        mc_fy = mc_py
        _clamp_lbl("DETAIL, MID CLAMP — FRONT VIEW", mc_fx, row0_top + 12)

        fe_w = 13
        fe_h = 44
        fe_y = mc_fy - fe_h // 2
        svg.append(f'<rect x="{mc_fx-52}" y="{fe_y}" width="{fe_w}" height="{fe_h}" fill="#ffffff" stroke="#000000" stroke-width="1.5"/>')
        svg.append(f'<text x="{mc_fx-52+fe_w//2}" y="{fe_y-4}" text-anchor="middle" font-size="7" font-family="Arial" fill="#000">PV MODULE FRAME</text>')
        svg.append(f'<rect x="{mc_fx+52-fe_w}" y="{fe_y}" width="{fe_w}" height="{fe_h}" fill="#ffffff" stroke="#000000" stroke-width="1.5"/>')

        rail_fe_y = mc_fy + fe_h // 2 - 16
        svg.append(f'<rect x="{mc_fx-58}" y="{rail_fe_y}" width="116" height="20" fill="#4a9e4a" stroke="#000" stroke-width="1"/>')
        svg.append(f'<text x="{mc_fx}" y="{rail_fe_y+33}" text-anchor="middle" font-size="7" font-family="Arial" fill="#000">{self._racking_full} RAIL</text>')

        cap_y = fe_y - 11
        svg.append(f'<rect x="{mc_fx-32}" y="{cap_y}" width="64" height="11" fill="#d0d0d0" stroke="#000" stroke-width="1.5"/>')
        svg.append(f'<line x1="{mc_fx}" y1="{cap_y}" x2="{mc_fx}" y2="{rail_fe_y}" stroke="#555" stroke-width="2"/>')

        sleeve_y = rail_fe_y - 7
        svg.append(f'<rect x="{mc_fx-52+fe_w}" y="{sleeve_y}" width="{2*(52-fe_w)}" height="7" fill="#f0f0f0" stroke="#000" stroke-width="1"/>')
        svg.append(f'<text x="{mc_fx}" y="{sleeve_y-4}" text-anchor="middle" font-size="7" font-family="Arial" fill="#555">{self._racking_manufacturer} END CLAMP</text>')
        svg.append(f'<text x="{mc_fx+37}" y="{cap_y+9}" font-size="7" font-family="Arial" fill="#000">{self._racking_manufacturer} CLAMP</text>')

        # ── END CLAMP — PLAN VIEW (row 1, col 0) ──────────────────────
        ec_px = mc_px
        ec_py = row1_top + cd_row_h // 2 + 8
        _clamp_lbl("DETAIL, END CLAMP — PLAN VIEW", ec_px, row1_top + 12)

        ef_w, ef_h = 95, 55
        ef_y2 = ec_py - ef_h // 2
        svg.append(f'<rect x="{ec_px-ef_w//2}" y="{ef_y2}" width="{ef_w}" height="{ef_h}" fill="#ffffff" stroke="#000000" stroke-width="2"/>')
        svg.append(f'<text x="{ec_px}" y="{ef_y2+ef_h//2+4}" text-anchor="middle" font-size="7" font-family="Arial" fill="#000000">PV MODULE FRAME</text>')

        rail_ec_y = ec_py - 7
        svg.append(f'<rect x="{ec_px-ef_w//2-12}" y="{rail_ec_y}" width="{ef_w+24}" height="13" fill="#4a9e4a" stroke="#000" stroke-width="1"/>')
        svg.append(f'<text x="{ec_px-ef_w//2-12}" y="{rail_ec_y+22}" font-size="7" font-family="Arial" fill="#000">{self._racking_full} RAIL</text>')

        ec_body_x = ec_px + ef_w // 2
        svg.append(f'<rect x="{ec_body_x}" y="{ec_py-14}" width="22" height="28" fill="#d0d0d0" stroke="#000" stroke-width="1.5"/>')
        svg.append(f'<circle cx="{ec_body_x+11}" cy="{ec_py}" r="5" fill="#888" stroke="#000" stroke-width="1"/>')
        svg.append(f'<text x="{ec_body_x+28}" y="{ec_py+4}" font-size="7" font-family="Arial" fill="#000">{self._racking_manufacturer} CLAMP</text>')
        svg.append(f'<text x="{ec_body_x+28}" y="{ec_py+13}" font-size="7" font-family="Arial" fill="#000">FASTENING OBJECT</text>')
        svg.append(f'<rect x="{ec_body_x-6}" y="{ec_py-7}" width="6" height="13" fill="#f0f0f0" stroke="#000" stroke-width="0.8"/>')
        svg.append(f'<text x="{ec_body_x-8}" y="{ec_py-11}" text-anchor="end" font-size="7" font-family="Arial" fill="#555">{self._racking_manufacturer} END CLAMP</text>')

        # ── END CLAMP — FRONT VIEW (row 1, col 1) ─────────────────────
        ef_fx = mc_fx
        ef_fy = ec_py
        _clamp_lbl("DETAIL, END CLAMP — FRONT VIEW", ef_fx, row1_top + 12)

        svg.append(f'<rect x="{ef_fx-32}" y="{ef_fy-24}" width="{fe_w}" height="{fe_h}" fill="#ffffff" stroke="#000000" stroke-width="1.5"/>')
        svg.append(f'<text x="{ef_fx-32+fe_w//2}" y="{ef_fy-28}" text-anchor="middle" font-size="7" font-family="Arial" fill="#000">PV MODULE FRAME</text>')

        svg.append(f'<rect x="{ef_fx-58}" y="{ef_fy+fe_h//2-28}" width="84" height="20" fill="#4a9e4a" stroke="#000" stroke-width="1"/>')
        svg.append(f'<text x="{ef_fx-16}" y="{ef_fy+fe_h//2+6}" text-anchor="middle" font-size="7" font-family="Arial" fill="#000">{self._racking_full} RAIL</text>')

        cap2_y = ef_fy - 24 - 12
        svg.append(f'<rect x="{ef_fx-32}" y="{cap2_y}" width="32" height="12" fill="#d0d0d0" stroke="#000" stroke-width="1.5"/>')
        svg.append(f'<rect x="{ef_fx}" y="{cap2_y}" width="12" height="36" fill="#d0d0d0" stroke="#000" stroke-width="1.5"/>')
        svg.append(f'<line x1="{ef_fx-26}" y1="{cap2_y}" x2="{ef_fx-26}" y2="{ef_fy+fe_h//2-8}" stroke="#555" stroke-width="2"/>')
        svg.append(f'<text x="{ef_fx+18}" y="{cap2_y+9}" font-size="7" font-family="Arial" fill="#000">{self._racking_manufacturer} CLAMP</text>')
        svg.append(f'<text x="{ef_fx+18}" y="{cap2_y+20}" font-size="7" font-family="Arial" fill="#555">PV MODULE FRAME / {self._racking_manufacturer} END CLAMP</text>')

        # ════════════════════════════════════════════════════════════════
        # CENTER COLUMN: Large Attachment Spec Text + BOM Table
        # Column: x=510–1040, width=530
        # ════════════════════════════════════════════════════════════════
        cc_x  = 510        # left edge of center column
        cc_cx = 775        # horizontal center of center column
        title_blk_x = 1050 # where title block starts

        # ── Large Attachment Spec Text (matches Cubillas PV-5 format) ──
        # Cubillas displays these specs as prominent large bold centred text
        spec_y  = 60
        spec_lh = 29   # line height

        large_spec_lines = [
            f"ATTACHMENT TYPE: {self._attachment_full}",
            f"WITH {self._racking_full} RAILS",
            f"ROOF TYPE: ASPHALT-SHINGLES,  ROOF PITCH: {pitch_deg}",
            "",
            f"MODULE WEIGHT: {panel_weight_lbs:.0f} LBS",
            f"MODULE DIMENSIONS: {panel_h_str} X {panel_w_str}",
            f"MODULE WEIGHT / SQ. FOOT: {panel_weight_per_sqft:.2f} LBS",
            "",
            f"TOTAL NO. OF MODULES: {n}",
            f"MODULE WEIGHT: {n * panel_weight_lbs:.0f} LBS",
        ]

        for line in large_spec_lines:
            if line:
                svg.append(f'<text x="{cc_cx}" y="{spec_y}" text-anchor="middle" '
                           f'font-size="17" font-weight="700" font-family="Arial" fill="#000">{line}</text>')
            spec_y += spec_lh

        # Divider between spec block and BOM
        bom_divider_y = spec_y + 6
        svg.append(f'<line x1="{cc_x}" y1="{bom_divider_y}" x2="{title_blk_x-10}" y2="{bom_divider_y}" stroke="#000" stroke-width="1"/>')

        # ── Bill of Material table ──────────────────────────────────────
        bom_y = bom_divider_y + 14
        svg.append(f'<text x="{cc_cx}" y="{bom_y}" text-anchor="middle" '
                   f'font-size="11" font-weight="700" font-family="Arial" fill="#000">BILL OF MATERIAL</text>')

        col_widths = [120, 330, 60]
        col_labels = ["EQUIPMENT", "MAKE / DESCRIPTION", "QTY"]
        col_x = [cc_x, cc_x + col_widths[0], cc_x + col_widths[0] + col_widths[1]]
        row_h_bom = 22
        hdr_y = bom_y + 14

        for i, lbl in enumerate(col_labels):
            svg.append(f'<rect x="{col_x[i]}" y="{hdr_y}" width="{col_widths[i]}" height="{row_h_bom}" '
                       f'fill="#000000" stroke="#000" stroke-width="1"/>')
            tx = col_x[i] + col_widths[i] // 2
            svg.append(f'<text x="{tx}" y="{hdr_y + 15}" text-anchor="middle" '
                       f'font-size="9" font-weight="700" font-family="Arial" fill="#ffffff">{lbl}</text>')

        bom_rows = [
            ("MODULE",
             f"{self._panel_model_full}  [{self._panel_wattage}W {self._project.panel.technology.upper() if self._project else 'HPBC BIFACIAL'}]",
             str(n)),
            ("END CLAMPS",
             f"{self._racking_manufacturer} END CLAMP STANDARD",
             str(n_end_clamps)),
            ("MID CLAMPS",
             f"{self._racking_manufacturer} MID CLAMP (INTEGRATED GROUNDING)",
             str(n_mid_clamps)),
            ("MOUNTING POINTS",
             f"{self._attachment_full}",
             str(n_mounts)),
            ("MOUNTING RAILS",
             f"{self._racking_full} RAILS",
             str(n_rails)),
            (inverter_row_label,
             f"{self.INV_MODEL_FULL}",
             str(n_inverters)),
            ("LOAD CENTER",
             "125A RATED PV LOAD CENTER (BACKFED FROM MAIN SERVICE PANEL)",
             "1"),
            ("PV BREAKER",
             f"2P/{system_ocpd_bom}A BACKFED PV BREAKER (AT PV LOAD CENTER)",
             "1"),
            ("DATA MONITORING",
             "ENPHASE ENVOY-S METERED WITH (1) 15A/2P BREAKER",
             "1"),
            ("CONDUIT",
             "3/4\" EMT CONDUIT (EXTERIOR RUNS) + 1/2\" EMT (INTERIOR RUNS)",
             "AS REQ."),
            ("WIRE",
             f"TRUNK CABLE (FREE AIR, ALONG RACKING) / {self._wire_type} #10 AWG CU (IN EMT, J-BOX ONWARD)",
             "AS REQ."),
        ]

        row_y_bom = hdr_y + row_h_bom
        for ri, (equip, make, qty) in enumerate(bom_rows):
            row_fill = "#f9f9f9" if ri % 2 == 0 else "#ffffff"
            for ci, (text, cw) in enumerate(zip([equip, make, qty], col_widths)):
                svg.append(f'<rect x="{col_x[ci]}" y="{row_y_bom}" width="{cw}" height="{row_h_bom}" '
                           f'fill="{row_fill}" stroke="#ccc" stroke-width="0.5"/>')
                if ci == 2:
                    tx = col_x[ci] + cw // 2
                    anchor = "middle"
                else:
                    tx = col_x[ci] + 4
                    anchor = "start"
                fs = "7.5" if len(text) > 48 else "8.5"
                svg.append(f'<text x="{tx}" y="{row_y_bom + 15}" text-anchor="{anchor}" '
                           f'font-size="{fs}" font-family="Arial" fill="#000">{text}</text>')
            row_y_bom += row_h_bom

        # Total weight note
        total_wt = n * panel_weight_lbs
        svg.append(f'<text x="{cc_x}" y="{row_y_bom + 18}" font-size="8" font-family="Arial" fill="#555">'
                   f'TOTAL PV MODULE WEIGHT: {total_wt:.0f} LBS ({total_wt*0.4536:.1f} KG)</text>')

        # Installation notes (if there is room)
        notes_y = row_y_bom + 38
        note_items = [
            "1. ALL HARDWARE SHALL BE STAINLESS STEEL OR HOT-DIPPED GALVANIZED UNLESS OTHERWISE NOTED.",
            f"2. LAG SCREWS SHALL PENETRATE MIN. 63mm (2.5\") INTO SOLID WOOD FRAMING MEMBERS ({self._code_prefix} {'690.43' if self._code_prefix == 'NEC' else 'RULE 64-104'}).",
            f"3. RACKING SYSTEM SHALL BE RATED FOR DESIGN WIND (53 m/s / 190 km/h) AND SNOW LOADS PER {self._building_code}.",
            "4. {self._racking_full} RAILS ARE FIELD-SPLICED WITH BONDED SPLICE CONNECTORS; MAX. SPAN PER MFGR.",
            "5. ATTACHMENT SPACING SHALL COMPLY WITH {self._racking_manufacturer.upper()} SPAN TABLES FOR LOCAL WIND/SNOW CONDITIONS.",
        ]
        if notes_y < 800:
            svg.append(f'<text x="{cc_x}" y="{notes_y - 4}" font-size="9" font-weight="700" font-family="Arial" fill="#000">NOTES:</text>')
            for ni, note in enumerate(note_items):
                if notes_y + ni * 14 < 830:
                    svg.append(f'<text x="{cc_x}" y="{notes_y + ni*14}" font-size="7.5" font-family="Arial" fill="#333">{note}</text>')

        # ── Title block ──────────────────────────────────────────────────
        svg.append(self._svg_title_block(
            1280, 960, "PV-5", "Mounting Details and BOM",
            "IronRidge FlashFoot2 / XR-10 Rails", "7 of 13",
            address, today
        ))

        svg_content = "\n".join(svg)
        return (
            f'<div class="page">'
            f'<svg width="100%" height="100%" viewBox="0 0 1280 960" '
            f'xmlns="http://www.w3.org/2000/svg" style="background:#fff;">'
            f'{svg_content}'
            f'</svg>'
            f'</div>'
        )



    # ════════════════════════════════════════════════════════════════════
    # DATASHEET PAGES  (PV-8.1, PV-8.2, PV-8.3)
    # ════════════════════════════════════════════════════════════════════

    def _build_module_datasheet_page(self, address: str, today: str) -> str:
        """PV-8.1: Module specification sheet — reads from ProjectSpec/catalog."""
        VW, VH = 1280, 960
        svg = []

        # ── Pull ALL specs from ProjectSpec (or fall back to legacy defaults) ──
        if self._project:
            p = self._project.panel
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
        svg.append(f'<text x="640" y="37" text-anchor="middle" font-size="14" font-weight="700" '
                   f'font-family="Arial" fill="#000000">{mfr.upper()} — {series.upper()}</text>')
        svg.append(f'<text x="640" y="53" text-anchor="middle" font-size="11" font-weight="400" '
                   f'font-family="Arial" fill="#444444">{model} | {technology} | {wattage} Wp</text>')

        # ── Manufacturer logo area (text-based) ──────────────────────────
        svg.append('<rect x="30" y="72" width="320" height="340" fill="#ffffff" stroke="#ccc" stroke-width="0.5"/>')
        svg.append(f'<text x="190" y="105" text-anchor="middle" font-size="13" font-weight="700" '
                   f'font-family="Arial" fill="#000000">{mfr}</text>')
        svg.append(f'<text x="190" y="120" text-anchor="middle" font-size="9" '
                   f'font-family="Arial" fill="#555">{model_short}</text>')

        # ── Module diagram (front view schematic) ─────────────────────────
        # Draw a simplified front view of the 132-cell panel (12×11 layout)
        mod_x, mod_y = 50, 130
        mod_w, mod_h = 140, 230  # proportional to 1134×1800mm
        svg.append(f'<rect x="{mod_x}" y="{mod_y}" width="{mod_w}" height="{mod_h}" '
                   f'fill="#1a2a3a" stroke="#000" stroke-width="1.5"/>')
        # Junction box (center bottom)
        svg.append(f'<rect x="{mod_x + mod_w//2 - 10}" y="{mod_y + mod_h - 16}" '
                   f'width="20" height="10" fill="#333" stroke="#666" stroke-width="0.5"/>')
        # Cell grid from catalog datasheet drawing hints
        cell_cols, cell_rows = cell_grid[0], cell_grid[1]
        margin_x, margin_y = 6, 6
        cw = (mod_w - 2 * margin_x) / cell_cols
        ch = (mod_h - 2 * margin_y - 20) / cell_rows
        for row in range(cell_rows):
            for col in range(cell_cols):
                cx = mod_x + margin_x + col * cw
                cy = mod_y + margin_y + row * ch
                svg.append(f'<rect x="{cx:.1f}" y="{cy:.1f}" width="{cw-0.5:.1f}" height="{ch-0.5:.1f}" '
                           f'fill="#1a3060" stroke="#0a1a40" stroke-width="0.3"/>')
                # Busbars (horizontal lines through each cell)
                for bi in range(1, 10):
                    bx = cx + (cw - 0.5) * bi / 10
                    svg.append(f'<line x1="{bx:.1f}" y1="{cy:.1f}" x2="{bx:.1f}" y2="{cy+ch-0.5:.1f}" '
                               f'stroke="rgba(120,160,220,0.3)" stroke-width="0.1"/>')
        # Cable leads
        svg.append(f'<line x1="{mod_x + mod_w//2 - 6}" y1="{mod_y + mod_h}" '
                   f'x2="{mod_x + mod_w//2 - 6}" y2="{mod_y + mod_h + 14}" stroke="#c00" stroke-width="1.5"/>')
        svg.append(f'<line x1="{mod_x + mod_w//2 + 6}" y1="{mod_y + mod_h}" '
                   f'x2="{mod_x + mod_w//2 + 6}" y2="{mod_y + mod_h + 14}" stroke="#000" stroke-width="1.5"/>')
        svg.append(f'<text x="{mod_x + mod_w//2 - 6}" y="{mod_y + mod_h + 24}" '
                   f'text-anchor="middle" font-size="7" font-family="Arial" fill="#c00">+</text>')
        svg.append(f'<text x="{mod_x + mod_w//2 + 6}" y="{mod_y + mod_h + 24}" '
                   f'text-anchor="middle" font-size="7" font-family="Arial" fill="#000">−</text>')
        # Module dimension labels
        svg.append(f'<text x="{mod_x + mod_w + 6}" y="{mod_y + mod_h//2}" '
                   f'font-size="7" font-family="Arial" fill="#333" '
                   f'transform="rotate(90,{mod_x + mod_w + 6},{mod_y + mod_h//2})">{length_mm:.0f} mm ({length_in:.1f}")</text>')
        svg.append(f'<text x="{mod_x + mod_w//2}" y="{mod_y - 5}" '
                   f'text-anchor="middle" font-size="7" font-family="Arial" fill="#333">{width_mm:.0f} mm ({width_in:.1f}")</text>')
        svg.append(f'<text x="195" y="{mod_y + mod_h + 38}" text-anchor="middle" font-size="8" '
                   f'font-weight="600" font-family="Arial" fill="#000000">FRONT VIEW (N.T.S.)</text>')

        # ── Certifications row (from catalog) ────────────────────────────
        for i, cert in enumerate(certs[:6]):
            cx2 = 35 + i * 53
            svg.append(f'<rect x="{cx2}" y="408" width="48" height="18" '
                       f'fill="none" stroke="#000000" stroke-width="1" rx="3"/>')
            svg.append(f'<text x="{cx2+24}" y="420" text-anchor="middle" font-size="7" '
                       f'font-weight="600" font-family="Arial" fill="#000000">{cert}</text>')

        # ── Electrical Characteristics table (left column, below cert) ────
        elec_y = 438
        svg.append(f'<text x="35" y="{elec_y}" font-size="10" font-weight="700" '
                   f'font-family="Arial" fill="#000">ELECTRICAL CHARACTERISTICS (STC*)</text>')
        elec_rows = [
            ("Peak Power (Pmax)",           f"{wattage} W"),
            ("Open Circuit Voltage (Voc)",  f"{voc} V"),
            ("Max Power Voltage (Vmp)",     f"{vmp} V"),
            ("Short Circuit Current (Isc)", f"{isc} A"),
            ("Max Power Current (Imp)",     f"{imp} A"),
            ("Module Efficiency",           f"{efficiency} %"),
            ("Max System Voltage",          f"{max_sys_v} V DC"),
            ("Max Series Fuse Rating",      f"{max_fuse} A"),
            ("Power Tolerance",             power_tol),
        ]
        row_h = 23
        for ri, (label, val) in enumerate(elec_rows):
            ry = elec_y + 12 + ri * row_h
            bg = "#f5f5f5" if ri % 2 == 0 else "#ffffff"
            svg.append(f'<rect x="30" y="{ry}" width="320" height="{row_h}" fill="{bg}" stroke="#ccc" stroke-width="0.5"/>')
            svg.append(f'<text x="38" y="{ry + 15}" font-size="9" font-family="Arial" fill="#000">{label}</text>')
            svg.append(f'<text x="342" y="{ry + 15}" text-anchor="end" font-size="9" font-weight="600" '
                       f'font-family="Arial" fill="#000000">{val}</text>')

        # *STC footnote
        svg.append(f'<text x="30" y="{elec_y + 12 + len(elec_rows)*row_h + 12}" font-size="7" '
                   f'font-family="Arial" fill="#666" font-style="italic">'
                   f'* STC: Irradiance 1000 W/m², AM1.5, Cell Temp 25°C</text>')

        # ── Temperature Coefficients (below electrical) ───────────────────
        tc_y = elec_y + 12 + len(elec_rows) * row_h + 28
        svg.append(f'<text x="35" y="{tc_y}" font-size="10" font-weight="700" '
                   f'font-family="Arial" fill="#000">TEMPERATURE COEFFICIENTS</text>')
        tc_rows = [
            ("Pmax (α)",  f"{tc_pmax:+.2f} %/°C"),
            ("Voc (β)",   f"{tc_voc:+.2f} %/°C"),
            ("Isc (γ)",   f"{tc_isc:+.2f} %/°C"),
            ("NOCT",      f"{noct:.0f} ± 2 °C"),
        ]
        for ri, (label, val) in enumerate(tc_rows):
            ry = tc_y + 12 + ri * row_h
            bg = "#f5f5f5" if ri % 2 == 0 else "#ffffff"
            svg.append(f'<rect x="30" y="{ry}" width="320" height="{row_h}" fill="{bg}" stroke="#ccc" stroke-width="0.5"/>')
            svg.append(f'<text x="38" y="{ry + 15}" font-size="9" font-family="Arial" fill="#000">{label}</text>')
            svg.append(f'<text x="342" y="{ry + 15}" text-anchor="end" font-size="9" font-weight="600" '
                       f'font-family="Arial" fill="#000000">{val}</text>')

        # ════════════════════════════════
        # RIGHT COLUMN (x=360 to 1250)
        # ════════════════════════════════
        rx = 360

        # ── Mechanical Specifications ──────────────────────────────────────
        mech_y = 72
        svg.append(f'<text x="{rx}" y="{mech_y}" font-size="10" font-weight="700" '
                   f'font-family="Arial" fill="#000">MECHANICAL SPECIFICATIONS</text>')
        mech_rows = [
            ("Dimensions (L × W × H)",   f"{length_mm:.0f} × {width_mm:.0f} × {depth_mm:.0f} mm  ({length_in:.1f} × {width_in:.1f} × {depth_in:.1f} in)"),
            ("Weight",                    f"{weight_kg} kg  ({weight_lbs:.1f} lbs)"),
            ("Cell Technology",           f"{cell_count} {cell_type}" + (" Bifacial" if bifacial else "")),
            ("Cell Configuration",        f"{cell_count}-cell {technology} configuration"),
            ("Frame",                     "Anodized aluminum alloy"),
            ("Junction Box",              "IP68, bypass diodes"),
            ("Connector",                 "MC4 compatible (± leads)"),
        ]
        for ri, (label, val) in enumerate(mech_rows):
            ry2 = mech_y + 14 + ri * row_h
            bg = "#f5f5f5" if ri % 2 == 0 else "#ffffff"
            svg.append(f'<rect x="{rx}" y="{ry2}" width="870" height="{row_h}" fill="{bg}" stroke="#ccc" stroke-width="0.5"/>')
            svg.append(f'<text x="{rx+8}" y="{ry2+15}" font-size="9" font-family="Arial" fill="#000">{label}</text>')
            svg.append(f'<text x="{rx+300}" y="{ry2+15}" font-size="9" font-weight="600" '
                       f'font-family="Arial" fill="#000000">{val}</text>')

        # ── Operating Conditions ──────────────────────────────────────────
        oc_y = mech_y + 14 + len(mech_rows) * row_h + 20
        svg.append(f'<text x="{rx}" y="{oc_y}" font-size="10" font-weight="700" '
                   f'font-family="Arial" fill="#000">OPERATING CONDITIONS</text>')
        oc_rows = [
            ("Operating Temperature Range",  "−40°C to +85°C  (−40°F to +185°F)"),
            ("Max Wind Load",                "3,600 Pa  (75.2 psf)"),
            ("Max Snow / Static Load",       "5,400 Pa  (112.8 psf)"),
            ("Max Hail Speed",               "23 m/s  (51 mph), ∅ 25mm (1\")"),
            ("Relative Humidity",            "0–100 %"),
            ("Altitude",                     "≤ 2000 m without derating"),
        ]
        for ri, (label, val) in enumerate(oc_rows):
            ry2 = oc_y + 14 + ri * row_h
            bg = "#f5f5f5" if ri % 2 == 0 else "#ffffff"
            svg.append(f'<rect x="{rx}" y="{ry2}" width="870" height="{row_h}" fill="{bg}" stroke="#ccc" stroke-width="0.5"/>')
            svg.append(f'<text x="{rx+8}" y="{ry2+15}" font-size="9" font-family="Arial" fill="#000">{label}</text>')
            svg.append(f'<text x="{rx+300}" y="{ry2+15}" font-size="9" font-weight="600" '
                       f'font-family="Arial" fill="#000000">{val}</text>')

        # ── BIPV / Bifacial Performance ──────────────────────────────────
        bif_y = oc_y + 14 + len(oc_rows) * row_h + 20
        svg.append(f'<text x="{rx}" y="{bif_y}" font-size="10" font-weight="700" '
                   f'font-family="Arial" fill="#000">BIFACIAL PERFORMANCE</text>')
        bif_rows = [
            ("Bifaciality Factor",       f"≥ {bifacial_gain:.0f} %" if bifacial else "N/A"),
            ("Rear Irradiance Gain",     "5–25 % (site dependent)" if bifacial else "N/A"),
        ] if bifacial else []
        for ri, (label, val) in enumerate(bif_rows):
            ry2 = bif_y + 14 + ri * row_h
            bg = "#f5f5f5" if ri % 2 == 0 else "#ffffff"
            svg.append(f'<rect x="{rx}" y="{ry2}" width="870" height="{row_h}" fill="{bg}" stroke="#ccc" stroke-width="0.5"/>')
            svg.append(f'<text x="{rx+8}" y="{ry2+15}" font-size="9" font-family="Arial" fill="#000">{label}</text>')
            svg.append(f'<text x="{rx+300}" y="{ry2+15}" font-size="9" font-weight="600" '
                       f'font-family="Arial" fill="#000000">{val}</text>')

        # ── I-V Curve diagram (simplified) ───────────────────────────────
        iv_x, iv_y = rx, bif_y + 14 + len(bif_rows) * row_h + 22
        iv_w, iv_h = 420, 160
        svg.append(f'<rect x="{iv_x}" y="{iv_y}" width="{iv_w}" height="{iv_h}" '
                   f'fill="#f8f9fa" stroke="#000" stroke-width="1"/>')
        svg.append(f'<text x="{iv_x + iv_w//2}" y="{iv_y + 14}" text-anchor="middle" '
                   f'font-size="9" font-weight="700" font-family="Arial" fill="#000">I-V CHARACTERISTIC CURVE (STC)</text>')
        # Axes
        ax_ox, ax_oy = iv_x + 45, iv_y + iv_h - 25
        ax_w, ax_h = iv_w - 60, iv_h - 45
        svg.append(f'<line x1="{ax_ox}" y1="{iv_y+20}" x2="{ax_ox}" y2="{ax_oy}" stroke="#000" stroke-width="1"/>')
        svg.append(f'<line x1="{ax_ox}" y1="{ax_oy}" x2="{ax_ox+ax_w}" y2="{ax_oy}" stroke="#000" stroke-width="1"/>')
        svg.append(f'<text x="{ax_ox+ax_w//2}" y="{ax_oy+18}" text-anchor="middle" '
                   f'font-size="7" font-family="Arial" fill="#333">Voltage (V) — Voc = 37.5V</text>')
        svg.append(f'<text x="{ax_ox-10}" y="{ax_oy-ax_h//2}" text-anchor="middle" '
                   f'font-size="7" font-family="Arial" fill="#333" '
                   f'transform="rotate(-90,{ax_ox-10},{ax_oy-ax_h//2})">Current (A) — Isc = 14.19A</text>')
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
        svg.append(f'<text x="{mpp_x+6:.1f}" y="{mpp_y-4:.1f}" font-size="7" font-family="Arial" fill="#e05">'
                   f'MPP ({vmp}V, {imp_val}A)</text>')
        # Tick marks
        for vi in [0, voc*0.25, voc*0.5, voc*0.75, voc]:
            tx = ax_ox + (vi / voc) * ax_w
            svg.append(f'<line x1="{tx:.1f}" y1="{ax_oy}" x2="{tx:.1f}" y2="{ax_oy+3}" stroke="#000" stroke-width="0.8"/>')
            svg.append(f'<text x="{tx:.1f}" y="{ax_oy+10}" text-anchor="middle" font-size="6" '
                       f'font-family="Arial" fill="#555">{vi}</text>')
        for ii in [0, isc*0.33, isc*0.67, isc]:
            ty = ax_oy - (ii / isc) * ax_h
            svg.append(f'<line x1="{ax_ox-3}" y1="{ty:.1f}" x2="{ax_ox}" y2="{ty:.1f}" stroke="#000" stroke-width="0.8"/>')
            svg.append(f'<text x="{ax_ox-5}" y="{ty+3:.1f}" text-anchor="end" font-size="6" '
                       f'font-family="Arial" fill="#555">{ii}</text>')

        # ── P-V Curve (power) ─────────────────────────────────────────────
        pv_x = iv_x + iv_w + 20
        pv_w, pv_h = iv_w - 10, iv_h
        svg.append(f'<rect x="{pv_x}" y="{iv_y}" width="{pv_w}" height="{pv_h}" '
                   f'fill="#f8f9fa" stroke="#000" stroke-width="1"/>')
        svg.append(f'<text x="{pv_x + pv_w//2}" y="{iv_y + 14}" text-anchor="middle" '
                   f'font-size="9" font-weight="700" font-family="Arial" fill="#000">POWER CURVE (STC)</text>')
        pax_ox, pax_oy = pv_x + 45, iv_y + pv_h - 25
        pax_w, pax_h = pv_w - 60, pv_h - 45
        svg.append(f'<line x1="{pax_ox}" y1="{iv_y+20}" x2="{pax_ox}" y2="{pax_oy}" stroke="#000" stroke-width="1"/>')
        svg.append(f'<line x1="{pax_ox}" y1="{pax_oy}" x2="{pax_ox+pax_w}" y2="{pax_oy}" stroke="#000" stroke-width="1"/>')
        svg.append(f'<text x="{pax_ox+pax_w//2}" y="{pax_oy+18}" text-anchor="middle" '
                   f'font-size="7" font-family="Arial" fill="#333">Voltage (V)</text>')
        svg.append(f'<text x="{pax_ox-10}" y="{pax_oy-pax_h//2}" text-anchor="middle" '
                   f'font-size="7" font-family="Arial" fill="#333" '
                   f'transform="rotate(-90,{pax_ox-10},{pax_oy-pax_h//2})">Power (W)</text>')
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
        svg.append(f'<text x="{mpp_px+5:.1f}" y="{mpp_py-4:.1f}" font-size="7" '
                   f'font-family="Arial" fill="#e05">Pmax = 455W</text>')

        # ── Footer note ───────────────────────────────────────────────────
        note_y = iv_y + iv_h + 16
        svg.append(f'<text x="{rx}" y="{note_y}" font-size="8" font-family="Arial" fill="#555">'
                   f'NOTE: Specifications are nominal values and subject to manufacturing tolerances. '
                   f'Refer to manufacturer\'s current datasheet for most recent specifications.</text>')

        # ── Title block ───────────────────────────────────────────────────
        svg.append(self._svg_title_block(
            VW, VH, "PV-8.1", "Module Datasheet",
            f"{mfr} {model}", "11 of 13", address, today
        ))

        content = "\n".join(svg)
        return (f'<div class="page">'
                f'<svg width="100%" height="100%" viewBox="0 0 {VW} {VH}" '
                f'xmlns="http://www.w3.org/2000/svg" style="background:#fff;">'
                f'{content}</svg></div>')

    def _build_racking_datasheet_page(self, address: str, today: str) -> str:
        """PV-8.2: IronRidge XR10 rail + bonded splice specification sheet (two-column cut sheet)."""
        VW, VH = 1280, 960
        svg = []

        # ── Arrow-head marker defs for dimension lines ─────────────────────
        svg.append('<defs>'
                   '<marker id="arr-l" markerWidth="6" markerHeight="6" refX="6" refY="3" orient="auto">'
                   '<polygon points="0,1 6,3 0,5" fill="#000"/></marker>'
                   '<marker id="arr-r" markerWidth="6" markerHeight="6" refX="0" refY="3" orient="auto">'
                   '<polygon points="6,1 0,3 6,5" fill="#000"/></marker>'
                   '</defs>')

        svg.append('<rect width="1280" height="960" fill="#ffffff"/>')
        svg.append('<rect x="20" y="20" width="1240" height="820" fill="none" stroke="#000" stroke-width="2"/>')

        # ── Two-section header: LEFT = XR10 Rail, RIGHT = XR10 Bonded Splice ──
        # Left section header (x=20–632)
        svg.append('<rect x="20" y="20" width="612" height="42" fill="#f5f5f5" stroke="#000" stroke-width="1"/>')
        svg.append('<rect x="519" y="23" width="60" height="16" fill="#e87722" rx="2"/>')
        svg.append('<text x="549" y="35" text-anchor="middle" font-size="8" font-weight="700" '
                   'font-family="Arial" fill="#ffffff">Cut Sheet</text>')
        svg.append('<text x="35" y="38" font-size="14" font-weight="700" '
                   'font-family="Arial" fill="#000">// IRONRIDGE</text>')
        svg.append('<text x="200" y="38" font-size="13" font-weight="700" '
                   'font-family="Arial" fill="#000">  XR10 Rail</text>')
        svg.append('<text x="35" y="54" font-size="9" font-family="Arial" fill="#444">'
                   '6005-T5 Extruded Aluminum  |  Clear Anodized  |  For Flush-Mount PV Arrays</text>')

        # Right section header (x=633–1260)
        svg.append('<rect x="633" y="20" width="627" height="42" fill="#f5f5f5" stroke="#000" stroke-width="1"/>')
        svg.append('<rect x="1133" y="23" width="60" height="16" fill="#e87722" rx="2"/>')
        svg.append('<text x="1163" y="35" text-anchor="middle" font-size="8" font-weight="700" '
                   'font-family="Arial" fill="#ffffff">Cut Sheet</text>')
        svg.append('<text x="648" y="38" font-size="14" font-weight="700" '
                   'font-family="Arial" fill="#000">// IRONRIDGE</text>')
        svg.append('<text x="813" y="38" font-size="13" font-weight="700" '
                   'font-family="Arial" fill="#000">  XR10 Bonded Splice</text>')
        svg.append('<text x="648" y="54" font-size="9" font-family="Arial" fill="#444">'
                   'For Splicing and Bonding IronRidge XR10 Rail Sections  |  Includes Self-Tapping Screws</text>')

        # Vertical divider between two cut-sheet sections
        svg.append('<line x1="633" y1="62" x2="633" y2="840" stroke="#000" stroke-width="1.5"/>')

        # ── Left column: cross-section diagram ───────────────────────────
        svg.append('<text x="35" y="82" font-size="11" font-weight="700" '
                   'font-family="Arial" fill="#000">XR10 RAIL CROSS-SECTION PROFILE</text>')
        svg.append('<text x="180" y="95" text-anchor="middle" font-size="9" '
                   'font-family="Arial" fill="#555">(N.T.S.)</text>')

        # C-channel cross section drawing
        cs_x, cs_y = 55, 110
        cs_w, cs_h = 250, 170  # scaled representation

        # Overall rail outer profile (C-channel shape)
        # Dimensions: 1.72" H x 2.22" W, wall ~0.099" (2.5mm)
        t = 14  # wall thickness in drawing units
        # Draw C-channel: top flange, web left, bottom flange
        rail_pts = (
            f"{cs_x},{cs_y} "                        # top-left outer
            f"{cs_x+cs_w},{cs_y} "                   # top-right outer
            f"{cs_x+cs_w},{cs_y+t} "                 # top-right inner (top flange bottom)
            f"{cs_x+t},{cs_y+t} "                    # top-left inner (web starts)
            f"{cs_x+t},{cs_y+cs_h-t} "               # bottom-left inner (web ends)
            f"{cs_x+cs_w},{cs_y+cs_h-t} "            # bottom-right inner (bottom flange top)
            f"{cs_x+cs_w},{cs_y+cs_h} "              # bottom-right outer
            f"{cs_x},{cs_y+cs_h} "                   # bottom-left outer
        )
        svg.append(f'<polygon points="{rail_pts}" fill="#b8c8d8" stroke="#000" stroke-width="2"/>')

        # T-slot channel in web (simplified)
        tslot_x = cs_x + t + 10
        tslot_w = 18
        tslot_inner_y = cs_y + t
        tslot_inner_h = cs_h - 2 * t
        svg.append(f'<rect x="{tslot_x}" y="{tslot_inner_y}" width="{tslot_w}" height="{tslot_inner_h}" '
                   f'fill="#e8f0f8" stroke="#555" stroke-width="0.8"/>')
        svg.append(f'<text x="{tslot_x + tslot_w//2}" y="{tslot_inner_y + tslot_inner_h//2 + 3}" '
                   f'text-anchor="middle" font-size="7" font-family="Arial" fill="#333">T-SLOT</text>')

        # Dimension lines on cross-section
        # Width (top)
        dim_y_top = cs_y - 20
        svg.append(f'<line x1="{cs_x}" y1="{cs_y}" x2="{cs_x}" y2="{dim_y_top-3}" stroke="#000" stroke-width="0.5"/>')
        svg.append(f'<line x1="{cs_x+cs_w}" y1="{cs_y}" x2="{cs_x+cs_w}" y2="{dim_y_top-3}" stroke="#000" stroke-width="0.5"/>')
        svg.append(f'<line x1="{cs_x}" y1="{dim_y_top}" x2="{cs_x+cs_w}" y2="{dim_y_top}" '
                   f'stroke="#000" stroke-width="0.8" marker-start="url(#arr-l)" marker-end="url(#arr-r)"/>')
        svg.append(f'<text x="{cs_x+cs_w//2}" y="{dim_y_top-5}" text-anchor="middle" '
                   f'font-size="9" font-family="Arial" fill="#000">2.22" (56.4mm)</text>')
        # Height (right)
        dim_x_right = cs_x + cs_w + 18
        svg.append(f'<line x1="{cs_x+cs_w}" y1="{cs_y}" x2="{dim_x_right+3}" y2="{cs_y}" stroke="#000" stroke-width="0.5"/>')
        svg.append(f'<line x1="{cs_x+cs_w}" y1="{cs_y+cs_h}" x2="{dim_x_right+3}" y2="{cs_y+cs_h}" stroke="#000" stroke-width="0.5"/>')
        svg.append(f'<line x1="{dim_x_right}" y1="{cs_y}" x2="{dim_x_right}" y2="{cs_y+cs_h}" '
                   f'stroke="#000" stroke-width="0.8" marker-start="url(#arr-l)" marker-end="url(#arr-r)"/>')
        svg.append(f'<text x="{dim_x_right+10}" y="{cs_y+cs_h//2+4}" font-size="9" '
                   f'font-family="Arial" fill="#000">1.72"</text>')
        # Wall thickness
        svg.append(f'<text x="{cs_x+t//2}" y="{cs_y+cs_h+20}" text-anchor="middle" '
                   f'font-size="8" font-family="Arial" fill="#555">t = 0.099"</text>')

        # Isometric perspective of a rail section (right of cross-section)
        rp_x, rp_y = cs_x + cs_w + 80, cs_y + 10
        rp_len = 130  # length of the perspective view
        rp_d = 35     # depth foreshortening
        rp_h_s = cs_h * 0.6  # scaled height
        rp_w_s = cs_w * 0.4  # scaled width
        # Draw 3D extruded C-channel (simplified perspective)
        # Front face (same C-channel but smaller)
        def rail3d(x, y):
            # Isometric projection offset
            return x + rp_x, y + rp_y
        # Top plane
        svg.append(f'<polygon points="'
                   f'{rp_x},{rp_y} {rp_x+rp_len},{rp_y-rp_d} '
                   f'{rp_x+rp_len+rp_w_s},{rp_y-rp_d} {rp_x+rp_w_s},{rp_y}" '
                   f'fill="#d0dce8" stroke="#000" stroke-width="1"/>')
        # Front face (C-channel)
        svg.append(f'<polygon points="'
                   f'{rp_x},{rp_y} {rp_x+rp_w_s},{rp_y} '
                   f'{rp_x+rp_w_s},{rp_y+rp_h_s} {rp_x},{rp_y+rp_h_s}" '
                   f'fill="#b8c8d8" stroke="#000" stroke-width="1"/>')
        # Bottom plane
        svg.append(f'<polygon points="'
                   f'{rp_x},{rp_y+rp_h_s} {rp_x+rp_w_s},{rp_y+rp_h_s} '
                   f'{rp_x+rp_len+rp_w_s},{rp_y+rp_h_s-rp_d} {rp_x+rp_len},{rp_y+rp_h_s-rp_d}" '
                   f'fill="#a0b0c0" stroke="#000" stroke-width="1"/>')
        svg.append(f'<text x="{rp_x+rp_len//2}" y="{rp_y+rp_h_s+22}" text-anchor="middle" '
                   f'font-size="9" font-family="Arial" fill="#333">ISOMETRIC VIEW (N.T.S.)</text>')
        # Length annotation
        svg.append(f'<text x="{rp_x+rp_len//2}" y="{rp_y-rp_d-10}" text-anchor="middle" '
                   f'font-size="8" font-family="Arial" fill="#555">Available: 168" or 204"</text>')

        # ── Structural Properties table (left column) ─────────────────────
        sp_y = cs_y + cs_h + 60
        svg.append(f'<text x="35" y="{sp_y}" font-size="10" font-weight="700" '
                   f'font-family="Arial" fill="#000">STRUCTURAL PROPERTIES</text>')
        sp_rows = [
            ("Extrusion Alloy",                "6005-T5 Aluminum"),
            ("Surface Finish",                 "Clear Anodized (Class I)"),
            ("Yield Strength (Fty)",           "35 ksi (241 MPa)"),
            ("Ultimate Tensile Strength (Ftu)", "38 ksi (262 MPa)"),
            ("Modulus of Elasticity",          "10,100 ksi (69.6 GPa)"),
            ("Moment of Inertia (Ix)",         "0.425 in⁴"),
            ("Section Modulus (Sx)",           "0.293 in³"),
            ("Weight",                         "0.88 lb/ft  (1.31 kg/m)"),
        ]
        row_h = 24
        for ri, (label, val) in enumerate(sp_rows):
            ry = sp_y + 14 + ri * row_h
            bg = "#f5f5f5" if ri % 2 == 0 else "#ffffff"
            svg.append(f'<rect x="30" y="{ry}" width="560" height="{row_h}" fill="{bg}" stroke="#ccc" stroke-width="0.5"/>')
            svg.append(f'<text x="38" y="{ry+16}" font-size="9" font-family="Arial" fill="#000">{label}</text>')
            svg.append(f'<text x="582" y="{ry+16}" text-anchor="end" font-size="9" font-weight="600" '
                       f'font-family="Arial" fill="#000000">{val}</text>')

        # ── Span / Load Table ──────────────────────────────────────────────
        sl_y = sp_y + 14 + len(sp_rows) * row_h + 22
        svg.append(f'<text x="35" y="{sl_y}" font-size="10" font-weight="700" '
                   f'font-family="Arial" fill="#000">ALLOWABLE LOAD vs. SPAN (UDL)</text>')
        svg.append(f'<text x="35" y="{sl_y+14}" font-size="8" font-family="Arial" fill="#555">'
                   f'Maximum uniformly distributed load (lb/ft) per IBC 2021 — Single span, L/180 deflection limit</text>')
        # Table header
        th_y = sl_y + 26
        headers = ["Span", "24\"", "36\"", "48\"", "60\"", "72\"", "84\"", "96\""]
        col_w = 72
        svg.append(f'<rect x="30" y="{th_y}" width="{len(headers)*col_w+10}" height="22" '
                   f'fill="#e8e8e8" stroke="#000" stroke-width="0.5"/>')
        for ci, hdr in enumerate(headers):
            svg.append(f'<text x="{30+ci*col_w+col_w//2+5}" y="{th_y+15}" text-anchor="middle" '
                       f'font-size="9" font-weight="700" font-family="Arial" fill="#000">{hdr}</text>')
        # Data rows (Allowable UDL for XR10)
        load_data = [
            ("XR10", "820", "364", "205", "131", "91", "67", "51"),
        ]
        for ri, row_data in enumerate(load_data):
            ry2 = th_y + 22 + ri * row_h
            svg.append(f'<rect x="30" y="{ry2}" width="{len(headers)*col_w+10}" height="{row_h}" '
                       f'fill="#f5f5f5" stroke="#ccc" stroke-width="0.5"/>')
            for ci, cell in enumerate(row_data):
                svg.append(f'<text x="{30+ci*col_w+col_w//2+5}" y="{ry2+16}" text-anchor="middle" '
                           f'font-size="9" font-weight="600" font-family="Arial" fill="#000">{cell}</text>')
        svg.append(f'<text x="35" y="{th_y+22+len(load_data)*row_h+14}" font-size="7" '
                   f'font-family="Arial" fill="#666" font-style="italic">'
                   f'Values in lb/ft. Consult IronRidge engineering specs for complete loading tables.</text>')

        # ── Left column: Part Numbers table (Cubillas 5-col format) ───────
        pnl_y = th_y + 22 + len(load_data) * row_h + 34
        svg.append(f'<text x="35" y="{pnl_y}" font-size="10" font-weight="700" '
                   f'font-family="Arial" fill="#000">PART NUMBERS</text>')
        pnl_col_widths = [95, 95, 185, 145, 70]   # total = 590 (x=30 to x=620)
        pnl_col_labels = ["Clear Part #", "Black Part #", "Description / Length", "Material", "Weight"]
        pnl_hdr_y = pnl_y + 14
        pnl_x_starts = [30]
        for cw in pnl_col_widths[:-1]:
            pnl_x_starts.append(pnl_x_starts[-1] + cw)
        svg.append(f'<rect x="30" y="{pnl_hdr_y}" width="590" height="22" '
                   f'fill="#e8e8e8" stroke="#000" stroke-width="0.5"/>')
        for ci, (hdr, xs) in enumerate(zip(pnl_col_labels, pnl_x_starts)):
            svg.append(f'<text x="{xs+6}" y="{pnl_hdr_y+15}" font-size="8" font-weight="700" '
                       f'font-family="Arial" fill="#000">{hdr}</text>')
        pnl_rows = [
            ("XR-10-168A", "XR-10-168B", "XR10 Rail, 168\" (14 ft)",  "6005-T5 Alum., Clear Anodized", "12.3 lb"),
            ("XR-10-204A", "XR-10-204B", "XR10 Rail, 204\" (17 ft)",  "6005-T5 Alum., Clear Anodized", "14.9 lb"),
        ]
        for ri, row_cells in enumerate(pnl_rows):
            pnl_ry = pnl_hdr_y + 22 + ri * 22
            bg = "#f5f5f5" if ri % 2 == 0 else "#ffffff"
            svg.append(f'<rect x="30" y="{pnl_ry}" width="590" height="22" '
                       f'fill="{bg}" stroke="#ccc" stroke-width="0.5"/>')
            for ci, (cell, xs) in enumerate(zip(row_cells, pnl_x_starts)):
                fw = "700" if ci == 0 else "400"
                svg.append(f'<text x="{xs+6}" y="{pnl_ry+15}" font-size="8" font-weight="{fw}" '
                           f'font-family="Arial" fill="#000">{cell}</text>')

        # ── Right column: XR10 Bonded Splice Cut Sheet ────────────────────
        rx2 = 648         # right col left edge (inside divider at 633)
        rc_cx = 946       # right col centre x

        # ── Assembly overview diagram ──────────────────────────────────────
        svg.append(f'<text x="{rx2}" y="73" font-size="11" font-weight="700" '
                   f'font-family="Arial" fill="#000">XR10 BONDED SPLICE — ASSEMBLY OVERVIEW</text>')
        svg.append(f'<text x="{rx2+430}" y="73" font-size="8" font-family="Arial" fill="#555">(N.T.S.)</text>')

        ov_y = 88
        ov_h = 48          # rail cross-section height in diagram
        ov_rail_w = 155    # length of each rail section
        ov_gap = 32        # gap between the two rail ends
        ov_splice_w = ov_gap + 44  # splice overlaps 22px into each rail

        # Left rail section (solid rect representing C-channel end)
        lr_x = rc_cx - ov_gap // 2 - ov_rail_w
        svg.append(f'<rect x="{lr_x}" y="{ov_y}" width="{ov_rail_w}" height="{ov_h}" '
                   f'fill="#b8c8d8" stroke="#000" stroke-width="1.5"/>')
        # Hatching to suggest open channel end
        for hi in range(0, ov_h, 8):
            svg.append(f'<line x1="{lr_x+ov_rail_w-10}" y1="{ov_y+hi}" '
                       f'x2="{lr_x+ov_rail_w}" y2="{ov_y+min(hi+10,ov_h)}" '
                       f'stroke="#6090b0" stroke-width="0.7"/>')
        svg.append(f'<text x="{lr_x + ov_rail_w//2}" y="{ov_y + ov_h + 14}" '
                   f'text-anchor="middle" font-size="8" font-family="Arial" fill="#444">XR10 Rail A</text>')

        # Right rail section
        rr_x = rc_cx + ov_gap // 2
        svg.append(f'<rect x="{rr_x}" y="{ov_y}" width="{ov_rail_w}" height="{ov_h}" '
                   f'fill="#b8c8d8" stroke="#000" stroke-width="1.5"/>')
        for hi in range(0, ov_h, 8):
            svg.append(f'<line x1="{rr_x}" y1="{ov_y+hi}" '
                       f'x2="{rr_x+10}" y2="{ov_y+min(hi+10,ov_h)}" '
                       f'stroke="#6090b0" stroke-width="0.7"/>')
        svg.append(f'<text x="{rr_x + ov_rail_w//2}" y="{ov_y + ov_h + 14}" '
                   f'text-anchor="middle" font-size="8" font-family="Arial" fill="#444">XR10 Rail B</text>')

        # Bonded splice (shown inset inside both rails)
        sp_ov_x = rc_cx - ov_splice_w // 2
        sp_inset = 5
        svg.append(f'<rect x="{sp_ov_x}" y="{ov_y + sp_inset}" '
                   f'width="{ov_splice_w}" height="{ov_h - 2*sp_inset}" '
                   f'fill="#e8c46a" stroke="#8b6914" stroke-width="2" rx="2"/>')
        svg.append(f'<text x="{rc_cx}" y="{ov_y + ov_h//2 + 4}" '
                   f'text-anchor="middle" font-size="8" font-weight="700" '
                   f'font-family="Arial" fill="#5a4010">SPLICE</text>')

        # Self-tapping screws on splice (×2 visible from side)
        for sc_off in [-14, 14]:
            scx = rc_cx + sc_off
            scy = ov_y + sp_inset
            svg.append(f'<circle cx="{scx}" cy="{scy}" r="5" fill="#c0c8d0" stroke="#333" stroke-width="1"/>')
            svg.append(f'<line x1="{scx-4}" y1="{scy}" x2="{scx+4}" y2="{scy}" stroke="#555" stroke-width="0.8"/>')
            svg.append(f'<line x1="{scx}" y1="{scy-4}" x2="{scx}" y2="{scy+4}" stroke="#555" stroke-width="0.8"/>')

        # Callout: screws
        svg.append(f'<text x="{rc_cx}" y="{ov_y-10}" text-anchor="middle" '
                   f'font-size="8" font-family="Arial" fill="#000">Self-Tapping Screws (×4 per splice)</text>')
        svg.append(f'<line x1="{rc_cx-14}" y1="{ov_y-4}" x2="{rc_cx-14}" y2="{ov_y+sp_inset}" '
                   f'stroke="#000" stroke-width="0.7" stroke-dasharray="3,2"/>')

        svg.append(f'<line x1="{rx2+10}" y1="162" x2="1248" y2="162" stroke="#ccc" stroke-width="0.8"/>')

        # ── Section 1: Splice dimensional drawing ─────────────────────────
        svg.append(f'<text x="{rx2}" y="178" font-size="10" font-weight="700" '
                   f'font-family="Arial" fill="#000">1)  Splice, XR10, Mill  —  12" long</text>')

        # Splice front view rectangle (12" length, .88" height)
        spl_x = rx2 + 35
        spl_y = 195
        spl_draw_w = 280   # represents 12" (23.3 px/inch)
        spl_draw_h = 24    # represents .88" (approx 27 px/inch — not to same scale)
        svg.append(f'<rect x="{spl_x}" y="{spl_y}" width="{spl_draw_w}" height="{spl_draw_h}" '
                   f'fill="#d8e8f4" stroke="#000" stroke-width="1.5" rx="1"/>')

        # Diagonal hatching on splice (material symbol)
        for hxi in range(8, spl_draw_w - 4, 12):
            hx = spl_x + hxi
            svg.append(f'<line x1="{hx}" y1="{spl_y}" '
                       f'x2="{min(hx + spl_draw_h, spl_x + spl_draw_w)}" y2="{min(spl_y + spl_draw_h, spl_y + spl_draw_h)}" '
                       f'stroke="#8aaac8" stroke-width="0.5"/>')

        # Length dimension (below splice)
        dim_spl_bot = spl_y + spl_draw_h + 14
        svg.append(f'<line x1="{spl_x}" y1="{spl_y+spl_draw_h}" x2="{spl_x}" y2="{dim_spl_bot-2}" '
                   f'stroke="#000" stroke-width="0.5"/>')
        svg.append(f'<line x1="{spl_x+spl_draw_w}" y1="{spl_y+spl_draw_h}" '
                   f'x2="{spl_x+spl_draw_w}" y2="{dim_spl_bot-2}" stroke="#000" stroke-width="0.5"/>')
        svg.append(f'<line x1="{spl_x}" y1="{dim_spl_bot}" x2="{spl_x+spl_draw_w}" y2="{dim_spl_bot}" '
                   f'stroke="#000" stroke-width="0.8" marker-start="url(#arr-l)" marker-end="url(#arr-r)"/>')
        svg.append(f'<text x="{spl_x+spl_draw_w//2}" y="{dim_spl_bot+12}" text-anchor="middle" '
                   f'font-size="9" font-family="Arial" fill="#000">12.0"</text>')

        # Width (.88") and depth (.60") annotations to the right
        dim_spl_rx = spl_x + spl_draw_w + 18
        svg.append(f'<line x1="{spl_x+spl_draw_w}" y1="{spl_y}" x2="{dim_spl_rx-2}" y2="{spl_y}" '
                   f'stroke="#000" stroke-width="0.5"/>')
        svg.append(f'<line x1="{spl_x+spl_draw_w}" y1="{spl_y+spl_draw_h}" x2="{dim_spl_rx-2}" y2="{spl_y+spl_draw_h}" '
                   f'stroke="#000" stroke-width="0.5"/>')
        svg.append(f'<line x1="{dim_spl_rx}" y1="{spl_y}" x2="{dim_spl_rx}" y2="{spl_y+spl_draw_h}" '
                   f'stroke="#000" stroke-width="0.8" marker-start="url(#arr-l)" marker-end="url(#arr-r)"/>')
        svg.append(f'<text x="{dim_spl_rx+8}" y="{spl_y+spl_draw_h//2+4}" '
                   f'font-size="9" font-family="Arial" fill="#000">.88" W × .60" D</text>')

        # ── Splice material property table ────────────────────────────────
        spt_y = dim_spl_bot + 26
        svg.append(f'<rect x="{rx2+10}" y="{spt_y}" width="580" height="22" '
                   f'fill="#e8e8e8" stroke="#000" stroke-width="0.5"/>')
        svg.append(f'<text x="{rx2+18}" y="{spt_y+15}" font-size="8" font-weight="700" '
                   f'font-family="Arial" fill="#000">Property</text>')
        svg.append(f'<text x="{rx2+220}" y="{spt_y+15}" font-size="8" font-weight="700" '
                   f'font-family="Arial" fill="#000">Value</text>')
        splice_props = [
            ("Material",    "6000 Series Aluminum"),
            ("Finish",      "Mill"),
            ("Part Number", "XR-10-SPLC-M1"),
        ]
        for ri, (lbl, val) in enumerate(splice_props):
            ry_sp = spt_y + 22 + ri * 22
            bg = "#f5f5f5" if ri % 2 == 0 else "#ffffff"
            svg.append(f'<rect x="{rx2+10}" y="{ry_sp}" width="580" height="22" '
                       f'fill="{bg}" stroke="#ccc" stroke-width="0.5"/>')
            svg.append(f'<text x="{rx2+18}" y="{ry_sp+15}" font-size="9" font-family="Arial" fill="#000">{lbl}</text>')
            svg.append(f'<text x="{rx2+220}" y="{ry_sp+15}" font-size="9" font-weight="600" '
                       f'font-family="Arial" fill="#000">{val}</text>')

        # ── Section 2: Screw dimensional drawing ──────────────────────────
        scr_sec_y = spt_y + 22 + len(splice_props) * 22 + 24
        svg.append(f'<text x="{rx2}" y="{scr_sec_y}" font-size="10" font-weight="700" '
                   f'font-family="Arial" fill="#000">2)  Screw, Self Drilling  —  #12-14 TYPE "B" THREAD</text>')

        # Screw side-view: scale = 150 px per inch
        scr_sc = 150      # px per inch
        scr_tot = int(0.63 * scr_sc)   # 94px total length
        scr_hd  = int(0.31 * scr_sc)   # 46px head length
        scr_shd = int(0.42 * scr_sc)   # 63px shank diameter
        scr_hdiam = scr_shd + 12       # head slightly taller (75px)
        scr_x = rx2 + 70
        scr_y = scr_sec_y + 36

        # Head (tapered trapezoid — hex drive representation)
        scr_hd_pts = (
            f"{scr_x},{scr_y + (scr_hdiam - scr_shd)//2} "
            f"{scr_x + scr_hd},{scr_y} "
            f"{scr_x + scr_hd},{scr_y + scr_hdiam} "
            f"{scr_x},{scr_y + scr_hdiam - (scr_hdiam - scr_shd)//2}"
        )
        svg.append(f'<polygon points="{scr_hd_pts}" fill="#c8d8e8" stroke="#000" stroke-width="1.5"/>')
        # Cross slot on head
        scr_hcx = scr_x + scr_hd // 3
        scr_hcy = scr_y + scr_hdiam // 2
        svg.append(f'<line x1="{scr_hcx-7}" y1="{scr_hcy}" x2="{scr_hcx+7}" y2="{scr_hcy}" '
                   f'stroke="#555" stroke-width="1.5"/>')
        svg.append(f'<line x1="{scr_hcx}" y1="{scr_hcy-7}" x2="{scr_hcx}" y2="{scr_hcy+7}" '
                   f'stroke="#555" stroke-width="1.5"/>')

        # Shank (threaded cylinder)
        shk_x = scr_x + scr_hd
        shk_y = scr_y + (scr_hdiam - scr_shd) // 2
        shk_len = scr_tot - scr_hd
        svg.append(f'<rect x="{shk_x}" y="{shk_y}" width="{shk_len}" height="{scr_shd}" '
                   f'fill="#d8eaf8" stroke="#000" stroke-width="1.5"/>')
        # Thread lines (diagonal)
        for ti in range(4, shk_len - 4, 7):
            svg.append(f'<line x1="{shk_x+ti}" y1="{shk_y}" x2="{shk_x+ti+6}" y2="{shk_y+scr_shd}" '
                       f'stroke="#7090b0" stroke-width="0.5"/>')

        # Self-drill tip (triangle)
        tip_bx = shk_x + shk_len
        tip_pts = (
            f"{tip_bx},{shk_y} "
            f"{tip_bx+14},{shk_y + scr_shd//2} "
            f"{tip_bx},{shk_y + scr_shd}"
        )
        svg.append(f'<polygon points="{tip_pts}" fill="#b8c8d8" stroke="#000" stroke-width="1"/>')

        # Total length dimension (above screw)
        scr_dim_top = scr_y - 16
        svg.append(f'<line x1="{scr_x}" y1="{scr_y}" x2="{scr_x}" y2="{scr_dim_top-2}" '
                   f'stroke="#000" stroke-width="0.5"/>')
        tip_rx = tip_bx + 14
        svg.append(f'<line x1="{tip_rx}" y1="{shk_y+scr_shd//2}" x2="{tip_rx}" y2="{scr_dim_top-2}" '
                   f'stroke="#000" stroke-width="0.5"/>')
        svg.append(f'<line x1="{scr_x}" y1="{scr_dim_top}" x2="{tip_rx}" y2="{scr_dim_top}" '
                   f'stroke="#000" stroke-width="0.8" marker-start="url(#arr-l)" marker-end="url(#arr-r)"/>')
        svg.append(f'<text x="{scr_x + (tip_rx-scr_x)//2}" y="{scr_dim_top-4}" text-anchor="middle" '
                   f'font-size="9" font-family="Arial" fill="#000">.63" Total</text>')

        # Head length dimension (below, bracketing head only)
        scr_bot = scr_y + scr_hdiam
        scr_dim_bot = scr_bot + 16
        svg.append(f'<line x1="{scr_x}" y1="{scr_bot}" x2="{scr_x}" y2="{scr_dim_bot-2}" '
                   f'stroke="#000" stroke-width="0.5"/>')
        svg.append(f'<line x1="{scr_x+scr_hd}" y1="{scr_bot}" x2="{scr_x+scr_hd}" y2="{scr_dim_bot-2}" '
                   f'stroke="#000" stroke-width="0.5"/>')
        svg.append(f'<line x1="{scr_x}" y1="{scr_dim_bot}" x2="{scr_x+scr_hd}" y2="{scr_dim_bot}" '
                   f'stroke="#000" stroke-width="0.8" marker-start="url(#arr-l)" marker-end="url(#arr-r)"/>')
        svg.append(f'<text x="{scr_x+scr_hd//2}" y="{scr_dim_bot+12}" text-anchor="middle" '
                   f'font-size="9" font-family="Arial" fill="#000">.31" Head</text>')

        # Shank diameter dimension (right side)
        scr_dim_rx = tip_rx + 22
        svg.append(f'<line x1="{shk_x + shk_len//2}" y1="{shk_y}" x2="{scr_dim_rx-2}" y2="{shk_y}" '
                   f'stroke="#000" stroke-width="0.5"/>')
        svg.append(f'<line x1="{shk_x + shk_len//2}" y1="{shk_y+scr_shd}" x2="{scr_dim_rx-2}" y2="{shk_y+scr_shd}" '
                   f'stroke="#000" stroke-width="0.5"/>')
        svg.append(f'<line x1="{scr_dim_rx}" y1="{shk_y}" x2="{scr_dim_rx}" y2="{shk_y+scr_shd}" '
                   f'stroke="#000" stroke-width="0.8" marker-start="url(#arr-l)" marker-end="url(#arr-r)"/>')
        svg.append(f'<text x="{scr_dim_rx+8}" y="{shk_y + scr_shd//2 + 4}" '
                   f'font-size="9" font-family="Arial" fill="#000">Ø .42"</text>')

        # ── Screw material property table ─────────────────────────────────
        scrpt_y = scr_bot + 46
        svg.append(f'<rect x="{rx2+10}" y="{scrpt_y}" width="580" height="22" '
                   f'fill="#e8e8e8" stroke="#000" stroke-width="0.5"/>')
        svg.append(f'<text x="{rx2+18}" y="{scrpt_y+15}" font-size="8" font-weight="700" '
                   f'font-family="Arial" fill="#000">Property</text>')
        svg.append(f'<text x="{rx2+220}" y="{scrpt_y+15}" font-size="8" font-weight="700" '
                   f'font-family="Arial" fill="#000">Value</text>')
        screw_props = [
            ("Material",    "300 Series Stainless Steel"),
            ("Finish",      "Clear"),
            ('Thread',      '#12-14 TYPE "B" SELF-DRILLING'),
        ]
        for ri, (lbl, val) in enumerate(screw_props):
            ry_sc = scrpt_y + 22 + ri * 22
            bg = "#f5f5f5" if ri % 2 == 0 else "#ffffff"
            svg.append(f'<rect x="{rx2+10}" y="{ry_sc}" width="580" height="22" '
                       f'fill="{bg}" stroke="#ccc" stroke-width="0.5"/>')
            svg.append(f'<text x="{rx2+18}" y="{ry_sc+15}" font-size="9" font-family="Arial" fill="#000">{lbl}</text>')
            svg.append(f'<text x="{rx2+220}" y="{ry_sc+15}" font-size="9" font-weight="600" '
                       f'font-family="Arial" fill="#000">{val}</text>')

        # ── Title block ───────────────────────────────────────────────────
        svg.append(self._svg_title_block(
            VW, VH, "PV-8.2", "Racking Datasheet",
            "IronRidge XR10 Flush Mount Rail System", "12 of 13", address, today
        ))

        content = "\n".join(svg)
        return (f'<div class="page">'
                f'<svg width="100%" height="100%" viewBox="0 0 {VW} {VH}" '
                f'xmlns="http://www.w3.org/2000/svg" style="background:#fff;">'
                f'{content}</svg></div>')

    def _build_attachment_datasheet_page(self, address: str, today: str) -> str:
        """PV-8.3: IronRidge FlashFoot2 roof attachment specification sheet."""
        VW, VH = 1280, 960
        svg = []

        svg.append('<rect width="1280" height="960" fill="#ffffff"/>')
        svg.append('<rect x="20" y="20" width="1240" height="820" fill="none" stroke="#000" stroke-width="2"/>')

        # ── Header ────────────────────────────────────────────────────────
        svg.append('<rect x="20" y="20" width="1240" height="42" fill="#f5f5f5" stroke="#000" stroke-width="1"/>')
        svg.append('<text x="640" y="37" text-anchor="middle" font-size="14" font-weight="700" '
                   'font-family="Arial" fill="#000000">IRONRIDGE — FLASHFOOT2 ROOF ATTACHMENT</text>')
        svg.append('<text x="640" y="53" text-anchor="middle" font-size="11" font-family="Arial" '
                   'fill="#444444">Flush-Mount Lag Bolt Attachment | EPDM Flashing | For Composite Shingle Roofs</text>')

        row_h = 24

        # ── Left column: exploded view diagram ───────────────────────────
        svg.append('<text x="35" y="82" font-size="11" font-weight="700" '
                   'font-family="Arial" fill="#000">FLASHFOOT2 COMPONENT DIAGRAM (EXPLODED)</text>')

        # Draw exploded view of FlashFoot2 components (side profile)
        exp_x, exp_y = 55, 100
        exp_cx = exp_x + 200  # center x for aligned components

        # Component 1: Cap (top)
        cap_y = exp_y
        svg.append(f'<rect x="{exp_cx-30}" y="{cap_y}" width="60" height="18" rx="4" '
                   f'fill="#d0d8e0" stroke="#000" stroke-width="1.5"/>')
        svg.append(f'<text x="{exp_cx}" y="{cap_y+13}" text-anchor="middle" '
                   f'font-size="8" font-weight="600" font-family="Arial" fill="#000">CAP</text>')
        svg.append(f'<text x="{exp_cx+50}" y="{cap_y+12}" font-size="8" '
                   f'font-family="Arial" fill="#555">6063-T5 Aluminum</text>')
        # leader line
        svg.append(f'<line x1="{exp_cx+32}" y1="{cap_y+9}" x2="{exp_cx+46}" y2="{cap_y+9}" '
                   f'stroke="#666" stroke-width="0.7"/>')
        svg.append(f'<circle cx="{exp_cx+30}" cy="{cap_y+9}" r="1.5" fill="#666"/>')

        # Component 2: Base (below cap)
        base_y = cap_y + 40
        svg.append(f'<rect x="{exp_cx-38}" y="{base_y}" width="76" height="22" rx="3" '
                   f'fill="#c0c8d0" stroke="#000" stroke-width="1.5"/>')
        svg.append(f'<rect x="{exp_cx-28}" y="{base_y+2}" width="56" height="18" rx="2" '
                   f'fill="#a8b8c8" stroke="#888" stroke-width="0.5"/>')
        svg.append(f'<text x="{exp_cx}" y="{base_y+14}" text-anchor="middle" '
                   f'font-size="8" font-weight="600" font-family="Arial" fill="#000">BASE</text>')
        svg.append(f'<text x="{exp_cx+52}" y="{base_y+14}" font-size="8" '
                   f'font-family="Arial" fill="#555">6063-T5 Aluminum</text>')
        svg.append(f'<line x1="{exp_cx+38}" y1="{base_y+11}" x2="{exp_cx+50}" y2="{base_y+11}" '
                   f'stroke="#666" stroke-width="0.7"/>')

        # Component 3: EPDM gasket / flashing
        gsk_y = base_y + 44
        svg.append(f'<ellipse cx="{exp_cx}" cy="{gsk_y+15}" rx="55" ry="14" '
                   f'fill="#2a2a2a" stroke="#000" stroke-width="1"/>')
        svg.append(f'<ellipse cx="{exp_cx}" cy="{gsk_y+15}" rx="38" ry="9" '
                   f'fill="#444" stroke="#666" stroke-width="0.5"/>')
        svg.append(f'<text x="{exp_cx}" y="{gsk_y+19}" text-anchor="middle" '
                   f'font-size="7" font-weight="600" font-family="Arial" fill="#fff">EPDM</text>')
        svg.append(f'<text x="{exp_cx+70}" y="{gsk_y+18}" font-size="8" '
                   f'font-family="Arial" fill="#555">EPDM Rubber Gasket</text>')
        svg.append(f'<text x="{exp_cx+70}" y="{gsk_y+30}" font-size="8" '
                   f'font-family="Arial" fill="#555">12" Round Aluminum Flash</text>')
        svg.append(f'<line x1="{exp_cx+56}" y1="{gsk_y+15}" x2="{exp_cx+68}" y2="{gsk_y+15}" '
                   f'stroke="#666" stroke-width="0.7"/>')

        # Component 4: Lag bolt
        bolt_y = gsk_y + 50
        bolt_head_y = bolt_y + 5
        svg.append(f'<polygon points="{exp_cx-8},{bolt_head_y} {exp_cx+8},{bolt_head_y} '
                   f'{exp_cx+8},{bolt_head_y+12} {exp_cx-8},{bolt_head_y+12}" '
                   f'fill="#888" stroke="#000" stroke-width="1"/>')
        svg.append(f'<rect x="{exp_cx-3}" y="{bolt_head_y+12}" width="6" height="50" '
                   f'fill="#999" stroke="#555" stroke-width="0.8"/>')
        # Thread lines
        for ti in range(0, 45, 5):
            ty = bolt_head_y + 12 + ti
            svg.append(f'<line x1="{exp_cx-5}" y1="{ty}" x2="{exp_cx+5}" y2="{ty+3}" '
                       f'stroke="#666" stroke-width="0.5"/>')
        svg.append(f'<text x="{exp_cx+22}" y="{bolt_head_y+30}" font-size="8" '
                   f'font-family="Arial" fill="#555">5/16" × 2.5" Lag Bolt</text>')
        svg.append(f'<text x="{exp_cx+22}" y="{bolt_head_y+42}" font-size="8" '
                   f'font-family="Arial" fill="#555">304 Stainless Steel</text>')
        svg.append(f'<line x1="{exp_cx+8}" y1="{bolt_head_y+20}" x2="{exp_cx+20}" y2="{bolt_head_y+20}" '
                   f'stroke="#666" stroke-width="0.7"/>')

        # Dimension annotations
        total_h_px = (bolt_head_y + 62) - cap_y
        dim_x_left = exp_cx - 80
        svg.append(f'<line x1="{dim_x_left}" y1="{cap_y}" x2="{exp_cx-42}" y2="{cap_y}" '
                   f'stroke="#000" stroke-width="0.5"/>')
        svg.append(f'<line x1="{dim_x_left}" y1="{bolt_head_y+62}" x2="{exp_cx-42}" y2="{bolt_head_y+62}" '
                   f'stroke="#000" stroke-width="0.5"/>')
        svg.append(f'<line x1="{dim_x_left}" y1="{cap_y}" x2="{dim_x_left}" y2="{bolt_head_y+62}" '
                   f'stroke="#000" stroke-width="0.8"/>')
        svg.append(f'<text x="{dim_x_left-5}" y="{cap_y + total_h_px//2 + 3}" text-anchor="end" '
                   f'font-size="8" font-family="Arial" fill="#333" '
                   f'transform="rotate(-90,{dim_x_left-5},{cap_y + total_h_px//2})">Total Height</text>')

        # Assembly note
        asm_note_y = bolt_head_y + 80
        svg.append(f'<text x="{exp_cx}" y="{asm_note_y}" text-anchor="middle" font-size="8" '
                   f'font-weight="600" font-family="Arial" fill="#000000">ASSEMBLED PROFILE (N.T.S.)</text>')

        # Assembled cross-section (side view installed on roof)
        asm_x = exp_x + 20
        asm_y = asm_note_y + 14
        asm_w = 340

        # Rafter (wood)
        svg.append(f'<rect x="{asm_x+80}" y="{asm_y+100}" width="180" height="35" '
                   f'fill="#d4b896" stroke="#000" stroke-width="1"/>')
        for xi in range(asm_x+90, asm_x+260, 20):
            svg.append(f'<line x1="{xi}" y1="{asm_y+102}" x2="{xi}" y2="{asm_y+133}" '
                       f'stroke="#b8936a" stroke-width="0.5"/>')
        svg.append(f'<text x="{asm_x+170}" y="{asm_y+120}" text-anchor="middle" '
                   f'font-size="8" font-family="Arial" fill="#000">RAFTER @ 24" O.C.</text>')

        # Decking
        svg.append(f'<rect x="{asm_x+60}" y="{asm_y+80}" width="220" height="20" '
                   f'fill="#c8b070" stroke="#000" stroke-width="1"/>')
        svg.append(f'<text x="{asm_x+170}" y="{asm_y+93}" text-anchor="middle" '
                   f'font-size="7" font-family="Arial" fill="#000">ROOF DECKING (OSB/PLYWOOD)</text>')

        # Shingles
        for shi in range(6):
            sx = asm_x + 62 + shi * 35
            svg.append(f'<rect x="{sx}" y="{asm_y+60}" width="38" height="22" '
                       f'fill="#888" stroke="#555" stroke-width="0.5"/>')
        svg.append(f'<text x="{asm_x+170}" y="{asm_y+75}" text-anchor="middle" '
                   f'font-size="7" font-family="Arial" fill="#fff">COMP. SHINGLES</text>')

        # FlashFoot2 flashing (round, sitting on shingles)
        svg.append(f'<ellipse cx="{asm_x+170}" cy="{asm_y+60}" rx="40" ry="8" '
                   f'fill="#2a2a2a" stroke="#000" stroke-width="1"/>')

        # Base block
        svg.append(f'<rect x="{asm_x+145}" y="{asm_y+38}" width="50" height="22" '
                   f'fill="#b0b8c0" stroke="#000" stroke-width="1.5"/>')
        svg.append(f'<text x="{asm_x+170}" y="{asm_y+52}" text-anchor="middle" '
                   f'font-size="7" font-weight="600" font-family="Arial" fill="#000">BASE</text>')

        # Cap
        svg.append(f'<rect x="{asm_x+152}" y="{asm_y+22}" width="36" height="16" rx="3" '
                   f'fill="#c8d0d8" stroke="#000" stroke-width="1.5"/>')
        svg.append(f'<text x="{asm_x+170}" y="{asm_y+33}" text-anchor="middle" '
                   f'font-size="7" font-weight="600" font-family="Arial" fill="#000">CAP</text>')

        # Lag bolt shaft
        svg.append(f'<rect x="{asm_x+167}" y="{asm_y+38}" width="6" height="97" '
                   f'fill="#888" stroke="#555" stroke-width="0.5"/>')
        svg.append(f'<line x1="{asm_x+170}" y1="{asm_y+60}" x2="{asm_x+170}" y2="{asm_y+135}" '
                   f'stroke="#999" stroke-width="4"/>')

        # Rail sitting on cap
        svg.append(f'<rect x="{asm_x+100}" y="{asm_y+8}" width="140" height="16" '
                   f'fill="#b8c4d0" stroke="#000" stroke-width="1.5"/>')
        svg.append(f'<text x="{asm_x+170}" y="{asm_y+20}" text-anchor="middle" '
                   f'font-size="7" font-weight="600" font-family="Arial" fill="#000">XR10 RAIL</text>')

        # Module on rail
        svg.append(f'<rect x="{asm_x+85}" y="{asm_y-18}" width="170" height="28" '
                   f'fill="#ffffff" stroke="#000" stroke-width="1.5"/>')
        svg.append(f'<text x="{asm_x+170}" y="{asm_y-1}" text-anchor="middle" '
                   f'font-size="8" font-weight="600" font-family="Arial" fill="#000000">PV MODULE</text>')

        # Annotation leaders
        svg.append(f'<line x1="{asm_x+215}" y1="{asm_y-4}" x2="{asm_x+265}" y2="{asm_y-20}" '
                   f'stroke="#444" stroke-width="0.7"/>')
        svg.append(f'<text x="{asm_x+268}" y="{asm_y-16}" font-size="7" font-family="Arial" fill="#333">{self._panel_model_short} {self._panel_wattage}W</text>')
        svg.append(f'<line x1="{asm_x+215}" y1="{asm_y+16}" x2="{asm_x+265}" y2="{asm_y+16}" '
                   f'stroke="#444" stroke-width="0.7"/>')
        svg.append(f'<text x="{asm_x+268}" y="{asm_y+20}" font-size="7" font-family="Arial" fill="#333">XR10 Rail</text>')
        svg.append(f'<line x1="{asm_x+195}" y1="{asm_y+38}" x2="{asm_x+265}" y2="{asm_y+42}" '
                   f'stroke="#444" stroke-width="0.7"/>')
        svg.append(f'<text x="{asm_x+268}" y="{asm_y+45}" font-size="7" font-family="Arial" fill="#333">FlashFoot2 Cap</text>')
        svg.append(f'<line x1="{asm_x+195}" y1="{asm_y+58}" x2="{asm_x+265}" y2="{asm_y+65}" '
                   f'stroke="#444" stroke-width="0.7"/>')
        svg.append(f'<text x="{asm_x+268}" y="{asm_y+69}" font-size="7" font-family="Arial" fill="#333">FlashFoot2 Base</text>')
        svg.append(f'<line x1="{asm_x+210}" y1="{asm_y+66}" x2="{asm_x+265}" y2="{asm_y+82}" '
                   f'stroke="#444" stroke-width="0.7"/>')
        svg.append(f'<text x="{asm_x+268}" y="{asm_y+86}" font-size="7" font-family="Arial" fill="#333">EPDM Flash</text>')
        svg.append(f'<line x1="{asm_x+195}" y1="{asm_y+90}" x2="{asm_x+265}" y2="{asm_y+100}" '
                   f'stroke="#444" stroke-width="0.7"/>')
        svg.append(f'<text x="{asm_x+268}" y="{asm_y+104}" font-size="7" font-family="Arial" fill="#333">Comp. Shingles</text>')

        # ── Right column: Specifications ──────────────────────────────────
        rx3 = 640
        spec_y = 72
        svg.append(f'<text x="{rx3}" y="{spec_y}" font-size="10" font-weight="700" '
                   f'font-family="Arial" fill="#000">PRODUCT SPECIFICATIONS</text>')
        spec_rows = [
            ("Product Name",             "FlashFoot2"),
            ("Manufacturer",             "IronRidge Inc."),
            ("Part Number (Cap)",        "FF2-CAP"),
            ("Part Number (Base)",       "FF2-BASE"),
            ("Cap Material",             "6063-T5 Aluminum, clear anodized"),
            ("Base Material",            "6063-T5 Aluminum, clear anodized"),
            ("Flashing",                 "12\" round aluminum, EPDM rubber gasket"),
            ("Lag Bolt Spec.",           "5/16\" × 2.5\" min. — 304 SS or hot-dip galv."),
            ("Lag Bolt Torque",          "15–25 ft-lbs  (must use torque wrench)"),
            ("Min. Embedment Depth",     "2.5\" into rafter (63.5mm)"),
            ("Working Load (per foot)",  "1,000 lbs (4,448 N)"),
            ("Assembly Weight",          "0.65 lbs (0.29 kg) per foot"),
            ("Compatible Roof Types",    "Comp. shingles, concrete/clay tile, metal"),
        ]
        for ri, (label, val) in enumerate(spec_rows):
            ry4 = spec_y + 14 + ri * row_h
            bg = "#f5f5f5" if ri % 2 == 0 else "#ffffff"
            svg.append(f'<rect x="{rx3}" y="{ry4}" width="610" height="{row_h}" fill="{bg}" stroke="#ccc" stroke-width="0.5"/>')
            svg.append(f'<text x="{rx3+8}" y="{ry4+16}" font-size="9" font-family="Arial" fill="#000">{label}</text>')
            svg.append(f'<text x="{rx3+230}" y="{ry4+16}" font-size="9" font-weight="600" '
                       f'font-family="Arial" fill="#000000">{val}</text>')

        # Installation Requirements
        ir_y = spec_y + 14 + len(spec_rows) * row_h + 22
        svg.append(f'<text x="{rx3}" y="{ir_y}" font-size="10" font-weight="700" '
                   f'font-family="Arial" fill="#000">INSTALLATION REQUIREMENTS</text>')
        ir_notes = [
            "1.  Locate and mark all rafters. Attachment points must hit rafter centers.",
            "2.  Pre-drill pilot hole: 17/64\" diameter through all layers into rafter.",
            "3.  Apply sealant to pilot hole before inserting lag bolt.",
            "4.  Thread lag bolt through FlashFoot2 base, flashing, and pre-drilled hole.",
            "5.  Torque to 15–25 ft-lbs using calibrated torque wrench. DO NOT over-torque.",
            "6.  Apply roofing sealant (e.g., NP1) around base perimeter.",
            "7.  Slide XR10 rail T-bolt into channel; position base on T-bolt.",
            "8.  Verify level and alignment of rail before final tightening.",
            "9.  Maintain minimum 18\" from ridge and eave per local fire code.",
        ]
        for ni, note in enumerate(ir_notes):
            ny2 = ir_y + 16 + ni * 20
            svg.append(f'<text x="{rx3}" y="{ny2}" font-size="9" font-family="Arial" fill="#000">{note}</text>')

        # Code compliance box
        cc_y = ir_y + 16 + len(ir_notes) * 20 + 20
        svg.append(f'<rect x="{rx3}" y="{cc_y}" width="610" height="80" '
                   f'fill="#ffffff" stroke="#000000" stroke-width="1.5" rx="3"/>')
        svg.append(f'<text x="{rx3+8}" y="{cc_y+18}" font-size="10" font-weight="700" '
                   f'font-family="Arial" fill="#000000">CODE COMPLIANCE &amp; CERTIFICATIONS</text>')
        certs2 = [
            "ICC-ES ESR-3164  |  UL 2703 Listed Attachment System",
            f"IBC 2021 / {self._building_code} 2020  |  ASCE 7-22 Wind/Snow Loading",
            f"{'NEC 690 / California Electrical Code' if self._code_prefix == 'NEC' else 'CEC Section 64 (CSA C22.1-2021)'}  |  {self._building_code} Compliant",
        ]
        for ci3, cert in enumerate(certs2):
            svg.append(f'<text x="{rx3+12}" y="{cc_y+36+ci3*18}" font-size="9" '
                       f'font-family="Arial" fill="#333">{cert}</text>')

        # ── Title block ───────────────────────────────────────────────────
        svg.append(self._svg_title_block(
            VW, VH, "PV-8.3", "Attachment Datasheet",
            "IronRidge FlashFoot2 Roof Attachment", "13 of 13", address, today
        ))

        content = "\n".join(svg)
        return (f'<div class="page">'
                f'<svg width="100%" height="100%" viewBox="0 0 {VW} {VH}" '
                f'xmlns="http://www.w3.org/2000/svg" style="background:#fff;">'
                f'{content}</svg></div>')

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

    def _svg_title_block(self, vw: int, vh: int,
                         sheet_id: str, sheet_title: str,
                         subtitle: str, page_of: str,
                         address: str, today: str,
                         transparent: bool = False) -> str:
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
        fill       = "rgba(0,0,0,0.75)" if transparent else "#ffffff"
        text_fill  = "#ffffff"           if transparent else "#000000"
        sub_fill   = "rgba(255,255,255,0.65)" if transparent else "#444444"
        border     = "rgba(255,255,255,0.35)" if transparent else "#000000"
        div_c      = "rgba(255,255,255,0.25)" if transparent else "#aaaaaa"

        # Derive owner name from address (street address before first comma)
        owner_name = address.split(",")[0].strip().upper() + " RESIDENCE"

        # Key x positions
        DIV_X   = tb_x + 350   # left/right column divider
        SIG_DIV = tb_x + 192   # divider within row 3 (contractor vs signature)

        # Key row y-positions (from tb_y)
        y1 = tb_y + 28          # end of row 1 (owner/addr)
        y2 = tb_y + 45          # end of row 2 (AHJ)
        y3 = tb_y + 83          # end of row 3 (contractor/sig)
        y4 = tb_y + 99          # end of row 4 (sheet title)
        # row 5: y4 → tb_y+130

        parts = []

        # ── Outer border ──────────────────────────────────────────────────
        parts.append(
            f'<rect x="{tb_x}" y="{tb_y}" width="{tb_w}" height="{tb_h}" '
            f'fill="{fill}" stroke="{border}" stroke-width="1.5"/>'
        )

        # ── Vertical divider (left col / right col) ───────────────────────
        parts.append(
            f'<line x1="{DIV_X}" y1="{tb_y}" x2="{DIV_X}" y2="{tb_y + tb_h}" '
            f'stroke="{border}" stroke-width="0.8"/>'
        )

        # ── Horizontal row dividers (left column only) ────────────────────
        for yd in [y1, y2, y3, y4]:
            parts.append(
                f'<line x1="{tb_x}" y1="{yd}" x2="{DIV_X}" y2="{yd}" '
                f'stroke="{div_c}" stroke-width="0.5"/>'
            )

        lx = tb_x + 6   # left text margin

        # ── Row 1: Owner name + address ───────────────────────────────────
        parts.append(
            f'<text x="{lx}" y="{tb_y + 14}" font-size="11" font-weight="700" '
            f'font-family="Arial" fill="{text_fill}">{owner_name}</text>'
        )
        parts.append(
            f'<text x="{lx}" y="{tb_y + 26}" font-size="7.5" '
            f'font-family="Arial" fill="{sub_fill}">{address}</text>'
        )

        # ── Row 2: AHJ ────────────────────────────────────────────────────
        parts.append(
            f'<text x="{lx}" y="{y1 + 12}" font-size="8.5" '
            f'font-family="Arial" fill="{text_fill}">AHJ: {self._make_ahj_label(address)}</text>'
        )

        # ── Row 3: Contractor info (left) + Signature (right) ─────────────
        # Inner vertical divider separating contractor and signature sub-columns
        parts.append(
            f'<line x1="{SIG_DIV}" y1="{y2}" x2="{SIG_DIV}" y2="{y3}" '
            f'stroke="{div_c}" stroke-width="0.5"/>'
        )
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
        cx_left = tb_x + 175   # center of left column
        parts.append(
            f'<text x="{cx_left}" y="{y3 + 11}" text-anchor="middle" font-size="9" '
            f'font-weight="700" font-family="Arial" fill="{text_fill}">{sheet_title.upper()}</text>'
        )

        # ── Row 5: Date / Drawn By + REV boxes ────────────────────────────
        parts.append(
            f'<text x="{lx}" y="{y4 + 11}" font-size="7.5" '
            f'font-family="Arial" fill="{text_fill}">DATE: {today}</text>'
        )
        drawn_label = (self.designer[:8] if len(self.designer) > 8 else self.designer).upper()
        parts.append(
            f'<text x="{lx}" y="{y4 + 22}" font-size="7.5" '
            f'font-family="Arial" fill="{text_fill}">DRAWN BY: {drawn_label}</text>'
        )
        # Three revision boxes
        rev_start = tb_x + 105
        rev_bw    = 81          # box width for each REV column
        rev_bh    = tb_h - (y4 - tb_y) - 2   # ≈ 29px
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
        cx_right = (DIV_X + tb_x + tb_w) // 2   # center of right column

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

        return f'<g>{"".join(parts)}</g>'

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
            (0, "N"), (45, "NE"), (90, "E"), (135, "SE"),
            (180, "S"), (225, "SW"), (270, "W"), (315, "NW"), (360, "N"),
        ]
        for deg, lbl in dirs:
            if abs(az - deg) <= 22.5:
                return lbl
        return "S"
