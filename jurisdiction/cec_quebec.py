"""
CEC Quebec Jurisdiction Engine
===============================
Implements JurisdictionEngine for Quebec, Canada under:
  - CEC CSA C22.1-2021 (Canadian Electrical Code, 25th Edition)
  - CCQ Chapter V (Quebec Construction Code — Electricity)
  - CMEQ (Corporation des maîtres électriciens du Québec) regulations
  - IFC 2021 (International Fire Code)
  - CSA C22.2 No.107.1 (Inverter safety standard)

Utility: Hydro-Québec (sole distributor across all of Quebec).
  - Net metering program: Autoproduction solaire (2025)
  - Max single-phase: 20 kW
  - Rate D: $0.0738/kWh
  - Incentive: $1,000/kW (2025 program)

Permit authority: CMEQ / Régie du bâtiment du Québec (RBQ)
Wire type: RW90-XLPE (Canadian standard — NOT THWN-2)
"""

from typing import List

from .base import JurisdictionEngine


# ── Conductor ampacity table (CEC Table 2 / 75 °C copper) ─────────────

CONDUCTOR_AMPACITY_75C = [
    (15,  "#14 AWG Cu"),
    (20,  "#12 AWG Cu"),
    (30,  "#10 AWG Cu"),
    (40,  "#8 AWG Cu"),
    (55,  "#6 AWG Cu"),
    (70,  "#4 AWG Cu"),
    (85,  "#3 AWG Cu"),
    (95,  "#2 AWG Cu"),
    (110, "#1 AWG Cu"),
    (125, "#1/0 AWG Cu"),
    (145, "#2/0 AWG Cu"),
    (165, "#3/0 AWG Cu"),
    (195, "#4/0 AWG Cu"),
]

# ── EGC sizing table (CEC 10-814) ─────────────────────────────────────

EGC_TABLE = [
    (15,  "#14 AWG Cu"),
    (20,  "#12 AWG Cu"),
    (60,  "#10 AWG Cu"),
    (100, "#8 AWG Cu"),
    (200, "#6 AWG Cu"),
    (300, "#4 AWG Cu"),
    (400, "#3 AWG Cu"),
    (500, "#2 AWG Cu"),
    (600, "#1 AWG Cu"),
    (800, "#1/0 AWG Cu"),
]

# ── Standard breaker sizes ─────────────────────────────────────────────

STANDARD_BREAKER_SIZES = [15, 20, 25, 30, 35, 40, 50, 60, 70, 80, 100, 125, 150, 200]

# ── Design temperatures by city (NBCC 2020 Appendix C) ────────────────

CITY_DESIGN_TEMPS = {
    "gatineau":        -25,
    "montreal":        -23,
    "quebec city":     -28,
    "ville de québec": -28,
    "sherbrooke":      -26,
    "trois-rivieres":  -27,
    "trois-rivières":  -27,
    "laval":           -23,
    "longueuil":       -23,
    "saguenay":        -31,   # Saguenay–Lac-Saint-Jean, coldest major city QC
    "lévis":           -28,   # Same climatic zone as Quebec City
    "levis":           -28,
    "terrebonne":      -23,   # North shore of Montreal, same zone
}

DEFAULT_COLD_TEMP_C = -25   # Conservative Quebec default

# ── Snow loads by city (PSF) — NBCC 2020 Appendix C ──────────────────
# Quebec has heavy snowfall; all residential racking must be designed for full load.

CITY_SNOW_LOAD_PSF = {
    "montreal":        40,
    "laval":           40,
    "longueuil":       40,
    "terrebonne":      40,
    "gatineau":        40,
    "sherbrooke":      45,
    "trois-rivieres":  42,
    "trois-rivières":  42,
    "quebec city":     50,
    "ville de québec": 50,
    "lévis":           50,
    "levis":           50,
    "saguenay":        55,   # Saguenay–Lac-Saint-Jean — highest snow region
}

DEFAULT_SNOW_LOAD_PSF = 40   # Montreal/southern Quebec baseline

# ── Wind design speed by city (mph, NBCC 2020 / ASCE 7 equivalent) ────

CITY_WIND_MPH = {
    "montreal":        90,
    "laval":           90,
    "longueuil":       90,
    "terrebonne":      90,
    "gatineau":        90,
    "sherbrooke":      90,
    "trois-rivieres":  90,
    "trois-rivières":  90,
    "quebec city":     90,
    "ville de québec": 90,
    "lévis":           90,
    "levis":           90,
    "saguenay":        90,
}

DEFAULT_WIND_MPH = 90   # Standard inland Quebec; coastal/Gaspésie = 100 mph


class CECQuebecEngine(JurisdictionEngine):
    """Quebec / CEC jurisdiction engine for solar PV planset generation.

    Args:
        city:       Quebec city name for climate data and load lookups.
        utility:    Override utility name (default: Hydro-Québec).
        municipality: Alias for city (test-harness compatibility).
        province:   Accepted but ignored (always Quebec).
    """

    def __init__(self, city: str = "", utility: str = "",
                 municipality: str = "", province: str = ""):
        # Accept municipality as alias for city
        if not city and municipality:
            city = municipality
        self.city = city
        city_lower = city.strip().lower()

        # Quebec-specific identity
        self.wire_type = "RW90-XLPE"
        self.conduit_type = "EMT (exposed); Schedule-40 PVC (concealed)"
        self.electrical_code = "CEC 25th Edition"
        self.cmeq = True   # CMEQ supervision required for all Quebec electrical work

        # Utility — always Hydro-Québec in Quebec
        self.utility_name = utility if utility else "Hydro-Québec"
        self.utility = self.utility_name  # alias for compatibility

        # Design loads from NBCC 2020
        self.snow_load_psf = CITY_SNOW_LOAD_PSF.get(city_lower, DEFAULT_SNOW_LOAD_PSF)
        self.wind_speed_mph = CITY_WIND_MPH.get(city_lower, DEFAULT_WIND_MPH)

    # ── Identity ──────────────────────────────────────────────────────

    def get_code_name(self) -> str:
        return "CEC"

    def get_code_edition(self) -> str:
        return "CEC 25th Edition (CSA C22.1-2021) + CMEQ"

    # ── Climate / design conditions ───────────────────────────────────

    def get_design_temperatures(self, city: str = "") -> dict:
        key = (city or self.city).strip().lower()
        cold_c = CITY_DESIGN_TEMPS.get(key, DEFAULT_COLD_TEMP_C)
        return {
            "cold_c": cold_c,
            "hot_module_c": 65,
            "stc_c": 25,
        }

    def get_wind_snow_loads(self, city: str = "") -> dict:
        """Return design wind speed (mph) and snow load (PSF) per NBCC 2020."""
        key = (city or self.city).strip().lower()
        return {
            "wind_mph": CITY_WIND_MPH.get(key, DEFAULT_WIND_MPH),
            "snow_psf": CITY_SNOW_LOAD_PSF.get(key, DEFAULT_SNOW_LOAD_PSF),
        }

    # ── Electrical sizing ─────────────────────────────────────────────

    def calculate_ac_breaker(self, continuous_amps: float) -> int:
        """CEC Rule 4-004 / 64-100: breaker = continuous × 1.25, rounded to standard size."""
        min_breaker = continuous_amps * 1.25
        for size in STANDARD_BREAKER_SIZES:
            if size >= min_breaker:
                return size
        return STANDARD_BREAKER_SIZES[-1]

    def calculate_dc_conductor(self, isc: float, num_strings: int) -> str:
        """CEC Rule 14-100: DC conductor sized for Isc × 1.56 (1.25 × 1.25)."""
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

    # ── Interconnection ───────────────────────────────────────────────

    def check_interconnection_rule(
        self,
        pv_breaker_a: int,
        main_breaker_a: int,
        bus_rating_a: int,
    ) -> dict:
        """CEC Rule 64-112 / 64-404: 120% rule.

        PV breaker + main breaker <= 1.2 × bus rating.
        """
        max_allowed = int(bus_rating_a * 1.20)
        total = pv_breaker_a + main_breaker_a
        return {
            "passes": total <= max_allowed,
            "max_allowed": max_allowed,
            "method": "120% rule (CEC 64-112 / 64-404)",
        }

    # ── Labels / placards ─────────────────────────────────────────────

    def get_required_labels(self) -> List[dict]:
        """Return 14 ANSI Z535 labels required for Quebec solar installations."""
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

    # ── Fire setbacks ─────────────────────────────────────────────────

    def get_fire_setbacks(self, building_type: str) -> dict:
        """IFC 2021 Section 605.11 fire setbacks."""
        bt = building_type.strip().lower()
        if bt in ("residential", "single-family", "detached", "semi-detached"):
            return {"ridge_ft": 3, "eave_ft": 1.5, "pathway_ft": 3}
        elif bt in ("commercial", "industrial", "multi-family"):
            return {"ridge_ft": 6, "eave_ft": 3, "pathway_ft": 4}
        else:
            return {"ridge_ft": 3, "eave_ft": 1.5, "pathway_ft": 3}

    # ── Notes ─────────────────────────────────────────────────────────

    def get_general_notes(self) -> List[str]:
        """17 general notes for Quebec solar installations."""
        return [
            f"Notify {self.utility_name} prior to activating the PV system. Net metering application must be approved under the Autoproduction solaire program before grid connection.",
            "All electrical equipment shall be CSA-listed and installed per manufacturer's installation instructions.",
            "Installer shall verify all dimensions and conditions at the job site. Report discrepancies to designer before proceeding.",
            "All system components not specified herein shall be reviewed and approved by the manufacturer's representative.",
            "All work shall be performed by or under the direct supervision of a licensed electrician (CMEQ/AECQ, Quebec).",
            "Installer shall verify adequate roof access pathways per NBCC and AHJ requirements before beginning work.",
            "Installer shall verify structural integrity of roof rafters/trusses prior to installing the racking system.",
            f"Racking system shall be designed for snow load of {self.snow_load_psf} PSF and wind speed of {self.wind_speed_mph} mph per NBCC 2020.",
            'Lag screws used for racking attachment shall penetrate a minimum of 63 mm (2.5") into solid wood framing members.',
            "Roof access pathways (ridge, eave, and ventilation access) shall be maintained per IFC Section 605.11.",
            "All DC conductors shall be contained in conduit unless listed as PV wire or RW90-XLPE rated for sunlight exposure.",
            "All plumbing vents, stacks, and HVAC equipment shall maintain required clearances from the PV system.",
            "All junction boxes and wiring devices shall remain accessible without removing permanent construction per CEC Rule 12-3036.",
            "Racking system shall be bonded to the grounding electrode system per CEC Rule 64-104.",
            "PV module frames shall be bonded using WEEB (Washer/Lug Bonding) clip or equivalent listed bonding hardware.",
            "All inverters shall be CSA C22.2 No.107.1 listed and certified for grid-interactive (GTI) operation.",
            "A grounding electrode shall be provided per CEC Rule 64-104 and interconnected with the utility grounding system.",
        ]

    def get_electrical_notes(self) -> List[str]:
        """17 electrical notes for CEC Section 64."""
        return [
            "All conductors shall be copper unless otherwise noted. Aluminum conductors are not permitted for branch circuits.",
            "PV source/output circuit conductors shall be identified as RW90-XLPE, PV wire, or USE-2 rated for sunlight resistance and wet locations.",
            "All DC conductors shall be labeled/identified at every junction, pull box, and termination point per CEC Rule 64-214.",
            "Conductors in exterior exposed locations shall be run in EMT or Schedule-40 PVC conduit per CSA C22.2 No.211.2.",
            "All metallic raceways and equipment enclosures shall be bonded to the grounding electrode system.",
            "Conduit fill shall not exceed 40% of interior cross-sectional area per CEC Table 6.",
            "Inverter AC output grounding bond shall be maintained even when the inverter is removed from service.",
            "Ground fault protection (GFP) is required for all grounded DC PV systems per CEC Rule 64-218.",
            "GFCI protection and rapid shutdown shall be provided per CEC Rule 64-218(8) and AHJ requirements.",
            "PV module frame bonding shall use listed bonding hardware (WEEB clip or equivalent) per CEC Rule 64-104.",
            "Racking rail-to-rail bonding shall be maintained using listed splice connectors or WEEB bonding hardware.",
            f"Inverter shall be CSA C22.2 No.107.1 listed and approved for grid-interactive operation per {self.utility_name} standards.",
            f"Racking system shall be rated for design snow load of {self.snow_load_psf} PSF and wind speed of {self.wind_speed_mph} mph per NBCC 2020.",
            "A continuous grounding path shall be maintained from all module frames to the grounding electrode conductor.",
            "All bus bar splices shall be rated for the conditions of use per applicable CEC requirements.",
            "The PV backfed breaker shall be positioned at the opposite end of the bus bar from the main breaker per CEC Rule 64-404.",
            "120% Rule: Sum of PV breaker + main breaker ampere ratings shall not exceed 120% of bus bar rating per CEC Rule 64-404.",
        ]

    # ── Governing codes ───────────────────────────────────────────────

    def get_governing_codes(self) -> List[dict]:
        return [
            {
                "code": "CEC",
                "title": "Canadian Electrical Code, Part I",
                "edition": "CSA C22.1-2021 (25th Edition)",
            },
            {
                "code": "CCQ Ch. V",
                "title": "Code de construction du Québec — Chapitre V, Électricité",
                "edition": "2021",
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

    # ── Utility information ───────────────────────────────────────────

    def get_utility_info(self, city: str = "") -> dict:
        return {
            "name": "Hydro-Québec",
            "net_metering_max_kw": 20,
            "rate_per_kwh": 0.0738,
            "incentive_per_kw": 1000,
            "program_name": "Autoproduction solaire (2025)",
            "voltage": "240V split-phase",
            "frequency_hz": 60,
            "interconnection_standard": "CEC Section 64 / Hydro-Québec E.21-V",
        }

    # ── Licensing / authority ─────────────────────────────────────────

    def get_code_references(self) -> List[str]:
        """Return list of applicable code reference strings."""
        return [
            "CEC CSA C22.1-2021 (25th Edition)",
            "CCQ Chapitre V — Électricité (2021)",
            "NBCC 2020",
            "IFC 2021 Section 605.11",
            "CSA C22.2 No.107.1",
        ]

    def get_licensing_info(self) -> dict:
        """Return CMEQ/RBQ licensing requirements for Quebec."""
        return {
            "licensing_body": "RBQ / CMEQ",
            "licensing_body_full": "Régie du bâtiment du Québec (RBQ) / Corporation des maîtres électriciens du Québec (CMEQ)",
            "permit_required": "Permis de construction — RBQ",
            "inspector": "Inspecteur RBQ",
            "contractor_license": "Licence RBQ — sous-catégorie électricité",
            "master_electrician": "Maître électricien — CMEQ (licence maîtrise)",
        }

    def get_contractor_license_type(self) -> str:
        """Quebec contractor licensing."""
        return "RBQ / CMEQ"

    def get_licensing_body(self) -> str:
        return "RBQ / CMEQ"

    def get_licensing_body_full(self) -> str:
        return "Régie du bâtiment du Québec (RBQ) / Corporation des maîtres électriciens du Québec (CMEQ)"

    # ── Convenience summary dict (used by test harness) ──────────────

    def get_jurisdiction_data(self) -> dict:
        """Return a flat summary dict for quick validation and rendering."""
        return {
            "utility": self.utility_name,
            "wire_type": self.wire_type,
            "electrical_code": self.get_code_edition(),
            "conduit_type": self.conduit_type,
            "snow_load_psf": self.snow_load_psf,
            "wind_speed_mph": self.wind_speed_mph,
            "cmeq": self.cmeq,
            "licensing_body": "RBQ / CMEQ",
            "code_name": self.get_code_name(),
        }
