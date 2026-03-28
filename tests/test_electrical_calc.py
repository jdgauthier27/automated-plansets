"""
Test: Centralized Electrical Calculations — Escalon Dr Reference Validation
============================================================================
Creates a SolarDesign for the Escalon Dr reference case (30 panels, Mission
Solar 395W, Enphase IQ8+, 225A MSP, 200A main) and verifies that
compute_electrical() produces values matching the reference data from E-602.

Reference: /home/user/workspace/reference_electrical_data.md
"""

import sys
import os
import math

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.models.solar_design import (
    SolarDesign,
    PanelPlacement,
    RoofSegment,
    ModuleSpec,
    InverterSpec,
    RackingSpec,
    AttachmentSpec,
    CombinerSpec,
    EquipmentSpec,
    ElectricalDesign,
    ConductorRun,
)
from engine.electrical_calc import compute_electrical


def build_escalon_dr_design() -> SolarDesign:
    """Build a SolarDesign for the Escalon Dr reference case."""

    # 30 panels: 16 on face #1 (segment 0), 14 on face #2 (segment 1)
    panels = []
    for i in range(16):
        panels.append(PanelPlacement(
            panel_id=i,
            lat=34.1726 + i * 0.00001,
            lng=-118.5210 + i * 0.00001,
            segment_id=0,
            orientation="portrait",
        ))
    for i in range(14):
        panels.append(PanelPlacement(
            panel_id=16 + i,
            lat=34.1728 + i * 0.00001,
            lng=-118.5208 + i * 0.00001,
            segment_id=1,
            orientation="portrait",
        ))

    roof_segments = [
        RoofSegment(segment_id=0, pitch_degrees=18.0, azimuth_degrees=99.0,
                    material="Asphalt", rafter_size="2x9", rafter_spacing_inches=16.0),
        RoofSegment(segment_id=1, pitch_degrees=18.0, azimuth_degrees=279.0,
                    material="Asphalt", rafter_size="2x9", rafter_spacing_inches=16.0),
    ]

    equipment = EquipmentSpec(
        module=ModuleSpec(
            manufacturer="Mission Solar",
            model="MSE395SX9R",
            wattage=395,
            width_inches=41.50,
            height_inches=75.08,
            weight_lbs=48.5,
            voc=48.2,
            isc=11.57,
            vmp=40.3,
            imp=10.82,
            temp_coeff_voc=-0.29,
        ),
        inverter=InverterSpec(
            manufacturer="Enphase",
            model="IQ8PLUS-72-2-US",
            continuous_va=290,
            max_ac_current=1.21,
            voltage=240,
            type="microinverter",
        ),
        racking=RackingSpec(
            manufacturer="IronRidge",
            model="XR100",
            rail_length_inches=168.0,
            rail_count=16,
        ),
        attachment=AttachmentSpec(
            manufacturer="IronRidge",
            model="FlashFoot 2",
            count=66,
            spacing_inches=48.0,
        ),
        combiner=CombinerSpec(
            manufacturer="Enphase",
            model="IQ Combiner 5C",
            part_number="X-IQ-AM1-240-5C",
        ),
    )

    electrical = ElectricalDesign(
        msp_bus_rating_amps=225,
        msp_main_breaker_amps=200,
        service_voltage=240,
    )

    design = SolarDesign(
        address="17001 Escalon Dr, Encino, CA 91436",
        city="Encino",
        state="CA",
        zip_code="91436",
        lat=34.1727,
        lng=-118.5209,
        ahj="City of Los Angeles",
        utility="LADWP",
        roof_segments=roof_segments,
        panels=panels,
        equipment=equipment,
        electrical=electrical,
    )

    return design


def test_system_sizing():
    """Verify DC kW, AC kW, and total panel count."""
    design = build_escalon_dr_design()
    compute_electrical(design)
    e = design.electrical

    assert e.total_panels == 30, f"Expected 30 panels, got {e.total_panels}"
    assert e.dc_kw == 11.85, f"Expected 11.85 kW DC, got {e.dc_kw}"
    assert e.ac_kw == 8.70, f"Expected 8.70 kW AC, got {e.ac_kw}"


def test_branch_circuits():
    """Verify branch circuit assignment: 3 branches of 10."""
    design = build_escalon_dr_design()
    compute_electrical(design)
    e = design.electrical

    assert e.num_branches == 3, f"Expected 3 branches, got {e.num_branches}"
    assert e.panels_per_branch == [10, 10, 10], (
        f"Expected [10, 10, 10], got {e.panels_per_branch}"
    )
    assert e.branch_breaker_amps == 20, (
        f"Expected 20A branch breaker, got {e.branch_breaker_amps}"
    )

    # Verify all panels have branch_id assigned
    for panel in design.panels:
        assert panel.branch_id in (1, 2, 3), (
            f"Panel {panel.panel_id} has invalid branch_id {panel.branch_id}"
        )


def test_ocpd():
    """Verify overcurrent protection calculations."""
    design = build_escalon_dr_design()
    compute_electrical(design)
    e = design.electrical

    # Total continuous current = 3 branches × 12.1A = 36.3A
    assert abs(e.total_continuous_current - 36.3) < 0.1, (
        f"Expected ~36.3A continuous, got {e.total_continuous_current}"
    )
    # Max current = 36.3 × 1.25 = 45.375A → round to 45.4A
    assert abs(e.total_max_current - 45.4) < 0.2, (
        f"Expected ~45.4A max, got {e.total_max_current}"
    )
    # Backfeed breaker: next standard OCPD above 45.4A = 50A
    assert e.backfeed_breaker_amps == 50, (
        f"Expected 50A backfeed breaker, got {e.backfeed_breaker_amps}"
    )


def test_120_pct_rule():
    """Verify 120% rule calculation per NEC 705.12(B)(3)(2)."""
    design = build_escalon_dr_design()
    compute_electrical(design)
    e = design.electrical

    assert e.passes_120_pct_rule is True, "120% rule should PASS"
    assert "200A + 50A = 250A" in e.rule_120_calc, (
        f"Expected '200A + 50A = 250A' in calc, got: {e.rule_120_calc}"
    )
    assert "270A" in e.rule_120_calc, (
        f"Expected '270A' (225×1.2) in calc, got: {e.rule_120_calc}"
    )


def test_ac_disconnect():
    """Verify AC disconnect sizing."""
    design = build_escalon_dr_design()
    compute_electrical(design)
    e = design.electrical

    assert e.ac_disconnect_amps == 60, (
        f"Expected 60A AC disconnect, got {e.ac_disconnect_amps}"
    )
    assert e.service_voltage == 240, (
        f"Expected 240V service, got {e.service_voltage}"
    )


def test_conductor_run_count():
    """Verify 4 conductor runs are created."""
    design = build_escalon_dr_design()
    compute_electrical(design)
    e = design.electrical

    assert len(e.conductor_runs) == 4, (
        f"Expected 4 conductor runs, got {len(e.conductor_runs)}"
    )


def test_conductor_run_1_array_to_jbox():
    """Verify Run 1: Array → Junction Box matches reference."""
    design = build_escalon_dr_design()
    compute_electrical(design)
    run = design.electrical.conductor_runs[0]

    assert run.id == 1
    assert run.typical_count == 3
    assert run.initial_location == "Array"
    assert run.final_location == "Junction Box"
    assert run.conductor_size == "12 AWG"
    assert "Trunk Cable" in run.conductor_type
    assert run.egc_size == "6 AWG"
    assert "Bare Copper" in run.egc_type
    assert abs(run.temp_corr_factor - 0.71) < 0.01, (
        f"Expected temp corr 0.71, got {run.temp_corr_factor}"
    )
    assert run.temp_basis == "57°C"
    assert abs(run.continuous_current - 12.1) < 0.1, (
        f"Expected 12.1A continuous, got {run.continuous_current}"
    )
    assert abs(run.max_current - 15.1) < 0.2, (
        f"Expected ~15.1A max, got {run.max_current}"
    )
    assert run.length_ft == 26.0
    # Voltage drop should be ~0.30%
    assert abs(run.voltage_drop_pct - 0.30) < 0.05, (
        f"Expected ~0.30% voltage drop, got {run.voltage_drop_pct}"
    )


def test_conductor_run_2_jbox_to_combiner():
    """Verify Run 2: Junction Box → IQ Combiner Box matches reference."""
    design = build_escalon_dr_design()
    compute_electrical(design)
    run = design.electrical.conductor_runs[1]

    assert run.id == 2
    assert run.typical_count == 1
    assert run.initial_location == "Junction Box"
    assert run.final_location == "IQ Combiner Box"
    assert run.conductor_size == "10 AWG"
    assert "THWN-2" in run.conductor_type
    assert run.parallel_circuits == 3
    assert run.current_carrying_conductors == 6
    assert run.ocpd_amps == 20
    assert run.egc_size == "8 AWG"
    assert abs(run.temp_corr_factor - 0.96) < 0.01
    assert run.temp_basis == "35°C"
    assert abs(run.continuous_current - 12.1) < 0.1
    assert abs(run.max_current - 15.1) < 0.2
    assert run.base_ampacity == 35.0
    assert abs(run.derated_ampacity - 33.60) < 0.01
    assert run.length_ft == 25.0
    # Conduit fill should be ~26.72%
    assert run.conduit_fill_pct is not None
    assert abs(run.conduit_fill_pct - 26.72) < 1.0, (
        f"Expected ~26.72% conduit fill, got {run.conduit_fill_pct}"
    )
    # Voltage drop ~0.31%
    assert abs(run.voltage_drop_pct - 0.31) < 0.05, (
        f"Expected ~0.31% voltage drop, got {run.voltage_drop_pct}"
    )


def test_conductor_run_3_combiner_to_acd():
    """Verify Run 3: IQ Combiner Box → ACD matches reference."""
    design = build_escalon_dr_design()
    compute_electrical(design)
    run = design.electrical.conductor_runs[2]

    assert run.id == 3
    assert run.initial_location == "IQ Combiner Box"
    assert run.final_location == "ACD"
    assert run.conductor_size == "8 AWG"
    assert "THWN-2" in run.conductor_type
    assert run.parallel_circuits == 1
    assert run.current_carrying_conductors == 3
    assert run.ocpd_amps is None  # protected by backfeed breaker
    assert run.egc_size == "8 AWG"
    assert abs(run.temp_corr_factor - 0.96) < 0.01
    assert abs(run.continuous_current - 36.3) < 0.1
    assert abs(run.max_current - 45.4) < 0.2
    assert run.base_ampacity == 50.0
    assert abs(run.derated_ampacity - 48.00) < 0.01
    assert run.length_ft == 5.0
    # Conduit fill ~26.73%
    assert run.conduit_fill_pct is not None
    assert abs(run.conduit_fill_pct - 26.73) < 1.0, (
        f"Expected ~26.73% conduit fill, got {run.conduit_fill_pct}"
    )
    # Voltage drop ~0.11%
    assert abs(run.voltage_drop_pct - 0.11) < 0.05, (
        f"Expected ~0.11% voltage drop, got {run.voltage_drop_pct}"
    )


def test_conductor_run_4_acd_to_msp():
    """Verify Run 4: ACD → MSP matches reference."""
    design = build_escalon_dr_design()
    compute_electrical(design)
    run = design.electrical.conductor_runs[3]

    assert run.id == 4
    assert run.initial_location == "ACD"
    assert run.final_location == "MSP"
    assert run.conductor_size == "8 AWG"
    assert "THWN-2" in run.conductor_type
    assert run.ocpd_amps == 50  # backfeed breaker
    assert abs(run.continuous_current - 36.3) < 0.1
    assert abs(run.max_current - 45.4) < 0.2
    assert run.base_ampacity == 50.0
    assert abs(run.derated_ampacity - 48.00) < 0.01
    assert run.length_ft == 5.0
    assert abs(run.voltage_drop_pct - 0.11) < 0.05


def test_all_voltage_drops_under_2_pct():
    """All voltage drops must be under 2% per CEC."""
    design = build_escalon_dr_design()
    compute_electrical(design)

    for run in design.electrical.conductor_runs:
        assert run.voltage_drop_pct < 2.0, (
            f"Run {run.id} ({run.initial_location} → {run.final_location}) "
            f"voltage drop {run.voltage_drop_pct}% exceeds 2% CEC limit"
        )


def test_serialization_roundtrip():
    """Verify SolarDesign with electrical data survives to_dict/from_dict."""
    design = build_escalon_dr_design()
    compute_electrical(design)

    d = design.to_dict()
    restored = SolarDesign.from_dict(d)

    assert restored.electrical.dc_kw == 11.85
    assert restored.electrical.ac_kw == 8.70
    assert restored.electrical.num_branches == 3
    assert restored.electrical.backfeed_breaker_amps == 50
    assert restored.electrical.passes_120_pct_rule is True
    assert len(restored.electrical.conductor_runs) == 4
    assert restored.electrical.conductor_runs[0].conductor_size == "12 AWG"
    assert restored.electrical.conductor_runs[1].base_ampacity == 35.0


def run_all_tests():
    """Run all tests and print results."""
    tests = [
        ("System Sizing", test_system_sizing),
        ("Branch Circuits", test_branch_circuits),
        ("OCPD", test_ocpd),
        ("120% Rule", test_120_pct_rule),
        ("AC Disconnect", test_ac_disconnect),
        ("Conductor Run Count", test_conductor_run_count),
        ("Run 1: Array → JBox", test_conductor_run_1_array_to_jbox),
        ("Run 2: JBox → Combiner", test_conductor_run_2_jbox_to_combiner),
        ("Run 3: Combiner → ACD", test_conductor_run_3_combiner_to_acd),
        ("Run 4: ACD → MSP", test_conductor_run_4_acd_to_msp),
        ("Voltage Drop < 2%", test_all_voltage_drops_under_2_pct),
        ("Serialization Roundtrip", test_serialization_roundtrip),
    ]

    passed = 0
    failed = 0
    errors = []

    for name, test_fn in tests:
        try:
            test_fn()
            passed += 1
            print(f"  [PASS] {name}")
        except AssertionError as e:
            failed += 1
            errors.append((name, str(e)))
            print(f"  [FAIL] {name}: {e}")
        except Exception as e:
            failed += 1
            errors.append((name, f"ERROR: {e}"))
            print(f"  [ERR]  {name}: {e}")

    print(f"\nResults: {passed}/{passed + failed} passed")

    if errors:
        print("\nFailures:")
        for name, msg in errors:
            print(f"  - {name}: {msg}")

    return failed == 0


if __name__ == "__main__":
    print("Escalon Dr Reference — Electrical Calculation Validation")
    print("=" * 60)
    success = run_all_tests()
    sys.exit(0 if success else 1)
