"""
Google Solar API Integration — re-exported from root module.

All classes and functions live in google_solar.py at the project root.
This module re-exports them for backward compatibility with address/ imports.
"""

from google_solar import (
    BuildingInsight,
    GoogleSolarClient,
    SolarPanel,
    SolarRoofSegment,
    solar_insight_to_roof_faces,
)

__all__ = [
    "BuildingInsight",
    "GoogleSolarClient",
    "SolarPanel",
    "SolarRoofSegment",
    "solar_insight_to_roof_faces",
]
