"""
Unified Electrical Calculator
=============================
Wraps jurisdiction-specific electrical code calculations into a single
interface that takes a ProjectSpec and produces an ElectricalDesign result.

Replaces the broken _append_quebec_electrical() and integrates with
the jurisdiction engine for multi-code support.
"""

import math
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

try:
    import rasterio
    from rasterio.io import MemoryFile
    _RASTERIO_AVAILABLE = True
except ImportError:
    _RASTERIO_AVAILABLE = False

logger = logging.getLogger(__name__)


# ── Standard breaker sizes (NEC 240.6 / CEC equivalent) ────────────────
STANDARD_BREAKER_SIZES = [15, 20, 25, 30, 35, 40, 50, 60, 70, 80, 90, 100,
                          110, 125, 150, 175, 200, 225, 250, 300, 350, 400]


@dataclass
class ElectricalDesign:
    """Complete electrical design result."""
    # System
    num_panels: int = 0
    system_dc_kw: float = 0.0
    system_ac_kw: float = 0.0
    inverter_type: str = "micro"  # "micro" or "string"

    # String configuration (string inverters only)
    num_strings: int = 1
    panels_per_string: int = 0
    string_voc: float = 0.0
    string_voc_cold: float = 0.0
    string_vmp: float = 0.0
    string_isc: float = 0.0

    # Branch circuit (microinverters)
    num_branches: int = 1
    units_per_branch: int = 0
    branch_breaker_a: int = 15

    # DC side
    dc_conductor: str = "#10 AWG PV Wire"
    dc_disconnect_amps: int = 30

    # AC side
    inverter_continuous_amps: float = 0.0
    ac_breaker_amps: int = 20
    ac_conductor: str = "#10 AWG Cu"
    ac_conductor_type: str = "THWN-2"

    # Grounding
    egc: str = "#10 AWG Cu"
    bond_conductor: str = "#6 AWG Cu"

    # Interconnection (120% rule)
    main_breaker_amps: int = 200
    bus_rating_amps: int = 225
    total_sources_amps: int = 0
    rule_120_max: int = 0
    rule_120_pass: bool = True
    interconnection_method: str = "load_side"

    # Warnings
    warnings: List[str] = field(default_factory=list)


def calculate_shade_factor(flux_geotiff_bytes: bytes,
                           panel_positions: list = None,
                           mask_bytes: bytes = None) -> float:
    """Calculate shade factor from annual flux GeoTIFF.

    Reads the GeoTIFF pixel values (annual flux in kWh/m²/yr). Returns
    shade_factor in [0.0, 1.0] where 1.0 = fully exposed, 0.7 = 30% shading.

    Algorithm:
      1. Load flux raster (and optional building mask).
      2. If mask provided, restrict to roof pixels only.
      3. If panel_positions (pixel coords) provided, sample those pixels.
      4. Otherwise, use the top-50% of valid pixels (panel-worthy areas).
      5. shade_factor = mean(panel_area) / p95(panel_area)
         Using p95 instead of max avoids single-pixel outlier inflation.

    Falls back to 1.0 (no shading assumed) on any error.
    """
    if not flux_geotiff_bytes:
        return 1.0

    try:
        import numpy as np

        if _RASTERIO_AVAILABLE:
            from rasterio.io import MemoryFile

            # Load flux
            with MemoryFile(flux_geotiff_bytes) as mf:
                with mf.open() as ds:
                    data = ds.read(1).astype(float)
                    nodata = ds.nodata
                    if nodata is not None:
                        data[data == nodata] = 0.0

            # Apply building mask if provided (restrict to roof pixels)
            if mask_bytes:
                with MemoryFile(mask_bytes) as mf:
                    with mf.open() as ds:
                        mask_arr = ds.read(1)
                valid_pixels = data[(data > 0) & (mask_arr > 0)]
            else:
                valid_pixels = data[data > 0]

            if valid_pixels.size == 0:
                return 1.0

            if panel_positions:
                # Sample flux at explicit panel pixel positions
                h, w = data.shape
                samples = []
                for pos in panel_positions:
                    px, py = int(round(pos[0])), int(round(pos[1]))
                    if 0 <= px < w and 0 <= py < h and data[py, px] > 0:
                        samples.append(data[py, px])
                panel_area = np.array(samples) if samples else valid_pixels
            else:
                # Use top 50% of valid pixels (panel-worthy: south-facing, unshaded)
                median_flux = np.percentile(valid_pixels, 50)
                panel_area = valid_pixels[valid_pixels >= median_flux]
                if panel_area.size == 0:
                    panel_area = valid_pixels

            p95 = float(np.percentile(panel_area, 95))
            if p95 <= 0:
                return 1.0
            mean_flux = float(panel_area.mean())
            shade = round(min(1.0, mean_flux / p95), 3)
            logger.info("Shade factor: %.3f (panel mean=%.1f, p95=%.1f kWh/m²/yr, n=%d px)",
                        shade, mean_flux, p95, panel_area.size)
            return shade

        else:
            # PIL fallback — no geospatial awareness, use percentile heuristic
            import io
            from PIL import Image
            img = Image.open(io.BytesIO(flux_geotiff_bytes))
            arr = np.array(img, dtype=float)
            valid = arr[arr > 0]
            if valid.size == 0:
                return 1.0
            median = np.percentile(valid, 50)
            panel_area = valid[valid >= median]
            p95 = float(np.percentile(panel_area, 95))
            if p95 <= 0:
                return 1.0
            shade = round(min(1.0, float(panel_area.mean()) / p95), 3)
            logger.info("Shade factor (PIL fallback): %.3f", shade)
            return shade

    except Exception as e:
        logger.warning("Shade factor calculation failed (%s) — defaulting to 1.0", e)
        return 1.0


def _get_design_temp_cold(project) -> float:
    """Return jurisdiction-specific cold design temperature in °C.

    Queries the jurisdiction engine based on project address/jurisdiction_id.
    Falls back to -25°C (Quebec CEC) only when jurisdiction cannot be determined.
    """
    jid = getattr(project, "jurisdiction_id", "") or ""
    address = getattr(project, "address", "") or ""
    country = getattr(project, "country", "CA") or "CA"
    city = getattr(project, "municipality", "") or ""
    if not city and address:
        parts = address.split(",")
        if len(parts) >= 2:
            city = parts[1].strip()

    addr_lower = address.lower()
    is_california = (
        jid == "nec_california"
        or any(s in addr_lower for s in ["california", ", ca ", ", ca,", " ca 9"])
    )

    try:
        if is_california:
            from jurisdiction.nec_california import NECCaliforniaEngine
            engine = NECCaliforniaEngine(city=city)
            return float(engine.get_design_temperatures(city).get("cold_c", 1))
        elif jid == "nec_base" or country == "US":
            from jurisdiction.nec_base import NECBaseEngine
            engine = NECBaseEngine()
            return float(engine.get_design_temperatures(city).get("cold_c", -10))
        else:
            from jurisdiction.cec_quebec import CECQuebecEngine
            engine = CECQuebecEngine()
            return float(engine.get_design_temperatures(city).get("cold_c", -25))
    except Exception:
        return -25.0  # safe fallback


def next_standard_breaker(amps: float) -> int:
    """Round up to next standard breaker size."""
    for size in STANDARD_BREAKER_SIZES:
        if size >= amps:
            return size
    return STANDARD_BREAKER_SIZES[-1]


def calculate_electrical_design(project) -> ElectricalDesign:
    """Calculate complete electrical design from a ProjectSpec.

    Uses the jurisdiction engine (when available) for code-specific rules.
    Falls back to CEC defaults if no jurisdiction engine is set.

    Args:
        project: ProjectSpec instance with all equipment and site data.

    Returns:
        ElectricalDesign with all calculated values.
    """
    panel = project.panel
    inverter = project.inverter
    n = project.num_panels
    design = ElectricalDesign(num_panels=n)

    # System capacity
    design.system_dc_kw = round(n * panel.wattage_w / 1000, 2)
    design.inverter_type = inverter.type

    # Design temperature (from jurisdiction engine, not hardcoded Quebec default)
    t_cold_c = _get_design_temp_cold(project)
    t_stc_c = 25.0

    # Temperature-corrected Voc (worst case = coldest)
    temp_coeff_voc = panel.temp_coeff_voc_frac  # e.g., -0.0024
    voc_corrected = panel.voc_v * (1 + temp_coeff_voc * (t_cold_c - t_stc_c))

    if inverter.is_micro:
        _calc_micro(design, project, n, voc_corrected)
    else:
        _calc_string(design, project, n, voc_corrected, t_cold_c, t_stc_c)

    # AC conductor sizing (CEC Rule 4-004: continuous × 1.25)
    design.ac_conductor = _conductor_for_amps(design.ac_breaker_amps)

    # EGC sizing
    design.egc = _egc_for_amps(design.ac_breaker_amps)

    # Interconnection / 120% rule
    design.main_breaker_amps = project.main_panel_breaker_a
    design.bus_rating_amps = project.main_panel_bus_rating_a
    design.rule_120_max = int(design.bus_rating_amps * 1.2)
    design.total_sources_amps = design.main_breaker_amps + design.ac_breaker_amps
    design.rule_120_pass = design.total_sources_amps <= design.rule_120_max

    if design.rule_120_pass:
        design.interconnection_method = "load_side"
    else:
        design.interconnection_method = "supply_side"
        design.warnings.append(
            f"120% rule FAILS: {design.total_sources_amps}A > {design.rule_120_max}A. "
            f"Supply-side connection required."
        )

    design.system_ac_kw = project.system_ac_kw

    logger.info("Electrical design: %d panels, DC=%.1fkW, AC=%.1fkW, "
                "breaker=%dA, 120%% rule=%s",
                n, design.system_dc_kw, design.system_ac_kw,
                design.ac_breaker_amps,
                "PASS" if design.rule_120_pass else "FAIL")

    return design


def _calc_micro(design: ElectricalDesign, project, n: int, voc_cold: float):
    """Calculate branch circuits for microinverter systems."""
    inv = project.inverter

    max_per_branch = inv.max_units_per_branch_15a or 7
    design.num_branches = math.ceil(n / max_per_branch)
    design.units_per_branch = math.ceil(n / design.num_branches)
    design.branch_breaker_a = 15  # standard 15A 2P for micro branches

    # AC breaker = total inverter output × 1.25 / 240V rounded up
    total_ac_amps = n * inv.max_ac_amps
    design.inverter_continuous_amps = total_ac_amps
    ac_breaker_raw = total_ac_amps * 1.25
    design.ac_breaker_amps = next_standard_breaker(ac_breaker_raw)

    # DC side (each panel is independent circuit for micros)
    design.dc_conductor = "#10 AWG PV Wire"
    isc_corrected = project.panel.isc_a * 1.25  # NEC/CEC safety factor
    design.dc_disconnect_amps = next_standard_breaker(isc_corrected)

    # String config (N/A for micro but record for reference)
    design.num_strings = n  # each panel is its own "string"
    design.panels_per_string = 1
    design.string_voc = project.panel.voc_v
    design.string_voc_cold = voc_cold
    design.string_isc = project.panel.isc_a


def _calc_string(design: ElectricalDesign, project, n: int, voc_cold: float,
                 t_cold_c: float, t_stc_c: float):
    """Calculate string configuration for string inverter systems."""
    panel = project.panel
    inv = project.inverter

    # Max panels per string (limited by inverter max DC voltage)
    max_per_string = int(inv.max_dc_voltage_v / voc_cold) if voc_cold > 0 else n

    # Min panels per string (MPPT minimum voltage)
    vmp_cold = panel.vmp_v * (1 + panel.temp_coeff_voc_frac * (t_cold_c - t_stc_c))
    min_per_string = math.ceil(inv.mppt_voltage_min_v / vmp_cold) if vmp_cold > 0 else 1

    # Optimal string length (target middle of MPPT range)
    target_vmp = (inv.mppt_voltage_min_v + inv.mppt_voltage_max_v) / 2
    optimal_length = max(min_per_string, min(max_per_string, round(target_vmp / panel.vmp_v)))

    # Distribute panels across strings
    num_strings = max(1, round(n / optimal_length))
    panels_per_string = math.ceil(n / num_strings)

    design.num_strings = num_strings
    design.panels_per_string = panels_per_string
    design.string_voc = panels_per_string * panel.voc_v
    design.string_voc_cold = panels_per_string * voc_cold
    design.string_vmp = panels_per_string * panel.vmp_v
    design.string_isc = panel.isc_a  # parallel strings don't add current per string

    # DC conductor sizing (CEC Rule 14-100: Isc × 1.56)
    dc_amps = panel.isc_a * 1.56 * num_strings
    design.dc_conductor = _conductor_for_amps(dc_amps)
    design.dc_disconnect_amps = next_standard_breaker(panel.isc_a * 1.25 * num_strings)

    # AC breaker (inverter output × 1.25)
    design.inverter_continuous_amps = inv.rated_ac_output_w / inv.ac_voltage_v
    ac_breaker_raw = design.inverter_continuous_amps * 1.25
    design.ac_breaker_amps = next_standard_breaker(ac_breaker_raw)

    # Validation warnings
    if design.string_voc_cold > inv.max_dc_voltage_v:
        design.warnings.append(
            f"String Voc at {t_cold_c}°C ({design.string_voc_cold:.1f}V) exceeds "
            f"inverter max DC voltage ({inv.max_dc_voltage_v}V)!"
        )
    if design.string_vmp < inv.mppt_voltage_min_v:
        design.warnings.append(
            f"String Vmp ({design.string_vmp:.1f}V) below inverter MPPT minimum "
            f"({inv.mppt_voltage_min_v}V)!"
        )


# ── Conductor lookup tables (CEC Table 2 / NEC 310.16 — 75°C Cu) ──────

CONDUCTOR_AMPACITY_75C = [
    (15, "#14 AWG Cu"), (20, "#12 AWG Cu"), (30, "#10 AWG Cu"),
    (40, "#8 AWG Cu"), (55, "#6 AWG Cu"), (70, "#4 AWG Cu"),
    (85, "#3 AWG Cu"), (95, "#2 AWG Cu"), (110, "#1 AWG Cu"),
    (125, "#1/0 AWG Cu"), (145, "#2/0 AWG Cu"), (165, "#3/0 AWG Cu"),
    (195, "#4/0 AWG Cu"),
]

EGC_TABLE = [
    (15, "#14 AWG Cu"), (20, "#12 AWG Cu"), (60, "#10 AWG Cu"),
    (100, "#8 AWG Cu"), (200, "#6 AWG Cu"), (300, "#4 AWG Cu"),
    (400, "#3 AWG Cu"), (500, "#2 AWG Cu"), (600, "#1 AWG Cu"),
    (800, "#1/0 AWG Cu"),
]


def calculate_string_config(panel, inverter, num_panels: int) -> dict:
    """Returns optimal string configuration.

    For microinverters: 1 panel per branch circuit, N branch circuits.
    For string inverters: compute series string length from Voc/MPPT window,
    then parallel strings needed.
    """
    inv_name = (getattr(inverter, 'model', '') or getattr(inverter, 'name', '') or '').upper()
    inv_type = (getattr(inverter, 'type', '') or getattr(inverter, 'inverter_type', '') or '').upper()
    is_micro = getattr(inverter, 'is_micro', False) or any(
        kw in inv_name + inv_type for kw in ('IQ8', 'IQ7', 'ENPHASE', 'MICRO')
    )

    isc = getattr(panel, 'isc_a', 0.0) or 0.0
    voc = getattr(panel, 'voc_v', 0.0) or 0.0
    vmp = getattr(panel, 'vmp_v', 0.0) or 0.0

    if is_micro:
        return {
            'type': 'microinverter',
            'modules_per_branch': 1,
            'num_branches': num_panels,
            'branch_current_a': round(isc * 1.25, 2),  # NEC 690.8 125% factor
            'system_voltage_v': voc,
        }
    else:
        max_input_v = (getattr(inverter, 'max_dc_voltage_v', None)
                       or getattr(inverter, 'max_input_voltage_v', 600) or 600)
        mppt_min_v = (getattr(inverter, 'mppt_voltage_min_v', None)
                      or getattr(inverter, 'mppt_min_v', 100) or 100)

        max_series = math.floor(max_input_v / voc * 0.80) if voc > 0 else 10
        min_series = math.ceil(mppt_min_v / vmp) if vmp > 0 else 1
        max_series = max(max_series, min_series)
        string_length = min(max_series, math.floor((max_series + min_series) / 2))
        string_length = max(string_length, 1)
        num_strings = math.ceil(num_panels / string_length)

        return {
            'type': 'string',
            'string_length': string_length,
            'num_strings': num_strings,
            'max_series': max_series,
            'min_series': min_series,
            'string_voc_v': round(string_length * voc, 1),
            'string_vmp_v': round(string_length * vmp, 1),
        }


def _conductor_for_amps(amps: float) -> str:
    """Look up minimum conductor size for given ampacity."""
    for rating, wire in CONDUCTOR_AMPACITY_75C:
        if rating >= amps:
            return wire
    return CONDUCTOR_AMPACITY_75C[-1][1]


def _egc_for_amps(breaker_amps: int) -> str:
    """Look up EGC size based on OCPD rating."""
    for rating, wire in EGC_TABLE:
        if rating >= breaker_amps:
            return wire
    return EGC_TABLE[-1][1]
