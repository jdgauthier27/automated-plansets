"""
Cross-jurisdiction contamination test.

Generates plansets for addresses in different jurisdictions and verifies
that each planset uses the correct code references without contamination
from other jurisdictions.

Usage:
    python3 tests/test_cross_jurisdiction.py

Requires: Backend running on port 8000
"""

import json
import re
import sys
import urllib.request
import urllib.error

BASE_URL = "http://localhost:8000"

# ── Test Addresses ────────────────────────────────────────────────────────

JURISDICTIONS = {
    "california": {
        "address": "17001 Escalon Dr, Encino, CA 91436",
        "label": "California (17001 Escalon Dr, Encino, CA)",
    },
    "texas": {
        "address": "4500 Worth St, Dallas, TX 75246",
        "label": "Texas (4500 Worth St, Dallas, TX)",
    },
    "quebec": {
        "address": "1234 Rue Sherbrooke Ouest, Montreal, QC H3G 1H9",
        "label": "Quebec (1234 Rue Sherbrooke Ouest, Montreal, QC)",
    },
}

# ── Equipment (valid catalog IDs) ────────────────────────────────────────

PROJECT_DEFAULTS = {
    "panel_id": "longi-himo7-455",
    "inverter_id": "enphase-iq8plus",
    "racking_id": "ironridge-xr10",
    "roof_material": "asphalt_shingle",
    "main_panel_breaker_a": 200,
    "main_panel_bus_rating_a": 225,
    "num_panels": 20,
    "company_name": "Test Solar Co",
    "designer_name": "Automated Test",
}


def strip_base64(html: str) -> str:
    """Remove base64 data URIs from HTML to avoid false positives."""
    return re.sub(r'data:[a-zA-Z0-9+/;=,\-]+[A-Za-z0-9+/=]+', '', html)


def api_post(path: str, data: dict) -> dict:
    """POST JSON to the API and return parsed response."""
    url = BASE_URL + path
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def generate_planset(address: str) -> str:
    """Validate address, create project, generate planset, return HTML."""
    # Step 1: Validate address to get lat/lng
    try:
        addr_resp = api_post("/api/address/validate", {"address": address})
        lat = addr_resp["lat"]
        lng = addr_resp["lng"]
        formatted = addr_resp.get("formatted_address", address)
    except Exception:
        # If geocoding fails (no API key), use 0,0 — server handles mock data
        lat, lng, formatted = 0.0, 0.0, address

    # Step 2: Create project
    project_data = {
        "address": formatted,
        "latitude": lat,
        "longitude": lng,
        **PROJECT_DEFAULTS,
    }
    proj_resp = api_post("/api/projects", project_data)
    project_id = proj_resp["project_id"]

    # Step 3: Generate planset
    gen_resp = api_post(f"/api/projects/{project_id}/generate", {})
    planset_path = gen_resp.get("planset_path", "")

    # Step 4: Read generated HTML
    if planset_path:
        with open(planset_path) as f:
            return f.read()

    # Fallback: try downloading via API
    url = f"{BASE_URL}/api/projects/{project_id}/planset"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


# ── Contamination Check Functions ─────────────────────────────────────────

def check_california(html: str) -> list:
    """Checks for a California (NEC) planset."""
    clean = strip_base64(html)
    results = []

    # Should contain
    results.append(("contains_nec_refs", bool(re.search(r'\bNEC\b', clean))))
    results.append(("contains_california_codes", "California" in clean))

    # Should NOT contain Quebec references
    qc_terms = ["CMEQ", "AECQ", "NBCC", "RW90-XLPE"]
    qc_count = sum(clean.count(t) for t in qc_terms)
    # CCQ specifically (not inside other words)
    ccq_matches = len(re.findall(r'\bCCQ\b', clean))
    qc_count += ccq_matches
    results.append(("no_quebec_contamination", qc_count == 0))

    # Should NOT contain Hydro-Quebec
    results.append(("no_hydro_quebec", "Hydro-Qu" not in clean))

    return results


def check_texas(html: str) -> list:
    """Checks for a Texas (NEC) planset."""
    clean = strip_base64(html)
    results = []

    # Should contain NEC references
    results.append(("contains_nec_refs", bool(re.search(r'\bNEC\b', clean))))

    # Should NOT contain California-specific codes
    # "CEC Weighted Efficiency" is OK — it's an industry standard, not California contamination
    cal_clean = clean.replace("CEC Weighted Efficiency", "").replace("CEC weighted efficiency", "")
    cal_clean = cal_clean.replace("CEC-weighted", "")
    # Check for California Building/Electrical/Fire/Energy Code
    has_california_codes = bool(re.search(
        r'California\s+(Building|Electrical|Fire|Energy|Residential|Plumbing|Mechanical)\s+Code',
        cal_clean
    ))
    results.append(("no_california_codes", not has_california_codes))

    # Should NOT contain Quebec references
    qc_terms = ["CMEQ", "AECQ", "NBCC", "RW90-XLPE"]
    qc_count = sum(clean.count(t) for t in qc_terms)
    ccq_matches = len(re.findall(r'\bCCQ\b', clean))
    qc_count += ccq_matches
    results.append(("no_quebec_contamination", qc_count == 0))

    # Check for Texas-specific utility/regulatory references
    has_texas_ref = any(
        term in clean
        for term in ["Oncor", "ERCOT", "TDLR", "PUCT", "Texas"]
    )
    results.append(("correct_utility", has_texas_ref))

    return results


def check_quebec(html: str) -> list:
    """Checks for a Quebec (CEC) planset."""
    clean = strip_base64(html)
    results = []

    # Should contain Canadian references
    # CEC here means Canadian Electrical Code (CSA C22.1)
    has_cec = bool(re.search(r'\bCEC\b', clean)) or "CSA C22.1" in clean or "Canadian Electrical" in clean
    results.append(("contains_cec_refs", has_cec))

    # Should contain Hydro-Quebec
    results.append(("contains_hydro_quebec", "Hydro-Qu" in clean or "HYDRO-QU" in clean.upper()))

    # Should contain RBQ
    results.append(("contains_rbq", "RBQ" in clean))

    # Should NOT contain California-specific codes
    # Again filter out CEC Weighted Efficiency (industry standard)
    cal_clean = clean.replace("CEC Weighted Efficiency", "").replace("CEC weighted efficiency", "")
    cal_clean = cal_clean.replace("CEC-weighted", "")
    has_california_codes = bool(re.search(
        r'California\s+(Building|Electrical|Fire|Energy|Residential|Plumbing|Mechanical)\s+Code',
        cal_clean
    ))
    results.append(("no_california_contamination", not has_california_codes))

    return results


CHECKERS = {
    "california": check_california,
    "texas": check_texas,
    "quebec": check_quebec,
}

# ── Main ──────────────────────────────────────────────────────────────────

def main():
    # Check server is running
    try:
        urllib.request.urlopen(f"{BASE_URL}/docs", timeout=5)
    except urllib.error.URLError as e:
        if hasattr(e, 'reason') and 'Connection refused' in str(e.reason):
            print("ERROR: Backend not running on port 8000. Start it first.")
            sys.exit(1)
        # Any HTTP error (404, 500) means server is up
    except Exception:
        pass  # Any response means server is up

    print("Cross-Jurisdiction Validation")
    print("=" * 40)

    total_checks = 0
    total_passed = 0
    all_results = {}

    for jur_key, jur_info in JURISDICTIONS.items():
        print(f"\n{jur_info['label']}:")
        try:
            html = generate_planset(jur_info["address"])
        except Exception as e:
            print(f"  [ERROR] Failed to generate planset: {e}")
            # Count all checks for this jurisdiction as failed
            checker = CHECKERS[jur_key]
            # Run checker with empty string to get check names
            dummy_results = checker("")
            for name, _ in dummy_results:
                print(f"  [FAIL] {name} (planset generation failed)")
                total_checks += 1
            all_results[jur_key] = {"error": str(e)}
            continue

        checker = CHECKERS[jur_key]
        results = checker(html)
        jur_results = {}

        for name, passed in results:
            status = "PASS" if passed else "FAIL"
            print(f"  [{status}] {name}")
            total_checks += 1
            if passed:
                total_passed += 1
            jur_results[name] = passed

        all_results[jur_key] = jur_results

    print(f"\nScore: {total_passed}/{total_checks}")

    # Exit with appropriate code
    sys.exit(0 if total_passed == total_checks else 1)


if __name__ == "__main__":
    main()
