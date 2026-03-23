"""
BOM Calculator
==============
Computes Bill of Materials quantities from a ProjectSpec.

All quantities are derived from project data — no hardcoded counts.
"""

import math
from dataclasses import dataclass
from typing import List

from models.project import ProjectSpec


@dataclass
class BOMItem:
    equipment: str
    qty: int | str      # int for counted items, str for "AS REQ."
    description: str


def calculate_bom(project: ProjectSpec) -> List[BOMItem]:
    """Return a list of BOMItems for the given project.

    Quantity formulas are based on the IronRidge XR-10 / FlashFoot2 reference
    planset (YifeiSun RevB, 30 panels) and are scaled linearly from num_panels.
    """
    items: List[BOMItem] = []
    n = project.num_panels

    # ── Modules ──────────────────────────────────────────────────────────────
    panel = project.panel
    items.append(BOMItem(
        "MODULE",
        n,
        f"{panel.manufacturer} {panel.model} ({panel.wattage_w}W {panel.technology.upper()})",
    ))

    # ── Inverters ─────────────────────────────────────────────────────────────
    inv = project.inverter
    if inv.is_micro:
        items.append(BOMItem(
            "MICROINVERTER",
            n,
            f"{inv.manufacturer} {inv.model} ({inv.ac_voltage_v}V)",
        ))
        # ── Enphase Q Cable connectors ────────────────────────────────────────
        # Q Cable count = 1 connector per inverter + 2 connectors per circuit
        # (1 circuit-start trunk + 1 branch terminator tail) + 1 system-end cap.
        # Formula verified against Enphase IQ8PLUS 30-panel reference (37 connectors,
        # 3 circuits at max 11 per branch): 30 + 2×3 + 1 = 37.
        _max_branch = inv.max_units_per_branch_15a or 7
        _n_circuits = math.ceil(n / _max_branch)
        n_q_cables = n + 2 * _n_circuits + 1
        items.append(BOMItem(
            "Q CABLE",
            n_q_cables,
            f"{inv.manufacturer} Q Cable 240V (Per Connector)",
        ))
    else:
        items.append(BOMItem(
            "STRING INVERTER",
            1,
            f"{inv.manufacturer} {inv.model}",
        ))

    # ── Rails ─────────────────────────────────────────────────────────────────
    # 2 rails per row (top + bottom chord).
    # panels_per_rail: derived from longest available rail length and actual
    # panel short-side width (portrait orientation).
    rack = project.racking
    _rail_ft = max(rack.available_lengths_ft) if rack.available_lengths_ft else 14
    _rail_in = _rail_ft * 12
    _panel_w_in = panel.dimensions.width_mm / 25.4   # short side in portrait
    panels_per_rail = max(1, int(_rail_in / _panel_w_in))
    n_rails = math.ceil(n / panels_per_rail) * 2
    items.append(BOMItem(
        "MOUNTING RAIL",
        n_rails,
        f"{rack.manufacturer} {rack.model} RAIL",
    ))

    # ── Mid clamps (between adjacent panels on each rail) ─────────────────────
    # Each interior gap between panels needs 2 clamps (top + bottom rail).
    # Panels per row ≈ panels_per_rail; interior gaps = (panels_per_row - 1).
    panels_per_row = panels_per_rail
    num_rows = math.ceil(n / panels_per_row)
    interior_gaps = max(0, panels_per_row - 1) * num_rows
    # ×3: IronRidge XR-10 portrait installs use 3 UFO positions per interior gap
    # (top-rail, mid-span, bottom-rail) per the reference 30-panel planset (72 total).
    n_mid_clamps = interior_gaps * 3
    mid_clamp_model = rack.clamps.mid_clamp or f"{rack.manufacturer} Mid Clamp"
    items.append(BOMItem(
        "MID CLAMP",
        max(4, n_mid_clamps),
        f"{mid_clamp_model} (INTEGRATED GROUNDING)",
    ))

    # ── Bonded splices (rail-to-rail joins) ───────────────────────────────────
    # Adjacent row-pairs share a splice at the rail boundary; one splice per
    # two rails (every pair of top/bottom rails for one row shares a splice
    # with the next row's rail run).  Formula: n_rails // 2.
    # Reference: 16 rails → 8 splices (YifeiSun RevB A-103).
    n_splices = n_rails // 2
    items.append(BOMItem(
        "BONDED SPLICE",
        n_splices,
        f"{rack.manufacturer} Splice Kit",
    ))

    # ── End clamps (at each exposed rail end) ─────────────────────────────────
    # Each rail has 2 ends, but splice positions replace one end clamp each.
    # Formula: n_rails × 2 − n_splices.
    # Reference: 16 rails − 8 splices = 24 end clamps (YifeiSun RevB A-103).
    n_end_clamps = n_rails * 2 - n_splices
    end_clamp_model = rack.clamps.end_clamp or f"{rack.manufacturer} End Clamp"
    items.append(BOMItem(
        "END CLAMP",
        n_end_clamps,
        f"{end_clamp_model} STANDARD",
    ))

    # ── Attachments (roof mounts) ─────────────────────────────────────────────
    # IronRidge FlashFoot2: 4 L-feet per panel (2 per rail × 2 rails).
    # Reference: 30 panels × 4 = 120 attachments (YifeiSun RevB A-103).
    att = project.attachment
    att_count = n * 4
    items.append(BOMItem(
        "MOUNTING POINT",
        att_count,
        f"{att.manufacturer} {att.model}" if att.model else "FlashFoot2 Deck Mount",
    ))

    # ── Grounding lugs ────────────────────────────────────────────────────────
    # 1 grounding lug per panel minimum (rail bond at each module location).
    # Reference: 30 panels → 30 lugs (YifeiSun RevB A-103).
    n_grounding = n
    items.append(BOMItem(
        "GROUNDING LUG",
        n_grounding,
        f"{rack.manufacturer} Grounding Lug",
    ))

    # ── Electrical (fixed counts for residential) ─────────────────────────────
    items.append(BOMItem("LOAD CENTER", 1, "125A RATED PV LOAD CENTER (BACKFED FROM MAIN SERVICE PANEL)"))
    items.append(BOMItem("CONDUIT", "AS REQ.", '3/4" EMT (EXTERIOR) + 1/2" EMT (INTERIOR)'))
    items.append(BOMItem("WIRE", "AS REQ.", "THWN-2 #10 AWG CU (IN EMT, J-BOX ONWARD)"))

    return items
