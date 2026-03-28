"""
engine.models — Canonical data models for the planset generation pipeline.

The SolarDesign dataclass is the single source of truth. Every page builder
reads from it; no page computes its own values.
"""

from engine.models.solar_design import (
    AttachmentSpec,
    CombinerSpec,
    ElectricalDesign,
    EquipmentSpec,
    InverterSpec,
    JurisdictionContext,
    ModuleSpec,
    PanelPlacement,
    RackingSpec,
    RoofSegment,
    SheetInfo,
    SolarDesign,
)

__all__ = [
    "SolarDesign",
    "RoofSegment",
    "PanelPlacement",
    "ModuleSpec",
    "InverterSpec",
    "RackingSpec",
    "AttachmentSpec",
    "CombinerSpec",
    "EquipmentSpec",
    "ElectricalDesign",
    "JurisdictionContext",
    "SheetInfo",
]
