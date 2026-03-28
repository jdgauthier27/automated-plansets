"""
Abstract base class for jurisdiction-specific electrical code engines.

Each jurisdiction (CEC/Canada, NEC/USA, etc.) implements this interface
to provide code-specific calculations, conductor sizing, labels, notes,
and interconnection rules for solar PV planset generation.
"""

from abc import ABC, abstractmethod
from typing import Dict, List


class JurisdictionEngine(ABC):
    """Abstract jurisdiction engine that every code-specific backend must implement."""

    # ── Identity ──────────────────────────────────────────────────────

    @abstractmethod
    def get_code_name(self) -> str:
        """Return the short code identifier, e.g. 'CEC' or 'NEC'."""
        ...

    @abstractmethod
    def get_code_edition(self) -> str:
        """Return the edition string, e.g. 'CSA C22.1-2021'."""
        ...

    # ── Climate / design conditions ───────────────────────────────────

    @abstractmethod
    def get_design_temperatures(self, city: str) -> dict:
        """Return design temperatures for the given city.

        Returns:
            dict with keys:
                cold_c      - coldest expected ambient (for Voc correction)
                hot_module_c - hottest module cell temperature
                stc_c       - standard test conditions (always 25)
        """
        ...

    # ── Electrical sizing ─────────────────────────────────────────────

    @abstractmethod
    def calculate_ac_breaker(self, continuous_amps: float) -> int:
        """Size the AC overcurrent protection device.

        Returns the next standard breaker size (amps) after applying the
        continuous-load multiplier required by the governing code.
        """
        ...

    @abstractmethod
    def calculate_dc_conductor(self, isc: float, num_strings: int) -> str:
        """Size the DC PV source-circuit conductor.

        Args:
            isc:         module short-circuit current at STC
            num_strings: number of parallel strings

        Returns:
            Conductor designation string, e.g. '#10 AWG PV Wire'.
        """
        ...

    @abstractmethod
    def calculate_ac_conductor(self, continuous_amps: float) -> str:
        """Size the AC conductor from inverter to panel.

        Returns:
            Conductor designation string, e.g. '#10 AWG Cu'.
        """
        ...

    @abstractmethod
    def calculate_egc(self, breaker_amps: int) -> str:
        """Size the equipment grounding conductor for a given breaker rating.

        Returns:
            Conductor designation string, e.g. '#10 AWG Cu'.
        """
        ...

    # ── Interconnection ───────────────────────────────────────────────

    @abstractmethod
    def check_interconnection_rule(
        self,
        pv_breaker_a: int,
        main_breaker_a: int,
        bus_rating_a: int,
    ) -> dict:
        """Verify the supply-side / load-side interconnection rule.

        Returns:
            dict with keys:
                passes      - bool
                max_allowed - int (maximum sum allowed)
                method      - str describing the rule (e.g. '120% rule')
        """
        ...

    # ── Labels / placards ─────────────────────────────────────────────

    @abstractmethod
    def get_required_labels(self) -> List[dict]:
        """Return the list of code-required labels/placards.

        Each dict contains:
            level    - severity word (DANGER, WARNING, CAUTION, NOTICE)
            text     - label body text
            location - where on the installation the label goes
            color    - ANSI Z535 color (red, orange, yellow, blue)
        """
        ...

    # ── Fire setbacks ─────────────────────────────────────────────────

    @abstractmethod
    def get_fire_setbacks(self, building_type: str) -> dict:
        """Return fire-service access setback requirements.

        Args:
            building_type: e.g. 'residential', 'commercial'

        Returns:
            dict with keys ridge_ft, eave_ft, pathway_ft
        """
        ...

    # ── Notes ─────────────────────────────────────────────────────────

    @abstractmethod
    def get_general_notes(self) -> List[str]:
        """Return general construction / installation notes for the planset."""
        ...

    @abstractmethod
    def get_electrical_notes(self) -> List[str]:
        """Return electrical code notes for the planset."""
        ...

    # ── Building code ──────────────────────────────────────────────────

    def get_building_code(self) -> str:
        """Return the applicable building code abbreviation.

        Override in subclasses for jurisdiction-specific building codes.
        Default: 'IBC' (International Building Code) for NEC jurisdictions.
        """
        return "IBC"

    # ── Governing codes ───────────────────────────────────────────────

    @abstractmethod
    def get_governing_codes(self) -> List[dict]:
        """Return the list of governing codes applicable to this jurisdiction.

        Each dict contains:
            code    - short identifier (e.g. 'CEC')
            title   - full title
            edition - edition year/version
        """
        ...

    # ── Utility information ───────────────────────────────────────────

    @abstractmethod
    def get_utility_info(self, city: str = "") -> dict:
        """Return utility-specific information.

        Returns:
            dict with keys such as:
                name              - utility company name
                net_metering_max_kw - max system size for net metering
                rate_per_kwh      - $/kWh rate
                incentive_per_kw  - $/kW incentive (if any)
                program_name      - incentive program name
        """
        ...
