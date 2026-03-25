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
    unit_cost_usd: float = 0.0


def calculate_bom(project: ProjectSpec) -> dict:
    """Return a dict with BOM line_items and cost rollup for the given project.

    Quantity formulas are based on the IronRidge XR-10 / FlashFoot2 reference
    planset (YifeiSun RevB, 30 panels) and are scaled linearly from num_panels.

    Returns:
        dict with keys: line_items, equipment_cost_usd, labor_cost_usd,
        labor_rate_per_watt, total_cost_usd.
    """
    items: List[BOMItem] = []
    n = project.num_panels

    # ── Modules ──────────────────────────────────────────────────────────────
    panel = project.panel
    items.append(BOMItem(
        "MODULE",
        n,
        f"{panel.manufacturer} {panel.model} ({panel.wattage_w}W {panel.technology.upper()})",
        unit_cost_usd=panel.unit_cost_usd,
    ))

    # ── Inverters ─────────────────────────────────────────────────────────────
    inv = project.inverter
    if inv.is_micro:
        items.append(BOMItem(
            "MICROINVERTER",
            n,
            f"{inv.manufacturer} {inv.model} ({inv.ac_voltage_v}V)",
            unit_cost_usd=inv.unit_cost_usd,
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
            unit_cost_usd=8.00,
        ))
    else:
        items.append(BOMItem(
            "STRING INVERTER",
            1,
            f"{inv.manufacturer} {inv.model}",
            unit_cost_usd=inv.unit_cost_usd,
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
        unit_cost_usd=rack.unit_cost_usd,
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
        unit_cost_usd=3.00,
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
        unit_cost_usd=8.00,
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
        unit_cost_usd=4.00,
    ))

    # ── Attachments (roof mounts) ─────────────────────────────────────────────
    # IronRidge FlashFoot2: 4 L-feet per panel (2 per rail × 2 rails).
    # Reference: 30 panels × 4 = 120 attachments (YifeiSun RevB A-103).
    att = project.attachment
    att_count = n * 4
    att_cost = att.unit_cost_usd if att.unit_cost_usd > 0 else 12.00
    items.append(BOMItem(
        "MOUNTING POINT",
        att_count,
        f"{att.manufacturer} {att.model}" if att.model else "FlashFoot2 Deck Mount",
        unit_cost_usd=att_cost,
    ))

    # ── Grounding lugs ────────────────────────────────────────────────────────
    # 1 grounding lug per panel minimum (rail bond at each module location).
    # Reference: 30 panels → 30 lugs (YifeiSun RevB A-103).
    n_grounding = n
    items.append(BOMItem(
        "GROUNDING LUG",
        n_grounding,
        f"{rack.manufacturer} Grounding Lug",
        unit_cost_usd=2.00,
    ))

    # ── Electrical (fixed counts for residential) ─────────────────────────────
    items.append(BOMItem("LOAD CENTER", 1, "125A RATED PV LOAD CENTER (BACKFED FROM MAIN SERVICE PANEL)", unit_cost_usd=150.00))
    items.append(BOMItem("CONDUIT", "AS REQ.", '3/4" EMT (EXTERIOR) + 1/2" EMT (INTERIOR)'))
    items.append(BOMItem("WIRE", "AS REQ.", "THWN-2 #10 AWG CU (IN EMT, J-BOX ONWARD)"))

    # ── Convert to line_items dicts and compute equipment cost ────────────────
    line_items = []
    equipment_cost_usd = 0.0
    for item in items:
        if isinstance(item.qty, (int, float)):
            total = round(item.qty * item.unit_cost_usd, 2)
            equipment_cost_usd += total
        else:
            total = 0.0
        line_items.append({
            "description": item.equipment,
            "qty": item.qty,
            "unit": "ea",
            "unit_cost_usd": item.unit_cost_usd,
            "total_cost_usd": total,
            "notes": item.description,
        })
    equipment_cost_usd = round(equipment_cost_usd, 2)

    # ── Labor ─────────────────────────────────────────────────────────────────
    LABOR_RATE_PER_WATT = 0.25  # $/W roof-mounted
    system_watts = project.num_panels * project.panel.wattage_w
    labor_cost_usd = round(system_watts * LABOR_RATE_PER_WATT, 2)
    line_items.append({
        "description": "Installation Labor",
        "qty": 1,
        "unit": "lot",
        "unit_cost_usd": labor_cost_usd,
        "total_cost_usd": labor_cost_usd,
        "notes": f"${LABOR_RATE_PER_WATT}/W x {system_watts}W",
    })

    total_cost_usd = round(equipment_cost_usd + labor_cost_usd, 2)

    return {
        "line_items": line_items,
        "equipment_cost_usd": equipment_cost_usd,
        "labor_cost_usd": labor_cost_usd,
        "labor_rate_per_watt": LABOR_RATE_PER_WATT,
        "total_cost_usd": total_cost_usd,
    }


def calculate_project_cost(bom_items: list, project_dc_kw: float) -> dict:
    """Estimate total project cost from BOM items with unit costs.

    Args:
        bom_items: list of dicts with {name, quantity, unit_cost_usd}.
                   Items with non-numeric quantity (e.g. "AS REQ.") are skipped.
        project_dc_kw: DC system size in kilowatts (for $/W calculation).

    Returns:
        dict with material_cost, labor_cost, permit_cost, total_cost, cost_per_watt.
    """
    material_cost = sum(
        item['quantity'] * item['unit_cost_usd']
        for item in bom_items
        if isinstance(item.get('quantity'), (int, float)) and item.get('unit_cost_usd', 0) > 0
    )
    labor_cost = round(material_cost * 0.25, 2)
    permit_cost = 500.00
    total_cost = round(material_cost + labor_cost + permit_cost, 2)
    dc_watts = project_dc_kw * 1000
    cost_per_watt = round(total_cost / dc_watts, 2) if dc_watts > 0 else 0.0
    return {
        'material_cost': round(material_cost, 2),
        'labor_cost': labor_cost,
        'permit_cost': permit_cost,
        'total_cost': total_cost,
        'cost_per_watt': cost_per_watt,
    }
