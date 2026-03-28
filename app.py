"""
FastAPI Application — Solar Planset Tool
=========================================
Main entry point for the web API.

Run with:
    uvicorn app:app --reload --port 8000

Or:
    python app.py
"""

import os
import sys
from pathlib import Path

# Ensure the tool directory is on the path
sys.path.insert(0, str(Path(__file__).parent))

# Load .env file if it exists
_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from api.equipment import router as equipment_router
from api.address import router as address_router
from api.projects import router as projects_router
from api.solar import router as solar_router

app = FastAPI(
    title="Solar Planset Tool API",
    description="Automated solar permit planset generation",
    version="1.0.0",
)

# CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routes
app.include_router(equipment_router)
app.include_router(address_router)
app.include_router(projects_router)
app.include_router(solar_router)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "solar-planset-tool"}


@app.get("/api/download/{project_id}")
def download_planset(project_id: str):
    """Download a generated planset as PDF. Converts HTML planset using Playwright."""
    import tempfile
    from fastapi import HTTPException
    from fastapi.responses import Response
    from engine.pdf_exporter import export_planset_pdf

    projects_dir = Path(__file__).parent / "data" / "projects"
    html_path = projects_dir / f"{project_id}_planset.html"

    # Also check legacy /tmp location
    if not html_path.exists():
        tmp_html = Path(f"/tmp/planset_{project_id}.html")
        if tmp_html.exists():
            html_path = tmp_html

    if not html_path.exists():
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_pdf = tmp.name

    try:
        export_planset_pdf(str(html_path), tmp_pdf)
        pdf_bytes = Path(tmp_pdf).read_bytes()
    finally:
        if Path(tmp_pdf).exists():
            Path(tmp_pdf).unlink()

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="planset_{project_id}.pdf"'},
    )


@app.get("/api/proposal-pdf/{project_id}")
def download_proposal_pdf(project_id: str):
    """Generate and download a 1-page customer proposal PDF (Letter landscape)."""
    import json
    import re
    import tempfile
    from fastapi import HTTPException
    from fastapi.responses import Response
    from catalog.loader import EquipmentCatalog
    from engine.proposal_html import render_proposal_html
    from engine.pdf_exporter import export_planset_pdf

    projects_dir = Path(__file__).parent / "data" / "projects"
    project_file = projects_dir / f"{project_id}.json"
    if not project_file.exists():
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    with open(project_file) as f:
        data = json.load(f)

    catalog = EquipmentCatalog()
    try:
        panel = catalog.get_panel(data["panel_id"])
        inverter = catalog.get_inverter(data["inverter_id"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    num_panels = data.get("num_panels", 0)
    system_kw = round(num_panels * panel.wattage_w / 1000, 2)

    # Production estimate: system_kw × 5.5 PSH × 365 × 0.85
    annual_prod = round(system_kw * 5.5 * 365 * 0.85)

    # Monthly distribution (seasonal factors, sums to ~1.0)
    monthly_factors = {
        "Jan": 0.058,
        "Feb": 0.068,
        "Mar": 0.088,
        "Apr": 0.098,
        "May": 0.108,
        "Jun": 0.118,
        "Jul": 0.112,
        "Aug": 0.104,
        "Sep": 0.090,
        "Oct": 0.076,
        "Nov": 0.058,
        "Dec": 0.022,
    }
    monthly_prod = {m: round(annual_prod * f) for m, f in monthly_factors.items()}

    annual_cons = data.get("annual_consumption_kwh", annual_prod)
    offset_pct = round(annual_prod / annual_cons * 100, 1) if annual_cons > 0 else 0.0

    co2_lbs = round(annual_prod * 0.92)  # ~0.92 lbs CO2/kWh (US grid avg)
    trees_eq = round(co2_lbs / 48)  # ~48 lbs CO2 absorbed per tree/year

    total_cost = data.get("total_cost_usd", 0)
    cost_per_w = round(total_cost / (system_kw * 1000), 2) if system_kw > 0 else 0.0
    annual_savings = round(annual_prod * 0.20)
    payback = round(total_cost / annual_savings, 1) if annual_savings > 0 else 0.0

    proposal_data = {
        "address": data.get("address", ""),
        "company_name": data.get("company_name", "Solar Installer"),
        "system_size_kw": system_kw,
        "num_panels": num_panels,
        "panel_model": panel.model_short,
        "inverter_model": inverter.model_short,
        "annual_production_kwh": annual_prod,
        "annual_consumption_kwh": int(annual_cons),
        "solar_offset_pct": offset_pct,
        "total_cost_usd": total_cost,
        "cost_per_watt": cost_per_w,
        "co2_offset_lbs_per_year": co2_lbs,
        "trees_equivalent": trees_eq,
        "payback_years": payback,
        "monthly_production": monthly_prod,
    }

    html_content = render_proposal_html(proposal_data)

    # Write HTML to a temp file so Playwright can load it via file://
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8") as tmp_html:
        tmp_html.write(html_content)
        tmp_html_path = tmp_html.name

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
        tmp_pdf_path = tmp_pdf.name

    try:
        # Letter landscape: 11" × 8.5"
        export_planset_pdf(tmp_html_path, tmp_pdf_path, page_size="letter_landscape")
        pdf_bytes = Path(tmp_pdf_path).read_bytes()
    finally:
        for p in [tmp_html_path, tmp_pdf_path]:
            if Path(p).exists():
                Path(p).unlink()

    # Build filename from address slug
    address_slug = re.sub(r"[^\w]+", "_", data.get("address", project_id)).strip("_")[:50]
    filename = f"proposal_{address_slug}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/proposal/{project_id}")
def get_proposal(project_id: str):
    """Return customer proposal data as JSON for a saved project."""
    import json
    from fastapi import HTTPException
    from catalog.loader import EquipmentCatalog
    from models.project import ProjectSpec
    from models.equipment import AttachmentCatalogEntry
    from engine.bom_calculator import calculate_bom
    from engine.electrical_calc import calculate_monthly_production
    from engine.proposal_generator import generate_proposal

    projects_dir = Path(__file__).parent / "data" / "projects"
    project_file = projects_dir / f"{project_id}.json"
    if not project_file.exists():
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    with open(project_file) as f:
        data = json.load(f)

    catalog = EquipmentCatalog()
    try:
        panel = catalog.get_panel(data["panel_id"])
        inverter = catalog.get_inverter(data["inverter_id"])
        racking = catalog.get_racking(data["racking_id"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    attachment = catalog.auto_select_attachment(
        data.get("roof_material", "asphalt_shingle"), data["racking_id"]
    ) or AttachmentCatalogEntry(model="Generic")

    project = ProjectSpec(
        address=data["address"],
        latitude=data.get("latitude", 0.0),
        longitude=data.get("longitude", 0.0),
        panel=panel,
        inverter=inverter,
        racking=racking,
        attachment=attachment,
        roof_material=data.get("roof_material", "asphalt_shingle"),
        main_panel_breaker_a=data.get("main_panel_breaker_a", 200),
        main_panel_bus_rating_a=data.get("main_panel_bus_rating_a", 225),
        num_panels=data["num_panels"],
        company_name=data.get("company_name", "Solar Contractor"),
        designer_name=data.get("designer_name", "AI Solar Design Engine"),
        project_name=data.get("project_name", "Solar Installation"),
        annual_consumption_kwh=data.get("annual_consumption_kwh", 0.0),
        target_production_kwh=data.get("target_production_kwh", 0.0),
        sun_hours_peak=data.get("sun_hours_peak", 0.0),
    )

    bom = calculate_bom(project)
    monthly = calculate_monthly_production(project)
    return generate_proposal(project, bom, monthly)


@app.get("/api/config")
def config():
    """Return non-secret configuration for the frontend."""
    return {
        "google_maps_api_key": os.environ.get("GOOGLE_SOLAR_API_KEY", ""),
    }


# Serve React UI static files if built
UI_BUILD_DIR = Path(__file__).parent / "ui" / "dist"
if UI_BUILD_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(UI_BUILD_DIR / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve React SPA — all non-API routes go to index.html."""
        file_path = UI_BUILD_DIR / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(UI_BUILD_DIR / "index.html"))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
