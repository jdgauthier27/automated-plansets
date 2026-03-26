"""
Florida NEC Jurisdiction Engine
================================
Florida solar jurisdiction engine.

Electrical code: NEC 2020 (statewide)
Wind: ASCE 7-22, 160+ mph for coastal counties (Miami-Dade, Broward, Palm Beach)
Utilities: FPL (south/east), Duke Energy (central), Tampa Electric (Tampa Bay),
           JEA (Jacksonville), Gulf Power/FPL Panhandle, OUC (Orlando)
Wire: THWN-2 (Florida heat — no RW90-XLPE)
Snow: 0 PSF statewide
AHJ: local county/city building department (no statewide permit authority)
Interconnection: FPL Rule 25-6.065, Duke Rule 25-17.0832
"""

from typing import Dict, List

from jurisdiction.nec_base import NECBaseEngine


# Florida cities with utility, wind speed (ASCE 7-22), and county
FLORIDA_CITIES = {
    "miami": {"utility": "FPL", "wind_mph": 175, "county": "Miami-Dade"},
    "orlando": {"utility": "OUC", "wind_mph": 130, "county": "Orange"},
    "tampa": {"utility": "Tampa Electric", "wind_mph": 130, "county": "Hillsborough"},
    "jacksonville": {"utility": "JEA", "wind_mph": 130, "county": "Duval"},
    "fort lauderdale": {"utility": "FPL", "wind_mph": 170, "county": "Broward"},
    "west palm beach": {"utility": "FPL", "wind_mph": 170, "county": "Palm Beach"},
    "st. petersburg": {"utility": "Tampa Electric", "wind_mph": 140, "county": "Pinellas"},
    "hialeah": {"utility": "FPL", "wind_mph": 175, "county": "Miami-Dade"},
    "tallahassee": {"utility": "Talquin Electric", "wind_mph": 120, "county": "Leon"},
    "cape coral": {"utility": "FPL", "wind_mph": 150, "county": "Lee"},
    # Additional major cities
    "gainesville": {"utility": "Gainesville Regional Utilities", "wind_mph": 120, "county": "Alachua"},
    "pensacola": {"utility": "Gulf Power (FPL)", "wind_mph": 130, "county": "Escambia"},
    "fort myers": {"utility": "FPL", "wind_mph": 150, "county": "Lee"},
    "sarasota": {"utility": "FPL", "wind_mph": 140, "county": "Sarasota"},
    "clearwater": {"utility": "Duke Energy", "wind_mph": 140, "county": "Pinellas"},
    "boca raton": {"utility": "FPL", "wind_mph": 170, "county": "Palm Beach"},
    "pompano beach": {"utility": "FPL", "wind_mph": 170, "county": "Broward"},
    "hollywood": {"utility": "FPL", "wind_mph": 170, "county": "Broward"},
    "daytona beach": {"utility": "Duke Energy", "wind_mph": 130, "county": "Volusia"},
    "kissimmee": {"utility": "KUA", "wind_mph": 130, "county": "Osceola"},
    "_default": {"utility": "FPL", "wind_mph": 130, "county": ""},
}

# Coastal counties with elevated wind per ASCE 7-22 (160+ mph)
COASTAL_HIGH_WIND_COUNTIES = {
    "miami-dade",
    "broward",
    "palm beach",
    "monroe",
    "collier",
    "lee",
    "charlotte",
    "sarasota",
    "manatee",
    "pinellas",
    "hillsborough",
    "bay",
    "okaloosa",
    "santa rosa",
}

# Utility interconnection standards by utility name
UTILITY_INTERCONNECTION = {
    "FPL": "FPL Rule 25-6.065 (Florida PSC)",
    "OUC": "OUC Net Metering / IEEE 1547",
    "Tampa Electric": "TECO Rule 25-17.0832 (Florida PSC)",
    "JEA": "JEA Net Metering / IEEE 1547",
    "Duke Energy": "Duke Rule 25-17.0832 (Florida PSC)",
    "Gulf Power (FPL)": "Gulf Power / FPL Rule 25-6.065",
    "_default": "Florida PSC Rule 25-17.0832 / IEEE 1547",
}


class FloridaNECJurisdiction(NECBaseEngine):
    """Florida NEC 2020 jurisdiction engine.

    Extends the NEC base engine with Florida-specific wind loads (ASCE 7-22),
    utility auto-selection, coastal wind zones, and local AHJ permit authority.
    """

    def __init__(self, city: str = "", county: str = "", municipality: str = "", state: str = ""):
        # Accept municipality/state as aliases for city/county (test harness compatibility)
        if not city and municipality:
            city = municipality
        self.city = city.lower().strip()
        self.county = county.lower().strip()
        # Resolve city data
        city_data = self._resolve_city_data()
        self.wind_speed_mph = city_data["wind_mph"]
        self.utility_name = city_data["utility"]
        self._county_resolved = city_data["county"]
        # Interconnection standard
        intercon_key = self.utility_name if self.utility_name in UTILITY_INTERCONNECTION else "_default"
        self._interconnection_std = UTILITY_INTERCONNECTION[intercon_key]
        self.utility_full_name = self.utility_name
        self._utility_info = {
            "name": self.utility_name,
            "full_name": self.utility_full_name,
            "interconnection_standard": self._interconnection_std,
            "net_metering_max_kw": 2000,  # Florida allows large systems
            "rate_per_kwh": 0.12,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_city_data(self) -> Dict:
        """Return city data dict matching on city name substring."""
        city_key = self.city
        for name, data in FLORIDA_CITIES.items():
            if name == "_default":
                continue
            if name in city_key or city_key in name:
                return data
        # County-based coastal wind override
        county_key = self.county.lower()
        for coastal in COASTAL_HIGH_WIND_COUNTIES:
            if coastal in county_key:
                default = dict(FLORIDA_CITIES["_default"])
                default["wind_mph"] = 160
                return default
        return dict(FLORIDA_CITIES["_default"])

    # ------------------------------------------------------------------
    # JurisdictionEngine interface
    # ------------------------------------------------------------------

    def get_code_name(self) -> str:
        return "NEC 2020 (Florida Adoption)"

    def get_code_edition(self) -> str:
        return "NEC 2020 (NFPA 70-2020) — Florida State Adoption"

    @property
    def wire_type(self) -> str:
        """Florida uses THWN-2 — hot and humid climate, no RW90-XLPE."""
        return "THWN-2"

    def get_governing_codes(self) -> List[Dict]:
        return [
            {"code": "NEC 2020", "title": "National Electrical Code (Florida Adoption)", "edition": "2020"},
            {"code": "FBC 7th Ed.", "title": "Florida Building Code", "edition": "2020"},
            {"code": "FBC-R 7th", "title": "Florida Building Code — Residential", "edition": "2020"},
            {"code": "ASCE 7-22", "title": "Minimum Design Loads for Buildings", "edition": "2022"},
            {"code": "IFC 2021", "title": "International Fire Code", "edition": "2021"},
            {"code": "UL 1741", "title": "Inverters, Converters, Controllers", "edition": "SA"},
            {"code": "UL 2703", "title": "Mounting Systems, Bonding", "edition": "2023"},
            {"code": "IEEE 1547", "title": "Interconnection Standard", "edition": "2018"},
        ]

    def get_design_temperatures(self, city: str = "") -> Dict:
        """Florida design temperatures by city (ASHRAE 99.6% / 2% values)."""
        city_key = (city or self.city).lower()
        temps = {
            "miami": {"cold_c": 10, "hot_module_c": 72, "stc_c": 25},
            "hialeah": {"cold_c": 10, "hot_module_c": 72, "stc_c": 25},
            "fort lauderdale": {"cold_c": 10, "hot_module_c": 70, "stc_c": 25},
            "west palm beach": {"cold_c": 8, "hot_module_c": 70, "stc_c": 25},
            "orlando": {"cold_c": 3, "hot_module_c": 70, "stc_c": 25},
            "kissimmee": {"cold_c": 3, "hot_module_c": 70, "stc_c": 25},
            "tampa": {"cold_c": 4, "hot_module_c": 70, "stc_c": 25},
            "st. petersburg": {"cold_c": 5, "hot_module_c": 68, "stc_c": 25},
            "clearwater": {"cold_c": 5, "hot_module_c": 68, "stc_c": 25},
            "jacksonville": {"cold_c": 0, "hot_module_c": 68, "stc_c": 25},
            "daytona beach": {"cold_c": 2, "hot_module_c": 68, "stc_c": 25},
            "sarasota": {"cold_c": 5, "hot_module_c": 70, "stc_c": 25},
            "fort myers": {"cold_c": 7, "hot_module_c": 72, "stc_c": 25},
            "cape coral": {"cold_c": 7, "hot_module_c": 72, "stc_c": 25},
            "tallahassee": {"cold_c": -3, "hot_module_c": 68, "stc_c": 25},
            "pensacola": {"cold_c": -1, "hot_module_c": 68, "stc_c": 25},
            "gainesville": {"cold_c": 0, "hot_module_c": 68, "stc_c": 25},
        }
        for key, t in temps.items():
            if key in city_key:
                return t
        # Generic Florida default (hot, humid)
        return {"cold_c": 5, "hot_module_c": 70, "stc_c": 25}

    def get_fire_setbacks(self, building_type: str = "residential") -> Dict:
        """NEC 690.12 rapid shutdown + IFC setbacks (Florida Building Code).

        FBC-R 324.4: 18" ridge, 36" sides/eave for residential.
        """
        if building_type == "residential":
            return {"ridge_ft": 1.5, "eave_ft": 3.0, "pathway_ft": 3.0}
        return {"ridge_ft": 1.5, "eave_ft": 3.0, "pathway_ft": 4.0}

    def get_wind_snow_loads(self, city: str = "") -> Dict:
        """Florida wind and snow loads per ASCE 7-22.

        Snow load is 0 PSF throughout Florida.
        Wind speed: 160-175 mph coastal (Miami-Dade, Broward, Palm Beach),
                    130-150 mph other coastal, 120-130 mph inland.
        """
        return {"wind_mph": self.wind_speed_mph, "snow_psf": 0}

    def get_utility_info(self, city: str = "") -> Dict:
        """Return utility info. If city is provided, re-resolve."""
        if city and city.lower().strip() != self.city:
            temp = FloridaNECJurisdiction(city=city, county=self.county)
            return temp._utility_info
        return self._utility_info

    def get_ahj_label(self, city: str = "") -> str:
        """Return AHJ label. Florida uses local county/city building departments."""
        city_title = (city or self.city).strip().title()
        county = self._county_resolved or self.county.title()
        if county:
            return f"{county} County Building Department"
        if city_title:
            return f"City of {city_title} Building Department"
        return "Local County Building Department (Florida)"

    def get_contractor_license_type(self) -> str:
        """Florida requires a licensed electrical contractor (EC) for PV work.
        Specialty solar contractor license also accepted (DBPR).
        """
        return "Florida Licensed Electrical Contractor (EC)"

    def get_licensing_body(self) -> str:
        return "DBPR"

    def get_licensing_body_full(self) -> str:
        return "Florida Department of Business and Professional Regulation (DBPR)"

    def get_general_notes(self) -> List[str]:
        return [
            "1. This drawing sets minimum standards for construction. All work shall comply with NEC 2020 (Florida Adoption), Florida Building Code 7th Edition, and all applicable local ordinances.",
            "2. All equipment shall be installed per manufacturer's installation manuals. Notify the contractor of any discrepancies prior to beginning work.",
            "3. Prior to the commencement of any work, the contractor shall visit the site to fully verify all existing conditions.",
            "4. All items to be removed, relocated, or replaced shall be handled with proper care and stored in a safe place to prevent damage.",
            "5. All effort must be made by the general contractor and subcontractors to mount equipment level and secure.",
            "6. Beams or joists shall not be drilled unless specifically authorized by the structural engineer of record.",
            f"7. A permit must be obtained from the Authority Having Jurisdiction ({self.get_ahj_label()}) prior to commencing any work.",
            "8. The local utility shall be notified prior to interconnection. Interconnection governed by Florida PSC rules.",
            f"9. Interconnection per {self._interconnection_std}.",
            "10. Rapid shutdown equipment shall comply with NEC 2020 Section 690.12.",
            "11. All conductors shall be THWN-2 rated for wet locations (no RW90-XLPE permitted).",
            f"12. Wind design per ASCE 7-22: {self.wind_speed_mph} mph design wind speed. Snow load: 0 PSF.",
            "13. All drawings and notes are not to scale. Contractor shall check and verify all dimensions at the job site.",
        ]

    def get_electrical_notes(self) -> List[str]:
        return [
            "1. The equipment and all associated wiring shall be installed only by qualified persons holding a valid Florida EC license. (NEC 2020 690.4(E))",
            "2. The local utility shall be notified prior to activation of any solar photovoltaic installation.",
            "3. All PV conductors shall be THWN-2 rated. RW90-XLPE conductors are NOT approved for Florida installations.",
            "4. DC conductors shall comply with NEC 2020 690.8(A): Isc × 1.25 × 1.25 (Isc × 1.56).",
            "5. AC breaker sizing per NEC 2020 690.8(A): continuous current × 1.25.",
            "6. Interconnection per NEC 2020 705.12 (120% rule or supply-side tap).",
            "7. Rapid shutdown shall comply with NEC 2020 Section 690.12.",
            "8. All inverters shall be UL 1741 SA listed and compliant with Florida utility requirements.",
            "9. Equipment grounding conductor per NEC 2020 Table 250.122.",
            "10. Voltage drop shall be limited to 2% for branch circuits and 3% cumulative.",
            "11. All conduit sizes and types specified in single-line and/or three-line diagrams shall be installed.",
            "12. The backfeed breaker shall be at the opposite end of the bus from the main breaker.",
            "13. All PV source circuits shall have individual overcurrent protection per NEC 2020 690.9.",
            "14. Hurricane-rated attachment hardware required for coastal wind zones (ASCE 7-22).",
        ]

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
FloridaJurisdiction = FloridaNECJurisdiction
