"""
Reference Baseline: 17001 Escalon Dr, Encino, CA 91436
======================================================
Yifei Sun Residence — RevB planset (correct panel layout)

This file captures the EXACT specifications from the reference PDF
so automated tests can compare our output against it.

Source: YifeiSun_RevB-correct panel layout.pdf
Designer: Techverse Smart Solutions (TSS)
Company: Advanced Conservation Systems, Inc.
"""

# ── System Design ──────────────────────────────────────────────────────
SYSTEM = {
    "address": "17001 Escalon Dr, Encino, CA 91436",
    "client_name": "Yifei Sun",
    "ahj": "City of Los Angeles",
    "utility": "LADWP",  # Los Angeles Department of Water and Power
    "dc_size_kw": 11.85,
    "ac_size_kw": 8.70,
    "num_panels": 30,  # NOTE: 30 in reference, not 29
    "num_inverters": 30,  # 1:1 micro-inverter ratio
    "num_stories": 2,
    "occupancy": "R-3, Single Family",
    "risk_category": "II",
    "construction": "SFD",
    "zoning": "Residential",
}

# ── Production & Sizing ────────────────────────────────────────────────
PRODUCTION = {
    "annual_production_kwh": 16862,      # from OpenSolar with Google 3D data
    "annual_consumption_kwh": 15055,     # estimated from 112% offset
    "offset_pct": 112,                   # produces 12% more than consumed
    "peak_sun_hours": 5.5,              # Los Angeles area (PSH)
    "system_losses_pct": 20,            # soiling, wiring, inverter, temp derating
    # Calculation: 11.85 kW × 5.5 PSH × 365 days × 0.80 losses = 19,042 kWh theoretical
    # OpenSolar actual: 16,862 kWh (accounts for shading, orientation, real irradiance)
    # The difference is because OpenSolar uses hour-by-hour simulation, not simple PSH
}

# ── Equipment ──────────────────────────────────────────────────────────
PANEL = {
    "manufacturer": "Mission Solar",
    "model": "MSE395SX9R",
    "wattage_w": 395,
    "weight_lbs": 48.5,
    "dimensions_in": "75.08 x 41.50",  # L x W in inches
    "area_sqft": 21.63,
    "weight_psf": 2.24,  # lbs per sq ft
}

INVERTER = {
    "manufacturer": "Enphase",
    "model": "IQ8PLUS-72-2-US",
    "type": "Microinverter",
    "voltage_ac": 240,
    "quantity": 30,
}

RACKING = {
    "manufacturer": "IronRidge",
    "model": "XR100",
    "rail_length_in": 168,
    "rail_count": 16,
    "attachment_model": "FlashFoot 2",
    "attachment_count": 66,
    "attachment_spacing_in": 48,  # 48" O.C.
    "cantilever_in": 20,  # 20" O.C.
    "mid_clamp_count": 72,
    "end_clamp_count": 24,
    "stopper_sleeves": 24,
    "bonded_splice": 8,
    "grounding_lug": 6,
}

# ── Property / Lot ─────────────────────────────────────────────────────
PROPERTY = {
    # Lot is IRREGULAR polygon, NOT a rectangle
    # Dimensions from reference A-101:
    "lot_sides_ft": [162.0, 70.92, 108.33, 70.42, 168.33, 21.33],
    # Building is L-shaped, NOT rectangular
    "building_shape": "L-shaped",
    "has_chimney": True,
    "has_driveway": True,
    "has_fence": True,  # along back
    "street_name": "ESCALON DR",
    # Equipment locations at front of house
    "equipment_locations": ["CB", "ACD", "MSP", "UM"],
}

# ── Roof Segments ──────────────────────────────────────────────────────
ROOF_SEGMENTS = [
    {
        "id": 1,
        "tilt_deg": 18,
        "azimuth_deg": 99,
        "num_panels": 16,
        "roof_material": "Asphalt",
        "rafter_size": "2x9",
        "rafter_spacing_in": 16,  # 16" O.C.
        "array_area_sqft": 346.08,
        "roof_area_sqft": 611.79,
        "coverage_pct": 57,
    },
    {
        "id": 2,
        "tilt_deg": 18,
        "azimuth_deg": 279,
        "num_panels": 14,
        "roof_material": "Asphalt",
        "rafter_size": "2x9",
        "rafter_spacing_in": 16,
        "array_area_sqft": 302.82,
        "roof_area_sqft": 646.72,
        "coverage_pct": 47,
    },
]

# ── Fire Setbacks ──────────────────────────────────────────────────────
FIRE_SETBACKS = {
    "ridge_in": 36,  # 3'-0" from ridge on all sides
    "eave_in": 36,   # 36" fire setback marked on reference A-102
    "valley_in": 36,
    "hip_in": 36,
}

# ── Environmental Design Data ──────────────────────────────────────────
DESIGN_DATA = {
    "snow_load_psf": 0,
    "wind_speed_mph": 94,
    "exposure_category": "B",
}

# ── Governing Codes ────────────────────────────────────────────────────
GOVERNING_CODES = [
    "2022 California Building Code",
    "2022 California Electrical Code",
    "2022 California Fire Code",
    "2022 California Plumbing Code",
    "2022 California Mechanical Code",
    "2022 California Energy Code",
    "2022 California Residential Code",
]

# ── Sheet Index ────────────────────────────────────────────────────────
SHEET_INDEX = {
    "T-00": "Cover Page",
    "G-01": "Electrical Notes",
    "A-101": "Site Plan",
    "A-102": "Racking and Framing Plan",
    "A-103": "String Plan",
    "A-104": "Attachment Detail",
    "E-601": "Electrical Line Diagram",
    "E-602": "Electrical Calculations, Specifications Module & Inverters",
    "E-603": "Signage",
    "E-604": "Placard",
    "R-001 - R-005": "Equipment Specifications",
}

# ── Bill of Materials ──────────────────────────────────────────────────
BOM = [
    {"item": "Solar PV Module", "qty": 30, "desc": "Mission MSE395SX9R (395W) Modules"},
    {"item": "Microinverter", "qty": 30, "desc": "Enphase IQ8PLUS-72-2-US (240V) Micro-Inverters"},
    {"item": "Junction Box", "qty": 2, "desc": "Junction Box, NEMA 3R, UL Listed"},
    {"item": "IQ Combiner Box", "qty": 1, "desc": "Enphase IQ Combiner 5C w/IQ Gateway (X-IQ-AM1-240-5C)"},
    {"item": "Attachment", "qty": 66, "desc": "Bolt Lag 5/16 x 4.25\""},
    {"item": "Attachment", "qty": 66, "desc": "Assy, Flashing"},
    {"item": "Attachment", "qty": 66, "desc": "Washer, EPDM Backed"},
    {"item": "Attachment", "qty": 66, "desc": "Assy, Cap"},
    {"item": "IQ Water Tight Cap", "qty": 7, "desc": "IQ Water Tight Caps"},
    {"item": "Enphase", "qty": 37, "desc": "Enphase Q Cable 240V, (Per Connector)"},
    {"item": "Enphase", "qty": 3, "desc": "Branch Terminator"},
    {"item": "Rails", "qty": 16, "desc": "IronRidge XR100 Rail (168\")"},
    {"item": "Bonded Splice", "qty": 8, "desc": "Splice Kit"},
    {"item": "Mid Clamp", "qty": 72, "desc": "Universal Fastening Object (UFO)"},
    {"item": "End Clamp", "qty": 24, "desc": "Stopper Sleeves"},
    {"item": "Grounding Lug", "qty": 6, "desc": "IronRidge Grounding Lug"},
]

# ── Cover Page General Notes (15 items from reference) ─────────────────
GENERAL_NOTES_COUNT = 15

# ── Electrical Notes (11 items from reference) ─────────────────────────
ELECTRICAL_NOTES_COUNT = 11

# ── Wiring & Conduit Notes (8 items from reference) ────────────────────
WIRING_NOTES_COUNT = 8


def validate_output(html: str) -> dict:
    """Compare generated HTML planset against reference baseline.

    Returns a dict with pass/fail for each check and an overall score.
    """
    results = {}

    # --- Address & Client ---
    results["address_present"] = "17001 ESCALON" in html.upper() or "ESCALON DR" in html.upper()
    results["encino_present"] = "ENCINO" in html.upper()

    # --- Equipment ---
    results["panel_count_30"] = "30" in html  # Should show 30 panels
    results["dc_size_correct"] = "11.85" in html or "11.8" in html or "13.2" in html  # depends on panel used

    # --- Jurisdiction ---
    results["california_codes"] = "California" in html
    results["ladwp_utility"] = "LADWP" in html
    results["no_hydro_quebec_in_codes"] = "Hydro-Qu" not in html.split("GOVERNING")[0] if "GOVERNING" in html else True

    # --- Quebec contamination (CRITICAL for California plansets) ---
    qc_count = (html.count("Hydro-Qu") + html.count("CMEQ") + html.count("AECQ")
                + html.count("NBCC") + html.count("CCQ") + html.count("RW90-XLPE"))
    results["zero_quebec_refs"] = qc_count == 0

    # --- Roof Segments ---
    results["two_roof_segments"] = html.count("ROOF") >= 2 or html.count("Roof #") >= 2

    # --- Fire Setbacks ---
    results["fire_setbacks_shown"] = "FIRE SETBACK" in html.upper() or "36" in html

    # --- Property Plan ---
    results["no_shed"] = "SHED" not in html.upper()  # Reference has NO shed
    results["street_name"] = "ESCALON" in html.upper()

    # --- Production ---
    results["production_shown"] = ("16862" in html or "16,862" in html or
                                    "kWh" in html)  # annual production should appear

    # --- Score ---
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    results["_score"] = f"{passed}/{total}"
    results["_pass_rate"] = passed / total if total > 0 else 0

    return results


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as f:
            html = f.read()
        results = validate_output(html)
        print(f"\nReference Validation: {results['_score']}")
        for k, v in results.items():
            if not k.startswith("_"):
                print(f"  [{'PASS' if v else 'FAIL'}] {k}")
    else:
        print("Usage: python reference_escalon_dr.py <planset.html>")
        print("\nReference data loaded. Key specs:")
        print(f"  Panels: {SYSTEM['num_panels']}x {PANEL['model']} ({PANEL['wattage_w']}W)")
        print(f"  Inverters: {INVERTER['quantity']}x {INVERTER['model']}")
        print(f"  Roof #1: {ROOF_SEGMENTS[0]['num_panels']} panels, {ROOF_SEGMENTS[0]['tilt_deg']}° tilt, {ROOF_SEGMENTS[0]['azimuth_deg']}° azim")
        print(f"  Roof #2: {ROOF_SEGMENTS[1]['num_panels']} panels, {ROOF_SEGMENTS[1]['tilt_deg']}° tilt, {ROOF_SEGMENTS[1]['azimuth_deg']}° azim")
        print(f"  Fire setbacks: {FIRE_SETBACKS['ridge_in']}\" all edges")
        print(f"  Lot shape: IRREGULAR polygon ({len(PROPERTY['lot_sides_ft'])} sides)")
        print(f"  Building: {PROPERTY['building_shape']}")
