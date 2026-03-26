"""
Jurisdiction registry for the solar planset tool.

Supported jurisdictions: CA, FL, TX, ON, BC, QC
"""

import re
from typing import Optional


def get_jurisdiction_engine(address: str, country: str = "US"):
    """Return the appropriate jurisdiction engine for a given address and country.

    Detects state/province from the address string and instantiates the
    correct engine. Falls back to NECBaseEngine for unrecognized US states,
    or CECQuebecEngine for unrecognized Canadian provinces.

    Args:
        address: Full address string (e.g. "123 Main St, Miami, FL 33101").
        country: "US" or "CA" (default "US").

    Returns:
        An instance of a JurisdictionEngine subclass.
    """
    address_upper = address.upper()
    city = _extract_city(address)

    # ── United States ──────────────────────────────────────────────────────
    if country == "US":
        # Florida
        if _state_match(address_upper, "FL", "FLORIDA"):
            from jurisdiction.nec_florida import FloridaNECJurisdiction

            return FloridaNECJurisdiction(city=city)

        # California
        if _state_match(address_upper, "CA", "CALIFORNIA"):
            from jurisdiction.nec_california import NECCaliforniaEngine

            return NECCaliforniaEngine(city=city)

        # Texas
        if _state_match(address_upper, "TX", "TEXAS"):
            from jurisdiction.nec_texas import TexasNECJurisdiction

            return TexasNECJurisdiction(city=city)

        # New York
        if _state_match(address_upper, "NY", "NEW YORK"):
            from jurisdiction.nec_newyork import NYJurisdiction

            return NYJurisdiction(city=city, state="NY")

        # Illinois
        if _state_match(address_upper, "IL", "ILLINOIS"):
            from jurisdiction.nec_illinois import IllinoisJurisdiction

            return IllinoisJurisdiction(city=city, state="IL")

        # Default US: NEC base
        from jurisdiction.nec_base import NECBaseEngine

        return NECBaseEngine()

    # ── Canada ─────────────────────────────────────────────────────────────
    if country == "CA":
        if _state_match(address_upper, "ON", "ONTARIO"):
            from jurisdiction.cec_ontario import OntarioJurisdiction

            return OntarioJurisdiction(city=city)

        if _state_match(address_upper, "BC", "BRITISH COLUMBIA"):
            from jurisdiction.cec_bc import BCJurisdiction

            return BCJurisdiction(city=city)

        # Default Canada: Quebec CEC
        from jurisdiction.cec_quebec import CECQuebecEngine

        return CECQuebecEngine()

    # ── Fallback ───────────────────────────────────────────────────────────
    from jurisdiction.nec_base import NECBaseEngine

    return NECBaseEngine()


# ── Helpers ────────────────────────────────────────────────────────────────


def _state_match(address_upper: str, abbr: str, full_name: str) -> bool:
    """Return True if state abbreviation or full name is found in address."""
    # Match ", FL " or ", FL," or ", FL 12345" at word boundary
    if re.search(r",\s*" + abbr + r"(\s|,|$)", address_upper):
        return True
    if full_name in address_upper:
        return True
    return False


def _extract_city(address: str) -> str:
    """Extract city from a comma-separated address string.

    Handles both "City, ST" (2-part) and "123 Street, City, ST ZIP" (3-part).
    If the first part starts with a digit it is a street address; city is parts[1].
    Otherwise the first part is already the city name.
    """
    parts = [p.strip() for p in address.split(",")]
    if not parts:
        return ""
    # "123 Main St, City, ST ZIP" → city is parts[1]
    if parts[0] and parts[0][0].isdigit() and len(parts) >= 2:
        return parts[1].strip()
    # "City, ST" or "City, ST ZIP" → city is parts[0]
    return parts[0].strip()
