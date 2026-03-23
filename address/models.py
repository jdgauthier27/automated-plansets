"""
Address Validation Data Models
==============================
Dataclasses used by the address validation and building selection pipeline.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict


@dataclass
class AddressValidation:
    """Result of geocoding + Street View validation for an address."""
    lat: float
    lng: float
    formatted_address: str
    street_view_b64: str  # base64-encoded JPEG from Street View
    street_view_url: str  # direct URL for browser display
    confirmed: bool = False


@dataclass
class BuildingCandidate:
    """A candidate building near the target address."""
    lat: float
    lng: float
    distance_m: float  # distance from geocoded address center
    building_insight: Optional[object] = None  # BuildingInsight when fetched
