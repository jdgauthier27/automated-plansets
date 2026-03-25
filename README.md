# Solar Planset Tool

Automated solar permit planset generator. Enter an address, select equipment, and generate professional engineering plan sets (PV-1 through PV-8) compliant with NEC (US) and CEC (Canada) electrical codes.

## Features

- **Address lookup** with Google Solar API building insights and GeoTIFF roof geometry
- **3D visualization** using CesiumJS + Google Photorealistic Tiles
- **Automated panel placement** with azimuth-aligned rotation, obstruction avoidance, and fire setbacks
- **Multi-jurisdiction support** — pluggable code engines for CEC Quebec/Ontario/BC and NEC California/Texas/Florida/Illinois/New York
- **Equipment catalog** — panels, inverters, racking, and attachments from JSON specs
- **Electrical calculations** — conductor sizing, breaker selection, shade factor analysis
- **Bill of materials** generation
- **HTML-to-PDF** planset export via Playwright

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- A Google Cloud API key with Solar API, Maps, Geocoding, and Street View enabled

### Backend

```bash
cp .env.example .env
# Edit .env and add your GOOGLE_SOLAR_API_KEY

pip install -r requirements.txt
pip install fastapi uvicorn rasterio scipy ezdxf
python3 app.py
```

The API starts on `http://localhost:8000`.

### Frontend

```bash
cd ui
npm install
npm run dev
```

The dev server starts on `http://localhost:5173` and proxies API requests to the backend.

### Production Build

```bash
cd ui
npm run build
```

Built files go to `ui/dist/` and are served by FastAPI as a single-page app.

## Project Structure

```
solar_planset_tool/
├── app.py                  # FastAPI entry point
├── api/                    # REST endpoints (projects, equipment, address, solar)
├── models/                 # Data models (ProjectSpec, equipment, roof obstacles)
├── engine/                 # Core calculations (placement, electrical, BOM, PDF export)
├── jurisdiction/           # Pluggable NEC/CEC code engines + AHJ registry
├── catalog/                # Equipment specs (panels.json, inverters.json, etc.)
├── renderer/               # SVG helpers, title block, page builders
├── address/                # Geocoding, Google Solar API, building selector
├── training/               # Agentic learning loop (evaluator, feedback)
├── importers/              # External data importers (OpenSolar)
├── tests/                  # Reference validation tests
├── ui/                     # React + Vite + Tailwind frontend
│   └── src/
│       ├── components/     # Wizard steps, 3D viewer, maps
│       └── pages/          # Dashboard, project detail, wizard
├── html_renderer.py        # Main planset generator (multi-page HTML)
├── panel_placer.py         # Panel placement with azimuth rotation
├── quebec_electrical.py    # CEC Section 64 electrical calculations
├── satellite_fetch.py      # Google Maps tile fetcher
├── geotiff_roof.py         # GeoTIFF DSM/mask roof extraction
├── roof_detector.py        # Roof face data structures
└── data_export.py          # JSON/CSV/BOM export utilities
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GOOGLE_SOLAR_API_KEY` | Yes | Google Cloud API key (Solar API, Maps, Geocoding, Street View) |

## Testing

```bash
python3 tests/reference_escalon_dr.py /tmp/output.html
```

Reference address: **17001 Escalon Dr, Encino, CA 91436** (30 panels, Mission Solar 395W). Target: 11/11 checks passing.

## Tech Stack

**Backend**: Python, FastAPI, NumPy, Shapely, Rasterio, Playwright

**Frontend**: React 18, Vite, Tailwind CSS, CesiumJS, Three.js
