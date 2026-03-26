"""
Texas NEC Jurisdiction Engine
==============================
Texas NEC 2020 jurisdiction engine. Texas has adopted NEC 2020 statewide.
Permit authority is TDLR (Texas Department of Licensing and Regulation)
for most installations. Utility is ERCOT grid for most of the state,
with Oncor (DFW) and CenterPoint (Houston) as major distribution utilities.

Key differences from California:
- Utility auto-select by city (Oncor / CenterPoint / AEP Texas / ERCOT)
- Wind speed 115 mph default (130 mph for Gulf Coast counties)
- Permit authority: TDLR (not city building departments)
- No dedicated solar contractor license — uses TDLR electrician license
- Snow load: 0 PSF (essentially all of Texas)
- Seismic: SDC B or less
"""

import math
from typing import Dict, List

from jurisdiction.nec_base import NECBaseEngine


# Texas utilities by city area
TX_UTILITIES = {
    # Oncor — Dallas / Fort Worth Metroplex
    "dallas": {
        "name": "Oncor",
        "full_name": "Oncor Electric Delivery",
        "net_metering_max_kw": 50,
        "rate_per_kwh": 0.11,
    },
    "fort worth": {
        "name": "Oncor",
        "full_name": "Oncor Electric Delivery",
        "net_metering_max_kw": 50,
        "rate_per_kwh": 0.11,
    },
    "arlington": {
        "name": "Oncor",
        "full_name": "Oncor Electric Delivery",
        "net_metering_max_kw": 50,
        "rate_per_kwh": 0.11,
    },
    "plano": {
        "name": "Oncor",
        "full_name": "Oncor Electric Delivery",
        "net_metering_max_kw": 50,
        "rate_per_kwh": 0.11,
    },
    # CenterPoint — Houston area
    "houston": {
        "name": "CenterPoint Energy",
        "full_name": "CenterPoint Energy Houston Electric",
        "net_metering_max_kw": 50,
        "rate_per_kwh": 0.10,
    },
    # AEP Texas — West and South Texas
    "el paso": {
        "name": "El Paso Electric",
        "full_name": "El Paso Electric (AEP partner / separate IOU)",
        "net_metering_max_kw": 25,
        "rate_per_kwh": 0.10,
    },
    "corpus christi": {
        "name": "AEP Texas",
        "full_name": "AEP Texas Central",
        "net_metering_max_kw": 50,
        "rate_per_kwh": 0.10,
    },
    "laredo": {
        "name": "AEP Texas",
        "full_name": "AEP Texas Central",
        "net_metering_max_kw": 50,
        "rate_per_kwh": 0.10,
    },
    # Default — ERCOT / retail choice (San Antonio uses CPS Energy, Austin uses AE)
    "san antonio": {
        "name": "CPS Energy",
        "full_name": "CPS Energy (City Public Service)",
        "net_metering_max_kw": 50,
        "rate_per_kwh": 0.09,
    },
    "austin": {
        "name": "Austin Energy",
        "full_name": "Austin Energy (City of Austin)",
        "net_metering_max_kw": 50,
        "rate_per_kwh": 0.10,
    },
    # Generic ERCOT fallback
    "_default": {
        "name": "ERCOT Retail Provider",
        "full_name": "ERCOT Grid — Local Retail Electric Provider",
        "net_metering_max_kw": 50,
        "rate_per_kwh": 0.11,
    },
}

# Gulf Coast counties with elevated wind (ASCE 7-16, 130 mph)
GULF_COAST_COUNTIES = {
    "galveston",
    "nueces",
    "cameron",
    "willacy",
    "kenedy",
    "kleberg",
    "san patricio",
    "aransas",
    "refugio",
    "calhoun",
    "matagorda",
    "brazoria",
    "jefferson",
    "orange",
}


class TexasNECJurisdiction(NECBaseEngine):
    """Texas NEC 2020 jurisdiction engine.

    Extends the NEC base engine with Texas-specific codes, wind/snow loads,
    utility auto-selection, and TDLR permit authority.
    """

    def __init__(self, city: str = "", county: str = "", municipality: str = "", state: str = ""):
        # Accept municipality/state as aliases for city/county (test harness compatibility)
        if not city and municipality:
            city = municipality
        self.city = city.lower().strip()
        self.county = county.lower().strip()
        # Determine wind speed at init time
        self.wind_speed_mph = self._calc_wind_speed()
        # Resolve utility
        util = self._resolve_utility()
        self.utility_name = util["name"]
        self.utility_full_name = util["full_name"]
        self._utility_info = util

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _calc_wind_speed(self) -> int:
        """Return design wind speed per ASCE 7-16 for Texas.

        Gulf Coast counties: 130 mph.
        All other Texas: 115 mph.
        """
        county_key = self.county.lower()
        for gc_county in GULF_COAST_COUNTIES:
            if gc_county in county_key:
                return 130
        # Also catch city names that are clearly coastal
        if any(c in self.city for c in ("galveston", "corpus christi", "brownsville", "harlingen")):
            return 130
        return 115

    def _resolve_utility(self) -> Dict:
        """Return utility dict for this city."""
        for key, info in TX_UTILITIES.items():
            if key == "_default":
                continue
            if key in self.city:
                return {
                    "name": info["name"],
                    "full_name": info["full_name"],
                    "net_metering_max_kw": info["net_metering_max_kw"],
                    "rate_per_kwh": info["rate_per_kwh"],
                    "interconnection_standard": "PUCT Net Metering / ERCOT Interconnection",
                }
        default = TX_UTILITIES["_default"]
        return {
            "name": default["name"],
            "full_name": default["full_name"],
            "net_metering_max_kw": default["net_metering_max_kw"],
            "rate_per_kwh": default["rate_per_kwh"],
            "interconnection_standard": "PUCT Net Metering / ERCOT Interconnection",
        }

    # ------------------------------------------------------------------
    # JurisdictionEngine interface
    # ------------------------------------------------------------------

    def get_code_name(self) -> str:
        return "NEC 2020 (Texas Adoption)"

    def get_code_edition(self) -> str:
        return "NEC 2020 (NFPA 70-2020) — Texas State Adoption"

    @property
    def wire_type(self) -> str:
        """Texas uses THWN-2 (same as NEC 2020 — no RW90-XLPE)."""
        return "THWN-2"

    def get_governing_codes(self) -> List[Dict]:
        return [
            {"code": "NEC 2020", "title": "National Electrical Code (Texas Adoption)", "edition": "2020"},
            {"code": "IBC 2021", "title": "International Building Code", "edition": "2021"},
            {"code": "IFC 2021", "title": "International Fire Code", "edition": "2021"},
            {"code": "IRC 2021", "title": "International Residential Code", "edition": "2021"},
            {"code": "ASCE 7-16", "title": "Minimum Design Loads for Buildings", "edition": "2016"},
            {"code": "UL 1741", "title": "Inverters, Converters, Controllers", "edition": "SA"},
            {"code": "UL 2703", "title": "Mounting Systems, Bonding", "edition": "2023"},
            {"code": "IEEE 1547", "title": "Interconnection Standard", "edition": "2018"},
        ]

    def get_design_temperatures(self, city: str = "") -> Dict:
        """Texas design temperatures by city (ASHRAE 99.6% / 2% values)."""
        city_key = (city or self.city).lower()
        temps = {
            "houston": {"cold_c": 2, "hot_module_c": 68, "stc_c": 25},
            "dallas": {"cold_c": -5, "hot_module_c": 70, "stc_c": 25},
            "fort worth": {"cold_c": -5, "hot_module_c": 70, "stc_c": 25},
            "san antonio": {"cold_c": -1, "hot_module_c": 68, "stc_c": 25},
            "austin": {"cold_c": -2, "hot_module_c": 68, "stc_c": 25},
            "el paso": {"cold_c": -6, "hot_module_c": 72, "stc_c": 25},
            "corpus christi": {"cold_c": 2, "hot_module_c": 65, "stc_c": 25},
            "laredo": {"cold_c": 1, "hot_module_c": 72, "stc_c": 25},
            "plano": {"cold_c": -5, "hot_module_c": 70, "stc_c": 25},
            "arlington": {"cold_c": -5, "hot_module_c": 70, "stc_c": 25},
        }
        for key, t in temps.items():
            if key in city_key:
                return t
        # Generic Texas default (hot interior)
        return {"cold_c": -3, "hot_module_c": 70, "stc_c": 25}

    def get_fire_setbacks(self, building_type: str = "residential") -> Dict:
        """NEC 690.12 rapid shutdown + IFC setbacks.

        IFC 605.11 / NEC 690.12: 18" ridge, 36" sides for hip/gable roofs.
        """
        if building_type == "residential":
            return {"ridge_ft": 1.5, "eave_ft": 3.0, "pathway_ft": 3.0}
        return {"ridge_ft": 1.5, "eave_ft": 3.0, "pathway_ft": 4.0}

    def get_wind_snow_loads(self, city: str = "") -> Dict:
        """Texas wind and snow loads per ASCE 7-16.

        Snow load is 0 PSF throughout Texas (no ground snow).
        Wind speed: 130 mph Gulf Coast counties, 115 mph elsewhere.
        """
        wind = self._calc_wind_speed()
        return {"wind_mph": wind, "snow_psf": 0}

    def get_utility_info(self, city: str = "") -> Dict:
        """Return utility info. If city is provided, re-resolve."""
        if city and city.lower().strip() != self.city:
            temp = TexasNECJurisdiction(city=city, county=self.county)
            return temp._utility_info
        return self._utility_info

    def get_ahj_label(self, city: str = "") -> str:
        """Return AHJ label. TDLR is the permit authority for most of Texas."""
        city_title = (city or self.city).strip().title()
        if city_title:
            return f"City of {city_title} / TDLR"
        return "TDLR (Texas Department of Licensing and Regulation)"

    def get_contractor_license_type(self) -> str:
        """Texas has no dedicated solar contractor license.
        Installations require a TDLR licensed master electrician.
        """
        return "TDLR Master Electrician License"

    def get_licensing_body(self) -> str:
        return "TDLR"

    def get_licensing_body_full(self) -> str:
        return "Texas Department of Licensing and Regulation (TDLR)"

    def get_general_notes(self) -> List[str]:
        return [
            "1. This drawing sets minimum standards for construction. All work shall comply with NEC 2020 (Texas Adoption), IBC 2021, IFC 2021, and all applicable local ordinances.",
            "2. All equipment shall be installed per manufacturer's installation manuals. Notify the contractor of any discrepancies prior to beginning work.",
            "3. Prior to the commencement of any work, the contractor shall visit the site to fully verify all existing conditions.",
            "4. All items to be removed, relocated, or replaced shall be handled with proper care and stored in a safe place to prevent damage.",
            "5. All effort must be made by the general contractor and subcontractors to mount equipment level and secure.",
            "6. Beams or joists shall not be drilled unless specifically authorized by the structural engineer of record.",
            "7. A permit must be obtained from the Authority Having Jurisdiction (AHJ) and TDLR prior to commencing any work.",
            "8. The local retail electric provider (REP) or distribution utility shall be notified prior to interconnection.",
            "9. Interconnection and net metering governed by PUCT rules (16 TAC Chapter 25).",
            "10. Rapid shutdown equipment shall comply with NEC 2020 Section 690.12.",
            "11. All conductors shall be THWN-2 rated for wet locations (no RW90-XLPE permitted).",
            "12. All drawings and notes are not to scale. Contractor shall check and verify all dimensions at the job site.",
        ]

    def get_electrical_notes(self) -> List[str]:
        return [
            "1. The equipment and all associated wiring shall be installed only by qualified persons holding a valid TDLR electrician license. (NEC 2020 690.4(E))",
            "2. The local utility or retail electric provider shall be notified prior to activation of any solar photovoltaic installation.",
            "3. All PV conductors shall be THWN-2 rated. RW90-XLPE conductors are NOT approved for Texas installations.",
            "4. DC conductors shall comply with NEC 2020 690.8(A): Isc × 1.25 × 1.25 (Isc × 1.56).",
            "5. AC breaker sizing per NEC 2020 690.8(A): continuous current × 1.25.",
            "6. Interconnection per NEC 2020 705.12 (120% rule or supply-side tap).",
            "7. Rapid shutdown shall comply with NEC 2020 Section 690.12.",
            "8. All inverters shall be UL 1741 SA listed and PUCT-compliant for ERCOT grid.",
            "9. Equipment grounding conductor per NEC 2020 Table 250.122.",
            "10. Voltage drop shall be limited to 2% for branch circuits and 3% cumulative.",
            "11. All conduit sizes and types specified in single-line and/or three-line diagrams shall be installed.",
            "12. The backfeed breaker shall be at the opposite end of the bus from the main breaker.",
            "13. All PV source circuits shall have individual overcurrent protection per NEC 2020 690.9.",
        ]

    # ── Convenience summary dict (used by test harness) ───────────────────

    def get_jurisdiction_data(self) -> dict:
        """Return a flat summary dict for quick validation and rendering."""
        return {
            "utility": self.utility_name,
            "wire_type": self.wire_type,
            "electrical_code": self.get_code_edition(),
            "utility_full": self.utility_full_name,
            "wind_mph": self.wind_speed_mph,
            "snow_psf": 0,
            "licensing_body": self.get_licensing_body(),
            "code_name": self.get_code_name(),
        }


# Alias for test harness compatibility
TexasJurisdiction = TexasNECJurisdiction
