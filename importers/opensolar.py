"""
OpenSolar Importer
==================
Maps OpenSolar project export JSON to our ProjectSpec model.
Handles equipment lookup from our catalog when possible,
falls back to creating catalog entries from OpenSolar data.
"""

import json
import logging
from pathlib import Path
from typing import Optional

from models.project import ProjectSpec
from models.equipment import (
    PanelCatalogEntry,
    PanelDimensions,
    DatasheetDrawing,
    InverterCatalogEntry,
    RackingCatalogEntry,
    AttachmentCatalogEntry,
)
from catalog.loader import EquipmentCatalog

logger = logging.getLogger(__name__)


def import_opensolar_json(filepath: str, catalog: Optional[EquipmentCatalog] = None) -> ProjectSpec:
    """Import an OpenSolar project export and map to ProjectSpec.

    Args:
        filepath: Path to OpenSolar JSON export file.
        catalog: Optional equipment catalog for matching equipment.

    Returns:
        ProjectSpec populated from OpenSolar data.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    if catalog is None:
        catalog = EquipmentCatalog()

    project = ProjectSpec()

    # ── Address / Site ──────────────────────────────────────────────────
    site = data.get("site", data.get("project", {}))
    project.address = site.get("address", site.get("street_address", ""))
    project.latitude = float(site.get("lat", site.get("latitude", 0)))
    project.longitude = float(site.get("lng", site.get("longitude", 0)))
    project.municipality = site.get("city", "")
    project.province_or_state = site.get("state", site.get("province", ""))
    project.country = site.get("country_code", "CA")

    # ── Panel ───────────────────────────────────────────────────────────
    system = data.get("system", data.get("design", {}))
    module_data = system.get("module", system.get("panel", {}))

    panel = _match_panel(module_data, catalog)
    if panel:
        project.panel = panel
    else:
        project.panel = _create_panel_from_opensolar(module_data)

    # ── Inverter ────────────────────────────────────────────────────────
    inverter_data = system.get("inverter", {})
    inverter = _match_inverter(inverter_data, catalog)
    if inverter:
        project.inverter = inverter
    else:
        project.inverter = _create_inverter_from_opensolar(inverter_data)

    # ── System sizing ───────────────────────────────────────────────────
    project.num_panels = int(system.get("module_quantity", system.get("panel_count", system.get("num_panels", 0))))

    project.target_kwh = system.get("annual_production_kwh")
    project.annual_consumption_kwh = system.get("annual_consumption_kwh", site.get("annual_kwh"))

    # ── Electrical ──────────────────────────────────────────────────────
    electrical = data.get("electrical", {})
    project.main_panel_breaker_a = int(electrical.get("main_breaker_amps", 200))
    project.main_panel_bus_rating_a = int(electrical.get("bus_rating_amps", 225))
    project.service_voltage_v = int(electrical.get("service_voltage", 240))

    # ── Racking (use first from catalog if not specified) ───────────────
    racking_data = system.get("racking", system.get("mounting", {}))
    racking_brand = racking_data.get("manufacturer", "").lower()
    if "ironridge" in racking_brand:
        project.racking = catalog.get_racking("ironridge-xr10")
    elif "k2" in racking_brand:
        project.racking = catalog.get_racking("k2-crossrail-48x")
    else:
        project.racking = catalog.get_racking(catalog.list_racking_ids()[0])

    # ── Roof material ───────────────────────────────────────────────────
    roof = site.get("roof", site.get("roof_type", {}))
    roof_material_str = ""
    if isinstance(roof, dict):
        roof_material_str = roof.get("material", roof.get("type", ""))
    elif isinstance(roof, str):
        roof_material_str = roof
    project.roof_material = _normalize_roof_material(roof_material_str)

    # ── Attachment (auto-select) ────────────────────────────────────────
    att = catalog.auto_select_attachment(project.roof_material, project.racking.id)
    if att:
        project.attachment = att

    # ── Company ─────────────────────────────────────────────────────────
    company = data.get("company", data.get("installer", {}))
    project.company_name = company.get("name", "Quebec Solaire")
    project.designer_name = company.get("designer", "AI Solar Design Engine")
    project.project_name = data.get("name", data.get("project_name", f"Installation Solaire — {project.address}"))

    logger.info(
        "Imported OpenSolar project: %s (%d panels, %s + %s)",
        project.address,
        project.num_panels,
        project.panel.model_short,
        project.inverter.model_short,
    )

    return project


def _match_panel(module_data: dict, catalog: EquipmentCatalog) -> Optional[PanelCatalogEntry]:
    """Try to match OpenSolar panel to our catalog by manufacturer/model."""
    manufacturer = module_data.get("manufacturer", "").lower()
    model = module_data.get("model", module_data.get("name", "")).lower()
    wattage = module_data.get("wattage", module_data.get("pstc", 0))

    for pid, panel in catalog.panels.items():
        if panel.manufacturer.lower() in manufacturer or manufacturer in panel.manufacturer.lower():
            if abs(panel.wattage_w - wattage) < 30:  # within 30W tolerance
                logger.info("Matched panel: %s -> %s", model, panel.model)
                return panel
    return None


def _match_inverter(inv_data: dict, catalog: EquipmentCatalog) -> Optional[InverterCatalogEntry]:
    """Try to match OpenSolar inverter to our catalog."""
    manufacturer = inv_data.get("manufacturer", "").lower()
    inv_type = inv_data.get("type", inv_data.get("inverter_type", "")).lower()

    for iid, inv in catalog.inverters.items():
        if inv.manufacturer.lower() in manufacturer or manufacturer in inv.manufacturer.lower():
            if inv_type and inv.type in inv_type:
                logger.info("Matched inverter: %s -> %s", manufacturer, inv.model)
                return inv
    return None


def _create_panel_from_opensolar(data: dict) -> PanelCatalogEntry:
    """Create a panel entry from OpenSolar data when no catalog match."""
    return PanelCatalogEntry(
        id="opensolar-import",
        manufacturer=data.get("manufacturer", "Unknown"),
        model=data.get("model", data.get("name", "Imported Panel")),
        model_short=data.get("model", "Imported")[:20],
        wattage_w=int(data.get("wattage", data.get("pstc", 400))),
        voc_v=float(data.get("voc", 40)),
        vmp_v=float(data.get("vmp", 34)),
        isc_a=float(data.get("isc", 10)),
        imp_a=float(data.get("imp", 9.5)),
        efficiency_pct=float(data.get("efficiency", 21)) * (100 if data.get("efficiency", 21) < 1 else 1),
        temp_coeff_voc_pct_per_c=float(data.get("temp_coeff_voc", -0.27)),
        temp_coeff_isc_pct_per_c=float(data.get("temp_coeff_isc", 0.05)),
        dimensions=PanelDimensions(
            length_mm=float(data.get("length_mm", data.get("height_mm", 1800))),
            width_mm=float(data.get("width_mm", 1134)),
        ),
        weight_kg=float(data.get("weight_kg", 25)),
    )


def _create_inverter_from_opensolar(data: dict) -> InverterCatalogEntry:
    """Create an inverter entry from OpenSolar data when no catalog match."""
    inv_type = data.get("type", data.get("inverter_type", "micro")).lower()
    if "string" in inv_type or "central" in inv_type:
        inv_type = "string"
    else:
        inv_type = "micro"

    return InverterCatalogEntry(
        id="opensolar-import",
        manufacturer=data.get("manufacturer", "Unknown"),
        model=data.get("model", data.get("name", "Imported Inverter")),
        model_short=data.get("model", "Imported")[:20],
        type=inv_type,
        rated_ac_output_w=int(data.get("paco", data.get("rated_watts", 400))),
        max_ac_output_va=int(data.get("paco", 400)),
        max_ac_amps=float(data.get("max_ac_amps", 1.6)),
        ac_voltage_v=int(data.get("ac_voltage", 240)),
        max_dc_voltage_v=int(data.get("vdc_max", 60 if inv_type == "micro" else 600)),
        mppt_voltage_min_v=int(data.get("mppt_min", 27)),
        mppt_voltage_max_v=int(data.get("mppt_max", 48)),
        cec_efficiency_pct=float(data.get("cec_efficiency", 96.5)),
    )


def _normalize_roof_material(raw: str) -> str:
    """Normalize roof material string to our standard keys."""
    raw_lower = raw.lower().strip()
    if "standing seam" in raw_lower or "metal" in raw_lower:
        return "metal_standing_seam"
    if "tile" in raw_lower and "clay" in raw_lower:
        return "clay_tile"
    if "tile" in raw_lower and "concrete" in raw_lower:
        return "concrete_tile"
    if "flat" in raw_lower or "membrane" in raw_lower or "tpo" in raw_lower or "epdm" in raw_lower:
        return "flat_membrane"
    if "composite" in raw_lower:
        return "composite_shingle"
    # Default
    return "asphalt_shingle"
