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
    description="Quebec Solaire — Automated solar permit planset generation",
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
