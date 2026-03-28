"""
SolarDesign — Single Source of Truth for Planset Generation
============================================================
Every page builder reads from this object. No page computes its own values.

This replaces the scattered data flow where each page builder computed its own
version of panel count, system kW, OCPD, wire sizing, etc. Now all values are
computed once (centrally) and stored here.

Built from:
  1. Google Solar API buildingInsights response (panels, roof segments, lat/lng)
  2. Equipment catalog selections (panel, inverter, racking, attachment)
  3. Centralized electrical calculations (compute_electrical fills in ElectricalDesign)
  4. Jurisdiction engine (fire setbacks, code references)

Nested dataclasses group related fields logically:
  - RoofSegment: individual roof face geometry and structural info
  - PanelPlacement: individual panel position and circuit assignment
  - ModuleSpec / InverterSpec / RackingSpec / AttachmentSpec / CombinerSpec: equipment
  - EquipmentSpec: container for all equipment specs
  - ElectricalDesign: all computed electrical values (DC, AC, OCPD, wire sizing, 120% rule)
  - JurisdictionContext: fire setbacks, governing codes
  - SheetInfo: page numbering for the planset
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Roof Segments
# ---------------------------------------------------------------------------


@dataclass
class RoofSegment:
    """A single roof face with geometry and structural properties.

    Populated from Google Solar API roofSegmentStats (pitch, azimuth, area)
    combined with the convex hull of panels assigned to this segment.
    Structural properties (material, rafter) come from user input or defaults.
    """

    segment_id: int = 0
    pitch_degrees: float = 0.0
    azimuth_degrees: float = 0.0
    area_sq_meters: float = 0.0
    polygon: List[Tuple[float, float]] = field(default_factory=list)
    material: str = "Asphalt Composition"
    rafter_size: str = "2x6"
    rafter_spacing_inches: float = 16.0


# ---------------------------------------------------------------------------
# Panel Placements
# ---------------------------------------------------------------------------


@dataclass
class PanelPlacement:
    """A single panel's position on the roof with circuit assignment.

    lat/lng come directly from Google Solar API solarPanels[].
    local_x/local_y are projected flat coordinates (meters from building center)
    computed during the coordinate projection step (Task 2.1).
    branch_id assigns the panel to a specific string/circuit.
    """

    panel_id: int = 0
    lat: float = 0.0
    lng: float = 0.0
    local_x: float = 0.0
    local_y: float = 0.0
    segment_id: int = 0
    orientation: str = "portrait"  # "portrait" or "landscape"
    branch_id: int = 0
    yearly_energy_kwh: float = 0.0


# ---------------------------------------------------------------------------
# Equipment Specs
# ---------------------------------------------------------------------------


@dataclass
class ModuleSpec:
    """Solar module (panel) electrical and physical specifications.

    Sourced from equipment catalog or manufacturer datasheet.
    """

    manufacturer: str = ""
    model: str = ""
    wattage: int = 0
    width_inches: float = 0.0
    height_inches: float = 0.0
    weight_lbs: float = 0.0
    voc: float = 0.0
    isc: float = 0.0
    vmp: float = 0.0
    imp: float = 0.0
    temp_coeff_voc: float = 0.0  # %/°C (e.g., -0.24)
    temp_coeff_pmax: float = 0.0  # %/°C (e.g., -0.29)


@dataclass
class InverterSpec:
    """Inverter electrical specifications.

    Supports both microinverters and string inverters.
    For microinverters, continuous_va and max_ac_current are per-unit values.
    """

    manufacturer: str = ""
    model: str = ""
    continuous_va: int = 0
    max_ac_current: float = 0.0
    voltage: int = 240
    type: str = "microinverter"  # "microinverter" or "string"


@dataclass
class RackingSpec:
    """Racking system specifications."""

    manufacturer: str = ""
    model: str = ""
    rail_length_inches: float = 0.0
    rail_count: int = 0


@dataclass
class AttachmentSpec:
    """Roof attachment specifications."""

    manufacturer: str = ""
    model: str = ""
    count: int = 0
    spacing_inches: float = 48.0


@dataclass
class CombinerSpec:
    """Combiner box specifications (for microinverter systems)."""

    manufacturer: str = ""
    model: str = ""
    part_number: str = ""


@dataclass
class EquipmentSpec:
    """Container for all equipment specifications used in the design.

    Groups module, inverter, racking, attachment, and combiner specs
    into a single object for clean access: design.equipment.module.wattage
    """

    module: ModuleSpec = field(default_factory=ModuleSpec)
    inverter: InverterSpec = field(default_factory=InverterSpec)
    racking: RackingSpec = field(default_factory=RackingSpec)
    attachment: AttachmentSpec = field(default_factory=AttachmentSpec)
    combiner: CombinerSpec = field(default_factory=CombinerSpec)


# ---------------------------------------------------------------------------
# Electrical Design (computed centrally, read everywhere)
# ---------------------------------------------------------------------------


@dataclass
class ElectricalDesign:
    """All computed electrical values for the solar system.

    Populated by compute_electrical(design) — a single function that runs
    ALL electrical calculations (DC kW, AC kW, OCPD, wire sizing, 120% rule,
    voltage drop, temperature corrections). No page builder should compute
    any of these values independently.

    Reference (Escalon Dr MVP):
      dc_kw=11.85, ac_kw=8.70, total_panels=30, 3 branches of 10,
      backfeed_breaker_amps=50, msp_bus=225A, msp_main=200A,
      120% rule: 200+50=250 <= 270 ✓
    """

    dc_kw: float = 0.0
    ac_kw: float = 0.0
    total_panels: int = 0
    panels_per_branch: List[int] = field(default_factory=list)
    num_branches: int = 0
    branch_breaker_amps: int = 20
    backfeed_breaker_amps: int = 0
    msp_bus_rating_amps: int = 225
    msp_main_breaker_amps: int = 200
    passes_120_pct_rule: bool = False
    rule_120_calc: str = ""
    service_voltage: int = 240
    ac_disconnect_amps: int = 60
    wire_sizes: Dict[str, str] = field(default_factory=dict)
    conduit_sizes: Dict[str, str] = field(default_factory=dict)
    ocpd_ratings: Dict[str, int] = field(default_factory=dict)
    voltage_drop_pct: float = 0.0
    temperature_derate_factor: float = 1.0


# ---------------------------------------------------------------------------
# Jurisdiction Context
# ---------------------------------------------------------------------------


@dataclass
class JurisdictionContext:
    """Fire setbacks and governing code references for the AHJ.

    Fire setbacks are per California Fire Code (CFC) 605.11 for CA residential,
    or per local amendments. Code references appear on notes pages and title blocks.
    """

    fire_setback_ridge_inches: int = 36
    fire_setback_eave_inches: int = 18
    fire_setback_valley_inches: int = 18
    building_code: str = ""
    electrical_code: str = ""
    fire_code: str = ""
    residential_code: str = ""
    energy_code: str = ""
    mechanical_code: str = ""
    plumbing_code: str = ""
    requires_pe_stamp: bool = False


# ---------------------------------------------------------------------------
# Sheet Info (planset page index)
# ---------------------------------------------------------------------------


@dataclass
class SheetInfo:
    """A single sheet/page in the planset.

    Used to build the sheet index on the cover page (T-00) and to
    drive sequential rendering of all pages.
    """

    sheet_number: str = ""  # e.g., "T-00", "A-101", "E-601"
    sheet_id: str = ""  # internal ID for the page builder
    title: str = ""  # e.g., "Cover Page", "Site Plan"


# ---------------------------------------------------------------------------
# SolarDesign — the top-level single source of truth
# ---------------------------------------------------------------------------


@dataclass
class SolarDesign:
    """Complete solar design — the single source of truth for planset generation.

    Every page builder reads from this object. No page computes its own values.
    All electrical calculations, equipment specs, panel positions, and jurisdiction
    rules are centralized here.

    Built by:
      1. from_google_solar_api() — parses API response into panels/roof segments
      2. Equipment selection — populates equipment specs from catalog
      3. compute_electrical() — fills in all electrical design values
      4. Jurisdiction engine — fills in fire setbacks and code references

    Usage:
      design = SolarDesign.from_google_solar_api(api_response, equipment)
      compute_electrical(design)  # fills design.electrical
      for page_builder in page_builders:
          html = page_builder.build_page(design)
    """

    # ── Site Info ─────────────────────────────────────────────────────────
    address: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""
    county: str = ""
    lat: float = 0.0
    lng: float = 0.0
    ahj: str = ""  # Authority Having Jurisdiction, e.g., "City of Los Angeles"
    utility: str = ""  # e.g., "LADWP", "SDG&E", "PG&E"
    lot_polygon: List[Tuple[float, float]] = field(default_factory=list)
    building_footprint: List[Tuple[float, float]] = field(default_factory=list)

    # ── Roof Segments ─────────────────────────────────────────────────────
    roof_segments: List[RoofSegment] = field(default_factory=list)

    # ── Panel Placements ──────────────────────────────────────────────────
    panels: List[PanelPlacement] = field(default_factory=list)

    # ── Equipment ─────────────────────────────────────────────────────────
    equipment: EquipmentSpec = field(default_factory=EquipmentSpec)

    # ── Electrical Design (computed centrally) ────────────────────────────
    electrical: ElectricalDesign = field(default_factory=ElectricalDesign)

    # ── Jurisdiction ──────────────────────────────────────────────────────
    jurisdiction: JurisdictionContext = field(default_factory=JurisdictionContext)

    # ── Production Estimates ──────────────────────────────────────────────
    annual_kwh: float = 0.0
    monthly_kwh: List[float] = field(default_factory=list)  # 12 values
    production_source: str = ""  # e.g., "Google Solar API", "PVWatts"

    # ── Metadata ──────────────────────────────────────────────────────────
    project_name: str = ""
    designer: str = ""
    company_name: str = ""
    company_address: str = ""
    company_phone: str = ""
    company_license: str = ""
    design_date: str = ""
    sheet_count: int = 0
    sheets: List[SheetInfo] = field(default_factory=list)

    # ── Serialization ─────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """Serialize the entire design to a plain dict for JSON storage.

        Recursively converts all nested dataclasses, tuples, and lists
        into JSON-compatible types (dicts, lists, primitives).
        """
        return _dataclass_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict) -> SolarDesign:
        """Deserialize a dict (e.g., from JSON) back into a SolarDesign.

        Reconstructs all nested dataclasses from their dict representations.
        Missing keys use the dataclass defaults.
        """
        if not data:
            return cls()

        # Reconstruct nested dataclasses
        roof_segments = [
            RoofSegment(
                segment_id=s.get("segment_id", 0),
                pitch_degrees=s.get("pitch_degrees", 0.0),
                azimuth_degrees=s.get("azimuth_degrees", 0.0),
                area_sq_meters=s.get("area_sq_meters", 0.0),
                polygon=[tuple(p) for p in s.get("polygon", [])],
                material=s.get("material", "Asphalt Composition"),
                rafter_size=s.get("rafter_size", "2x6"),
                rafter_spacing_inches=s.get("rafter_spacing_inches", 16.0),
            )
            for s in data.get("roof_segments", [])
        ]

        panels = [
            PanelPlacement(
                panel_id=p.get("panel_id", 0),
                lat=p.get("lat", 0.0),
                lng=p.get("lng", 0.0),
                local_x=p.get("local_x", 0.0),
                local_y=p.get("local_y", 0.0),
                segment_id=p.get("segment_id", 0),
                orientation=p.get("orientation", "portrait"),
                branch_id=p.get("branch_id", 0),
                yearly_energy_kwh=p.get("yearly_energy_kwh", 0.0),
            )
            for p in data.get("panels", [])
        ]

        equipment_data = data.get("equipment", {})
        equipment = EquipmentSpec(
            module=_dict_to_dataclass(ModuleSpec, equipment_data.get("module", {})),
            inverter=_dict_to_dataclass(InverterSpec, equipment_data.get("inverter", {})),
            racking=_dict_to_dataclass(RackingSpec, equipment_data.get("racking", {})),
            attachment=_dict_to_dataclass(AttachmentSpec, equipment_data.get("attachment", {})),
            combiner=_dict_to_dataclass(CombinerSpec, equipment_data.get("combiner", {})),
        )

        electrical = _dict_to_dataclass(ElectricalDesign, data.get("electrical", {}))
        jurisdiction = _dict_to_dataclass(JurisdictionContext, data.get("jurisdiction", {}))

        sheets = [
            SheetInfo(
                sheet_number=s.get("sheet_number", ""),
                sheet_id=s.get("sheet_id", ""),
                title=s.get("title", ""),
            )
            for s in data.get("sheets", [])
        ]

        return cls(
            address=data.get("address", ""),
            city=data.get("city", ""),
            state=data.get("state", ""),
            zip_code=data.get("zip_code", ""),
            county=data.get("county", ""),
            lat=data.get("lat", 0.0),
            lng=data.get("lng", 0.0),
            ahj=data.get("ahj", ""),
            utility=data.get("utility", ""),
            lot_polygon=[tuple(p) for p in data.get("lot_polygon", [])],
            building_footprint=[tuple(p) for p in data.get("building_footprint", [])],
            roof_segments=roof_segments,
            panels=panels,
            equipment=equipment,
            electrical=electrical,
            jurisdiction=jurisdiction,
            annual_kwh=data.get("annual_kwh", 0.0),
            monthly_kwh=data.get("monthly_kwh", []),
            production_source=data.get("production_source", ""),
            project_name=data.get("project_name", ""),
            designer=data.get("designer", ""),
            company_name=data.get("company_name", ""),
            company_address=data.get("company_address", ""),
            company_phone=data.get("company_phone", ""),
            company_license=data.get("company_license", ""),
            design_date=data.get("design_date", ""),
            sheet_count=data.get("sheet_count", 0),
            sheets=sheets,
        )

    # ── Google Solar API Parser ───────────────────────────────────────────

    @classmethod
    def from_google_solar_api(
        cls,
        response: dict,
        equipment: Optional[EquipmentSpec] = None,
    ) -> SolarDesign:
        """Parse a Google Solar API buildingInsights response into a SolarDesign.

        Extracts:
          - lat/lng from response center
          - Panel positions from solarPanels[] (lat, lng, segment, orientation, energy)
          - Roof segments from roofSegmentStats[] (pitch, azimuth, area)
          - Annual production from wholeRoofStats or sum of panel energies

        Equipment specs, electrical calculations, and jurisdiction context are
        left as defaults — they are populated by separate pipeline steps.

        Args:
            response: Raw JSON dict from Google Solar API buildingInsights:findClosest
            equipment: Optional EquipmentSpec to attach to the design

        Returns:
            SolarDesign with panels, roof_segments, and site coordinates populated
        """
        if not response:
            return cls(equipment=equipment or EquipmentSpec())

        # Extract center coordinates
        center = response.get("center", {})
        lat = center.get("latitude", 0.0)
        lng = center.get("longitude", 0.0)

        # Extract address if present (not always in buildingInsights)
        address = response.get("name", "")

        # Parse solar potential
        solar_potential = response.get("solarPotential", {})

        # Parse roof segments
        roof_segments = []
        for seg in solar_potential.get("roofSegmentStats", []):
            stats = seg.get("stats", {})
            center_pt = seg.get("center", {})
            roof_segments.append(
                RoofSegment(
                    segment_id=seg.get("segmentIndex", len(roof_segments)),
                    pitch_degrees=seg.get("pitchDegrees", 0.0),
                    azimuth_degrees=seg.get("azimuthDegrees", 0.0),
                    area_sq_meters=stats.get("areaMeters2", 0.0),
                )
            )

        # Parse panel positions
        panels = []
        for i, sp in enumerate(solar_potential.get("solarPanels", [])):
            panel_center = sp.get("center", {})
            orientation_raw = sp.get("orientation", "PORTRAIT")
            panels.append(
                PanelPlacement(
                    panel_id=i,
                    lat=panel_center.get("latitude", 0.0),
                    lng=panel_center.get("longitude", 0.0),
                    segment_id=sp.get("segmentIndex", 0),
                    orientation="landscape" if orientation_raw == "LANDSCAPE" else "portrait",
                    yearly_energy_kwh=sp.get("yearlyEnergyDcKwh", 0.0),
                )
            )

        # Production estimate from whole-roof stats
        whole_roof = solar_potential.get("wholeRoofStats", {}).get("stats", {})
        annual_kwh = whole_roof.get("sunshineQuantiles", [0])[-1] if whole_roof else 0.0
        # Better estimate: sum of per-panel energy for the selected panel count
        if panels:
            annual_kwh = sum(p.yearly_energy_kwh for p in panels)

        return cls(
            address=address,
            lat=lat,
            lng=lng,
            roof_segments=roof_segments,
            panels=panels,
            equipment=equipment or EquipmentSpec(),
            annual_kwh=round(annual_kwh, 1),
            production_source="Google Solar API",
        )


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def _dataclass_to_dict(obj) -> dict:
    """Recursively convert a dataclass instance to a plain dict."""
    from dataclasses import fields, asdict

    # Use dataclasses.asdict which handles nested dataclasses, lists, tuples
    # but convert tuples to lists for JSON compatibility
    result = {}
    for f in fields(obj):
        value = getattr(obj, f.name)
        result[f.name] = _convert_value(value)
    return result


def _convert_value(value):
    """Convert a value to a JSON-serializable type."""
    from dataclasses import fields as dc_fields

    if hasattr(value, "__dataclass_fields__"):
        return _dataclass_to_dict(value)
    elif isinstance(value, list):
        return [_convert_value(v) for v in value]
    elif isinstance(value, tuple):
        return list(value)
    elif isinstance(value, dict):
        return {k: _convert_value(v) for k, v in value.items()}
    else:
        return value


def _dict_to_dataclass(cls, data: dict):
    """Reconstruct a simple (flat) dataclass from a dict.

    Uses only keys that match the dataclass field names. Missing keys
    fall back to the field's default value.
    """
    if not data:
        return cls()
    from dataclasses import fields as dc_fields

    valid_keys = {f.name for f in dc_fields(cls)}
    filtered = {k: v for k, v in data.items() if k in valid_keys}
    return cls(**filtered)
