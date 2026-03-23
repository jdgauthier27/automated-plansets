# Solar Planset Tool

## Commands

### Backend (FastAPI)
```bash
cd solar_planset_tool
pip install fastapi uvicorn rasterio scipy ezdxf
python app.py  # Starts on port 8000
```

### Frontend (React + Vite)
```bash
cd solar_planset_tool/ui
npm install
npm run dev  # Starts on port 5173
```

### Validation
```bash
python tests/reference_escalon_dr.py /tmp/output.html  # Target: 11/11
```

## Environment
- `GOOGLE_SOLAR_API_KEY` — Required. Used for Solar API, Street View, Geocoding, and dataLayers GeoTIFF.

## Architecture
- `app.py` — FastAPI entry point, mounts API routes + serves React SPA
- `api/` — REST endpoints: projects, equipment, address, solar
- `html_renderer.py` — Main planset generator (13-page HTML → PDF)
- `panel_placer.py` — Rotated grid placement with azimuth alignment
- `engine/geotiff_roof.py` — Downloads mask+DSM GeoTIFF, extracts roof polygons
- `engine/electrical_calc.py` — Conductor sizing, breaker calcs
- `catalog/*.json` — Equipment catalog (panels, inverters, racking, attachments)
- `jurisdiction/` — Pluggable code engines (CEC Quebec, NEC California, NEC base)
- `models/project.py` — `ProjectSpec` dataclass — single source of truth for all design data
- `ui/src/` — React wizard: Address → Roof → Equipment → Solar → Electrical → Review

## Key Conventions
- ALL equipment specs come from `catalog/*.json` — never hardcode panel/inverter/racking values
- ALL code references come from `jurisdiction/*.py` — never hardcode CEC/NEC rules
- `ProjectSpec` is the single source of truth — every renderer page reads from it
- Panel placement must be portrait orientation, grouped in arrays, rotated to roof azimuth
- Fire setbacks: 36" all edges (California), configurable per jurisdiction

## Testing
- Reference planset: `~/Downloads/YifeiSun_RevB-correct panel layout.pdf`
- Test address: 17001 Escalon Dr, Encino, CA 91436 (30 panels, Mission Solar 395W)
- Validation: `python tests/reference_escalon_dr.py <output.html>` — must score 11/11
- Use `/validate` skill after any code change

## Gotchas
- `buildingInsights` API gives rough bounding boxes (40% too small) — use `dataLayers` GeoTIFF for accurate roof geometry
- SSL cert verification fails on macOS Python 3.12 — use `ssl._create_unverified_context`
- Panel placement order matters: equipment selection MUST come before panel placement (panel dimensions affect count)
- The GeoTIFF extractor returns ~150 micro-faces — they need merging for clean output
- deck.gl cannot properly place panels on 3D tiles — CesiumJS is the correct choice for 3D
