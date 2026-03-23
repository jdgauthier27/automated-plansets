"""
Data Export Module
==================
Exports solar planset data to JSON, CSV, and BOM (Bill of Materials) formats.
"""

import csv
import json
import logging
from dataclasses import asdict
from datetime import date
from io import StringIO
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def export_json(
    output_path: str,
    address: str,
    total_panels: int,
    total_kw: float,
    total_kwh: float,
    panel_name: str,
    panel_wattage: int,
    segments: Optional[List[Dict]] = None,
    electrical: Optional[Dict] = None,
) -> str:
    """Export system design data as JSON."""
    data = {
        "project": {
            "address": address,
            "date": date.today().isoformat(),
            "tool": "Quebec Solaire — Solar Planset Tool",
        },
        "system": {
            "total_panels": total_panels,
            "total_kw_dc": round(total_kw, 2),
            "estimated_annual_kwh": round(total_kwh, 0),
            "panel_model": panel_name,
            "panel_wattage": panel_wattage,
        },
    }
    if segments:
        data["segments"] = segments
    if electrical:
        data["electrical"] = electrical

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    logger.info("Exported JSON: %s", output_path)
    return output_path


def export_csv(
    output_path: str,
    panels: List[Dict],
) -> str:
    """Export panel placement data as CSV."""
    if not panels:
        logger.warning("No panel data to export")
        return output_path

    fieldnames = list(panels[0].keys())
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(panels)

    logger.info("Exported CSV (%d rows): %s", len(panels), output_path)
    return output_path


def export_bom(
    output_path: str,
    total_panels: int,
    panel_name: str,
    panel_wattage: int,
    total_kw: float,
) -> str:
    """Export Bill of Materials as CSV."""
    bom_items = [
        {
            "Item": "Solar Module",
            "Description": panel_name,
            "Quantity": total_panels,
            "Unit": "ea",
            "Rating": f"{panel_wattage}W",
        },
        {
            "Item": "Inverter",
            "Description": "Grid-Tied / Hybrid Inverter",
            "Quantity": 1,
            "Unit": "ea",
            "Rating": f"{total_kw:.1f} kW AC",
        },
        {
            "Item": "DC Disconnect",
            "Description": "Fused Safety Switch",
            "Quantity": 1,
            "Unit": "ea",
            "Rating": "30A, 600V DC",
        },
        {
            "Item": "AC Disconnect",
            "Description": "Lockable Circuit Breaker",
            "Quantity": 1,
            "Unit": "ea",
            "Rating": "30A, 240V AC",
        },
        {
            "Item": "Racking System",
            "Description": "Flush-mount rail system (UL 2703)",
            "Quantity": 1,
            "Unit": "set",
            "Rating": f"For {total_panels} panels",
        },
        {
            "Item": "Roof Attachments",
            "Description": "Flashed lag bolts / stanchions",
            "Quantity": total_panels * 2,
            "Unit": "ea",
            "Rating": "Per mfg spec",
        },
        {
            "Item": "DC Wiring",
            "Description": "#10 AWG PV Wire (USE-2)",
            "Quantity": 1,
            "Unit": "lot",
            "Rating": "600V DC",
        },
        {
            "Item": "AC Wiring",
            "Description": "#10 AWG Cu THWN-2",
            "Quantity": 1,
            "Unit": "lot",
            "Rating": "240V AC",
        },
        {
            "Item": "Grounding",
            "Description": "#6 Cu EGC + WEEB clips",
            "Quantity": 1,
            "Unit": "lot",
            "Rating": "Per CEC 10-814",
        },
        {
            "Item": "Labels & Placards",
            "Description": "CEC 64-060 through 64-222 compliant",
            "Quantity": 6,
            "Unit": "ea",
            "Rating": "Lamicoid",
        },
    ]

    fieldnames = ["Item", "Description", "Quantity", "Unit", "Rating"]
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(bom_items)

    logger.info("Exported BOM (%d items): %s", len(bom_items), output_path)
    return output_path
