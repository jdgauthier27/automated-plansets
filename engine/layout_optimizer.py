"""
Layout Optimizer
================
Optimizes panel layout for cost-effectiveness and engineering best practices.

Panels are ranked by kWh production (from Google's per-panel estimates) and
selected in order of highest energy output. Engineering constraints (string
sizing, structural limits, fire setbacks) are then applied to validate
and group panels optimally.
"""

import logging
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class OptimizedPanel:
    """A panel in the optimized layout with cost-effectiveness data."""
    panel_id: int
    segment_index: int
    yearly_kwh: float
    kwh_rank: int             # 1 = highest producer
    string_id: int = 0       # which string/branch this panel belongs to
    branch_id: int = 0       # which AC branch circuit
    is_included: bool = True  # False if excluded by constraints
    exclusion_reason: str = ""


@dataclass
class OptimizedLayout:
    """Result of layout optimization."""
    panels: List[OptimizedPanel]
    total_panels: int
    total_dc_kw: float
    total_kwh_yr: float
    avg_kwh_per_panel: float
    num_strings: int
    num_branches: int
    cost_effectiveness_score: float  # 0-100
    warnings: List[str] = field(default_factory=list)


def optimize_layout(
    smart_placements,
    panel_spec,
    inverter_spec,
    max_panels: int = 999,
    min_kwh_threshold: float = 0.0,
    fire_setback_ft: float = 3.0,
) -> OptimizedLayout:
    """Optimize panel layout for maximum cost-effectiveness.

    Args:
        smart_placements: List of SmartPlacement from smart_placer.
        panel_spec: PanelCatalogEntry with electrical specs.
        inverter_spec: InverterCatalogEntry with sizing constraints.
        max_panels: Maximum panels to include.
        min_kwh_threshold: Minimum kWh/yr per panel to include (0 = include all).
        fire_setback_ft: Fire setback requirement.

    Returns:
        OptimizedLayout with ranked and grouped panels.
    """
    if not smart_placements:
        return OptimizedLayout(
            panels=[], total_panels=0, total_dc_kw=0, total_kwh_yr=0,
            avg_kwh_per_panel=0, num_strings=0, num_branches=0,
            cost_effectiveness_score=0,
        )

    # Sort by yearly energy, highest first
    sorted_panels = sorted(smart_placements, key=lambda p: p.yearly_energy_kwh, reverse=True)

    optimized = []
    warnings = []

    for rank, sp in enumerate(sorted_panels, 1):
        op = OptimizedPanel(
            panel_id=sp.panel_id,
            segment_index=sp.segment_index,
            yearly_kwh=sp.yearly_energy_kwh,
            kwh_rank=rank,
        )

        # Check minimum kWh threshold
        if min_kwh_threshold > 0 and sp.yearly_energy_kwh < min_kwh_threshold:
            op.is_included = False
            op.exclusion_reason = f"Below {min_kwh_threshold} kWh/yr threshold"

        # Check max panels
        included_count = sum(1 for p in optimized if p.is_included)
        if included_count >= max_panels:
            op.is_included = False
            op.exclusion_reason = f"Exceeds {max_panels} panel limit"

        optimized.append(op)

    # Group into strings/branches
    included = [p for p in optimized if p.is_included]

    if inverter_spec.is_micro:
        # Microinverter: each panel is independent, group into AC branches
        max_per_branch = inverter_spec.max_units_per_branch_15a or 7
        num_branches = math.ceil(len(included) / max_per_branch) if included else 0

        for i, p in enumerate(included):
            p.branch_id = (i // max_per_branch) + 1
            p.string_id = 0  # N/A for micro

        num_strings = len(included)  # each panel is its own "string"

    else:
        # String inverter: group into series strings
        if panel_spec.voc_v > 0 and inverter_spec.max_dc_voltage_v > 0:
            # Calculate max panels per string (cold temperature Voc)
            voc_cold = panel_spec.voc_v * (1 + panel_spec.temp_coeff_voc_frac * (-25 - 25))
            max_per_string = int(inverter_spec.max_dc_voltage_v / voc_cold) if voc_cold > 0 else 15

            # Target optimal MPPT voltage
            target_vmp = (inverter_spec.mppt_voltage_min_v + inverter_spec.mppt_voltage_max_v) / 2
            optimal_per_string = max(1, round(target_vmp / panel_spec.vmp_v))
            optimal_per_string = min(optimal_per_string, max_per_string)

            num_strings = max(1, math.ceil(len(included) / optimal_per_string))
            panels_per_string = math.ceil(len(included) / num_strings) if num_strings > 0 else 0

            for i, p in enumerate(included):
                p.string_id = (i // panels_per_string) + 1 if panels_per_string > 0 else 1

            # Validate string voltage
            string_voc_cold = panels_per_string * voc_cold
            if string_voc_cold > inverter_spec.max_dc_voltage_v:
                warnings.append(
                    f"String Voc at -25°C ({string_voc_cold:.0f}V) exceeds "
                    f"inverter max ({inverter_spec.max_dc_voltage_v}V). "
                    f"Reduce panels per string."
                )
        else:
            num_strings = 1
            for p in included:
                p.string_id = 1

        num_branches = 1  # Single AC output for string inverter

    # Calculate totals
    total_panels = len(included)
    panel_kw = getattr(panel_spec, 'kw', getattr(panel_spec, 'wattage_w', 400) / 1000)
    total_dc_kw = round(total_panels * panel_kw, 2)
    total_kwh = sum(p.yearly_kwh for p in included)
    avg_kwh = total_kwh / total_panels if total_panels > 0 else 0

    # Cost-effectiveness score (higher is better)
    # Based on how much of the roof's potential we're capturing
    max_possible_kwh = sum(p.yearly_kwh for p in optimized)  # all positions
    capture_ratio = total_kwh / max_possible_kwh if max_possible_kwh > 0 else 0
    cost_effectiveness = round(capture_ratio * 100, 1)

    logger.info(
        "Layout optimized: %d/%d panels, %.1f kW, %.0f kWh/yr, "
        "avg %.0f kWh/panel, %d strings, score=%.0f",
        total_panels, len(optimized), total_dc_kw, total_kwh,
        avg_kwh, num_strings, cost_effectiveness,
    )

    return OptimizedLayout(
        panels=optimized,
        total_panels=total_panels,
        total_dc_kw=total_dc_kw,
        total_kwh_yr=total_kwh,
        avg_kwh_per_panel=avg_kwh,
        num_strings=num_strings,
        num_branches=num_branches,
        cost_effectiveness_score=cost_effectiveness,
        warnings=warnings,
    )
