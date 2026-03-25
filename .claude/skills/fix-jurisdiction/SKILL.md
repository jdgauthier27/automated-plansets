---
name: fix-jurisdiction
description: Audit and fix jurisdiction code references in generated plansets. Detects Quebec/CEC codes on US addresses and NEC codes on Canadian addresses, then fixes them in html_renderer.py.
---

# Fix Jurisdiction References

Audit a generated planset for jurisdiction mismatches and fix them in the renderer code.

## When to Use
- After generating a planset, if you see Quebec/CEC/CMEQ references on a US address
- After generating a planset, if you see NEC/NFPA references on a Canadian address
- Proactively after any change to html_renderer.py jurisdiction logic

## Steps

1. **Determine the address jurisdiction** from the project:
   - US addresses → NEC/NFPA 70, IBC, state-specific codes
   - California → California Electrical Code, Title 24, CalFire, CSLB C-46, LADWP/SCE/PG&E
   - Quebec/Canada → CEC CSA C22.1, CCQ Chapter V, Hydro-Quebec, RBQ, CMEQ

2. **Check the jurisdiction engine selection** in `html_renderer.py`:
   - Read the `__init__` method to see how `self._jurisdiction` is set
   - Verify it uses `jurisdiction/nec_california.py` for CA addresses
   - Verify it uses `jurisdiction/cec_quebec.py` for QC addresses
   - Check the `ahj_registry.json` for correct AHJ mapping

3. **Audit the generated HTML** for mismatches:
   ```bash
   # For a US/CA planset, these should NOT appear:
   grep -i "CMEQ\|Hydro-Quebec\|CSA C22\.1\|CCQ\|RBQ\|Quebec" /tmp/validate_planset.html

   # For a US/CA planset, these SHOULD appear:
   grep -i "NEC\|NFPA 70\|California\|CSLB\|Title 24" /tmp/validate_planset.html
   ```

4. **Fix mismatches** in `html_renderer.py`:
   - Find hardcoded Quebec/CEC references and replace with jurisdiction-aware lookups
   - Use `self._jurisdiction.governing_codes()` instead of hardcoded strings
   - Use `self._jurisdiction.utility_name()` instead of "Hydro-Quebec"
   - Use `self._jurisdiction.licensing_body()` instead of "CMEQ"/"RBQ"

5. **Verify the fix** by regenerating and re-auditing:
   ```bash
   cd "/Users/jdelafontaine/Quebec Solaire/Automated plans/solar_planset_tool"
   python3 -c "
   # Quick jurisdiction check
   from jurisdiction.nec_california import NECCalifornia
   j = NECCalifornia()
   print('Codes:', j.governing_codes())
   print('Utility:', j.utility_name('Encino'))
   print('License:', j.licensing_body())
   "
   ```

## Jurisdiction Engine Reference
- `jurisdiction/base.py` — Abstract base with required methods
- `jurisdiction/cec_quebec.py` — CEC/CSA for Quebec
- `jurisdiction/nec_california.py` — NEC/Title 24 for California
- `jurisdiction/nec_base.py` — Generic NEC for other US states
- `jurisdiction/ahj_registry.json` — City → AHJ mapping
