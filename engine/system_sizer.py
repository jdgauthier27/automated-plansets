"""
System Sizer
=============
Auto-sizes a PV system based on annual consumption target and panel specs.
"""

import math
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def calculate_panels_needed(
    target_kwh: float,
    panel_wattage_w: int,
    sun_hours_peak: float = 3.80,
    system_loss_factor: float = 0.80,
) -> int:
    """Calculate number of panels needed to meet annual kWh target.

    Args:
        target_kwh: Annual production target in kWh.
        panel_wattage_w: Panel STC wattage.
        sun_hours_peak: Peak sun hours per day for the location.
        system_loss_factor: System derating factor (default 0.80 = 80%).

    Returns:
        Number of panels needed (rounded up).
    """
    kwh_per_panel_per_year = panel_wattage_w * sun_hours_peak * 365 * system_loss_factor / 1000.0
    if kwh_per_panel_per_year <= 0:
        return 1
    panels = math.ceil(target_kwh / kwh_per_panel_per_year)
    logger.info(
        "Auto-sizing: %.0f kWh target / %.0f kWh per panel = %d panels",
        target_kwh,
        kwh_per_panel_per_year,
        panels,
    )
    return max(1, panels)


def estimate_annual_kwh(
    num_panels: int,
    panel_wattage_w: int,
    sun_hours_peak: float = 3.80,
    system_loss_factor: float = 0.80,
) -> float:
    """Estimate annual production for a given system size."""
    return num_panels * panel_wattage_w * sun_hours_peak * 365 * system_loss_factor / 1000.0


def calculate_offset_target(
    annual_consumption_kwh: float,
    offset_pct: float = 100.0,
) -> float:
    """Calculate target kWh from consumption and desired offset percentage."""
    return annual_consumption_kwh * (offset_pct / 100.0)
