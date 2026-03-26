"""
CEC British Columbia Jurisdiction Engine
=========================================
Implements JurisdictionEngine for British Columbia, Canada under:
  - CEC CSA C22.1-2021 (Canadian Electrical Code, 25th Edition)
  - BC Building Code 2018 (BCBC)
  - BC Safety Authority (Technical Safety BC) electrical permit
  - CSA C22.2 No.107.1 (Inverter safety standard)

Utilities:
  - BC Hydro (most of BC)
  - FortisBC (Okanagan / Kootenay region: Kelowna, Penticton, Vernon, Trail,
    Nelson, Castlegar, and surrounding communities)

Net Metering: BC Hydro Net Metering program (up to 100 kW residential/commercial).
  - FortisBC: FortisBC Net Metering program (up to 100 kW)

BC Safety Authority / Technical Safety BC:
  - Electrical permit required from Technical Safety BC before commencing work
  - Electrician must be licensed under BC Safety Authority (Red Seal or BC ticket)
"""

from typing import List

from .base import JurisdictionEngine


# ── Conductor ampacity table (CEC Table 2 / 75 deg C copper / RW90) ──────

CONDUCTOR_AMPACITY_75C = [
    (15, "#14 AWG Cu"),
    (20, "#12 AWG Cu"),
    (30, "#10 AWG Cu"),
    (40, "#8 AWG Cu"),
    (55, "#6 AWG Cu"),
    (70, "#4 AWG Cu"),
    (85, "#3 AWG Cu"),
    (95, "#2 AWG Cu"),
    (110, "#1 AWG Cu"),
    (125, "#1/0 AWG Cu"),
    (145, "#2/0 AWG Cu"),
    (165, "#3/0 AWG Cu"),
    (195, "#4/0 AWG Cu"),
]

# ── EGC sizing table (CEC 10-814) ────────────────────────────────────────

EGC_TABLE = [
    (15, "#14 AWG Cu"),
    (20, "#12 AWG Cu"),
    (60, "#10 AWG Cu"),
    (100, "#8 AWG Cu"),
    (200, "#6 AWG Cu"),
    (300, "#4 AWG Cu"),
    (400, "#3 AWG Cu"),
    (500, "#2 AWG Cu"),
    (600, "#1 AWG Cu"),
    (800, "#1/0 AWG Cu"),
]

# ── Standard breaker sizes ────────────────────────────────────────────────

STANDARD_BREAKER_SIZES = [15, 20, 25, 30, 35, 40, 50, 60, 70, 80, 100, 125, 150, 200]

# ── Design temperatures by BC city (BCBC 2018 / NBCC 2020 Appendix C) ────

CITY_DESIGN_TEMPS = {
    "vancouver": -7,
    "surrey": -8,
    "burnaby": -7,
    "richmond": -7,
    "abbotsford": -12,
    "coquitlam": -9,
    "langley": -10,
    "saanich": -6,  # Victoria area — mild marine climate
    "victoria": -6,
    "kelowna": -22,  # Interior — much colder
    "penticton": -20,
    "vernon": -22,
    "kamloops": -23,
    "prince george": -33,
    "nanaimo": -7,
    "trail": -18,
    "nelson": -19,
    "castlegar": -18,
    "chilliwack": -12,
    "maple ridge": -10,
    "north vancouver": -8,
    "west vancouver": -7,
    "new westminster": -8,
    "port coquitlam": -9,
    "port moody": -9,
}

DEFAULT_COLD_TEMP_C = -15  # Conservative BC default (balances coastal/interior)

# ── Snow loads by city (kPa) — BCBC 2018 Table C-2 ───────────────────────

CITY_SNOW_LOAD_KPA = {
    "vancouver": 1.9,
    "surrey": 1.9,
    "burnaby": 1.9,
    "richmond": 1.9,
    "abbotsford": 2.2,
    "coquitlam": 2.0,
    "langley": 2.0,
    "saanich": 1.4,  # Victoria area — less snow
    "victoria": 1.4,
    "kelowna": 2.5,
    "penticton": 2.2,
    "vernon": 2.6,
    "kamloops": 2.2,
    "prince george": 3.8,
    "nanaimo": 1.6,
    "trail": 2.8,
    "nelson": 3.0,
    "castlegar": 2.6,
    "chilliwack": 2.0,
    "north vancouver": 2.2,
    "west vancouver": 2.0,
    "new westminster": 1.9,
    "port coquitlam": 2.0,
    "port moody": 2.0,
}

DEFAULT_SNOW_LOAD_KPA = 2.4  # Conservative BC default (interior bias)

# ── Seismic design category by city ──────────────────────────────────────

CITY_SEISMIC = {
    "vancouver": "SDC D",  # Lower Mainland — high seismic zone
    "surrey": "SDC D",
    "burnaby": "SDC D",
    "richmond": "SDC D",  # Extreme liquefaction risk
    "coquitlam": "SDC D",
    "north vancouver": "SDC D",
    "west vancouver": "SDC D",
    "new westminster": "SDC D",
    "port coquitlam": "SDC D",
    "port moody": "SDC D",
    "abbotsford": "SDC C",
    "langley": "SDC D",
    "saanich": "SDC D",  # Victoria — also high seismic
    "victoria": "SDC D",
    "nanaimo": "SDC C",
    "kelowna": "SDC B",
    "penticton": "SDC B",
    "vernon": "SDC B",
    "kamloops": "SDC B",
    "prince george": "SDC B",
    "trail": "SDC B",
    "nelson": "SDC B",
    "castlegar": "SDC B",
    "chilliwack": "SDC C",
}

DEFAULT_SEISMIC = "SDC C"

# ── FortisBC service territory cities ────────────────────────────────────

FORTISBC_CITIES = {
    "kelowna",
    "penticton",
    "vernon",
    "trail",
    "nelson",
    "castlegar",
    "osoyoos",
    "oliver",
    "keremeos",
    "princeton",
    "summerland",
    "peachland",
    "west kelowna",
    "lake country",
    "enderby",
    "armstrong",
    "lumby",
    "grand forks",
    "greenwood",
    "midway",
    "rossland",
    "fruitvale",
    "salmo",
    "creston",
    "kaslo",
    "nakusp",
    "new denver",
}

DEFAULT_UTILITY = "BC Hydro"


def _get_utility_for_city(city: str) -> str:
    return "FortisBC" if city.strip().lower() in FORTISBC_CITIES else DEFAULT_UTILITY


class BCJurisdiction(JurisdictionEngine):
    """British Columbia / CEC jurisdiction engine for solar PV planset generation.

    Args:
        city:    BC city name for climate data, utility lookup, and seismic zone.
        utility: Override utility name. If omitted, auto-selected by city.
    """

    def __init__(self, city: str = "", utility: str = "", municipality: str = "", province: str = ""):
        # Accept municipality/province as aliases for city (test harness compatibility)
        if not city and municipality:
            city = municipality
        self.city = city
        city_lower = city.strip().lower()

        # Utility — auto-select or override
        self.utility_name = utility if utility else _get_utility_for_city(city)
        self.utility = self.utility_name  # alias for compatibility

        # BC-specific design parameters
        self.wire_type = "RW90-XLPE"
        self.conduit_type = "EMT (exposed); Schedule-40 PVC (concealed)"
        self.snow_load_kpa = CITY_SNOW_LOAD_KPA.get(city_lower, DEFAULT_SNOW_LOAD_KPA)
        self.seismic_zone = CITY_SEISMIC.get(city_lower, DEFAULT_SEISMIC)
        self.wind_speed_ms = 40  # 40 m/s coastal design wind (BCBC 2018)

    # ── Identity ──────────────────────────────────────────────────────────

    def get_building_code(self) -> str:
        return "BCBC"

    def get_code_name(self) -> str:
        return "CEC"

    def get_code_edition(self) -> str:
        return "CSA C22.1-2021 (25th Edition)"

    # ── Climate / design conditions ───────────────────────────────────────

    def get_design_temperatures(self, city: str) -> dict:
        key = (city or self.city).strip().lower()
        cold_c = CITY_DESIGN_TEMPS.get(key, DEFAULT_COLD_TEMP_C)
        return {
            "cold_c": cold_c,
            "hot_module_c": 65,
            "stc_c": 25,
        }

    # ── Electrical sizing ─────────────────────────────────────────────────

    def calculate_ac_breaker(self, continuous_amps: float) -> int:
        """CEC Rule 4-004 / 64-100: breaker = continuous x 1.25, rounded to standard size."""
        min_breaker = continuous_amps * 1.25
        for size in STANDARD_BREAKER_SIZES:
            if size >= min_breaker:
                return size
        return STANDARD_BREAKER_SIZES[-1]

    def calculate_dc_conductor(self, isc: float, num_strings: int) -> str:
        """CEC Rule 14-100: DC conductor sized for Isc x 1.56 (1.25 x 1.25)."""
        required_ampacity = isc * num_strings * 1.56
        for ampacity, conductor in CONDUCTOR_AMPACITY_75C:
            if ampacity >= required_ampacity:
                return conductor.replace(" Cu", " PV Wire")
        return CONDUCTOR_AMPACITY_75C[-1][1].replace(" Cu", " PV Wire")

    def calculate_ac_conductor(self, continuous_amps: float) -> str:
        """Size AC conductor for breaker rating from CEC Table 2."""
        breaker = self.calculate_ac_breaker(continuous_amps)
        for ampacity, conductor in CONDUCTOR_AMPACITY_75C:
            if ampacity >= breaker:
                return conductor
        return CONDUCTOR_AMPACITY_75C[-1][1]

    def calculate_egc(self, breaker_amps: int) -> str:
        """Size EGC per CEC 10-814."""
        for ampacity, conductor in EGC_TABLE:
            if ampacity >= breaker_amps:
                return conductor
        return EGC_TABLE[-1][1]

    # ── Interconnection ───────────────────────────────────────────────────

    def check_interconnection_rule(
        self,
        pv_breaker_a: int,
        main_breaker_a: int,
        bus_rating_a: int,
    ) -> dict:
        """CEC Rule 64-112 / 64-404: 120% rule.

        PV breaker + main breaker <= 1.2 x bus rating.
        """
        max_allowed = int(bus_rating_a * 1.20)
        total = pv_breaker_a + main_breaker_a
        return {
            "passes": total <= max_allowed,
            "max_allowed": max_allowed,
            "method": "120% rule (CEC 64-112 / 64-404)",
        }

    # ── Labels / placards ─────────────────────────────────────────────────

    def get_required_labels(self) -> List[dict]:
        """Return 14 ANSI Z535 labels required for BC solar installations."""
        return [
            {
                "level": "DANGER",
                "text": "SOLAR PV SYSTEM — DC DISCONNECT\nDO NOT OPEN UNDER LOAD\nRisk of electric shock from DC voltage",
                "location": "DC Disconnect",
                "color": "red",
            },
            {
                "level": "DANGER",
                "text": "SOLAR PV SYSTEM — ENERGIZED IN DAYLIGHT\nMultiple power sources present\nDisconnect AC and DC before servicing",
                "location": "Inverter",
                "color": "red",
            },
            {
                "level": "DANGER",
                "text": "ELECTRIC SHOCK HAZARD\nDo not touch terminals\nBoth line and load may be energized",
                "location": "AC Combiner / Junction Box",
                "color": "red",
            },
            {
                "level": "WARNING",
                "text": "DUAL POWER SOURCE\nThis panel is fed by solar PV and utility power\nDisconnect both sources before servicing",
                "location": "Main Electrical Panel",
                "color": "orange",
            },
            {
                "level": "WARNING",
                "text": "SOLAR PV SYSTEM INSTALLED ON THIS STRUCTURE\nBackfed breaker — do not relocate\nSee CEC Rule 64-404",
                "location": "Main Panel Cover",
                "color": "orange",
            },
            {
                "level": "WARNING",
                "text": f"BIDIRECTIONAL METER\nNet Metering — {self.utility_name}\nDO NOT REMOVE",
                "location": "Utility Meter",
                "color": "orange",
            },
            {
                "level": "CAUTION",
                "text": "AC DISCONNECT\nService disconnect for solar PV system\nBreaker location: see single-line diagram",
                "location": "AC Disconnect",
                "color": "yellow",
            },
            {
                "level": "CAUTION",
                "text": "SOLAR PV — CONDUIT CONTAINS DC WIRING\nDo not cut or damage conduit\nRisk of electric shock",
                "location": "DC Conduit Runs",
                "color": "yellow",
            },
            {
                "level": "CAUTION",
                "text": "ROOF-MOUNTED PV ARRAY\nUse fall protection when accessing roof\nDo not step on modules",
                "location": "Roof Access Point",
                "color": "yellow",
            },
            {
                "level": "NOTICE",
                "text": "RAPID SHUTDOWN SWITCH\nPV System Shutdown\nActivate in emergency\nArray voltage drops to <= 30V within 30 seconds",
                "location": "Rapid Shutdown Initiator",
                "color": "blue",
            },
            {
                "level": "NOTICE",
                "text": "SOLAR PV INVERTER\nGrid-interactive operation\nCSA C22.2 No.107.1 listed",
                "location": "Inverter Enclosure",
                "color": "blue",
            },
            {
                "level": "NOTICE",
                "text": "GROUNDING ELECTRODE CONDUCTOR\nDo not remove or disconnect\nRequired for equipment safety grounding",
                "location": "Grounding Electrode",
                "color": "blue",
            },
            {
                "level": "NOTICE",
                "text": "PV SYSTEM POINT OF INTERCONNECTION\nBackfed breaker per CEC 64-404\n120% rule verified — see calculations",
                "location": "Point of Interconnection",
                "color": "blue",
            },
            {
                "level": "NOTICE",
                "text": "FIRE DEPARTMENT — SOLAR PV INSTALLED\nSee site plan for array location\nRapid shutdown at main panel",
                "location": "Front Door / Electrical Room Entry",
                "color": "blue",
            },
        ]

    # ── Fire setbacks ─────────────────────────────────────────────────────

    def get_fire_setbacks(self, building_type: str) -> dict:
        """BC Building Code 2018 / IFC 2021 Section 605.11 fire setbacks."""
        bt = building_type.strip().lower()
        if bt in ("residential", "single-family", "detached", "semi-detached"):
            return {"ridge_ft": 3, "eave_ft": 1.5, "pathway_ft": 3}
        elif bt in ("commercial", "industrial", "multi-family"):
            return {"ridge_ft": 6, "eave_ft": 3, "pathway_ft": 4}
        else:
            return {"ridge_ft": 3, "eave_ft": 1.5, "pathway_ft": 3}

    # ── Notes ─────────────────────────────────────────────────────────────

    def get_general_notes(self) -> List[str]:
        """General notes for BC solar installations."""
        net_metering_program = (
            "FortisBC Net Metering program" if "FortisBC" in self.utility_name else "BC Hydro Net Metering program"
        )
        return [
            f"Notify {self.utility_name} prior to activating the PV system. Net metering application must be approved under the {net_metering_program} before grid connection.",
            "All electrical equipment shall be CSA-listed and installed per manufacturer's installation instructions.",
            "A Technical Safety BC (BC Safety Authority) electrical permit is required before commencing electrical work. Permit holder must be a BC-licensed electrical contractor.",
            "Installer shall verify all dimensions and conditions at the job site. Report discrepancies to designer before proceeding.",
            "All electrical work shall be performed by or under the direct supervision of a Journeyman Electrician licensed under Technical Safety BC.",
            "A Technical Safety BC inspector must inspect and approve the installation before the system is energized.",
            "Installer shall verify adequate roof access pathways per BCBC 2018 and AHJ requirements before beginning work.",
            "Installer shall verify structural integrity of roof rafters/trusses prior to installing the racking system.",
            f"Racking system shall be designed for snow load of {self.snow_load_kpa} kPa and wind speed of {self.wind_speed_ms} m/s per BCBC 2018.",
            f"Seismic design category: {self.seismic_zone} — racking attachments and equipment anchorage shall meet BCBC 2018 seismic requirements.",
            'Lag screws used for racking attachment shall penetrate a minimum of 63 mm (2.5") into solid wood framing members.',
            "Roof access pathways (ridge, eave, and ventilation access) shall be maintained per IFC Section 605.11 and BC Fire Code.",
            "All DC conductors shall be contained in conduit unless listed as PV wire or RW90-XLPE rated for sunlight exposure.",
            "All plumbing vents, stacks, and HVAC equipment shall maintain required clearances from the PV system.",
            "All junction boxes and wiring devices shall remain accessible without removing permanent construction per CEC Rule 12-3036.",
            "Racking system shall be bonded to the grounding electrode system per CEC Rule 64-104.",
            "PV module frames shall be bonded using WEEB (Washer/Lug Bonding) clip or equivalent listed bonding hardware.",
            "All inverters shall be CSA C22.2 No.107.1 listed and certified for grid-interactive (GTI) operation.",
            "A grounding electrode shall be provided per CEC Rule 64-104 and interconnected with the utility grounding system.",
        ]

    def get_electrical_notes(self) -> List[str]:
        """Electrical code notes for CEC Section 64 / BC."""
        return [
            "All conductors shall be copper unless otherwise noted. Aluminum conductors are not permitted for branch circuits.",
            "PV source/output circuit conductors shall be RW90-XLPE or PV wire rated for sunlight resistance and wet locations per CEC Rule 64-208.",
            "All DC conductors shall be labeled/identified at every junction, pull box, and termination point per CEC Rule 64-214.",
            "Conductors in exterior exposed locations shall be run in EMT (exposed) or Schedule-40 PVC (concealed) per CEC Section 12.",
            "All metallic raceways and equipment enclosures shall be bonded to the grounding electrode system per CEC Section 10.",
            "Conduit fill shall not exceed 40% of interior cross-sectional area per CEC Table 6.",
            "Inverter AC output grounding bond shall be maintained even when the inverter is removed from service.",
            "Ground fault protection (GFP) is required for all grounded DC PV systems per CEC Rule 64-218.",
            "GFCI protection and rapid shutdown shall be provided per CEC Rule 64-218(8) and Technical Safety BC requirements.",
            "PV module frame bonding shall use listed bonding hardware (WEEB clip or equivalent) per CEC Rule 64-104.",
            "Racking rail-to-rail bonding shall be maintained using listed splice connectors or WEEB bonding hardware.",
            f"Inverter shall be CSA C22.2 No.107.1 listed and approved for grid-interactive operation per {self.utility_name} standards.",
            f"Racking system shall be rated for design snow load of {self.snow_load_kpa} kPa and wind speed of {self.wind_speed_ms} m/s per BCBC 2018.",
            "A continuous grounding path shall be maintained from all module frames to the grounding electrode conductor.",
            "All bus bar splices shall be rated for the conditions of use per applicable CEC requirements.",
            "The PV backfed breaker shall be positioned at the opposite end of the bus bar from the main breaker per CEC Rule 64-404.",
            "120% Rule: Sum of PV breaker + main breaker ampere ratings shall not exceed 120% of bus bar rating per CEC Rule 64-404.",
        ]

    # ── Governing codes ───────────────────────────────────────────────────

    def get_governing_codes(self) -> List[dict]:
        return [
            {
                "code": "CEC",
                "title": "Canadian Electrical Code, Part I",
                "edition": "CSA C22.1-2021 (25th Edition)",
            },
            {
                "code": "BCBC",
                "title": "BC Building Code",
                "edition": "2018",
            },
            {
                "code": "NBCC",
                "title": "National Building Code of Canada",
                "edition": "2020",
            },
            {
                "code": "IFC",
                "title": "International Fire Code",
                "edition": "2021",
            },
            {
                "code": "CSA C22.2 No.107.1",
                "title": "CSA Standard for Power Conversion Equipment (Inverters)",
                "edition": "2016 (R2021)",
            },
        ]

    # ── Utility information ───────────────────────────────────────────────

    def get_utility_info(self, city: str = "") -> dict:
        effective_city = city or self.city
        utility_name = _get_utility_for_city(effective_city) if effective_city else self.utility_name

        # Both BC Hydro and FortisBC allow up to 100 kW net metering
        if "FortisBC" in utility_name:
            return {
                "name": utility_name,
                "net_metering_max_kw": 100,
                "rate_per_kwh": 0.1223,  # FortisBC residential rate Step 1 (2024)
                "incentive_per_kw": 0,
                "program_name": "FortisBC Net Metering Program",
                "voltage": "240V split-phase",
                "frequency_hz": 60,
                "interconnection_standard": "CEC Section 64 / FortisBC Interconnection Requirements",
            }
        else:
            return {
                "name": utility_name,
                "net_metering_max_kw": 100,
                "rate_per_kwh": 0.1399,  # BC Hydro residential rate Step 1 (2024)
                "incentive_per_kw": 0,
                "program_name": "BC Hydro Net Metering Program",
                "voltage": "240V split-phase",
                "frequency_hz": 60,
                "interconnection_standard": "CEC Section 64 / BC Hydro Interconnection Requirements",
            }

    # ── Licensing / authority ─────────────────────────────────────────────

    def get_code_references(self) -> List[str]:
        """Return list of applicable code reference strings."""
        return [
            "CEC CSA C22.1-2021 (25th Edition)",
            "BC Building Code 2018 (BCBC)",
            "NBCC 2020",
            "IFC 2021 Section 605.11",
            "CSA C22.2 No.107.1",
        ]

    def get_licensing_info(self) -> dict:
        """Return Technical Safety BC licensing requirements."""
        return {
            "licensing_body": "Technical Safety BC",
            "licensing_body_full": "Technical Safety BC (BC Safety Authority)",
            "permit_required": "Technical Safety BC Electrical Permit",
            "inspector": "Technical Safety BC Inspector",
            "contractor_license": "BC Electrical Contractor Licence (Technical Safety BC)",
            "master_electrician": "Journeyman Electrician — BC Certificate of Qualification (309A)",
        }

    def get_contractor_license_type(self) -> str:
        """BC contractor licensing."""
        return "Technical Safety BC"

    def get_licensing_body(self) -> str:
        return "Technical Safety BC"

    def get_licensing_body_full(self) -> str:
        return "Technical Safety BC (BC Safety Authority)"

    # ── Convenience summary dict (used by test harness) ───────────────────

    def get_jurisdiction_data(self) -> dict:
        """Return a flat summary dict for quick validation and rendering."""
        return {
            "utility": self.utility_name,
            "wire_type": self.wire_type,
            "electrical_code": self.get_code_edition(),
            "conduit_type": self.conduit_type,
            "snow_load_kpa": self.snow_load_kpa,
            "seismic_zone": self.seismic_zone,
            "wind_speed_ms": self.wind_speed_ms,
            "licensing_body": "Technical Safety BC",
            "code_name": self.get_code_name(),
        }
