"""
ProjectSpec — Single Source of Truth
=====================================
Every page builder, electrical calculation, and note/label reads from this
one object. Nothing is hardcoded in rendering code.

A ProjectSpec is built from:
  1. CLI arguments + catalog lookups, OR
  2. Web UI form submission, OR
  3. OpenSolar import
"""

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from models.equipment import (
    AttachmentCatalogEntry,
    InverterCatalogEntry,
    PanelCatalogEntry,
    RackingCatalogEntry,
)


# ---------------------------------------------------------------------------
# Roof material constants
# ---------------------------------------------------------------------------

ROOF_MATERIALS = {
    "asphalt_shingle": "Asphalt Shingle",
    "composite_shingle": "Composite Shingle",
    "metal_standing_seam": "Metal Standing Seam",
    "clay_tile": "Clay Tile",
    "concrete_tile": "Concrete Tile",
    "flat_membrane": "Flat Membrane (TPO/EPDM)",
    "metal_corrugated": "Corrugated Metal",
}


# ---------------------------------------------------------------------------
# ProjectSpec
# ---------------------------------------------------------------------------


@dataclass
class ProjectSpec:
    """Complete project specification — the single source of truth for a design.

    Every rendering function, electrical calculation, and template receives this
    object. No equipment specs, code references, or jurisdiction values should
    be hardcoded outside of this structure.
    """

    # ── Site ──────────────────────────────────────────────────────────────
    address: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    municipality: str = ""
    province_or_state: str = ""
    country: str = "US"  # "US" or "CA"

    # ── Equipment (from catalog) ──────────────────────────────────────────
    panel: PanelCatalogEntry = field(default_factory=PanelCatalogEntry)
    inverter: InverterCatalogEntry = field(default_factory=InverterCatalogEntry)
    racking: RackingCatalogEntry = field(default_factory=RackingCatalogEntry)
    attachment: AttachmentCatalogEntry = field(default_factory=AttachmentCatalogEntry)

    # ── Property / Lot ──────────────────────────────────────────────────
    lot_width_ft: float = 0.0  # from manual entry or GIS
    lot_depth_ft: float = 0.0
    front_setback_ft: float = 15.0
    side_setback_ft: float = 5.0
    building_width_ft: float = 0.0  # from API or manual
    building_depth_ft: float = 0.0  # from API or manual
    building_outline_ft: list = field(default_factory=list)  # [(x,y),...] polygon from GeoTIFF
    lot_outline_ft: list = field(default_factory=list)  # [(x,y),...] lot polygon if known
    street_name: str = ""  # extracted from address

    # ── Roof ──────────────────────────────────────────────────────────────
    roof_material: str = "asphalt_shingle"  # key from ROOF_MATERIALS
    roof_pitch_deg: float = 0.0  # from API or manual
    roof_azimuth_deg: float = 180.0  # from API or manual (180 = south)

    # ── Electrical (site-specific, entered by engineer) ───────────────────
    main_panel_breaker_a: int = 200
    main_panel_bus_rating_a: int = 225
    main_panel_brand: str = ""  # "Square D QO", "Eaton BR"
    service_voltage_v: int = 240
    is_residential: bool = True
    num_panels: int = 0

    # ── System sizing & production ──────────────────────────────────────
    target_production_kwh: float = 0.0  # annual kWh production target
    annual_consumption_kwh: float = 0.0  # customer's annual usage
    target_offset_pct: float = 100.0  # desired offset (100% = net zero)
    sun_hours_peak: float = 0.0  # peak sun hours (location-specific)
    # Computed:
    #   system_kw = num_panels × panel.wattage_w / 1000
    #   estimated_annual_kwh = system_kw × sun_hours_peak × 365
    #   actual_offset_pct = estimated_annual_kwh / annual_consumption_kwh × 100

    # Legacy alias
    target_kwh: Optional[float] = None  # deprecated, use target_production_kwh

    # ── Solar resource ────────────────────────────────────────────────────
    shade_factor: float = 1.0  # 0.0–1.0 from annual flux GeoTIFF (1.0 = no shading)

    # ── Jurisdiction ───────────────────────────────────────────────────────
    jurisdiction_id: str = ""  # "cec_quebec", "nec_california", "nec_base"

    # ── Company ───────────────────────────────────────────────────────────
    company_name: str = "Solar Contractor"
    company_license: str = ""  # "CMEQ #12345"
    company_email: str = ""
    designer_name: str = "AI Solar Design Engine"
    project_name: str = "Solar Installation"

    # ── Calculated (populated by engine, not by user) ─────────────────────
    # These are filled in during the generation pipeline
    building_insight: Optional[Any] = None  # BuildingInsight from Google Solar
    placements: Optional[List[Any]] = None  # List[PlacementResult]
    electrical_design: Optional[Any] = None  # ElectricalDesign result
    roof_faces_latlng: Optional[List[Dict]] = None  # GeoTIFF roof face polygons [{polygon_latlng, usable_polygon_latlng, azimuth_deg, pitch_deg, area_sqft}]
    parcel_boundary_latlng: Optional[List[Dict]] = None  # Lot boundary [{lat, lng}] from parcel API

    # ── Convenience properties ────────────────────────────────────────────

    @property
    def system_dc_kw(self) -> float:
        """Total DC system capacity in kW."""
        return self.num_panels * self.panel.kw

    @property
    def system_ac_kw(self) -> float:
        """Total AC system capacity in kW.

        For microinverters: num_panels × inverter rated output.
        For string inverters: inverter rated output (total).
        """
        if self.inverter.is_micro:
            return round(self.num_panels * self.inverter.rated_ac_output_w / 1000, 2)
        else:
            return self.inverter.ac_kw

    @property
    def estimated_annual_kwh(self) -> float:
        """Estimated annual production in kWh.

        Prefers Google Solar API per-panel energy data (accounts for shading
        hour-by-hour). Falls back to generic formula if not available.
        """
        # Use Google's per-panel energy if available — much more accurate
        if self.building_insight and hasattr(self.building_insight, 'panels') and self.building_insight.panels:
            google_panels = self.building_insight.panels[:self.num_panels] if self.num_panels else self.building_insight.panels
            google_total = sum(p.yearly_energy_kwh for p in google_panels if hasattr(p, 'yearly_energy_kwh'))
            if google_total > 0:
                return round(google_total, 0)

        # Fallback: generic formula
        psh = self.sun_hours_peak
        if psh <= 0:
            if self.country == "US":
                psh = 5.5  # California average
            else:
                psh = 3.8  # Quebec average
        shade = self.shade_factor if 0.0 < self.shade_factor <= 1.0 else 1.0
        return round(self.system_dc_kw * psh * 365 * shade * 0.85, 0)

    @property
    def actual_offset_pct(self) -> float:
        """Actual energy offset percentage.

        Returns 0 if annual_consumption_kwh is not set.
        """
        if self.annual_consumption_kwh > 0:
            return round(self.estimated_annual_kwh / self.annual_consumption_kwh * 100, 1)
        return 0.0

    @property
    def panels_needed_for_target(self) -> int:
        """Calculate panels needed to meet target_production_kwh.

        Useful for system sizing: given a production target and panel wattage,
        how many panels are needed?
        """
        if self.target_production_kwh <= 0 or self.panel.wattage_w <= 0:
            return 0
        psh = self.sun_hours_peak if self.sun_hours_peak > 0 else (5.5 if self.country == "US" else 3.8)
        # target = n_panels × (wattage/1000) × psh × 365 × 0.80
        panel_annual = (self.panel.wattage_w / 1000) * psh * 365 * 0.80
        if panel_annual <= 0:
            return 0
        return math.ceil(self.target_production_kwh / panel_annual)

    @property
    def inverter_count(self) -> int:
        """Number of inverter units needed.

        Microinverters: one per panel.
        String inverters: 1 (may need logic for multi-inverter systems later).
        """
        if self.inverter.is_micro:
            return self.num_panels
        return 1

    @property
    def roof_material_display(self) -> str:
        """Human-readable roof material name."""
        return ROOF_MATERIALS.get(self.roof_material, self.roof_material)

    @property
    def total_estimated_kwh(self) -> float:
        """Rough annual kWh estimate using DC capacity and sun hours."""
        shade = self.shade_factor if 0.0 < self.shade_factor <= 1.0 else 1.0
        return self.system_dc_kw * self.sun_hours_peak * 365 * shade * 0.85

    @property
    def monthly_production(self) -> list:
        """Monthly energy production breakdown as list of MonthlyProduction objects."""
        from engine.electrical_calc import calculate_monthly_production

        return calculate_monthly_production(self, self.estimated_annual_kwh)

    @property
    def structural_loads(self) -> dict:
        """Structural loading calculations per IBC / ASCE 7-16."""
        from engine.electrical_calc import calculate_structural_loads

        return calculate_structural_loads(self)
