"""
NEC Base Engine (Skeleton)
==========================
National Electrical Code (USA) jurisdiction engine.
Implements NEC 2023 rules as a proof of multi-jurisdiction architecture.

This is a skeleton for Phase 6 — it provides the correct code references
and basic calculations but is NOT production-ready for US permits.
"""

import math
from typing import Dict, List

try:
    from jurisdiction.base import JurisdictionEngine
except ImportError:
    # Fallback if base not yet built by agent
    class JurisdictionEngine:
        pass


# NEC 240.6(A) standard breaker sizes
NEC_BREAKER_SIZES = [
    15,
    20,
    25,
    30,
    35,
    40,
    45,
    50,
    60,
    70,
    80,
    90,
    100,
    110,
    125,
    150,
    175,
    200,
    225,
    250,
    300,
    350,
    400,
]

# NEC Table 310.16 — Ampacity at 75°C copper THWN-2
NEC_CONDUCTOR_75C = [
    (15, "#14 AWG Cu"),
    (20, "#12 AWG Cu"),
    (30, "#10 AWG Cu"),
    (40, "#8 AWG Cu"),
    (55, "#6 AWG Cu"),
    (65, "#4 AWG Cu"),
    (85, "#3 AWG Cu"),
    (95, "#2 AWG Cu"),
    (110, "#1 AWG Cu"),
    (125, "#1/0 AWG Cu"),
    (145, "#2/0 AWG Cu"),
    (165, "#3/0 AWG Cu"),
    (195, "#4/0 AWG Cu"),
    (230, "250 kcmil Cu"),
    (255, "300 kcmil Cu"),
    (285, "350 kcmil Cu"),
    (310, "400 kcmil Cu"),
    (335, "500 kcmil Cu"),
]

# NEC Table 250.122 — EGC sizing by OCPD
NEC_EGC_TABLE = [
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
    (1000, "#2/0 AWG Cu"),
    (1200, "#3/0 AWG Cu"),
]


class NECBaseEngine(JurisdictionEngine):
    """NEC 2023 base jurisdiction engine for US installations."""

    def get_code_name(self) -> str:
        return "NEC (NFPA 70)"

    def get_code_edition(self) -> str:
        return "NEC 2023 (NFPA 70-2023)"

    def get_design_temperatures(self, city: str = "") -> Dict:
        # NEC uses ASHRAE data — these are example defaults
        defaults = {
            "phoenix": {"cold_c": 2, "hot_module_c": 75, "stc_c": 25},
            "los angeles": {"cold_c": 5, "hot_module_c": 70, "stc_c": 25},
            "denver": {"cold_c": -20, "hot_module_c": 65, "stc_c": 25},
            "new york": {"cold_c": -15, "hot_module_c": 65, "stc_c": 25},
        }
        city_lower = city.lower() if city else ""
        for key, temps in defaults.items():
            if key in city_lower:
                return temps
        return {"cold_c": -10, "hot_module_c": 70, "stc_c": 25}

    def calculate_ac_breaker(self, continuous_amps: float) -> int:
        """NEC 690.8(A): Continuous × 1.25, rounded to standard size."""
        raw = continuous_amps * 1.25
        for size in NEC_BREAKER_SIZES:
            if size >= raw:
                return size
        return NEC_BREAKER_SIZES[-1]

    def calculate_dc_conductor(self, isc: float, num_strings: int = 1) -> str:
        """NEC 690.8(A): Isc × 1.25 × 1.25 = Isc × 1.56."""
        amps = isc * 1.56 * num_strings
        for rating, wire in NEC_CONDUCTOR_75C:
            if rating >= amps:
                return wire
        return NEC_CONDUCTOR_75C[-1][1]

    def calculate_ac_conductor(self, continuous_amps: float) -> str:
        amps = continuous_amps * 1.25
        for rating, wire in NEC_CONDUCTOR_75C:
            if rating >= amps:
                return wire
        return NEC_CONDUCTOR_75C[-1][1]

    def calculate_egc(self, breaker_amps: int) -> str:
        for rating, wire in NEC_EGC_TABLE:
            if rating >= breaker_amps:
                return wire
        return NEC_EGC_TABLE[-1][1]

    def check_interconnection_rule(self, pv_breaker_a: int, main_breaker_a: int, bus_rating_a: int) -> Dict:
        """NEC 705.12(B)(2): 120% rule."""
        max_allowed = int(bus_rating_a * 1.2)
        total = pv_breaker_a + main_breaker_a
        passes = total <= max_allowed
        method = "load_side" if passes else "supply_side"
        return {"passes": passes, "max_allowed": max_allowed, "total": total, "method": method}

    def get_required_labels(self) -> List[Dict]:
        return [
            {
                "level": "DANGER",
                "text": "SOLAR ELECTRIC SYSTEM — DO NOT TOUCH",
                "location": "DC combiner",
                "color": "#cc0000",
            },
            {
                "level": "DANGER",
                "text": "DUAL POWER SOURCE — DISCONNECT BOTH BEFORE SERVICING",
                "location": "Main panel",
                "color": "#cc0000",
            },
            {
                "level": "WARNING",
                "text": "SOLAR ELECTRIC SYSTEM IS INTERCONNECTED WITH THIS PANEL",
                "location": "Utility meter",
                "color": "#ff8800",
            },
            {"level": "WARNING", "text": "PHOTOVOLTAIC POWER SOURCE", "location": "Inverter", "color": "#ff8800"},
            {
                "level": "CAUTION",
                "text": "SOLAR ARRAY — PRODUCES VOLTAGE IN SUNLIGHT",
                "location": "Array",
                "color": "#ffcc00",
            },
            {
                "level": "NOTICE",
                "text": "RAPID SHUTDOWN SWITCH",
                "location": "RSD initiation point",
                "color": "#0066cc",
            },
        ]

    def get_fire_setbacks(self, building_type: str = "residential") -> Dict:
        """IFC 2021 fire setbacks."""
        if building_type == "residential":
            return {"ridge_ft": 3.0, "eave_ft": 1.5, "pathway_ft": 3.0}
        return {"ridge_ft": 3.0, "eave_ft": 1.5, "pathway_ft": 4.0}

    def get_general_notes(self) -> List[str]:
        return [
            "1. All work shall comply with NEC 2023 (NFPA 70), IFC 2021, and local AHJ requirements.",
            "2. Contractor shall obtain all required permits before commencing work.",
            "3. All equipment shall be listed and labeled per NEC 110.2.",
            "4. PV modules shall be installed per manufacturer instructions and NEC 690.",
            "5. Rapid shutdown shall comply with NEC 690.12 (2017/2020/2023 as adopted).",
            "6. All conductors shall be supported and secured per NEC 338 and 690.",
            "7. Equipment grounding per NEC 690.43 and 250.134.",
            "8. System grounding per NEC 690.41.",
            "9. Arc-fault protection per NEC 690.11 where required by AHJ.",
            "10. Disconnecting means per NEC 690.13 and 690.15.",
        ]

    def get_electrical_notes(self) -> List[str]:
        return [
            "1. Conductor ampacity per NEC Table 310.16 at 75°C copper.",
            "2. AC breaker sizing per NEC 690.8(A): continuous current × 1.25.",
            "3. Overcurrent protection per NEC 240 and 690.9.",
            "4. Interconnection per NEC 705.12 (120% rule or supply-side).",
            "5. DC conductor sizing per NEC 690.8(A): Isc × 1.56.",
            "6. Equipment grounding conductor per NEC Table 250.122.",
            "7. All PV source circuits shall be protected per NEC 690.9(A).",
            "8. Voltage drop shall not exceed 3% per NEC 210.19(A) recommendation.",
        ]

    def get_governing_codes(self) -> List[Dict]:
        return [
            {"code": "NEC", "title": "National Electrical Code", "edition": "NFPA 70-2023"},
            {"code": "IFC", "title": "International Fire Code", "edition": "2021"},
            {"code": "IBC", "title": "International Building Code", "edition": "2021"},
            {"code": "UL 1741", "title": "Inverters, Converters, Controllers", "edition": "SA"},
            {"code": "UL 2703", "title": "Mounting Systems, Bonding", "edition": "2023"},
            {"code": "IEEE 1547", "title": "Interconnection Standard", "edition": "2018"},
        ]

    def get_utility_info(self, city: str = "") -> Dict:
        return {
            "name": "Local Utility",
            "net_metering_max_kw": 25.0,
            "rate_per_kwh": 0.12,
            "incentive_per_kw": 0,
            "interconnection_standard": "IEEE 1547 / State NEM",
        }

    def get_contractor_license_type(self) -> str:
        return "Licensed Electrical Contractor"

    def get_licensing_body(self) -> str:
        return "State License Board"

    def get_licensing_body_full(self) -> str:
        return "State License Board"
