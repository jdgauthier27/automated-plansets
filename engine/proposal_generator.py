"""
Proposal Generator
==================
Builds the customer-facing proposal data dict from a ProjectSpec, BOM result,
and monthly production breakdown.
"""

from models.project import ProjectSpec


def generate_proposal(project: ProjectSpec, bom_result, monthly_production) -> dict:
    """Generate customer proposal data.

    Args:
        project: ProjectSpec with all design data.
        bom_result: Either a List[BOMItem] (from calculate_bom) or a dict with
                    'total_cost_usd' key (from calculate_project_cost).
        monthly_production: Either a List[MonthlyProduction] (from
                            calculate_monthly_production) or a dict {month->kWh}.

    Returns:
        Dict ready for customer-facing proposal PDF rendering.
    """
    # ── Resolve total cost ────────────────────────────────────────────────
    if isinstance(bom_result, dict):
        total_cost = float(bom_result.get("total_cost_usd", 0.0))
    else:
        # bom_result is List[BOMItem] — compute cost from item quantities
        material_cost = sum(
            item.qty * item.unit_cost_usd
            for item in bom_result
            if isinstance(getattr(item, "qty", None), (int, float)) and getattr(item, "unit_cost_usd", 0.0) > 0
        )
        labor_cost = material_cost * 0.25
        permit_cost = 500.0
        total_cost = round(material_cost + labor_cost + permit_cost, 2)

    # ── Resolve monthly production dict {month_name: kwh} ─────────────────
    if isinstance(monthly_production, dict):
        monthly_dict = {str(k): float(v) for k, v in monthly_production.items()}
    else:
        # List of MonthlyProduction dataclass objects
        monthly_dict = {mp.month_name: mp.kwh for mp in monthly_production}

    annual_kwh = sum(monthly_dict.values())
    system_watts = project.num_panels * project.panel.wattage_w

    return {
        "address": project.address,
        "company_name": project.company_name,
        "system_size_kw": round(system_watts / 1000, 2),
        "num_panels": project.num_panels,
        "panel_model": project.panel.model,
        "inverter_model": project.inverter.model,
        "annual_production_kwh": round(annual_kwh, 1),
        "annual_consumption_kwh": project.annual_consumption_kwh,
        "solar_offset_pct": round(annual_kwh / project.annual_consumption_kwh * 100, 1)
        if project.annual_consumption_kwh > 0
        else 0.0,
        "total_cost_usd": total_cost,
        "cost_per_watt": round(total_cost / system_watts, 2) if system_watts > 0 else 0.0,
        "co2_offset_lbs_per_year": round(annual_kwh * 0.92, 0),
        "trees_equivalent": round(annual_kwh * 0.92 / 48, 0),
        "payback_years": round(total_cost / (annual_kwh * 0.15), 1) if annual_kwh > 0 else 0.0,
        "monthly_production": monthly_dict,
    }
