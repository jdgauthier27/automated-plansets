"""
California NEC Engine
=====================
California Electrical Code (NEC adopted by California) jurisdiction engine.
Implements NEC 2020 rules as adopted by California, with California-specific
fire code, building code, and utility requirements.

Note: "CEC" in California context = California Electrical Code = NEC.
NOT Canadian Electrical Code (CSA C22.1).
"""

import math
from typing import Dict, List

from jurisdiction.nec_base import NECBaseEngine


# California utilities by city/area
CA_UTILITIES = {
    "los angeles": {
        "name": "LADWP",
        "full_name": "Los Angeles Department of Water and Power",
        "net_metering_max_kw": 30,
        "rate_per_kwh": 0.10,
    },
    "sherman oaks": {
        "name": "LADWP",
        "full_name": "Los Angeles Department of Water and Power",
        "net_metering_max_kw": 30,
        "rate_per_kwh": 0.10,
    },
    "encino": {
        "name": "LADWP",
        "full_name": "Los Angeles Department of Water and Power",
        "net_metering_max_kw": 30,
        "rate_per_kwh": 0.10,
    },
    "van nuys": {
        "name": "LADWP",
        "full_name": "Los Angeles Department of Water and Power",
        "net_metering_max_kw": 30,
        "rate_per_kwh": 0.10,
    },
    "north hollywood": {
        "name": "LADWP",
        "full_name": "Los Angeles Department of Water and Power",
        "net_metering_max_kw": 30,
        "rate_per_kwh": 0.10,
    },
    "pasadena": {
        "name": "SCE",
        "full_name": "Southern California Edison",
        "net_metering_max_kw": 25,
        "rate_per_kwh": 0.12,
    },
    "glendale": {"name": "GWP", "full_name": "Glendale Water & Power", "net_metering_max_kw": 25, "rate_per_kwh": 0.11},
    "san diego": {
        "name": "SDG&E",
        "full_name": "San Diego Gas & Electric",
        "net_metering_max_kw": 25,
        "rate_per_kwh": 0.14,
    },
    "san francisco": {
        "name": "PG&E",
        "full_name": "Pacific Gas and Electric",
        "net_metering_max_kw": 25,
        "rate_per_kwh": 0.13,
    },
    "sacramento": {
        "name": "SMUD",
        "full_name": "Sacramento Municipal Utility District",
        "net_metering_max_kw": 25,
        "rate_per_kwh": 0.09,
    },
    # Default for unrecognized California cities
    "_default": {
        "name": "SCE",
        "full_name": "Southern California Edison",
        "net_metering_max_kw": 25,
        "rate_per_kwh": 0.12,
    },
}


class NECCaliforniaEngine(NECBaseEngine):
    """California-specific NEC jurisdiction engine.

    Extends the base NEC engine with California codes, fire code,
    building code, and utility-specific requirements.
    """

    def __init__(self, city: str = ""):
        self.city = city.lower().strip()
        self.wire_type = "THWN-2"

    # ── Convenience properties ────────────────────────────────────────────

    @property
    def utility_name(self) -> str:
        return self.get_utility_info()["name"]

    @property
    def ahj_name(self) -> str:
        return self.get_ahj_label()

    def get_code_name(self) -> str:
        return "California Electrical Code (NEC 2020)"

    def get_code_edition(self) -> str:
        return "2020 NEC / California Electrical Code"

    def get_design_temperatures(self, city: str = "") -> Dict:
        """California design temperatures by region."""
        city_key = (city or self.city).lower()
        temps = {
            "los angeles": {"cold_c": 1, "hot_module_c": 57, "stc_c": 25},
            "sherman oaks": {"cold_c": 1, "hot_module_c": 57, "stc_c": 25},
            "encino": {"cold_c": 1, "hot_module_c": 57, "stc_c": 25},
            "san diego": {"cold_c": 5, "hot_module_c": 55, "stc_c": 25},
            "san francisco": {"cold_c": 3, "hot_module_c": 50, "stc_c": 25},
            "sacramento": {"cold_c": -2, "hot_module_c": 60, "stc_c": 25},
            "fresno": {"cold_c": -3, "hot_module_c": 62, "stc_c": 25},
        }
        for key, t in temps.items():
            if key in city_key:
                return t
        return {"cold_c": 1, "hot_module_c": 57, "stc_c": 25}  # LA default

    def get_governing_codes(self) -> List[Dict]:
        return [
            {"code": "CEC", "title": "California Electrical Code (NEC 2020)", "edition": "2020"},
            {"code": "CBC", "title": "California Building Code", "edition": "2022"},
            {"code": "CFC", "title": "California Fire Code", "edition": "2022"},
            {"code": "CRC", "title": "California Residential Code", "edition": "2022"},
            {"code": "CEnC", "title": "California Energy Code (Title 24)", "edition": "2022"},
            {"code": "UL 1741", "title": "Inverters, Converters, Controllers", "edition": "SA"},
            {"code": "UL 2703", "title": "Mounting Systems, Bonding", "edition": "2023"},
            {"code": "IEEE 1547", "title": "Interconnection Standard", "edition": "2018"},
        ]

    def get_fire_setbacks(self, building_type: str = "residential") -> Dict:
        """California fire setbacks per CFC 605.11."""
        if building_type == "residential":
            return {"ridge_ft": 3.0, "eave_ft": 1.5, "pathway_ft": 3.0}
        return {"ridge_ft": 3.0, "eave_ft": 1.5, "pathway_ft": 4.0}

    def get_general_notes(self) -> List[str]:
        return [
            "1. This drawing sets minimum standards for construction. The drawings govern over these notes to the extent that any note shall conflict with the drawing standards of the code governing the building code, electrical code, any portion of the work, and those codes and standards listed in these drawings.",
            "2. All equipment shall be installed per manufacturer's installation manuals. Notify the contractor of any discrepancies prior to beginning work.",
            "3. Prior to the commencement of any work, the contractor shall visit the site to fully verify all existing conditions and modify the contractor's requirements of other trades.",
            "4. All items to be removed, relocated, or replaced shall be handled with proper care and stored in a safe place to prevent damage.",
            "5. All effort must be made by the general contractor and subcontractors to mount equipment level and secure.",
            "6. Any metal damage resulting from of over work shall be cleaned from roof surfaces, driveways, and any additional areas where damage or corrosion may cause electrical short circuits.",
            "7. Beams or joists shall not be drilled unless specifically authorized by the contractor.",
            "8. Where required by a larger jurisdiction, conduit cables shall not be used for yard cutting or damaging reinforcement.",
            "9. If the occupancy structure is residential, it shall be upgraded to comply with the 2022 California residential code where applicable.",
            "10. The requirements stated herein are minimum requirements. The contractor shall provide all components and materials in order to complete the work and provide a complete and usable system.",
            "11. All drawings and notes are not to scale. Where no scale is given, drawings are not to scale. All contractor and sub-contractor shall check and verify all dimensions and conditions at the job site and report any discrepancies to the engineer before proceeding with work.",
            "12. All conduit sizes and types specified in single-line and/or three-line diagrams shall be installed.",
        ]

    def get_electrical_notes(self) -> List[str]:
        return [
            "1. The equipment and all associated wiring and interconnections shall be installed only by qualified persons. (NEC 690.4(E) and 705.6)",
            "2. The local utility provider shall be notified prior to the use and activation of any solar photovoltaic installation. For a line-side tap connection, the utility must be notified well in advance.",
            "3. Array wiring shall not be readily accessible to unqualified persons.",
            "4. Wiring methods for PV system conductors are not permitted within 10 inches of the roof decking or sheathing, except where located directly below the roof surface covered by PV modules. (CEC 2019 690.12(B))",
            "5. The backfeed breaker shall be at the opposite end of the bus from the main breaker (or main lug) supplying current from the utilities.",
            "6. All conductors and wire ties bonded to building shall be listed as meeting PV requirements.",
            "7. PV source, output, and inverter circuits shall be identified at all points of termination, connection, and splices. The means of identification may include separate color coding, marking tape, tagging, or other approved means.",
            "8. Measure the line-to-line and line-to-neutral voltage of all service entrance conductors prior to installing any solar equipment. The voltages shall be verified to match the 240V AC rating.",
            "9. All conduit sizes and types shall be listed for their intended purpose and approved for the site application.",
            "10. All inverters shall be accessible. The IPC, ESE, or equivalent solar cable shall be specified by the manufacturer or an equivalent approved. Routed to source circuit combiner box as required.",
            "11. All conduits and raceways shall be installed per manufacturer's specifications.",
            "12. All PV circuits shall have appropriate overcurrent protection.",
            "13. All source circuits shall have individual source circuit protection.",
            "14. Voltage drop shall be limited to 2% for AC circuits.",
            "15. AC conductors larger than 4 AWG shall be color coded or marked as follows: Phase A or L1: Black/Phase B or L2: Red/Phase C or L3: Blue/Neutral: White/Ground: Green.",
        ]

    def get_utility_info(self, city: str = "") -> Dict:
        """Get utility info for a California city."""
        city_key = (city or self.city).lower()
        for key, info in CA_UTILITIES.items():
            if key in city_key:
                return {
                    "name": info["name"],
                    "full_name": info["full_name"],
                    "net_metering_max_kw": info["net_metering_max_kw"],
                    "rate_per_kwh": info["rate_per_kwh"],
                    "interconnection_standard": "Rule 21 / NEM 3.0",
                }
        return {
            "name": CA_UTILITIES["_default"]["name"],
            "full_name": CA_UTILITIES["_default"]["full_name"],
            "net_metering_max_kw": 25,
            "rate_per_kwh": 0.12,
            "interconnection_standard": "Rule 21 / NEM 3.0",
        }

    def get_contractor_license_type(self) -> str:
        """California contractor licensing."""
        return "CSLB C-46 Solar"

    def get_licensing_body(self) -> str:
        return "CSLB"

    def get_licensing_body_full(self) -> str:
        return "Contractors State License Board (CSLB)"

    # Neighborhoods that are within the City of Los Angeles (not separate cities)
    _LA_NEIGHBORHOODS = {
        "encino",
        "sherman oaks",
        "van nuys",
        "north hollywood",
        "studio city",
        "tarzana",
        "woodland hills",
        "canoga park",
        "chatsworth",
        "reseda",
        "northridge",
        "granada hills",
        "winnetka",
        "west hills",
        "porter ranch",
        "sylmar",
        "sun valley",
        "arleta",
        "pacoima",
        "mission hills",
        "panorama city",
        "north hills",
        "lake balboa",
        "valley village",
        "toluca lake",
        "burbank adjacent",
        "los feliz",
        "silver lake",
        "echo park",
        "atwater village",
        "glassell park",
        "mount washington",
        "highland park",
        "eagle rock",
        "elysian valley",
        "cypress park",
        "west adams",
        "leimert park",
        "hyde park",
        "crenshaw",
        "mid-city",
        "palms",
        "mar vista",
        "del rey",
        "playa del rey",
        "westchester",
        "playa vista",
        "venice",
        "marina del rey adjacent",
        "brentwood",
        "westwood",
        "sawtelle",
        "century city",
        "cheviot hills",
        "rancho park",
        "culver city adjacent",
        "south los angeles",
        "watts",
        "willowbrook",
        "central-alameda",
        "boyle heights",
        "lincoln heights",
        "el sereno",
        "city terrace",
        "east los angeles adjacent",
        "northeast los angeles",
        "sunland",
        "tujunga",
        "shadow hills",
        "hansen hills",
        "lakeview terrace",
        "kagel canyon",
    }

    def get_ahj_label(self, city: str = "") -> str:
        """Return the correct Authority Having Jurisdiction label.

        Many addresses in Los Angeles County use neighborhood names (e.g. 'Encino',
        'Sherman Oaks') that are NOT independent cities — they are unincorporated
        neighborhoods within the City of Los Angeles.  Submitting a permit to a
        non-existent 'City of Encino' building department results in immediate rejection.

        This method maps those neighborhoods to 'City of Los Angeles' so that plans
        show the correct AHJ (LADBS) on every sheet.
        """
        city_key = (city or self.city).lower().strip()
        if city_key in self._LA_NEIGHBORHOODS or "los angeles" in city_key:
            return "City of Los Angeles"
        # For recognized California cities that ARE independent
        known_cities = {
            "pasadena": "City of Pasadena",
            "glendale": "City of Glendale",
            "burbank": "City of Burbank",
            "long beach": "City of Long Beach",
            "santa monica": "City of Santa Monica",
            "culver city": "City of Culver City",
            "torrance": "City of Torrance",
            "san diego": "City of San Diego",
            "san francisco": "City of San Francisco",
            "sacramento": "City of Sacramento",
            "fresno": "City of Fresno",
        }
        for key, label in known_cities.items():
            if key in city_key:
                return label
        return f"City of {city.strip().title()}" if city.strip() else "City of Los Angeles"

    def get_wind_snow_loads(self, city: str = "") -> Dict:
        """Return design wind speed (mph) and snow load (psf) per ASCE 7-22 / CBC 2022.

        Southern California has essentially zero ground snow load.
        Wind speeds are per ASCE 7-22 Risk Category II maps for LA County.
        """
        city_key = (city or self.city).lower()
        # Mountain / high-elevation areas in CA have snow
        if any(k in city_key for k in ("mammoth", "tahoe", "big bear", "wrightwood")):
            return {"wind_mph": 90, "snow_psf": 60}
        # San Francisco / Bay Area
        if any(k in city_key for k in ("san francisco", "oakland", "berkeley")):
            return {"wind_mph": 85, "snow_psf": 0}
        # San Diego
        if "san diego" in city_key:
            return {"wind_mph": 85, "snow_psf": 0}
        # Default: Los Angeles County / Southern California (ASCE 7-22, Exposure B)
        return {"wind_mph": 94, "snow_psf": 0}


# Convenience alias
CaliforniaJurisdiction = NECCaliforniaEngine
