# Solar Planset Tool

## Commands

### Backend (FastAPI)
```bash
cd solar_planset_tool
pip3 install fastapi uvicorn rasterio scipy ezdxf
python3 app.py  # Starts on port 8000 (--reload enabled)
```

### Frontend (React + Vite)
```bash
cd solar_planset_tool/ui
npm install
npm run dev  # Starts on port 5173
```

### Frontend Build (production)
```bash
cd solar_planset_tool/ui
npm run build  # Builds to ui/dist/, served by FastAPI
```

### Validation
```bash
python3 tests/reference_escalon_dr.py /tmp/output.html  # Target: 13/13
```

## Environment
- `GOOGLE_SOLAR_API_KEY` — Required. Used for Solar API, Street View, Geocoding, and dataLayers GeoTIFF.

## Architecture
- `app.py` — FastAPI entry point, mounts API routes + serves React SPA
- `api/` — REST endpoints: projects, equipment, address, solar
- `html_renderer.py` — Planset orchestrator (delegates to page builders, ~1,195 lines)
- `renderer/page_builders/` — 16 individual page builder modules (extracted from html_renderer.py)
- `renderer/svg_helpers.py` — Shared SVG utilities (wire_gauge, dimension helpers, svg_page_frame)
- `renderer/shared/geo_utils.py` — Mercator projection utilities (meters_per_pixel, latlng_to_pixel)
- `renderer/shared/electrical.py` — Branch circuit calculations (compute_branch_circuits)
- `panel_placer.py` — Rotated grid placement with azimuth alignment
- `engine/geotiff_roof.py` — Downloads mask+DSM GeoTIFF, extracts roof polygons
- `engine/electrical_calc.py` — Conductor sizing, breaker calcs, shade factor
- `engine/dsm_processor.py` — DSM height analysis, obstruction detection
- `engine/bom_calculator.py` — Bill of materials generation
- `engine/smart_placer.py` — Advanced panel placement with obstruction avoidance
- `engine/proposal_generator.py` + `proposal_html.py` — Customer proposal PDF
- `engine/pdf_exporter.py` — HTML-to-PDF via Playwright
- `catalog/*.json` — Equipment catalog (panels, inverters, racking, attachments)
- `jurisdiction/` — Pluggable code engines: CEC (Quebec, BC, Ontario), NEC (CA, TX, FL, IL, NY, base)
- `jurisdiction/ahj_registry.json` — City → Authority Having Jurisdiction mapping
- `models/project.py` — `ProjectSpec` dataclass — single source of truth for all design data
- `ui/src/components/` — React wizard: Address → Roof → Equipment → Solar → Electrical → Review
- `ui/src/components/CesiumMap3D.jsx` — 3D viewer using Google Photorealistic Tiles + CesiumJS
- `ui/src/components/SolarMap.jsx` — 2D satellite view with Google Maps + flux overlay

## Key Conventions
- ALL equipment specs come from `catalog/*.json` — never hardcode panel/inverter/racking values
- ALL code references come from `jurisdiction/*.py` — never hardcode CEC/NEC rules
- `ProjectSpec` is the single source of truth — every renderer page reads from it
- Panel placement must be portrait orientation, grouped in arrays, rotated to roof azimuth
- Fire setbacks: 36" all edges (California), configurable per jurisdiction
- Page builders follow delegation pattern: standalone function receiving `HtmlRenderer` instance as first arg

## Testing
- Reference planset: `~/Downloads/YifeiSun_RevB-correct panel layout.pdf`
- Test address: 17001 Escalon Dr, Encino, CA 91436 (30 panels, Mission Solar 395W)
- Validation: `python tests/reference_escalon_dr.py <output.html>` — must score 13/13
- Cross-jurisdiction: `python3 tests/test_cross_jurisdiction.py` — must score 12/12
- Use `/validate` skill after any code change
- Use `/fix-jurisdiction` skill to audit/fix jurisdiction code references

## Skills & Agents
- `/generate` — Full pipeline: address → GeoTIFF → panels → planset HTML
- `/validate` — Run reference validation (13/13 checks)
- `/fix-jurisdiction` — Audit planset for jurisdiction mismatches (Quebec codes on US address etc.)
- `jurisdiction-auditor` agent — Parallel audit of generated HTML for code reference errors
- `planset-reviewer` agent — Full quality review against reference baseline

## Gotchas
- `buildingInsights` API gives rough bounding boxes (40% too small) — use `dataLayers` GeoTIFF for accurate roof geometry
- SSL cert verification fails on macOS Python 3.12 — use `ssl._create_unverified_context`
- Panel placement order matters: equipment selection MUST come before panel placement (panel dimensions affect count)
- The GeoTIFF extractor returns ~150 micro-faces — they need merging for clean output
- deck.gl cannot properly place panels on 3D tiles — CesiumJS is the correct choice for 3D
- CesiumJS `heightReference` (CLAMP_TO_GROUND, RELATIVE_TO_GROUND) does NOT work with Google 3D Tiles — use `scene.sampleHeight()` to get actual tile surface height, then `perPositionHeight: true` with absolute heights
- DSM elevations are geoid-referenced (MSL) — Google 3D Tiles use WGS84 ellipsoid. There's a ~33m offset in Encino CA. Never use DSM absolute heights directly for CesiumJS entity placement
- Jurisdiction engine MUST match the address country/state — California addresses must use `nec_california.py`, Quebec must use `cec_quebec.py`. Check `ahj_registry.json` for mapping
- `__pycache__` stale bytecode can cause AttributeError on new properties — clear `models/` and `engine/` pycache if server crashes after model changes
