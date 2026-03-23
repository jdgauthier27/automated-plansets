"""
Quebec Electrical Calculator
=============================
CEC Section 64 (Canadian Electrical Code — Solar PV Systems) calculations
for Quebec residential solar installations.

Key rules implemented:
  - 64-060: Disconnect switches at inverter and main panel
  - 64-070: Equipment bonding/grounding (EGC per CSA 22.1)
  - 64-100: AC breaker = inverter continuous output × 1.25
  - 64-112: 120% rule (PV breaker + main breaker ≤ 120% bus rating)
  - 64-218: Rapid shutdown ≤30V in 30s outside array boundary

Hydro-Québec net metering:
  - Max single-phase: 20 kW
  - Rate D: $0.0738/kWh
  - Incentive: $1,000/kW (2025 program)
"""

import math
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ── NEC/CEC Conductor Tables ──────────────────────────────────────

# CEC Table 2 / NEC 310.16 equivalent — ampacity at 75°C copper
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

# EGC sizing per CEC 10-814 / NEC 250.122
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


@dataclass
class PanelModuleSpec:
    """Solar panel module electrical specifications."""
    name: str = "Generic 400W"
    wattage: float = 400
    voc: float = 49.0        # Open circuit voltage (STC)
    isc: float = 10.5        # Short circuit current (STC)
    vmp: float = 41.0        # Voltage at max power
    imp: float = 9.76        # Current at max power
    temp_coeff_voc: float = -0.0027  # %/°C typical
    temp_coeff_isc: float = 0.0005   # %/°C typical


@dataclass
class InverterSpec:
    """Inverter specifications."""
    name: str = "Grid-Tied Inverter"
    rated_ac_watts: float = 5000
    rated_ac_volts: float = 240
    max_dc_volts: float = 600
    mppt_min_volts: float = 100
    mppt_max_volts: float = 500
    max_input_current: float = 15
    num_mppt: int = 2
    efficiency: float = 0.97


@dataclass
class ElectricalDesign:
    """Complete electrical design result."""
    # System
    num_panels: int = 0
    num_strings: int = 1
    panels_per_string: int = 0
    dc_system_kw: float = 0.0

    # DC side
    string_voc: float = 0.0
    string_voc_cold: float = 0.0  # temperature corrected
    string_isc: float = 0.0
    dc_conductor: str = "#10 AWG PV Wire"
    dc_disconnect_amps: int = 30

    # AC side
    inverter_continuous_amps: float = 0.0
    ac_breaker_amps: int = 20
    ac_conductor: str = "#10 AWG Cu"
    ac_conductor_type: str = "THWN-2"

    # Grounding
    egc: str = "#10 AWG Cu"
    bond_conductor: str = "#6 AWG Cu"

    # 120% rule
    main_breaker_amps: int = 200
    bus_rating_amps: int = 200
    rule_120_max: int = 240
    rule_120_pass: bool = True

    # Rapid shutdown
    rapid_shutdown_required: bool = True

    # Hydro-Québec
    hq_max_kw: float = 20.0
    hq_compliant: bool = True
    hq_incentive: float = 0.0
    hq_rate_d: float = 0.0738

    # Warnings
    warnings: List[str] = field(default_factory=list)


class QuebecElectricalCalculator:
    """
    Performs CEC Section 64 electrical calculations for Quebec solar PV systems.

    Usage:
        calc = QuebecElectricalCalculator()
        design = calc.calculate(
            num_panels=13,
            panel=PanelModuleSpec(wattage=455, voc=39.90, isc=14.45),
            main_breaker_amps=200,
        )
    """

    # Quebec design temperatures
    LOW_TEMP_C = -30   # coldest expected (for Voc correction)
    HIGH_TEMP_C = 45   # hottest expected

    def __init__(self):
        pass

    def calculate(
        self,
        num_panels: int,
        panel: Optional[PanelModuleSpec] = None,
        inverter: Optional[InverterSpec] = None,
        main_breaker_amps: int = 200,
        bus_rating_amps: int = 200,
    ) -> ElectricalDesign:
        """Run all electrical calculations and return the design."""
        if panel is None:
            panel = PanelModuleSpec()
        if inverter is None:
            # Auto-size inverter to match array
            ac_watts = num_panels * panel.wattage
            inverter = InverterSpec(rated_ac_watts=ac_watts)

        design = ElectricalDesign()
        design.num_panels = num_panels
        design.dc_system_kw = round(num_panels * panel.wattage / 1000, 2)

        # String sizing
        design.panels_per_string, design.num_strings = self._size_strings(
            num_panels, panel, inverter
        )

        # DC calculations
        design.string_voc = round(design.panels_per_string * panel.voc, 1)
        design.string_voc_cold = round(
            design.panels_per_string * panel.voc *
            (1 + panel.temp_coeff_voc * (self.LOW_TEMP_C - 25)),
            1
        )
        design.string_isc = round(panel.isc, 2)

        # Check DC voltage limits
        if design.string_voc_cold > inverter.max_dc_volts:
            design.warnings.append(
                f"String Voc at {self.LOW_TEMP_C}°C ({design.string_voc_cold}V) "
                f"exceeds inverter max DC input ({inverter.max_dc_volts}V)"
            )

        # DC disconnect
        design.dc_disconnect_amps = self._dc_disconnect_size(panel, design.num_strings)
        design.dc_conductor = "#10 AWG PV Wire"

        # AC calculations (CEC 64-100)
        design.inverter_continuous_amps = round(
            inverter.rated_ac_watts / inverter.rated_ac_volts, 1
        )
        design.ac_breaker_amps = self._ac_breaker_size(
            inverter.rated_ac_watts, inverter.rated_ac_volts
        )
        design.ac_conductor = self._conductor_for_amps(design.ac_breaker_amps)
        design.egc = self._egc_for_amps(design.ac_breaker_amps)

        # 120% rule (CEC 64-112)
        design.main_breaker_amps = main_breaker_amps
        design.bus_rating_amps = bus_rating_amps
        design.rule_120_max = int(bus_rating_amps * 1.20)
        design.rule_120_pass = (
            design.ac_breaker_amps + main_breaker_amps <= design.rule_120_max
        )
        if not design.rule_120_pass:
            design.warnings.append(
                f"120% rule FAIL: {design.ac_breaker_amps}A + {main_breaker_amps}A = "
                f"{design.ac_breaker_amps + main_breaker_amps}A > {design.rule_120_max}A"
            )

        # Hydro-Québec
        design.hq_max_kw = 20.0
        design.hq_compliant = design.dc_system_kw <= design.hq_max_kw
        design.hq_incentive = round(design.dc_system_kw * 1000, 0)  # $1,000/kW
        if not design.hq_compliant:
            design.warnings.append(
                f"System size {design.dc_system_kw} kW exceeds Hydro-Québec "
                f"single-phase net metering limit of {design.hq_max_kw} kW"
            )

        return design

    def _size_strings(
        self, num_panels: int, panel: PanelModuleSpec, inverter: InverterSpec
    ) -> Tuple[int, int]:
        """Determine panels per string and number of strings."""
        # Temperature-corrected voltages
        voc_cold = panel.voc * (1 + panel.temp_coeff_voc * (self.LOW_TEMP_C - 25))
        vmp_cold = panel.vmp * (1 + panel.temp_coeff_voc * (self.LOW_TEMP_C - 25))

        # Max panels per string (limited by inverter max DC voltage)
        max_per_string = int(inverter.max_dc_volts / voc_cold) if voc_cold > 0 else 20

        # Min panels per string (must exceed MPPT minimum)
        min_per_string = math.ceil(inverter.mppt_min_volts / vmp_cold) if vmp_cold > 0 else 1

        # Try to fit all in one string
        if num_panels <= max_per_string and num_panels >= min_per_string:
            return num_panels, 1

        # Otherwise split into multiple strings
        panels_per_string = max_per_string
        while panels_per_string >= min_per_string:
            if num_panels % panels_per_string == 0:
                return panels_per_string, num_panels // panels_per_string
            panels_per_string -= 1

        # Fallback: use max and have remainder
        panels_per_string = min(max_per_string, num_panels)
        num_strings = math.ceil(num_panels / panels_per_string)
        return panels_per_string, num_strings

    @staticmethod
    def _ac_breaker_size(inverter_watts: float, voltage: float = 240) -> int:
        """CEC 64-100: breaker = continuous amps × 1.25, rounded up to standard size."""
        continuous = inverter_watts / voltage
        min_breaker = continuous * 1.25
        # Standard breaker sizes
        standard = [15, 20, 25, 30, 35, 40, 50, 60, 70, 80, 100, 125, 150, 200]
        for size in standard:
            if size >= min_breaker:
                return size
        return standard[-1]

    @staticmethod
    def _dc_disconnect_size(panel: PanelModuleSpec, num_strings: int) -> int:
        """Size DC disconnect switch."""
        max_current = panel.isc * num_strings * 1.25
        standard = [15, 20, 30, 40, 60, 100]
        for size in standard:
            if size >= max_current:
                return size
        return standard[-1]

    @staticmethod
    def _conductor_for_amps(amps: int) -> str:
        """Look up conductor from CEC Table 2 / NEC 310.16."""
        for ampacity, conductor in CONDUCTOR_AMPACITY_75C:
            if ampacity >= amps:
                return conductor
        return CONDUCTOR_AMPACITY_75C[-1][1]

    @staticmethod
    def _egc_for_amps(amps: int) -> str:
        """Look up EGC from CEC 10-814 / NEC 250.122."""
        for ampacity, conductor in EGC_TABLE:
            if ampacity >= amps:
                return conductor
        return EGC_TABLE[-1][1]


# ── Labels / Placards Generator ────────────────────────────────────

@dataclass
class LabelSpec:
    """A required label/placard per CEC Section 64."""
    location: str
    text: str
    code_ref: str
    color: str = "red"  # "red", "orange", "blue"
    mandatory: bool = True


def get_required_labels(design: ElectricalDesign) -> List[LabelSpec]:
    """Return all CEC-required labels for the installation."""
    return [
        LabelSpec(
            location="DC Disconnect",
            text=(
                f"CAUTION: SOLAR PV SYSTEM\n"
                f"DC DISCONNECT\n"
                f"Voc = {design.string_voc:.0f}V DC\n"
                f"DO NOT OPEN UNDER LOAD"
            ),
            code_ref="CEC 64-060",
            color="red",
        ),
        LabelSpec(
            location="AC Disconnect",
            text=(
                f"CAUTION: SOLAR PV SYSTEM\n"
                f"AC DISCONNECT\n"
                f"{design.ac_breaker_amps}A / 240V\n"
                f"SERVICE DISCONNECT"
            ),
            code_ref="CEC 64-060",
            color="red",
        ),
        LabelSpec(
            location="Main Panel",
            text=(
                f"WARNING: DUAL POWER SOURCE\n"
                f"This panel is fed by solar PV\n"
                f"({design.dc_system_kw} kW) and utility power.\n"
                f"PV Breaker: {design.ac_breaker_amps}A"
            ),
            code_ref="CEC 64-060(4)",
            color="orange",
        ),
        LabelSpec(
            location="Inverter",
            text=(
                f"SOLAR PV INVERTER\n"
                f"Rated: {design.dc_system_kw} kW DC / "
                f"{design.dc_system_kw * 0.96:.1f} kW AC\n"
                f"Rapid Shutdown Equipped"
            ),
            code_ref="CEC 64-218",
            color="blue",
        ),
        LabelSpec(
            location="Utility Meter",
            text=(
                f"BIDIRECTIONAL METER\n"
                f"Net Metering — Hydro-Québec\n"
                f"DO NOT REMOVE"
            ),
            code_ref="HQ Net Metering Requirements",
            color="blue",
        ),
        LabelSpec(
            location="Rapid Shutdown Initiator",
            text=(
                f"RAPID SHUTDOWN SWITCH\n"
                f"PV System Shutdown\n"
                f"Activate in Emergency\n"
                f"≤30V within 30 seconds"
            ),
            code_ref="CEC 64-218",
            color="red",
        ),
    ]
