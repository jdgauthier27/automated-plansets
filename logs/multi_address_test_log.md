# Multi-Address Test Log

## Run 1 — 2026-03-22 — Sherman Oaks, CA (13221 Weddington St)

**Status: PASS (after bug fix)**

### Results
- Panels: 6, System: 2.37 kW
- AHJ: City of Los Angeles ✅ (fixed from "City of Sherman")
- Utility: LADWP ✅
- NEC refs: 83 ✅
- Quebec refs: 0 ✅
- Pages: 13 ✅
- No crashes ✅

### Bug Fixed
`html_renderer.py` `_extract_municipality()` was splitting city on spaces and taking only the first word.
"Sherman Oaks" → "Sherman" → `get_ahj_label("Sherman")` → "City of Sherman" (WRONG)

Fix: only strip last token if it looks like a postal code (numeric/alphanumeric like "J8T").
After fix: "Sherman Oaks" passes through intact → `get_ahj_label("Sherman Oaks")` → "City of Los Angeles" ✅

### Regression: Escalon Dr (17001 Escalon Dr, Encino, CA)
- AHJ: City of Los Angeles ✅
- LADWP ✅
- No Quebec refs ✅
- Pages: 13 ✅

---

## Run 2 — 2026-03-22 — Gatineau, QC (123 Rue Principale)

**Status: PASS**

### Results
- Panels: 12, System: 4.74 kW
- AHJ: Ville de Gatineau / RBQ ✅
- Utility: Hydro-Quebec ✅
- Hydro-Quebec refs: 9 ✅
- CMEQ refs: 15 ✅
- CEC refs: 74 ✅
- RW90 wire refs: 18 ✅
- US refs (CSLB, THWN-2, CBC 2022): 0 ✅
- NEC refs: 31 — all are "CEC Rule 64-218 | NEC 690.x" cross-refs + "DISCONNECT" substring false positives. No standalone NEC code citations. ✅
- Pages: 13 ✅
- No crashes ✅

### Notes
- Quebec jurisdiction engine correctly selected (country='CA')
- All wire references use RW90-XLPE (Quebec standard), not THWN-2
- CMEQ licensing note present
- NEC appears only as cross-reference in format "CEC Rule 64-218 | NEC 690.17" (informational) and as substring of "DISCONNECT" — both acceptable

---

---

## Run 3 — 2026-03-22 — San Diego, CA (1234 Main St, CA 92101)

**Status: PASS (after 2 bug fixes)**

### Results
- Panels: 2940 (large commercial building), System: ~1176 kW DC
- AHJ: City of San Diego ✅
- Utility: SDG&E ✅ (7 refs)
- NEC refs: 36 ✅
- Hydro-Quebec refs: 0 ✅
- CMEQ refs: 0 ✅
- RW90 refs: 0 ✅
- THWN-2 refs: 16 ✅ (correct US wire spec)
- CSLB refs: 14 ✅ (correct CA contractor license)
- CEC Canada refs: 0 ✅
- Pages: 13 ✅

### Bugs Fixed

**Bug 1 — PlacementConfig tilt_deg not a valid field**
`solar_planset.py` `run_address_mode()` passed `tilt_deg=args.tilt` to `PlacementConfig.__init__()`,
but `PlacementConfig` has no `tilt_deg` parameter → `TypeError` crash.
Fix: removed `tilt_deg` from the `PlacementConfig(...)` call.

**Bug 2 — country not passed to ProjectSpec (root cause of all Quebec contamination)**
`run_address_mode()` never passed `country=` to `ProjectSpec(...)`.
`ProjectSpec.country` defaults to `"CA"` (Canada), so ALL US addresses silently used the
CEC Quebec jurisdiction engine → Hydro-Quebec, CMEQ, RW90-XLPE, CSA C22.1 refs on every US planset.
Fix: added `_detect_country(address)` helper that parses the address for Canadian postal codes,
province abbreviations, or US ZIP codes. Pass detected country to `ProjectSpec(country=country)`.

### Regression: Escalon Dr (17001 Escalon Dr, Encino, CA)
- Score: 13/13 ✅ — no regression introduced

---

## Next runs
- Run 4: Montreal, QC (different city design temps from Gatineau)
- Run 5: Encino, CA (consistency check vs Run 1 Escalon baseline)
- Run 6: Toronto, ON (ESA licensing, Toronto Hydro)
