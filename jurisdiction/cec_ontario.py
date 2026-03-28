"""
CEC Ontario Jurisdiction Engine
=================================
Implements JurisdictionEngine for Ontario, Canada under:
  - CEC CSA C22.1-2021 (Canadian Electrical Code, 25th Edition)
  - ESA (Electrical Safety Authority) Ontario Electrical Safety Code
  - NBCC 2020 (National Building Code of Canada)
  - IFC 2021 (International Fire Code)
  - CSA C22.2 No.107.1 (Inverter safety standard)

Utilities:
  - Hydro One Networks Inc. (most of Ontario)
  - Toronto Hydro (City of Toronto)
  - Ottawa Hydro (City of Ottawa)

Net Metering: Ontario Energy Board (OEB) net metering program.
  - Max single-phase: 10 kW residential
  - Retail rate credit (time-of-use or tiered billing)

ESA / ECRA licensing:
  - Electrical work requires ESA permit
  - Contractor must hold ECRA (Electrical Contractor Registration Agency) licence
  - Master Electrician or Licensed Electrician to perform work
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

# ── Design temperatures by Ontario city (NBCC 2020 Table C-2) ────────────

CITY_DESIGN_TEMPS = {
    "toronto": -18,
    "north york": -18,
    "scarborough": -18,
    "etobicoke": -18,
    "mississauga": -19,
    "brampton": -19,
    "hamilton": -17,
    "ottawa": -25,
    "london": -19,
    "windsor": -14,
    "kingston": -22,
    "thunder bay": -31,
    "sudbury": -29,
    "sault ste. marie": -28,
    "north bay": -29,
    "barrie": -22,
    "oshawa": -19,
    "waterloo": -20,
    "kitchener": -20,
    "guelph": -20,
    "cambridge": -20,
    "st. catharines": -16,
    "niagara falls": -16,
    "brantford": -18,
    "peterborough": -23,
}

DEFAULT_COLD_TEMP_C = -23  # Conservative Ontario default

# ── Utility map (city → utility) ─────────────────────────────────────────

CITY_UTILITY_MAP = {
    "toronto": "Toronto Hydro",
    "north york": "Toronto Hydro",
    "scarborough": "Toronto Hydro",
    "etobicoke": "Toronto Hydro",
    "east york": "Toronto Hydro",
    "ottawa": "Ottawa Hydro",
    "kanata": "Ottawa Hydro",
    "nepean": "Ottawa Hydro",
    "gloucester": "Ottawa Hydro",
}

DEFAULT_UTILITY = "Hydro One Networks Inc."


def _get_utility_for_city(city: str) -> str:
    return CITY_UTILITY_MAP.get(city.strip().lower(), DEFAULT_UTILITY)


class OntarioJurisdiction(JurisdictionEngine):
    """Ontario / CEC jurisdiction engine for solar PV planset generation.

    Args:
        city:    Ontario city name for climate data and utility lookup.
        utility: Override utility name. If omitted, auto-selected by city.
    """

    def __init__(self, city: str = "", utility: str = ""):
        self.city = city
        if utility:
            self.utility = utility
        else:
            self.utility = _get_utility_for_city(city)
        self.wire_type = "RW90-XLPE"
        self.conduit_type = "EMT or RMC (exposed); Schedule-40 PVC (concealed)"

    # ── Convenience properties ────────────────────────────────────────────

    @property
    def utility_name(self) -> str:
        return self.utility

    @property
    def electrical_code(self) -> str:
        return "CEC 25th Ed (CSA C22.1-2021)"

    @property
    def permit_authority(self) -> str:
        return "ESA (Electrical Safety Authority)"

    # ── Identity ──────────────────────────────────────────────────────────

    def get_building_code(self) -> str:
        return "OBC"

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
        """Return 14 ANSI Z535 labels required for Ontario solar installations."""
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
                "text": f"BIDIRECTIONAL METER\nNet Metering — {self.utility}\nDO NOT REMOVE",
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
        """IFC 2021 Section 605.11 / Ontario Fire Code fire setbacks."""
        bt = building_type.strip().lower()
        if bt in ("residential", "single-family", "detached", "semi-detached"):
            return {"ridge_ft": 3, "eave_ft": 1.5, "pathway_ft": 3}
        elif bt in ("commercial", "industrial", "multi-family"):
            return {"ridge_ft": 6, "eave_ft": 3, "pathway_ft": 4}
        else:
            return {"ridge_ft": 3, "eave_ft": 1.5, "pathway_ft": 3}

    # ── Notes ─────────────────────────────────────────────────────────────

    def get_general_notes(self) -> List[str]:
        """General notes for Ontario solar installations."""
        return [
            f"Notify {self.utility} prior to activating the PV system. Net metering application must be approved by the Ontario Energy Board before grid connection.",
            "All electrical equipment shall be CSA-listed and installed per manufacturer's installation instructions.",
            "An ESA (Electrical Safety Authority) permit is required before commencing electrical work. ECRA-licensed contractor must obtain permit.",
            "Installer shall verify all dimensions and conditions at the job site. Report discrepancies to designer before proceeding.",
            "All electrical work shall be performed by or under the direct supervision of a Licensed Electrician holding an ECRA contractor registration.",
            "An ESA-certified inspector must inspect and approve the installation before the system is energized.",
            "Installer shall verify adequate roof access pathways per NBCC 2020 and AHJ requirements before beginning work.",
            "Installer shall verify structural integrity of roof rafters/trusses prior to installing the racking system.",
            'Lag screws used for racking attachment shall penetrate a minimum of 63 mm (2.5") into solid wood framing members.',
            "Roof access pathways (ridge, eave, and ventilation access) shall be maintained per IFC Section 605.11 and Ontario Fire Code.",
            "All DC conductors shall be contained in conduit unless listed as PV wire or RW90-XLPE rated for sunlight exposure.",
            "All plumbing vents, stacks, and HVAC equipment shall maintain required clearances from the PV system.",
            "All junction boxes and wiring devices shall remain accessible without removing permanent construction per CEC Rule 12-3036.",
            "Racking system shall be bonded to the grounding electrode system per CEC Rule 64-104.",
            "PV module frames shall be bonded using WEEB (Washer/Lug Bonding) clip or equivalent listed bonding hardware.",
            "All inverters shall be CSA C22.2 No.107.1 listed and certified for grid-interactive (GTI) operation.",
            "A grounding electrode shall be provided per CEC Rule 64-104 and interconnected with the utility grounding system.",
        ]

    def get_electrical_notes(self) -> List[str]:
        """Electrical code notes for CEC Section 64 / Ontario."""
        return [
            "All conductors shall be copper unless otherwise noted. Aluminum conductors are not permitted for branch circuits.",
            "PV source/output circuit conductors shall be RW90-XLPE or PV wire rated for sunlight resistance and wet locations per CEC Rule 64-208.",
            "All DC conductors shall be labeled/identified at every junction, pull box, and termination point per CEC Rule 64-214.",
            "Conductors in exterior exposed locations shall be run in EMT or RMC (exposed) or Schedule-40 PVC (concealed) per CEC Section 12.",
            "All metallic raceways and equipment enclosures shall be bonded to the grounding electrode system per CEC Section 10.",
            "Conduit fill shall not exceed 40% of interior cross-sectional area per CEC Table 6.",
            "Inverter AC output grounding bond shall be maintained even when the inverter is removed from service.",
            "Ground fault protection (GFP) is required for all grounded DC PV systems per CEC Rule 64-218.",
            "GFCI protection and rapid shutdown shall be provided per CEC Rule 64-218(8) and ESA requirements.",
            "PV module frame bonding shall use listed bonding hardware (WEEB clip or equivalent) per CEC Rule 64-104.",
            "Racking rail-to-rail bonding shall be maintained using listed splice connectors or WEEB bonding hardware.",
            f"Inverter shall be CSA C22.2 No.107.1 listed and approved for grid-interactive operation per {self.utility} standards.",
            "Racking system shall be rated for design wind and snow loads per NBCC 2020 Part 4 Structural Design requirements.",
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
                "code": "OESC",
                "title": "Ontario Electrical Safety Code",
                "edition": "25th Edition (ESA)",
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
        utility_name = _get_utility_for_city(effective_city) if effective_city else self.utility

        # Toronto Hydro has different net metering cap than Hydro One
        net_metering_max_kw = 10 if "Toronto Hydro" in utility_name else 10

        return {
            "name": utility_name,
            "net_metering_max_kw": net_metering_max_kw,
            "rate_per_kwh": 0.113,  # Ontario mid-peak TOU rate (OEB 2024)
            "incentive_per_kw": 0,  # No current provincial incentive (2025)
            "program_name": "Ontario Net Metering (OEB)",
            "voltage": "240V split-phase",
            "frequency_hz": 60,
            "interconnection_standard": "CEC Section 64 / Ontario Energy Board Net Metering Rules",
        }

    # ── Licensing / authority ─────────────────────────────────────────────

    def get_code_references(self) -> List[str]:
        """Return list of applicable code reference strings."""
        return [
            "CEC CSA C22.1-2021 (25th Edition)",
            "Ontario Electrical Safety Code (OESC) — ESA",
            "NBCC 2020",
            "IFC 2021 Section 605.11",
            "CSA C22.2 No.107.1",
        ]

    def get_licensing_info(self) -> dict:
        """Return ESA / ECRA licensing requirements."""
        return {
            "licensing_body": "ESA / ECRA",
            "licensing_body_full": "Electrical Safety Authority (ESA) / Electrical Contractor Registration Agency (ECRA)",
            "permit_required": "ESA Electrical Permit",
            "inspector": "ESA-Certified Inspector",
            "contractor_license": "ECRA Electrical Contractor Licence",
            "master_electrician": "Licensed Electrician (309A or 309C certificate)",
        }

    def get_contractor_license_type(self) -> str:
        """Ontario contractor licensing."""
        return "ESA / ECRA"

    def get_licensing_body(self) -> str:
        return "ESA / ECRA"

    def get_licensing_body_full(self) -> str:
        return "Electrical Safety Authority (ESA) / Electrical Contractor Registration Agency (ECRA)"
