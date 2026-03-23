"""
Catalog Loader
==============
Loads equipment catalog JSON files into typed dataclass instances.
Provides lookup by ID and auto-selection of attachments based on
roof material + racking compatibility.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from models.equipment import (
    AttachmentCatalogEntry,
    DatasheetDrawing,
    InverterCatalogEntry,
    PanelCatalogEntry,
    PanelDimensions,
    RackingCatalogEntry,
    RackingClamps,
    RackingProfile,
)

logger = logging.getLogger(__name__)

CATALOG_DIR = Path(__file__).parent


def _load_json(filename: str) -> list:
    path = CATALOG_DIR / filename
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Panel loader
# ---------------------------------------------------------------------------

def _dict_to_panel(d: dict) -> PanelCatalogEntry:
    dims = d.pop("dimensions", {})
    drawing = d.pop("datasheet_drawing", {})
    panel = PanelCatalogEntry(**d)
    panel.dimensions = PanelDimensions(**dims)
    panel.datasheet_drawing = DatasheetDrawing(**drawing)
    return panel


def load_panels() -> Dict[str, PanelCatalogEntry]:
    """Load all panels from catalog/panels.json, keyed by ID."""
    raw = _load_json("panels.json")
    panels = {}
    for item in raw:
        entry = _dict_to_panel(dict(item))
        panels[entry.id] = entry
        logger.debug("Loaded panel: %s (%s)", entry.id, entry.model)
    return panels


# ---------------------------------------------------------------------------
# Inverter loader
# ---------------------------------------------------------------------------

def load_inverters() -> Dict[str, InverterCatalogEntry]:
    """Load all inverters from catalog/inverters.json, keyed by ID."""
    raw = _load_json("inverters.json")
    inverters = {}
    for item in raw:
        entry = InverterCatalogEntry(**item)
        inverters[entry.id] = entry
        logger.debug("Loaded inverter: %s (%s)", entry.id, entry.model)
    return inverters


# ---------------------------------------------------------------------------
# Racking loader
# ---------------------------------------------------------------------------

def _dict_to_racking(d: dict) -> RackingCatalogEntry:
    profile = d.pop("profile", {})
    clamps = d.pop("clamps", {})
    racking = RackingCatalogEntry(**d)
    racking.profile = RackingProfile(**profile)
    racking.clamps = RackingClamps(**clamps)
    return racking


def load_racking() -> Dict[str, RackingCatalogEntry]:
    """Load all racking systems from catalog/racking.json, keyed by ID."""
    raw = _load_json("racking.json")
    racking = {}
    for item in raw:
        entry = _dict_to_racking(dict(item))
        racking[entry.id] = entry
        logger.debug("Loaded racking: %s (%s)", entry.id, entry.model)
    return racking


# ---------------------------------------------------------------------------
# Attachment loader
# ---------------------------------------------------------------------------

def load_attachments() -> Dict[str, AttachmentCatalogEntry]:
    """Load all attachments from catalog/attachments.json, keyed by ID."""
    raw = _load_json("attachments.json")
    attachments = {}
    for item in raw:
        entry = AttachmentCatalogEntry(**item)
        attachments[entry.id] = entry
        logger.debug("Loaded attachment: %s (%s)", entry.id, entry.model)
    return attachments


# ---------------------------------------------------------------------------
# Auto-selection
# ---------------------------------------------------------------------------

def select_attachment(
    roof_material: str,
    racking_id: str,
    attachments: Optional[Dict[str, AttachmentCatalogEntry]] = None,
) -> Optional[AttachmentCatalogEntry]:
    """Auto-select the best attachment for a given roof material + racking combo.

    Returns the first attachment that is compatible with both the roof material
    and the racking system. Returns None if no match found.
    """
    if attachments is None:
        attachments = load_attachments()

    for att in attachments.values():
        if (
            roof_material in att.compatible_roof_materials
            and racking_id in att.compatible_racking_ids
        ):
            logger.info(
                "Auto-selected attachment: %s for roof=%s, racking=%s",
                att.id, roof_material, racking_id,
            )
            return att

    # Fallback: try any attachment matching roof material regardless of racking
    for att in attachments.values():
        if roof_material in att.compatible_roof_materials:
            logger.warning(
                "No exact racking match — falling back to attachment %s for roof=%s",
                att.id, roof_material,
            )
            return att

    logger.warning(
        "No attachment found for roof=%s, racking=%s", roof_material, racking_id,
    )
    return None


# ---------------------------------------------------------------------------
# Full catalog loader
# ---------------------------------------------------------------------------

class EquipmentCatalog:
    """Unified access to all equipment catalogs."""

    def __init__(self):
        self.panels = load_panels()
        self.inverters = load_inverters()
        self.racking = load_racking()
        self.attachments = load_attachments()

    def get_panel(self, panel_id: str) -> PanelCatalogEntry:
        if panel_id not in self.panels:
            available = ", ".join(self.panels.keys())
            raise ValueError(f"Panel '{panel_id}' not found. Available: {available}")
        return self.panels[panel_id]

    def get_inverter(self, inverter_id: str) -> InverterCatalogEntry:
        if inverter_id not in self.inverters:
            available = ", ".join(self.inverters.keys())
            raise ValueError(f"Inverter '{inverter_id}' not found. Available: {available}")
        return self.inverters[inverter_id]

    def get_racking(self, racking_id: str) -> RackingCatalogEntry:
        if racking_id not in self.racking:
            available = ", ".join(self.racking.keys())
            raise ValueError(f"Racking '{racking_id}' not found. Available: {available}")
        return self.racking[racking_id]

    def get_attachment(self, attachment_id: str) -> AttachmentCatalogEntry:
        if attachment_id not in self.attachments:
            available = ", ".join(self.attachments.keys())
            raise ValueError(f"Attachment '{attachment_id}' not found. Available: {available}")
        return self.attachments[attachment_id]

    def auto_select_attachment(
        self, roof_material: str, racking_id: str
    ) -> Optional[AttachmentCatalogEntry]:
        return select_attachment(roof_material, racking_id, self.attachments)

    def list_panel_ids(self) -> List[str]:
        return list(self.panels.keys())

    def list_inverter_ids(self) -> List[str]:
        return list(self.inverters.keys())

    def list_racking_ids(self) -> List[str]:
        return list(self.racking.keys())

    def list_attachment_ids(self) -> List[str]:
        return list(self.attachments.keys())
