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

## Next runs
- Run 3: 1234 Main St, San Diego, CA 92101 (SDG&E utility)
- Run 4: 17001 Escalon Dr with LONGi 455W + Solis S6 string inverter
