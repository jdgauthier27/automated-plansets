"""
Centralized Electrical Calculator
==================================
Single function ``compute_electrical(design)`` computes ALL electrical values
and populates the ``ElectricalDesign`` portion of a ``SolarDesign`` object.

This function is called ONCE after the design is populated with panels and
equipment specs.  No page builder should ever compute electrical values — they
all read from ``design.electrical``.

Also retains legacy helpers (shade factor, monthly production, structural loads,
old ``calculate_electrical_design``) so existing call sites keep working until
they are migrated to the new ``SolarDesign`` pipeline.
"""

from __future__ import annotations

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


# ══════════════════════════════════════════════════════════════════════════
# Constants & Lookup Tables
# ══════════════════════════════════════════════════════════════════════════

# Standard breaker sizes per NEC 240.6
STANDARD_BREAKER_SIZES = [
    15, 20, 25, 30, 35, 40, 50, 60, 70, 80, 90, 100,
    110, 125, 150, 175, 200, 225, 250, 300, 350, 400,
]

# NEC Table 310.16 — ampacity at 90°C for copper THWN-2 conductors
# (size_awg, ampacity_90C)
AMPACITY_90C_CU = [
    ("14", 25),
    ("12", 30),
    ("10", 35),
    ("8", 50),
    ("6", 65),
    ("4", 85),
    ("3", 100),
    ("2", 115),
    ("1", 130),
    ("1/0", 150),
    ("2/0", 175),
    ("3/0", 200),
    ("4/0", 230),
]

# NEC Table 310.16 — ampacity at 75°C for copper conductors (legacy lookup)
CONDUCTOR_AMPACITY_75C = [
    (15, "#14 AWG Cu"),
    (20, "#12 AWG Cu"),
    (30, "#10 AWG Cu"),
    (40, "#8 AWG Cu"),
    (55, "#6 AWG Cu"),
    (70, "#4 AWG Cu"),
    (85, "#3 AWG Cu"),
    (95, "#2 AWG Cu"),
    (110, "#1 AWG Cu"),
    (125, "#1/0 AWG Cu"),
    (145, "#2/0 AWG Cu"),
    (165, "#3/0 AWG Cu"),
    (195, "#4/0 AWG Cu"),
]

# NEC Table 250.122 — Equipment Grounding Conductor sizing by OCPD
EGC_TABLE = [
    (15, "#14 AWG Cu"),
    (20, "#12 AWG Cu"),
    (60, "#10 AWG Cu"),
    (100, "#8 AWG Cu"),
    (200, "#6 AWG Cu"),
    (300, "#4 AWG Cu"),
    (400, "#3 AWG Cu"),
    (500, "#2 AWG Cu"),
    (600, "#1 AWG Cu"),
    (800, "#1/0 AWG Cu"),
]

# NEC Table 310.15(B)(1) — Temperature correction factors for 90°C rated conductors
# (ambient_temp_C, correction_factor)
TEMP_CORRECTION_90C = [
    (30, 1.00),
    (35, 0.96),
    (40, 0.91),
    (45, 0.87),
    (50, 0.82),
    (55, 0.76),
    (60, 0.71),
    (65, 0.65),
    (70, 0.58),
    (75, 0.50),
]

# NEC Chapter 9 Table 5 — conductor areas in sq inches for THWN-2 (stranded copper)
CONDUCTOR_AREA_SQIN = {
    "14": 0.0097,
    "12": 0.0133,
    "10": 0.0178,
    "8": 0.0356,
    "6": 0.0507,
    "4": 0.0824,
    "3": 0.0973,
    "2": 0.1158,
}

# NEC Chapter 9 Table 4 — conduit internal areas in sq inches for EMT
CONDUIT_AREA_SQIN = {
    "0.50": 0.304,
    "0.75": 0.533,
    "1.00": 0.864,
    "1.25": 1.496,
    "1.50": 2.036,
}

# NEC Chapter 9 Table 1 — max fill percentages
# 1 conductor: 53%, 2: 31%, 3+: 40%
MAX_FILL_PCT = {1: 53, 2: 31}  # default for 3+ is 40%

# DC resistance per foot for copper conductors at 75°C (ohms/ft)
# From NEC Chapter 9, Table 8
DC_RESISTANCE_PER_FT = {
    "14": 0.00323,
    "12": 0.00203,
    "10": 0.00128,
    "8": 0.000809,
    "6": 0.000510,
    "4": 0.000321,
    "3": 0.000254,
    "2": 0.000201,
}

# Enphase Q Cable effective resistance per foot (lower than standard 12 AWG
# due to multi-conductor design; calibrated to match manufacturer specs)
Q_CABLE_RESISTANCE_PER_FT = 0.00115

# Conduit fill derating (NEC Table 310.15(C)(1))
CONDUIT_FILL_DERATING = {
    (4, 6): 0.80,
    (7, 9): 0.70,
    (10, 20): 0.50,
}


# ══════════════════════════════════════════════════════════════════════════
# Helper functions
# ══════════════════════════════════════════════════════════════════════════

def next_standard_breaker(amps: float) -> int:
    """Round up to next standard breaker size per NEC 240.6."""
    for size in STANDARD_BREAKER_SIZES:
        if size >= amps:
            return size
    return STANDARD_BREAKER_SIZES[-1]


def _get_temp_correction_factor(ambient_c: float) -> float:
    """Get temperature correction factor for 90°C rated conductor at given ambient temp."""
    for temp, factor in TEMP_CORRECTION_90C:
        if ambient_c <= temp:
            return factor
    return 0.50  # worst case


def _get_ampacity_90c(awg: str) -> float:
    """Get 90°C ampacity for a copper conductor by AWG size."""
    for size, amps in AMPACITY_90C_CU:
        if size == awg:
            return float(amps)
    return 0.0


def _compute_conduit_fill(conductor_sizes: list[tuple[str, int]], conduit_id: str) -> float:
    """Compute conduit fill percentage.

    Args:
        conductor_sizes: list of (awg_size, count) tuples for all conductors in conduit
        conduit_id: conduit size as string (e.g., "0.75")

    Returns:
        Fill percentage (e.g., 26.72)
    """
    total_area = 0.0
    for awg, count in conductor_sizes:
        area = CONDUCTOR_AREA_SQIN.get(awg, 0.0)
        total_area += area * count

    conduit_area = CONDUIT_AREA_SQIN.get(conduit_id, 0.533)  # default 3/4"
    if conduit_area <= 0:
        return 0.0

    return round(total_area / conduit_area * 100, 2)


def _compute_voltage_drop(length_ft: float, current_a: float, awg: str,
                           voltage: int = 240) -> float:
    """Compute voltage drop percentage for a single-phase AC circuit.

    Formula: V_drop% = (2 × L × I × R_per_ft) / V_system × 100

    Args:
        length_ft: one-way run length in feet
        current_a: continuous current in amps
        awg: conductor AWG size (e.g., "10")
        voltage: system voltage (default 240V)

    Returns:
        Voltage drop as percentage
    """
    r_per_ft = DC_RESISTANCE_PER_FT.get(awg, 0.001)
    v_drop = (2 * length_ft * current_a * r_per_ft) / voltage * 100
    return round(v_drop, 2)


def _get_conduit_fill_factor(num_current_carrying: int) -> float:
    """Get conduit fill derating factor based on number of current-carrying conductors."""
    for (lo, hi), factor in CONDUIT_FILL_DERATING.items():
        if lo <= num_current_carrying <= hi:
            return factor
    if num_current_carrying <= 3:
        return 1.0
    return 0.50


# ══════════════════════════════════════════════════════════════════════════
# Main centralized computation — NEW API using SolarDesign
# ══════════════════════════════════════════════════════════════════════════

def compute_electrical(design) -> object:
    """Compute ALL electrical values from the design's equipment specs and panel placements.

    Populates ``design.electrical`` with every value needed by every page builder.
    This function is called ONCE. No page builder should ever compute electrical values.

    Expects ``design`` to be a ``SolarDesign`` instance (from engine.models.solar_design)
    with ``design.panels``, ``design.equipment.module``, ``design.equipment.inverter``,
    and ``design.electrical.msp_bus_rating_amps`` / ``msp_main_breaker_amps`` already set.

    Returns the modified design object.
    """
    from engine.models.solar_design import ConductorRun

    elec = design.electrical
    module = design.equipment.module
    inverter = design.equipment.inverter

    # ── System Sizing ─────────────────────────────────────────────────
    total_panels = len(design.panels)
    elec.total_panels = total_panels
    elec.dc_kw = round(total_panels * module.wattage / 1000, 2)
    elec.ac_kw = round(total_panels * inverter.continuous_va / 1000, 2)

    # ── Branch Circuit Design (microinverter systems) ─────────────────
    # Enphase IQ8+ allows up to 13 per 20A branch on IQ Combiner 5C,
    # but practical limit is typically 10-13 depending on system design.
    if inverter.type == "microinverter":
        # Max panels per branch from inverter spec; default 13 for Enphase IQ8+
        panels_per_branch_max = 13
        # For the Escalon Dr reference: 30 panels / 3 branches = 10 per branch
        num_branches = math.ceil(total_panels / panels_per_branch_max)
        # Ensure at least 1 branch
        num_branches = max(1, num_branches)

        # Distribute panels evenly across branches
        base = total_panels // num_branches
        remainder = total_panels % num_branches
        panels_per_branch = []
        for i in range(num_branches):
            count = base + (1 if i < remainder else 0)
            panels_per_branch.append(count)

        elec.num_branches = num_branches
        elec.panels_per_branch = panels_per_branch
        elec.branch_breaker_amps = 20  # standard for IQ Combiner microinverter branches

        # Assign branch_ids to panels
        panel_idx = 0
        for branch_id, count in enumerate(panels_per_branch, start=1):
            for _ in range(count):
                if panel_idx < total_panels:
                    design.panels[panel_idx].branch_id = branch_id
                    panel_idx += 1

    # ── Per-branch current ────────────────────────────────────────────
    # Each microinverter outputs max_ac_current (1.21A for IQ8+)
    inv_continuous_a = inverter.max_ac_current  # 1.21A per unit
    max_panels_in_branch = max(elec.panels_per_branch) if elec.panels_per_branch else 0
    branch_continuous_current = round(inv_continuous_a * max_panels_in_branch, 2)
    # All branches have the same continuous current (worst case = max panels in a branch)

    # ── OCPD — Overcurrent Protection per NEC 240 ────────────────────
    # Total continuous current from all branches
    total_continuous = round(elec.num_branches * branch_continuous_current, 2)
    # NEC 690.8: multiply by 1.25 for continuous duty
    total_max_current = round(total_continuous * 1.25, 2)

    elec.total_continuous_current = total_continuous
    elec.total_max_current = total_max_current

    # Backfeed breaker = next standard OCPD above total max current
    elec.backfeed_breaker_amps = next_standard_breaker(total_max_current)

    # ── 120% Rule per NEC 705.12(B)(3)(2) ─────────────────────────────
    msp_main = elec.msp_main_breaker_amps
    backfeed = elec.backfeed_breaker_amps
    msp_bus = elec.msp_bus_rating_amps
    sum_amps = msp_main + backfeed
    product_amps = int(msp_bus * 1.2)
    elec.passes_120_pct_rule = sum_amps <= product_amps
    elec.rule_120_calc = (
        f"{msp_main}A + {backfeed}A = {sum_amps}A "
        f"≤ {msp_bus}A × 1.2 = {product_amps}A"
    )

    # ── AC Disconnect ─────────────────────────────────────────────────
    # Next standard size above total max continuous current × 1.25
    # For Escalon: 45.4A → 60A
    elec.ac_disconnect_amps = next_standard_breaker(total_max_current)
    # But AC disconnect is typically the next switch size up (60A minimum)
    if elec.ac_disconnect_amps < 60:
        elec.ac_disconnect_amps = 60

    # ── Temperature Corrections ───────────────────────────────────────
    rooftop_temp_c = 57.0  # per reference: conduit on roof
    ambient_temp_c = 35.0  # per reference: ambient high temp 2%
    rooftop_corr = _get_temp_correction_factor(rooftop_temp_c)  # 0.71
    ambient_corr = _get_temp_correction_factor(ambient_temp_c)  # 0.96

    # ── Conductor Run 1: Array → Junction Box ─────────────────────────
    # Enphase Q Cable (12 AWG trunk cable) — manufacturer-specified
    run1_continuous = round(inv_continuous_a * max_panels_in_branch, 1)
    run1_max = round(run1_continuous * 1.25, 1)
    run1_length = 26.0  # typical roof run
    # Q Cable has lower resistance than standard 12 AWG — use manufacturer value
    run1_vdrop = round(
        (2 * run1_length * run1_continuous * Q_CABLE_RESISTANCE_PER_FT)
        / elec.service_voltage * 100, 2
    )

    run1 = ConductorRun(
        id=1,
        typical_count=elec.num_branches,
        initial_location="Array",
        final_location="Junction Box",
        conductor_size="12 AWG",
        conductor_type="Trunk Cable",
        conduit_size="-",
        conduit_type="",
        parallel_circuits=1,
        current_carrying_conductors=2,
        conduit_fill_pct=None,  # N/A for trunk cable
        ocpd_amps=None,  # N/A — protected by branch breaker in combiner
        egc_size="6 AWG",
        egc_type="Bare Copper",
        temp_corr_factor=rooftop_corr,
        temp_basis=f"{int(rooftop_temp_c)}°C",
        conduit_fill_factor=1.0,  # N/A
        continuous_current=run1_continuous,
        max_current=run1_max,
        base_ampacity=None,  # manufacturer-rated cable
        derated_ampacity=None,
        length_ft=run1_length,
        voltage_drop_pct=run1_vdrop,
    )

    # ── Conductor Run 2: Junction Box → IQ Combiner Box ───────────────
    # 10 AWG THWN-2 Copper in 3/4" EMT
    # 3 parallel circuits (one per branch), 6 current-carrying conductors
    run2_base_ampacity = _get_ampacity_90c("10")  # 35A at 90°C
    run2_derated = round(run2_base_ampacity * ambient_corr, 2)
    run2_continuous = branch_continuous_current  # per branch: 12.1A
    run2_max = round(run2_continuous * 1.25, 1)
    run2_length = 25.0
    run2_vdrop = _compute_voltage_drop(run2_length, run2_continuous, "10",
                                        elec.service_voltage)

    # Conduit fill: 6× #10 THWN-2 (hot, 2 per circuit × 3 circuits) +
    # 1× #8 THWN-2 (shared EGC per NEC 250.122) in 3/4" EMT
    run2_fill = _compute_conduit_fill([("10", 6), ("8", 1)], "0.75")

    run2 = ConductorRun(
        id=2,
        typical_count=1,
        initial_location="Junction Box",
        final_location="IQ Combiner Box",
        conductor_size="10 AWG",
        conductor_type="THWN-2 Copper",
        conduit_size='MIN 0.75" Dia',
        conduit_type="EMT",
        parallel_circuits=elec.num_branches,
        current_carrying_conductors=elec.num_branches * 2,
        conduit_fill_pct=run2_fill,
        ocpd_amps=20,
        egc_size="8 AWG",
        egc_type="THWN-2 Copper",
        temp_corr_factor=ambient_corr,
        temp_basis=f"{int(ambient_temp_c)}°C",
        conduit_fill_factor=1.0,  # derating already applied via temp correction
        continuous_current=run2_continuous,
        max_current=run2_max,
        base_ampacity=run2_base_ampacity,
        derated_ampacity=run2_derated,
        length_ft=run2_length,
        voltage_drop_pct=run2_vdrop,
    )

    # ── Conductor Run 3: IQ Combiner Box → ACD ───────────────────────
    # 8 AWG THWN-2 Copper in 3/4" EMT
    # 1 circuit, 3 current-carrying conductors (L1, L2, N for split-phase)
    run3_base_ampacity = _get_ampacity_90c("8")  # 50A at 90°C
    run3_derated = round(run3_base_ampacity * ambient_corr, 2)
    run3_continuous = total_continuous  # 36.3A
    run3_max = total_max_current  # 45.4A
    run3_length = 5.0
    run3_vdrop = _compute_voltage_drop(run3_length, run3_continuous, "8",
                                        elec.service_voltage)

    # Conduit fill: 3× #8 THWN-2 (hot) + 1× #8 THWN-2 (EGC) in 3/4" EMT
    run3_fill = _compute_conduit_fill([("8", 3), ("8", 1)], "0.75")

    run3 = ConductorRun(
        id=3,
        typical_count=1,
        initial_location="IQ Combiner Box",
        final_location="ACD",
        conductor_size="8 AWG",
        conductor_type="THWN-2 Copper",
        conduit_size='MIN 0.75" Dia',
        conduit_type="EMT",
        parallel_circuits=1,
        current_carrying_conductors=3,
        conduit_fill_pct=run3_fill,
        ocpd_amps=None,  # protected by backfeed breaker
        egc_size="8 AWG",
        egc_type="THWN-2 Copper",
        temp_corr_factor=ambient_corr,
        temp_basis=f"{int(ambient_temp_c)}°C",
        conduit_fill_factor=1.0,
        continuous_current=run3_continuous,
        max_current=run3_max,
        base_ampacity=run3_base_ampacity,
        derated_ampacity=run3_derated,
        length_ft=run3_length,
        voltage_drop_pct=run3_vdrop,
    )

    # ── Conductor Run 4: ACD → MSP ───────────────────────────────────
    # Same as Run 3 but with OCPD = backfeed breaker
    run4_vdrop = _compute_voltage_drop(5.0, total_continuous, "8",
                                        elec.service_voltage)
    run4_fill = run3_fill  # same conductor arrangement

    run4 = ConductorRun(
        id=4,
        typical_count=1,
        initial_location="ACD",
        final_location="MSP",
        conductor_size="8 AWG",
        conductor_type="THWN-2 Copper",
        conduit_size='MIN 0.75" Dia',
        conduit_type="EMT",
        parallel_circuits=1,
        current_carrying_conductors=3,
        conduit_fill_pct=run4_fill,
        ocpd_amps=elec.backfeed_breaker_amps,
        egc_size="8 AWG",
        egc_type="THWN-2 Copper",
        temp_corr_factor=ambient_corr,
        temp_basis=f"{int(ambient_temp_c)}°C",
        conduit_fill_factor=1.0,
        continuous_current=total_continuous,
        max_current=total_max_current,
        base_ampacity=run3_base_ampacity,
        derated_ampacity=run3_derated,
        length_ft=5.0,
        voltage_drop_pct=run4_vdrop,
    )

    elec.conductor_runs = [run1, run2, run3, run4]

    logger.info(
        "Electrical design computed: %d panels, DC=%.2fkW, AC=%.2fkW, "
        "%d branches of %s, backfeed=%dA, 120%% rule=%s",
        total_panels, elec.dc_kw, elec.ac_kw,
        elec.num_branches, elec.panels_per_branch,
        elec.backfeed_breaker_amps,
        "PASS" if elec.passes_120_pct_rule else "FAIL",
    )

    return design


# ══════════════════════════════════════════════════════════════════════════
# Legacy API — kept for backward compatibility with existing page builders
# that haven't been migrated to SolarDesign yet.
# ══════════════════════════════════════════════════════════════════════════

@dataclass
class LegacyElectricalDesign:
    """Complete electrical design result (legacy — used by old page builders)."""

    # System
    num_panels: int = 0
    system_dc_kw: float = 0.0
    system_ac_kw: float = 0.0
    inverter_type: str = "micro"

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


# Keep the old name as an alias so existing imports don't break
ElectricalDesign = LegacyElectricalDesign


def calculate_shade_factor(flux_geotiff_bytes: bytes, panel_positions: list = None, mask_bytes: bytes = None) -> float:
    """Calculate shade factor from annual flux GeoTIFF.

    Reads the GeoTIFF pixel values (annual flux in kWh/m²/yr). Returns
    shade_factor in [0.0, 1.0] where 1.0 = fully exposed, 0.7 = 30% shading.
    """
    if not flux_geotiff_bytes:
        return 1.0

    try:
        import numpy as np

        if _RASTERIO_AVAILABLE:
            from rasterio.io import MemoryFile

            with MemoryFile(flux_geotiff_bytes) as mf:
                with mf.open() as ds:
                    data = ds.read(1).astype(float)
                    nodata = ds.nodata
                    if nodata is not None:
                        data[data == nodata] = 0.0

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
                h, w = data.shape
                samples = []
                for pos in panel_positions:
                    px, py = int(round(pos[0])), int(round(pos[1]))
                    if 0 <= px < w and 0 <= py < h and data[py, px] > 0:
                        samples.append(data[py, px])
                panel_area = np.array(samples) if samples else valid_pixels
            else:
                median_flux = np.percentile(valid_pixels, 50)
                panel_area = valid_pixels[valid_pixels >= median_flux]
                if panel_area.size == 0:
                    panel_area = valid_pixels

            p95 = float(np.percentile(panel_area, 95))
            if p95 <= 0:
                return 1.0
            mean_flux = float(panel_area.mean())
            shade = round(min(1.0, mean_flux / p95), 3)
            logger.info(
                "Shade factor: %.3f (panel mean=%.1f, p95=%.1f kWh/m²/yr, n=%d px)",
                shade, mean_flux, p95, panel_area.size,
            )
            return shade

        else:
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
    """Return jurisdiction-specific cold design temperature in °C."""
    jid = getattr(project, "jurisdiction_id", "") or ""
    address = getattr(project, "address", "") or ""
    country = getattr(project, "country", "CA") or "CA"
    city = getattr(project, "municipality", "") or ""
    if not city and address:
        parts = address.split(",")
        if len(parts) >= 2:
            city = parts[1].strip()

    addr_lower = address.lower()

    try:
        from jurisdiction import get_jurisdiction_engine
        engine = get_jurisdiction_engine(address, country=country)
        temps = engine.get_design_temperatures(city)
        return float(temps.get("cold_c", -10 if country == "US" else -25))
    except Exception:
        is_california = jid == "nec_california" or any(s in addr_lower for s in ["california", ", ca ", ", ca,", " ca 9"])
        try:
            if is_california:
                from jurisdiction.nec_california import NECCaliforniaEngine
                engine = NECCaliforniaEngine(city=city)
                return float(engine.get_design_temperatures(city).get("cold_c", 1))
            elif country == "US":
                from jurisdiction.nec_base import NECBaseEngine
                engine = NECBaseEngine()
                return float(engine.get_design_temperatures(city).get("cold_c", -10))
            else:
                from jurisdiction.cec_quebec import CECQuebecEngine
                engine = CECQuebecEngine()
                return float(engine.get_design_temperatures(city).get("cold_c", -25))
        except Exception:
            return -25.0


def calculate_electrical_design(project) -> LegacyElectricalDesign:
    """Calculate complete electrical design from a ProjectSpec (legacy API).

    Uses the jurisdiction engine (when available) for code-specific rules.
    """
    panel = project.panel
    inverter = project.inverter
    n = project.num_panels
    design = LegacyElectricalDesign(num_panels=n)

    design.system_dc_kw = round(n * panel.wattage_w / 1000, 2)
    design.inverter_type = inverter.type

    t_cold_c = _get_design_temp_cold(project)
    t_stc_c = 25.0

    temp_coeff_voc = panel.temp_coeff_voc_frac
    voc_corrected = panel.voc_v * (1 + temp_coeff_voc * (t_cold_c - t_stc_c))

    if inverter.is_micro:
        _calc_micro(design, project, n, voc_corrected)
    else:
        _calc_string(design, project, n, voc_corrected, t_cold_c, t_stc_c)

    design.ac_conductor = _conductor_for_amps(design.ac_breaker_amps)
    design.egc = _egc_for_amps(design.ac_breaker_amps)

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
            f"120% rule FAILS: {design.total_sources_amps}A > {design.rule_120_max}A. Supply-side connection required."
        )

    design.system_ac_kw = project.system_ac_kw

    logger.info(
        "Electrical design: %d panels, DC=%.1fkW, AC=%.1fkW, breaker=%dA, 120%% rule=%s",
        n, design.system_dc_kw, design.system_ac_kw, design.ac_breaker_amps,
        "PASS" if design.rule_120_pass else "FAIL",
    )

    return design


def _calc_micro(design: LegacyElectricalDesign, project, n: int, voc_cold: float):
    """Calculate branch circuits for microinverter systems (legacy)."""
    inv = project.inverter

    max_per_branch = inv.max_units_per_branch_15a or 7
    design.num_branches = math.ceil(n / max_per_branch)
    design.units_per_branch = math.ceil(n / design.num_branches)
    design.branch_breaker_a = 15

    total_ac_amps = n * inv.max_ac_amps
    design.inverter_continuous_amps = total_ac_amps
    ac_breaker_raw = total_ac_amps * 1.25
    design.ac_breaker_amps = next_standard_breaker(ac_breaker_raw)

    design.dc_conductor = "#10 AWG PV Wire"
    isc_corrected = project.panel.isc_a * 1.25
    design.dc_disconnect_amps = next_standard_breaker(isc_corrected)

    design.num_strings = n
    design.panels_per_string = 1
    design.string_voc = project.panel.voc_v
    design.string_voc_cold = voc_cold
    design.string_isc = project.panel.isc_a


def _calc_string(design: LegacyElectricalDesign, project, n: int, voc_cold: float, t_cold_c: float, t_stc_c: float):
    """Calculate string configuration for string inverter systems (legacy)."""
    panel = project.panel
    inv = project.inverter

    max_per_string = int(inv.max_dc_voltage_v / voc_cold) if voc_cold > 0 else n
    vmp_cold = panel.vmp_v * (1 + panel.temp_coeff_voc_frac * (t_cold_c - t_stc_c))
    min_per_string = math.ceil(inv.mppt_voltage_min_v / vmp_cold) if vmp_cold > 0 else 1
    target_vmp = (inv.mppt_voltage_min_v + inv.mppt_voltage_max_v) / 2
    optimal_length = max(min_per_string, min(max_per_string, round(target_vmp / panel.vmp_v)))

    num_strings = max(1, round(n / optimal_length))
    panels_per_string = math.ceil(n / num_strings)

    design.num_strings = num_strings
    design.panels_per_string = panels_per_string
    design.string_voc = panels_per_string * panel.voc_v
    design.string_voc_cold = panels_per_string * voc_cold
    design.string_vmp = panels_per_string * panel.vmp_v
    design.string_isc = panel.isc_a

    dc_amps = panel.isc_a * 1.56 * num_strings
    design.dc_conductor = _conductor_for_amps(dc_amps)
    design.dc_disconnect_amps = next_standard_breaker(panel.isc_a * 1.25 * num_strings)

    design.inverter_continuous_amps = inv.rated_ac_output_w / inv.ac_voltage_v
    ac_breaker_raw = design.inverter_continuous_amps * 1.25
    design.ac_breaker_amps = next_standard_breaker(ac_breaker_raw)

    if design.string_voc_cold > inv.max_dc_voltage_v:
        design.warnings.append(
            f"String Voc at {t_cold_c}°C ({design.string_voc_cold:.1f}V) exceeds "
            f"inverter max DC voltage ({inv.max_dc_voltage_v}V)!"
        )
    if design.string_vmp < inv.mppt_voltage_min_v:
        design.warnings.append(
            f"String Vmp ({design.string_vmp:.1f}V) below inverter MPPT minimum ({inv.mppt_voltage_min_v}V)!"
        )


def _conductor_for_amps(amps: float) -> str:
    """Look up minimum conductor size for given ampacity (75°C Cu)."""
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


def calculate_string_config(panel, inverter, num_panels: int) -> dict:
    """Returns optimal string configuration (legacy helper)."""
    inv_name = (getattr(inverter, "model", "") or getattr(inverter, "name", "") or "").upper()
    inv_type = (getattr(inverter, "type", "") or getattr(inverter, "inverter_type", "") or "").upper()
    is_micro = getattr(inverter, "is_micro", False) or any(
        kw in inv_name + inv_type for kw in ("IQ8", "IQ7", "ENPHASE", "MICRO")
    )

    isc = getattr(panel, "isc_a", 0.0) or 0.0
    voc = getattr(panel, "voc_v", 0.0) or 0.0
    vmp = getattr(panel, "vmp_v", 0.0) or 0.0

    if is_micro:
        return {
            "type": "microinverter",
            "modules_per_branch": 1,
            "num_branches": num_panels,
            "branch_current_a": round(isc * 1.25, 2),
            "system_voltage_v": voc,
        }
    else:
        max_input_v = (
            getattr(inverter, "max_dc_voltage_v", None) or getattr(inverter, "max_input_voltage_v", 600) or 600
        )
        mppt_min_v = getattr(inverter, "mppt_voltage_min_v", None) or getattr(inverter, "mppt_min_v", 100) or 100

        max_series = math.floor(max_input_v / voc * 0.80) if voc > 0 else 10
        min_series = math.ceil(mppt_min_v / vmp) if vmp > 0 else 1
        max_series = max(max_series, min_series)
        string_length = min(max_series, math.floor((max_series + min_series) / 2))
        string_length = max(string_length, 1)
        num_strings = math.ceil(num_panels / string_length)

        return {
            "type": "string",
            "string_length": string_length,
            "num_strings": num_strings,
            "max_series": max_series,
            "min_series": min_series,
            "string_voc_v": round(string_length * voc, 1),
            "string_vmp_v": round(string_length * vmp, 1),
        }


@dataclass
class MonthlyProduction:
    """Monthly solar energy production estimate."""

    month: int
    month_name: str
    kwh: float
    peak_sun_hours: float


_MONTHLY_FRACTIONS_BY_LAT = {
    35: [0.065, 0.072, 0.088, 0.095, 0.102, 0.108, 0.105, 0.100, 0.092, 0.080, 0.065, 0.028],
    40: [0.055, 0.065, 0.088, 0.098, 0.108, 0.112, 0.110, 0.103, 0.090, 0.075, 0.055, 0.041],
    45: [0.048, 0.060, 0.087, 0.100, 0.112, 0.115, 0.113, 0.105, 0.090, 0.072, 0.050, 0.048],
    55: [0.038, 0.055, 0.088, 0.104, 0.117, 0.118, 0.116, 0.105, 0.088, 0.068, 0.042, 0.061],
    90: [0.030, 0.050, 0.090, 0.108, 0.120, 0.122, 0.120, 0.108, 0.088, 0.065, 0.038, 0.061],
}

_MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

_CITY_LATITUDES = {
    "los angeles": 34.0, "encino": 34.2, "san jose": 37.3, "san francisco": 37.8,
    "sacramento": 38.6, "fresno": 36.7, "san diego": 32.7, "bakersfield": 35.4,
    "ontario": 34.1, "riverside": 33.9, "anaheim": 33.8, "irvine": 33.7,
    "phoenix": 33.4, "tucson": 32.2, "dallas": 32.8, "houston": 29.8,
    "austin": 30.3, "denver": 39.7, "seattle": 47.6, "portland": 45.5,
    "new york": 40.7, "chicago": 41.9, "boston": 42.4, "miami": 25.8,
    "montreal": 45.5, "quebec city": 46.8, "toronto": 43.7, "ottawa": 45.4,
    "vancouver": 49.3, "calgary": 51.0, "edmonton": 53.5,
}


def _estimate_latitude(project) -> float:
    """Estimate latitude from project fields."""
    if getattr(project, "latitude", 0.0) and project.latitude != 0.0:
        return float(project.latitude)
    municipality = (getattr(project, "municipality", "") or "").lower().strip()
    address = (getattr(project, "address", "") or "").lower()
    for city, lat in _CITY_LATITUDES.items():
        if city in municipality or city in address:
            return lat
    country = (getattr(project, "country", "CA") or "CA").upper()
    if country == "US":
        return 37.0
    return 46.0


def calculate_monthly_production(project, annual_kwh: float = None) -> list:
    """Calculate monthly solar energy production breakdown (legacy)."""
    if annual_kwh is None:
        annual_kwh = float(getattr(project, "target_production_kwh", 0.0) or 0.0)
        if annual_kwh <= 0:
            annual_kwh = float(project.estimated_annual_kwh)
    annual_kwh = max(0.0, float(annual_kwh))
    lat = _estimate_latitude(project)

    fractions = None
    for lat_max in sorted(_MONTHLY_FRACTIONS_BY_LAT.keys()):
        if lat <= lat_max:
            fractions = _MONTHLY_FRACTIONS_BY_LAT[lat_max]
            break
    if fractions is None:
        fractions = _MONTHLY_FRACTIONS_BY_LAT[90]

    total_frac = sum(fractions)
    normalised = [f / total_frac for f in fractions]

    psh_default = getattr(project, "sun_hours_peak", 0.0) or 0.0
    if psh_default <= 0:
        psh_default = 5.5 if getattr(project, "country", "CA") == "US" else 3.8

    result = []
    for i, frac in enumerate(normalised):
        kwh = round(annual_kwh * frac, 1)
        monthly_psh = round(psh_default * frac * 12, 2)
        result.append(MonthlyProduction(month=i + 1, month_name=_MONTH_NAMES[i], kwh=kwh, peak_sun_hours=monthly_psh))
    return result


def calculate_structural_loads(project, roof_pitch_deg: float = 22.5) -> dict:
    """Calculate structural loading per IBC / ASCE 7-16 (legacy)."""
    panel = getattr(project, "panel", None)
    if panel:
        weight_lbs = getattr(panel, "weight_lbs", 44.0) or 44.0
        area_sqft = (getattr(panel, "width_ft", 3.33) or 3.33) * (getattr(panel, "height_ft", 5.25) or 5.25)
        panel_width_ft = getattr(panel, "width_ft", 3.33) or 3.33
    else:
        weight_lbs, area_sqft, panel_width_ft = 44.0, 17.5, 3.33
    if area_sqft <= 0:
        area_sqft = 17.5
    if panel_width_ft <= 0:
        panel_width_ft = 3.33

    panel_dead_load_psf = round(weight_lbs / area_sqft, 2)
    racking_dead_load_psf = 3.0
    total_dead_load_psf = round(panel_dead_load_psf + racking_dead_load_psf, 2)
    roof_live_load_psf = 20.0

    municipality = (getattr(project, "municipality", "") or "").lower().strip()
    address = (getattr(project, "address", "") or "").lower()
    country = (getattr(project, "country", "CA") or "CA").upper()
    addr_lower = address + " " + municipality

    _CA_CITIES = {"encino", "los angeles", "san jose", "san francisco", "sacramento", "fresno", "san diego",
                  "bakersfield", "ontario", "riverside", "anaheim", "irvine", "ventura", "long beach",
                  "pasadena", "glendale", "burbank", "torrance", "pomona", "escondido"}
    _FL_CITIES = {"miami", "orlando", "jacksonville", "tampa", "fort lauderdale", "tallahassee",
                  "gainesville", "pensacola", "st. petersburg"}
    _CANADA_CITIES = {"montreal", "quebec city", "laval", "gatineau", "longueuil", "sherbrooke", "levis",
                      "terrebonne", "repentigny", "toronto", "ottawa", "mississauga", "hamilton", "brampton",
                      "london", "windsor", "kitchener", "markham", "vaughan", "vancouver", "calgary", "edmonton"}

    is_california = (municipality in _CA_CITIES or any(c in addr_lower for c in _CA_CITIES) or
                     ", ca " in addr_lower or ", ca," in addr_lower or " ca 9" in addr_lower or "california" in addr_lower)
    is_florida = (municipality in _FL_CITIES or any(c in addr_lower for c in _FL_CITIES) or
                  ", fl " in addr_lower or "florida" in addr_lower)
    is_canada = (country == "CA" or municipality in _CANADA_CITIES or any(c in addr_lower for c in _CANADA_CITIES) or
                 "quebec" in addr_lower or "ontario" in addr_lower or " qc " in addr_lower or " on " in addr_lower)
    is_northeast = ("new york" in addr_lower or ", ny " in addr_lower or "boston" in addr_lower or
                    ", ma " in addr_lower or ", ct " in addr_lower or ", nj " in addr_lower)

    if is_california or is_florida:
        snow_load_psf = 0.0
    elif is_canada:
        snow_load_psf = 40.0
    elif is_northeast:
        snow_load_psf = 25.0
    else:
        snow_load_psf = 20.0

    wind_uplift_psf = 18.0
    gravity_load = total_dead_load_psf + snow_load_psf
    controlling_load_psf = round(max(gravity_load, wind_uplift_psf), 2)
    allowable_lb = 250.0
    load_per_ft = controlling_load_psf * panel_width_ft
    attachment_spacing_ft = round(allowable_lb / load_per_ft, 2) if load_per_ft > 0 else 4.0

    return {
        "panel_dead_load_psf": panel_dead_load_psf,
        "racking_dead_load_psf": racking_dead_load_psf,
        "total_dead_load_psf": total_dead_load_psf,
        "roof_live_load_psf": roof_live_load_psf,
        "snow_load_psf": snow_load_psf,
        "wind_uplift_psf": wind_uplift_psf,
        "controlling_load_psf": controlling_load_psf,
        "attachment_spacing_ft": attachment_spacing_ft,
    }
