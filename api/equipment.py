"""
Equipment Catalog API
=====================
REST endpoints for browsing the equipment catalog.
"""

from fastapi import APIRouter, HTTPException
from catalog.loader import EquipmentCatalog

router = APIRouter(prefix="/api/catalog", tags=["Equipment Catalog"])

_catalog = None


def get_catalog() -> EquipmentCatalog:
    global _catalog
    if _catalog is None:
        _catalog = EquipmentCatalog()
    return _catalog


@router.get("/panels")
def list_panels():
    """List all panels in the catalog."""
    cat = get_catalog()
    return [
        {
            "id": p.id,
            "manufacturer": p.manufacturer,
            "model": p.model,
            "model_short": p.model_short,
            "wattage_w": p.wattage_w,
            "voc_v": p.voc_v,
            "isc_a": p.isc_a,
            "efficiency_pct": p.efficiency_pct,
            "dimensions_mm": {
                "length": p.dimensions.length_mm,
                "width": p.dimensions.width_mm,
            },
            "weight_kg": p.weight_kg,
            "technology": p.technology,
            "bifacial": p.bifacial,
        }
        for p in cat.panels.values()
    ]


@router.get("/panels/{panel_id}")
def get_panel(panel_id: str):
    """Get a specific panel by ID."""
    cat = get_catalog()
    try:
        p = cat.get_panel(panel_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {
        "id": p.id,
        "manufacturer": p.manufacturer,
        "model": p.model,
        "model_short": p.model_short,
        "wattage_w": p.wattage_w,
        "voc_v": p.voc_v,
        "vmp_v": p.vmp_v,
        "isc_a": p.isc_a,
        "imp_a": p.imp_a,
        "efficiency_pct": p.efficiency_pct,
        "temp_coeff_voc_pct_per_c": p.temp_coeff_voc_pct_per_c,
        "temp_coeff_isc_pct_per_c": p.temp_coeff_isc_pct_per_c,
        "dimensions_mm": {
            "length": p.dimensions.length_mm,
            "width": p.dimensions.width_mm,
            "depth": p.dimensions.depth_mm,
        },
        "weight_kg": p.weight_kg,
        "technology": p.technology,
        "bifacial": p.bifacial,
        "certifications": p.certifications,
        "warranty_product_years": p.warranty_product_years,
        "warranty_performance_years": p.warranty_performance_years,
    }


@router.get("/inverters")
def list_inverters():
    """List all inverters in the catalog."""
    cat = get_catalog()
    return [
        {
            "id": inv.id,
            "manufacturer": inv.manufacturer,
            "model": inv.model,
            "model_short": inv.model_short,
            "type": inv.type,
            "rated_ac_output_w": inv.rated_ac_output_w,
            "max_dc_voltage_v": inv.max_dc_voltage_v,
            "mppt_count": inv.mppt_count,
            "cec_efficiency_pct": inv.cec_efficiency_pct,
            "rapid_shutdown_builtin": inv.rapid_shutdown_builtin,
        }
        for inv in cat.inverters.values()
    ]


@router.get("/inverters/{inverter_id}")
def get_inverter(inverter_id: str):
    cat = get_catalog()
    try:
        inv = cat.get_inverter(inverter_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {
        "id": inv.id,
        "manufacturer": inv.manufacturer,
        "model": inv.model,
        "model_short": inv.model_short,
        "type": inv.type,
        "rated_ac_output_w": inv.rated_ac_output_w,
        "max_ac_amps": inv.max_ac_amps,
        "ac_voltage_v": inv.ac_voltage_v,
        "max_dc_voltage_v": inv.max_dc_voltage_v,
        "mppt_voltage_min_v": inv.mppt_voltage_min_v,
        "mppt_voltage_max_v": inv.mppt_voltage_max_v,
        "mppt_count": inv.mppt_count,
        "cec_efficiency_pct": inv.cec_efficiency_pct,
        "rapid_shutdown_builtin": inv.rapid_shutdown_builtin,
        "certifications": inv.certifications,
    }


@router.get("/racking")
def list_racking():
    cat = get_catalog()
    return [
        {
            "id": r.id,
            "manufacturer": r.manufacturer,
            "model": r.model,
            "type": r.type,
            "material": r.material,
            "wind_load_psf": r.wind_load_psf,
            "snow_load_psf": r.snow_load_psf,
            "certifications": r.certifications,
        }
        for r in cat.racking.values()
    ]


@router.get("/attachments")
def list_attachments(roof_material: str = None):
    """List attachments, optionally filtered by roof material."""
    cat = get_catalog()
    attachments = cat.attachments.values()
    if roof_material:
        attachments = [a for a in attachments if roof_material in a.compatible_roof_materials]
    return [
        {
            "id": a.id,
            "manufacturer": a.manufacturer,
            "model": a.model,
            "type": a.type,
            "compatible_roof_materials": a.compatible_roof_materials,
            "compatible_racking_ids": a.compatible_racking_ids,
            "max_load_lbs": a.max_load_lbs,
            "certifications": a.certifications,
        }
        for a in attachments
    ]
