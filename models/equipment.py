"""
Equipment Data Models
=====================
Pydantic models for solar panels, inverters, racking systems, and roof attachments.
These models define the schema for the equipment catalog (JSON files) and are used
throughout the planset generation pipeline.

All electrical/mechanical specs needed by the renderer, electrical calculator,
and datasheet pages are defined here — nothing is hardcoded in rendering code.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Panel
# ---------------------------------------------------------------------------

@dataclass
class PanelDimensions:
    """Panel physical dimensions in mm."""
    length_mm: float = 1800.0
    width_mm: float = 1134.0
    depth_mm: float = 30.0

    @property
    def length_in(self) -> float:
        return self.length_mm / 25.4

    @property
    def width_in(self) -> float:
        return self.width_mm / 25.4

    @property
    def length_ft(self) -> float:
        return self.length_mm / 304.8

    @property
    def width_ft(self) -> float:
        return self.width_mm / 304.8


@dataclass
class DatasheetDrawing:
    """Hints for rendering a generic datasheet page."""
    cell_grid: List[int] = field(default_factory=lambda: [12, 11])
    junction_box_position: str = "center_bottom"
    busbar_count: int = 9


@dataclass
class PanelCatalogEntry:
    """Complete solar panel specification from the equipment catalog."""

    # Identity
    id: str = ""
    manufacturer: str = ""
    model: str = ""
    model_short: str = ""
    series: str = ""
    technology: str = ""                    # "HPBC Bifacial", "Mono PERC", etc.
    cell_count: int = 132
    cell_type: str = ""                     # "n-type TOPCon", "p-type PERC"

    # Electrical — STC
    wattage_w: int = 400
    voc_v: float = 37.5                     # Open-circuit voltage
    vmp_v: float = 31.7                     # Voltage at max power
    isc_a: float = 14.19                    # Short-circuit current
    imp_a: float = 13.56                    # Current at max power
    efficiency_pct: float = 22.0
    max_system_voltage_v: int = 1500
    max_series_fuse_a: int = 25
    power_tolerance: str = "+3/-0 %"

    # Temperature coefficients (as %/°C — divide by 100 for fractional)
    temp_coeff_pmax_pct_per_c: float = -0.29
    temp_coeff_voc_pct_per_c: float = -0.24
    temp_coeff_isc_pct_per_c: float = 0.05
    noct_c: float = 45.0

    # Physical
    dimensions: PanelDimensions = field(default_factory=PanelDimensions)
    weight_kg: float = 26.5

    # Bifacial
    bifacial: bool = False
    bifacial_gain_pct: float = 0.0

    # Certifications & warranty
    certifications: List[str] = field(default_factory=list)
    warranty_product_years: int = 25
    warranty_performance_years: int = 30
    first_year_degradation_pct: float = 1.0
    annual_degradation_pct: float = 0.4

    # Datasheet rendering hints
    datasheet_drawing: DatasheetDrawing = field(default_factory=DatasheetDrawing)

    # Pricing
    unit_cost_usd: float = 0.0

    # -- Convenience properties --

    @property
    def kw(self) -> float:
        return self.wattage_w / 1000.0

    @property
    def width_ft(self) -> float:
        """Panel width in feet (shorter dimension)."""
        return self.dimensions.width_ft

    @property
    def height_ft(self) -> float:
        """Panel height/length in feet (longer dimension)."""
        return self.dimensions.length_ft

    @property
    def weight_lbs(self) -> float:
        return self.weight_kg * 2.20462

    @property
    def temp_coeff_voc_frac(self) -> float:
        """Temperature coefficient of Voc as a fraction (e.g., -0.0024)."""
        return self.temp_coeff_voc_pct_per_c / 100.0

    @property
    def temp_coeff_isc_frac(self) -> float:
        """Temperature coefficient of Isc as a fraction."""
        return self.temp_coeff_isc_pct_per_c / 100.0

    @property
    def area_sqft(self) -> float:
        return self.width_ft * self.height_ft


# ---------------------------------------------------------------------------
# Inverter
# ---------------------------------------------------------------------------

@dataclass
class InverterCatalogEntry:
    """Complete inverter specification from the equipment catalog.

    Supports both microinverters (type="micro") and string inverters (type="string").
    """

    # Identity
    id: str = ""
    manufacturer: str = ""
    model: str = ""
    model_short: str = ""
    type: str = "micro"                     # "micro" or "string"

    # AC output
    max_ac_output_va: int = 384             # For micro: per unit. For string: total.
    rated_ac_output_w: int = 384            # Rated continuous AC watts
    max_ac_amps: float = 1.6               # Per unit (micro) or total (string)
    ac_voltage_v: int = 240
    ac_phases: int = 1

    # DC input
    max_dc_input_w: int = 460              # Max DC input watts
    max_dc_voltage_v: int = 60             # For micro: ~60V. For string: 600V.
    mppt_voltage_min_v: int = 27
    mppt_voltage_max_v: int = 48
    max_dc_input_current_a: float = 14.0
    mppt_count: int = 1

    # Efficiency
    cec_efficiency_pct: float = 96.5

    # Operating conditions
    operating_temp_min_c: int = -40
    operating_temp_max_c: int = 65

    # Safety
    rapid_shutdown_builtin: bool = True
    rapid_shutdown_method: str = ""         # "Integrated", "Tigo TS4", etc.
    monitoring: str = ""                    # "Enphase Envoy", "Hoymiles DTU", "SolisCloud"

    # Branch circuit limits (for microinverters)
    max_units_per_branch_15a: int = 0       # 0 = not applicable (string inverter)
    max_units_per_branch_20a: int = 0

    # Certifications
    certifications: List[str] = field(default_factory=list)

    # Compatibility
    compatible_panel_wattage_min_w: int = 0
    compatible_panel_wattage_max_w: int = 9999

    # Pricing
    unit_cost_usd: float = 0.0

    # -- Convenience properties --

    @property
    def is_micro(self) -> bool:
        return self.type == "micro"

    @property
    def is_string(self) -> bool:
        return self.type == "string"

    @property
    def ac_kw(self) -> float:
        return self.rated_ac_output_w / 1000.0


# ---------------------------------------------------------------------------
# Racking
# ---------------------------------------------------------------------------

@dataclass
class RackingProfile:
    """Cross-section dimensions of a rail."""
    width_in: float = 2.22
    height_in: float = 1.72
    wall_thickness_in: float = 0.099


@dataclass
class RackingClamps:
    """Compatible clamp models."""
    mid_clamp: str = ""
    end_clamp: str = ""


@dataclass
class RackingCatalogEntry:
    """Complete racking system specification from the equipment catalog."""

    # Identity
    id: str = ""
    manufacturer: str = ""
    model: str = ""
    type: str = "flush_mount_rail"          # "flush_mount_rail", "tilt_up", "ground_mount"
    material: str = ""                      # "6005-T5 Extruded Aluminum"
    finish: str = ""                        # "Clear Anodized", "Mill"

    # Profile
    profile: RackingProfile = field(default_factory=RackingProfile)
    available_lengths_ft: List[int] = field(default_factory=lambda: [7, 11, 14, 17])

    # Load ratings
    wind_load_psf: int = 55
    snow_load_psf: int = 70
    max_span_ft: float = 6.0
    max_cantilever_ft: float = 1.5

    # Compatibility
    compatible_attachment_ids: List[str] = field(default_factory=list)
    clamps: RackingClamps = field(default_factory=RackingClamps)
    bonding_method: str = ""                # "Bonded Splice", "Integrated Grounding Clip"

    # Certifications
    certifications: List[str] = field(default_factory=list)

    # Inverter compatibility
    compatible_inverter_types: List[str] = field(default_factory=lambda: ["string", "micro"])

    # Pricing (per rail unit at longest available length)
    unit_cost_usd: float = 0.0


# ---------------------------------------------------------------------------
# Attachment (roof mount)
# ---------------------------------------------------------------------------

@dataclass
class AttachmentCatalogEntry:
    """Complete roof attachment specification from the equipment catalog.

    Attachments are selected based on roof_material + racking compatibility.
    """

    # Identity
    id: str = ""
    manufacturer: str = ""
    model: str = ""
    type: str = "deck_mount"                # "deck_mount", "clamp_mount", "ballasted"

    # Compatibility
    compatible_roof_materials: List[str] = field(default_factory=list)
    compatible_racking_ids: List[str] = field(default_factory=list)

    # Specs
    flashing_material: str = ""
    flashing_dimensions_in: Dict[str, float] = field(default_factory=dict)
    fastener_spec: str = ""                 # '5/16" × 4" SS Lag'
    min_penetration_in: float = 0.0
    max_load_lbs: int = 0
    sealant: str = ""

    # Certifications
    certifications: List[str] = field(default_factory=list)
    code_compliance: List[str] = field(default_factory=list)

    # Installation
    installation_steps: List[str] = field(default_factory=list)

    # Pricing (per unit/point)
    unit_cost_usd: float = 0.0
