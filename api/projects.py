"""
Projects API
=============
CRUD for solar installation projects and planset generation.
"""

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

from catalog.loader import EquipmentCatalog
from models.project import ProjectSpec

router = APIRouter(prefix="/api/projects", tags=["Projects"])


def _detect_country(address: str) -> str:
    """Detect country from address string. Returns 'US' or 'CA'."""
    import re

    addr = address.upper()
    _CA_PROVINCES = {"QC", "ON", "BC", "AB", "MB", "SK", "NS", "NB", "NL", "PE", "YT", "NT", "NU"}

    # Explicit country suffix
    if addr.endswith(", CANADA") or ", CANADA," in addr:
        return "CA"
    if addr.endswith(", USA") or ", USA," in addr or addr.endswith(" USA"):
        return "US"

    # Canadian postal code pattern (e.g. H3G 1H9)
    if re.search(r"\b[A-Z]\d[A-Z]\s*\d[A-Z]\d\b", addr):
        return "CA"

    # Canadian province abbreviation after comma
    for prov in _CA_PROVINCES:
        if f", {prov} " in addr or f", {prov}," in addr or addr.endswith(f", {prov}"):
            return "CA"

    # Default to US
    return "US"

# Simple file-based storage for v1
PROJECTS_DIR = Path(__file__).parent.parent / "data" / "projects"
PROJECTS_DIR.mkdir(parents=True, exist_ok=True)


class ProjectCreateRequest(BaseModel):
    address: str
    latitude: float = 0.0
    longitude: float = 0.0
    panel_id: str = "longi-himo7-455"
    inverter_id: str = "solis-s6-eh1p5k"
    racking_id: str = "ironridge-xr10"
    roof_material: str = "asphalt_shingle"
    main_panel_breaker_a: int = 200
    main_panel_bus_rating_a: int = 225
    num_panels: int = 13
    company_name: str = "Solar Contractor"
    designer_name: str = "AI Solar Design Engine"
    project_name: Optional[str] = None


class ProjectResponse(BaseModel):
    project_id: str
    address: str
    panel: str
    inverter: str
    racking: str
    roof_material: str
    num_panels: int
    system_dc_kw: float
    system_ac_kw: float
    created_at: str
    planset_ready: bool = False


@router.post("", response_model=ProjectResponse)
def create_project(req: ProjectCreateRequest):
    """Create a new project from equipment selections."""
    catalog = EquipmentCatalog()

    try:
        panel = catalog.get_panel(req.panel_id)
        inverter = catalog.get_inverter(req.inverter_id)
        racking = catalog.get_racking(req.racking_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    attachment = catalog.auto_select_attachment(req.roof_material, req.racking_id)
    if not attachment:
        from models.equipment import AttachmentCatalogEntry

        attachment = AttachmentCatalogEntry(model="Generic")

    project_id = str(uuid.uuid4())[:8]
    project_name = req.project_name or f"Solar Installation — {req.address}"

    # Detect country from address
    country = _detect_country(req.address)

    project = ProjectSpec(
        address=req.address,
        latitude=req.latitude,
        longitude=req.longitude,
        country=country,
        panel=panel,
        inverter=inverter,
        racking=racking,
        attachment=attachment,
        roof_material=req.roof_material,
        main_panel_breaker_a=req.main_panel_breaker_a,
        main_panel_bus_rating_a=req.main_panel_bus_rating_a,
        num_panels=req.num_panels,
        company_name=req.company_name,
        designer_name=req.designer_name,
        project_name=project_name,
    )

    # Save project
    project_data = {
        "project_id": project_id,
        "created_at": datetime.now().isoformat(),
        "address": req.address,
        "latitude": req.latitude,
        "longitude": req.longitude,
        "panel_id": req.panel_id,
        "inverter_id": req.inverter_id,
        "racking_id": req.racking_id,
        "roof_material": req.roof_material,
        "main_panel_breaker_a": req.main_panel_breaker_a,
        "main_panel_bus_rating_a": req.main_panel_bus_rating_a,
        "num_panels": req.num_panels,
        "company_name": req.company_name,
        "designer_name": req.designer_name,
        "project_name": project_name,
    }

    project_file = PROJECTS_DIR / f"{project_id}.json"
    with open(project_file, "w") as f:
        json.dump(project_data, f, indent=2)

    return ProjectResponse(
        project_id=project_id,
        address=req.address,
        panel=panel.model_short,
        inverter=inverter.model_short,
        racking=racking.model,
        roof_material=req.roof_material,
        num_panels=req.num_panels,
        system_dc_kw=project.system_dc_kw,
        system_ac_kw=project.system_ac_kw,
        created_at=project_data["created_at"],
    )


@router.get("")
def list_projects():
    """List all saved projects."""
    projects = []
    for f in PROJECTS_DIR.glob("*.json"):
        with open(f) as fp:
            data = json.load(fp)
        projects.append(
            {
                "project_id": data["project_id"],
                "address": data["address"],
                "panel_id": data["panel_id"],
                "inverter_id": data["inverter_id"],
                "num_panels": data["num_panels"],
                "created_at": data["created_at"],
                "planset_ready": (PROJECTS_DIR / f"{data['project_id']}_planset.html").exists(),
            }
        )
    return sorted(projects, key=lambda x: x["created_at"], reverse=True)


@router.get("/{project_id}")
def get_project(project_id: str):
    """Get a specific project."""
    project_file = PROJECTS_DIR / f"{project_id}.json"
    if not project_file.exists():
        raise HTTPException(status_code=404, detail="Project not found")
    with open(project_file) as f:
        return json.load(f)


@router.post("/{project_id}/generate")
def generate_planset(project_id: str):
    """Generate a planset for a project."""
    project_file = PROJECTS_DIR / f"{project_id}.json"
    if not project_file.exists():
        raise HTTPException(status_code=404, detail="Project not found")

    with open(project_file) as f:
        data = json.load(f)

    catalog = EquipmentCatalog()
    panel = catalog.get_panel(data["panel_id"])
    inverter = catalog.get_inverter(data["inverter_id"])
    racking = catalog.get_racking(data["racking_id"])
    attachment = catalog.auto_select_attachment(data["roof_material"], data["racking_id"])

    from models.equipment import AttachmentCatalogEntry

    project = ProjectSpec(
        address=data["address"],
        latitude=data.get("latitude", 0),
        longitude=data.get("longitude", 0),
        panel=panel,
        inverter=inverter,
        racking=racking,
        attachment=attachment or AttachmentCatalogEntry(model="Generic"),
        roof_material=data["roof_material"],
        main_panel_breaker_a=data["main_panel_breaker_a"],
        main_panel_bus_rating_a=data["main_panel_bus_rating_a"],
        num_panels=data["num_panels"],
        company_name=data["company_name"],
        designer_name=data["designer_name"],
        project_name=data["project_name"],
    )

    # Detect country and jurisdiction from the address
    from jurisdiction import get_jurisdiction_engine
    project.country = _detect_country(data["address"])
    _engine = get_jurisdiction_engine(data["address"], country=project.country)
    project.jurisdiction_id = type(_engine).__module__.rsplit(".", 1)[-1]  # e.g. "nec_california"

    # Generate planset using the existing pipeline
    from panel_placer import PanelSpec, PanelPlacer, PlacementConfig
    from google_solar import GoogleSolarClient, solar_insight_to_roof_faces
    from html_renderer import HtmlRenderer
    from pdf_parser import PlansetData, PageData

    api_key = os.environ.get("GOOGLE_SOLAR_API_KEY", "")

    # Fetch building data
    insight = None
    if api_key and (project.latitude != 0 or project.longitude != 0):
        client = GoogleSolarClient(api_key=api_key)
        insight = client.get_building_insight(
            address=project.address,
            lat=project.latitude,
            lng=project.longitude,
        )
    else:
        # Use mock data
        client = GoogleSolarClient(api_key="")
        insight = client.get_building_insight(address=project.address)

    # Compute shade factor from annual flux GeoTIFF (async, non-blocking)
    if api_key and client.api_key:
        try:
            flux_result = client.get_flux_and_mask(project.address)
            if flux_result:
                from engine.electrical_calc import calculate_shade_factor

                project.shade_factor = calculate_shade_factor(
                    flux_result.get("flux_bytes"),
                    mask_bytes=flux_result.get("mask_bytes"),
                )
                import logging as _log

                _log.getLogger(__name__).info("Shade factor: %.3f", project.shade_factor)
        except Exception as _e:
            import logging as _log

            _log.getLogger(__name__).warning("Shade factor skipped: %s", _e)

    # Fetch real building outline + roof faces from GeoTIFF (more accurate than Solar API)
    geotiff_roofs = None
    geotiff_scale = 1.0
    if api_key and project.latitude and project.longitude:
        try:
            from engine.geotiff_roof import get_roof_geometry_from_geotiff
            scene = get_roof_geometry_from_geotiff(project.latitude, project.longitude, api_key)
            outline = scene.get("building_outline_ft", [])
            if outline and len(outline) >= 3:
                project.building_outline_ft = outline
            _faces = scene.get("roof_faces", [])
            if _faces:
                geotiff_roofs = _faces
                geotiff_scale = float(scene.get("scale_pts_per_ft", 1.0))
        except Exception as _e:
            import logging
            logging.getLogger(__name__).warning("GeoTIFF pipeline skipped: %s", _e)

    # Use GeoTIFF roof faces if available, otherwise fall back to Solar API
    if geotiff_roofs:
        roofs, scale = geotiff_roofs, geotiff_scale
    else:
        roofs, scale = solar_insight_to_roof_faces(insight)

    panel_spec = PanelSpec(
        name=panel.model,
        wattage=panel.wattage_w,
        width_ft=panel.width_ft,
        height_ft=panel.height_ft,
    )
    placer = PanelPlacer(panel=panel_spec, config=PlacementConfig(
        max_panels=project.num_panels,
        latitude=project.latitude,
    ))
    placements = placer.place_on_roofs(roofs, scale)

    # Render
    virtual_page = PageData(page_number=1, width=792, height=612, scale_factor=scale)
    planset_data = PlansetData(
        filepath=f"(API: {project.address})",
        total_pages=1,
        pages=[virtual_page],
        metadata={"address": project.address},
    )

    renderer = HtmlRenderer(panel_spec=panel_spec, project=project)
    output_path = str(PROJECTS_DIR / f"{project_id}_planset.html")
    renderer.render(planset_data, placements, output_path, building_insight=insight)

    return {"status": "success", "planset_path": output_path}


@router.get("/{project_id}/planset")
def download_planset(project_id: str, format: str = "html"):
    """Serve the generated planset as HTML (preview) or PDF (download).

    Query params:
      format=html  — returns the HTML file for iframe preview (default)
      format=pdf   — converts to PDF and streams it as application/pdf
    """
    from fastapi.responses import Response

    planset_file = PROJECTS_DIR / f"{project_id}_planset.html"
    if not planset_file.exists():
        raise HTTPException(status_code=404, detail="Planset not yet generated. Call /generate first.")

    if format == "pdf":
        import tempfile
        from engine.pdf_exporter import export_planset_pdf

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_pdf = tmp.name

        try:
            export_planset_pdf(str(planset_file), tmp_pdf)
            pdf_bytes = Path(tmp_pdf).read_bytes()
        finally:
            if os.path.exists(tmp_pdf):
                os.unlink(tmp_pdf)

        filename = f"planset_{project_id}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(pdf_bytes)),
            },
        )

    # Default: serve HTML for iframe preview
    content = planset_file.read_bytes()
    return Response(
        content=content,
        media_type="text/html",
        headers={
            "X-Frame-Options": "SAMEORIGIN",
            "Content-Security-Policy": "frame-ancestors 'self'",
        },
    )


@router.post("/import/opensolar")
async def import_opensolar(file: UploadFile = File(...)):
    """Import a project from OpenSolar JSON export."""
    import tempfile
    from importers.opensolar import import_opensolar_json

    # Save uploaded file
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        project = import_opensolar_json(tmp_path)
        # Save as new project
        project_id = str(uuid.uuid4())[:8]
        project_data = {
            "project_id": project_id,
            "created_at": datetime.now().isoformat(),
            "address": project.address,
            "latitude": project.latitude,
            "longitude": project.longitude,
            "panel_id": project.panel.id,
            "inverter_id": project.inverter.id,
            "racking_id": project.racking.id,
            "roof_material": project.roof_material,
            "main_panel_breaker_a": project.main_panel_breaker_a,
            "main_panel_bus_rating_a": project.main_panel_bus_rating_a,
            "num_panels": project.num_panels,
            "company_name": project.company_name,
            "designer_name": project.designer_name,
            "project_name": project.project_name,
            "source": "opensolar",
        }
        with open(PROJECTS_DIR / f"{project_id}.json", "w") as f:
            json.dump(project_data, f, indent=2)

        return {
            "project_id": project_id,
            "imported": True,
            "panel": project.panel.model_short,
            "inverter": project.inverter.model_short,
            "num_panels": project.num_panels,
        }
    finally:
        os.unlink(tmp_path)
