"""
Illinois NEC Jurisdiction Engine
=================================
Illinois solar jurisdiction engine.

Electrical code: NEC 2020 + Illinois Energy Code (IECC 2021)
Wire: THWN-2
Snow load: 25 PSF for Chicago metro / Rockford / Waukegan;
           20 PSF for Springfield / Peoria / Decatur and downstate
Wind: 90 mph ASCE 7
Utilities: ComEd (Commonwealth Edison) — Chicago metro / northern IL
           Ameren Illinois — central / southern IL
AHJ note: "Illinois Structural Engineering Act requires PE stamp for
           systems >10 kW on residential"
"""

from typing import Dict, List

from jurisdiction.nec_base import NECBaseEngine


# ---------------------------------------------------------------------------
# City data table
# ---------------------------------------------------------------------------

# Keys are lowercase city names.
# 'region': 'comed' | 'ameren'
IL_CITIES = {
    # ComEd territory — Chicago metro and northern Illinois
    "chicago": {"utility": "ComEd", "wind_mph": 90, "snow_psf": 25, "region": "comed", "ahj": "City of Chicago"},
    "aurora": {"utility": "ComEd", "wind_mph": 90, "snow_psf": 25, "region": "comed", "ahj": "City of Aurora"},
    "naperville": {"utility": "ComEd", "wind_mph": 90, "snow_psf": 25, "region": "comed", "ahj": "City of Naperville"},
    "joliet": {"utility": "ComEd", "wind_mph": 90, "snow_psf": 25, "region": "comed", "ahj": "City of Joliet"},
    "rockford": {"utility": "ComEd", "wind_mph": 90, "snow_psf": 25, "region": "comed", "ahj": "City of Rockford"},
    "waukegan": {"utility": "ComEd", "wind_mph": 90, "snow_psf": 25, "region": "comed", "ahj": "City of Waukegan"},
    "elgin": {"utility": "ComEd", "wind_mph": 90, "snow_psf": 25, "region": "comed", "ahj": "City of Elgin"},
    "evanston": {"utility": "ComEd", "wind_mph": 90, "snow_psf": 25, "region": "comed", "ahj": "City of Evanston"},
    "schaumburg": {
        "utility": "ComEd",
        "wind_mph": 90,
        "snow_psf": 25,
        "region": "comed",
        "ahj": "Village of Schaumburg",
    },
    "bolingbrook": {
        "utility": "ComEd",
        "wind_mph": 90,
        "snow_psf": 25,
        "region": "comed",
        "ahj": "Village of Bolingbrook",
    },
    "arlington heights": {
        "utility": "ComEd",
        "wind_mph": 90,
        "snow_psf": 25,
        "region": "comed",
        "ahj": "Village of Arlington Heights",
    },
    # Ameren Illinois territory — central and southern Illinois
    "springfield": {
        "utility": "Ameren Illinois",
        "wind_mph": 90,
        "snow_psf": 20,
        "region": "ameren",
        "ahj": "City of Springfield",
    },
    "decatur": {
        "utility": "Ameren Illinois",
        "wind_mph": 90,
        "snow_psf": 20,
        "region": "ameren",
        "ahj": "City of Decatur",
    },
    "bloomington": {
        "utility": "Ameren Illinois",
        "wind_mph": 90,
        "snow_psf": 20,
        "region": "ameren",
        "ahj": "City of Bloomington",
    },
    "peoria": {
        "utility": "Ameren Illinois",
        "wind_mph": 90,
        "snow_psf": 20,
        "region": "ameren",
        "ahj": "City of Peoria",
    },
    "champaign": {
        "utility": "Ameren Illinois",
        "wind_mph": 90,
        "snow_psf": 20,
        "region": "ameren",
        "ahj": "City of Champaign",
    },
    "urbana": {
        "utility": "Ameren Illinois",
        "wind_mph": 90,
        "snow_psf": 20,
        "region": "ameren",
        "ahj": "City of Urbana",
    },
    "normal": {
        "utility": "Ameren Illinois",
        "wind_mph": 90,
        "snow_psf": 20,
        "region": "ameren",
        "ahj": "Town of Normal",
    },
    "east st. louis": {
        "utility": "Ameren Illinois",
        "wind_mph": 90,
        "snow_psf": 20,
        "region": "ameren",
        "ahj": "City of East St. Louis",
    },
    "galesburg": {
        "utility": "Ameren Illinois",
        "wind_mph": 90,
        "snow_psf": 20,
        "region": "ameren",
        "ahj": "City of Galesburg",
    },
    # Default
    "_default": {"utility": "ComEd", "wind_mph": 90, "snow_psf": 25, "region": "comed", "ahj": ""},
}

# Interconnection standards by utility
UTILITY_INTERCONNECTION = {
    "ComEd": "ComEd Net Metering / IEEE 1547 (ICC / ILSFA)",
    "Ameren Illinois": "Ameren Illinois Net Metering / IEEE 1547 (ICC / ILSFA)",
    "_default": "Illinois Commerce Commission Net Metering / IEEE 1547",
}


class IllinoisJurisdiction(NECBaseEngine):
    """Illinois NEC 2020 + IECC 2021 jurisdiction engine.

    Covers Chicago metro (ComEd) and central/southern Illinois (Ameren Illinois).
    Handles automatic utility assignment, snow/wind loads, and AHJ labelling.

    AHJ note: Illinois Structural Engineering Act requires PE stamp for
    systems >10 kW on residential.
    """

    AHJ_NOTE = "Illinois Structural Engineering Act requires PE stamp for systems >10 kW on residential"

    def __init__(self, city: str = "", state: str = "IL"):
        self.city = city.lower().strip()
        self._state = state
        city_data = self._resolve_city_data()
        self.wind_speed_mph = city_data["wind_mph"]
        self.snow_load_psf = city_data["snow_psf"]
        self.utility_name = city_data["utility"]
        self._region = city_data["region"]
        self._ahj = city_data["ahj"]
        intercon_key = self.utility_name if self.utility_name in UTILITY_INTERCONNECTION else "_default"
        self._interconnection_std = UTILITY_INTERCONNECTION[intercon_key]
        self._utility_info = {
            "name": self.utility_name,
            "full_name": self.utility_name,
            "interconnection_standard": self._interconnection_std,
            "net_metering_max_kw": 2000,
            "rate_per_kwh": 0.13,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_city_data(self) -> Dict:
        """Match city name against IL_CITIES table using substring matching."""
        city_key = self.city
        for name, data in IL_CITIES.items():
            if name == "_default":
                continue
            if name in city_key or city_key in name:
                return data
        return dict(IL_CITIES["_default"])

    # ------------------------------------------------------------------
    # JurisdictionEngine interface
    # ------------------------------------------------------------------

    def get_code_name(self) -> str:
        return "NEC 2020 + Illinois Energy Code (IECC 2021)"

    def get_code_edition(self) -> str:
        return "NEC 2020 (NFPA 70-2020) + Illinois Energy Code (IECC 2021)"

    @property
    def wire_type(self) -> str:
        return "THWN-2"

    def get_governing_codes(self) -> List[Dict]:
        return [
            {"code": "NEC 2020", "title": "National Electrical Code", "edition": "2020"},
            {"code": "IECC 2021", "title": "Illinois Energy Code (IECC)", "edition": "2021"},
            {"code": "ASCE 7-16", "title": "Minimum Design Loads for Buildings", "edition": "2016"},
            {"code": "IFC 2021", "title": "International Fire Code", "edition": "2021"},
            {"code": "UL 1741", "title": "Inverters, Converters, Controllers", "edition": "SA"},
            {"code": "UL 2703", "title": "Mounting Systems, Bonding", "edition": "2023"},
            {"code": "IEEE 1547", "title": "Interconnection Standard", "edition": "2018"},
        ]

    def get_design_temperatures(self, city: str = "") -> Dict:
        city_key = (city or self.city).lower()
        temps = {
            "chicago": {"cold_c": -20, "hot_module_c": 65, "stc_c": 25},
            "rockford": {"cold_c": -22, "hot_module_c": 64, "stc_c": 25},
            "waukegan": {"cold_c": -20, "hot_module_c": 64, "stc_c": 25},
            "aurora": {"cold_c": -20, "hot_module_c": 64, "stc_c": 25},
            "joliet": {"cold_c": -20, "hot_module_c": 64, "stc_c": 25},
            "springfield": {"cold_c": -18, "hot_module_c": 66, "stc_c": 25},
            "peoria": {"cold_c": -18, "hot_module_c": 65, "stc_c": 25},
            "decatur": {"cold_c": -18, "hot_module_c": 66, "stc_c": 25},
            "champaign": {"cold_c": -16, "hot_module_c": 67, "stc_c": 25},
            "urbana": {"cold_c": -16, "hot_module_c": 67, "stc_c": 25},
        }
        for key, t in temps.items():
            if key in city_key:
                return t
        return {"cold_c": -20, "hot_module_c": 65, "stc_c": 25}  # Illinois default

    def get_fire_setbacks(self, building_type: str = "residential") -> Dict:
        """NEC 690.12 rapid shutdown + IFC setbacks (Illinois Building Code).

        18" ridge, 36" sides/eave for residential per IFC 2021.
        """
        if building_type == "residential":
            return {"ridge_ft": 1.5, "eave_ft": 3.0, "pathway_ft": 3.0}
        return {"ridge_ft": 1.5, "eave_ft": 3.0, "pathway_ft": 4.0}

    def get_wind_snow_loads(self, city: str = "") -> Dict:
        """Illinois wind and snow loads per ASCE 7.

        Snow: 25 PSF Chicago metro / Rockford / Waukegan; 20 PSF central/southern IL.
        Wind: 90 mph statewide per ASCE 7.
        """
        return {"wind_mph": self.wind_speed_mph, "snow_psf": self.snow_load_psf}

    def get_utility_info(self, city: str = "") -> Dict:
        if city and city.lower().strip() != self.city:
            return IllinoisJurisdiction(city=city)._utility_info
        return self._utility_info

    def get_ahj_label(self, city: str = "") -> str:
        """Return AHJ label for the city."""
        if self._ahj:
            return self._ahj
        city_title = (city or self.city).strip().title()
        if city_title:
            return f"City of {city_title}"
        return "Local Building Department (Illinois)"

    def get_contractor_license_type(self) -> str:
        return "Illinois Licensed Electrical Contractor (ILEC)"

    def get_licensing_body(self) -> str:
        return "IDFPR"

    def get_licensing_body_full(self) -> str:
        return "Illinois Department of Financial and Professional Regulation (IDFPR)"

    def get_general_notes(self) -> List[str]:
        return [
            "1. This drawing sets minimum standards for construction. All work shall comply with NEC 2020 (NFPA 70-2020) and all applicable local ordinances.",
            f"2. Governing building code: {self.get_code_name()}.",
            "3. All equipment shall be installed per manufacturer's installation manuals. Notify the contractor of any discrepancies prior to beginning work.",
            "4. Prior to the commencement of any work, the contractor shall visit the site to fully verify all existing conditions.",
            "5. All effort must be made by the general contractor and subcontractors to mount equipment level and secure.",
            "6. Beams or joists shall not be drilled unless specifically authorized by the structural engineer of record.",
            f"7. A permit must be obtained from the Authority Having Jurisdiction ({self.get_ahj_label()}) prior to commencing any work.",
            "8. The local utility shall be notified prior to interconnection.",
            f"9. Interconnection per {self._interconnection_std}.",
            "10. Rapid shutdown equipment shall comply with NEC 2020 Section 690.12.",
            "11. All conductors shall be THWN-2 rated for wet locations.",
            f"12. Wind design per ASCE 7: {self.wind_speed_mph} mph design wind speed. Snow load: {self.snow_load_psf} PSF.",
            f"13. {self.AHJ_NOTE}.",
            "14. All drawings and notes are not to scale. Contractor shall check and verify all dimensions at the job site.",
        ]

    def get_electrical_notes(self) -> List[str]:
        return [
            "1. The equipment and all associated wiring shall be installed only by qualified persons holding a valid Illinois Licensed Electrical Contractor (ILEC) license. (NEC 2020 690.4(E))",
            "2. The local utility shall be notified prior to activation of any solar photovoltaic installation.",
            "3. All PV conductors shall be THWN-2 rated.",
            "4. DC conductors shall comply with NEC 2020 690.8(A): Isc × 1.25 × 1.25 (Isc × 1.56).",
            "5. AC breaker sizing per NEC 2020 690.8(A): continuous current × 1.25.",
            "6. Interconnection per NEC 2020 705.12 (120% rule or supply-side tap).",
            "7. Rapid shutdown shall comply with NEC 2020 Section 690.12.",
            "8. All inverters shall be UL 1741 SA listed and compliant with Illinois utility requirements.",
            "9. Equipment grounding conductor per NEC 2020 Table 250.122.",
            "10. Voltage drop shall be limited to 2% for branch circuits and 3% cumulative.",
            "11. All conduit sizes and types specified in single-line and/or three-line diagrams shall be installed.",
            "12. The backfeed breaker shall be at the opposite end of the bus from the main breaker.",
            "13. All PV source circuits shall have individual overcurrent protection per NEC 2020 690.9.",
            f"14. Snow load design: {self.snow_load_psf} PSF per ASCE 7. Racking shall be certified for this load.",
            f"15. {self.AHJ_NOTE}.",
        ]

    def get_jurisdiction_data(self, city: str = "", state: str = "IL") -> Dict:
        """Return a flat summary dict. Accepts optional city/state to re-resolve."""
        if city and city.lower().strip() != self.city:
            return IllinoisJurisdiction(city=city, state=state).get_jurisdiction_data()
        return {
            "utility": self.utility_name,
            "wire_type": self.wire_type,
            "electrical_code": self.get_code_edition(),
            "utility_full": self.utility_name,
            "wind_mph": self.wind_speed_mph,
            "snow_load_psf": self.snow_load_psf,
            "snow_psf": self.snow_load_psf,
            "ahj": self.get_ahj_label(),
            "licensing_body": self.get_licensing_body(),
            "code_name": self.get_code_name(),
            "ahj_note": self.AHJ_NOTE,
        }
