"""
Solar Data API
==============
Endpoints for Google Solar API building insights, optimized panel placements,
data layers, and roof analysis.
"""

import os
import ssl
import json
import urllib.request
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

router = APIRouter(prefix="/api/solar", tags=["Solar Data"])

_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE


@router.get("/building")
def get_building_insights(lat: float = Query(...), lng: float = Query(...)):
    """Fetch full buildingInsights from Google Solar API."""
    api_key = os.environ.get("GOOGLE_SOLAR_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=400, detail="No API key configured")

    url = (
        f"https://solar.googleapis.com/v1/buildingInsights:findClosest"
        f"?location.latitude={lat}&location.longitude={lng}"
        f"&requiredQuality=MEDIUM&key={api_key}"
    )
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=30, context=_ssl_ctx) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Solar API error: {e}")

    # Extract and structure the response
    solar = data.get("solarPotential", {})
    segments = []
    for seg in solar.get("roofSegmentStats", []):
        stats = seg.get("stats", {})
        segments.append(
            {
                "pitch_deg": seg.get("pitchDegrees", 0),
                "azimuth_deg": seg.get("azimuthDegrees", 0),
                "area_m2": stats.get("areaMeters2", 0),
                "sunshine_hours": stats.get("sunshineQuantiles", []),
                "center": seg.get("center", {}),
                "bounding_box": seg.get("boundingBox", {}),
                "height_m": seg.get("planeHeightAtCenterMeters", 0),
            }
        )

    panels = []
    for p in solar.get("solarPanels", []):
        center = p.get("center", {})
        panels.append(
            {
                "lat": center.get("latitude", 0),
                "lng": center.get("longitude", 0),
                "orientation": p.get("orientation", "PORTRAIT"),
                "segment_index": p.get("segmentIndex", 0),
                "yearly_energy_kwh": p.get("yearlyEnergyDcKwh", 0),
            }
        )

    configs = []
    for c in solar.get("solarPanelConfigs", []):
        configs.append(
            {
                "panels_count": c.get("panelsCount", 0),
                "yearly_energy_kwh": c.get("yearlyEnergyDcKwh", 0),
            }
        )

    return {
        "center": data.get("center", {}),
        "imagery_quality": data.get("imageryQuality", ""),
        "imagery_date": data.get("imageryDate", {}),
        "max_panels": solar.get("maxArrayPanelsCount", 0),
        "max_kw": round(solar.get("maxArrayPanelsCount", 0) * solar.get("panelCapacityWatts", 400) / 1000, 2),
        "max_sunshine_hours": solar.get("maxSunshineHoursPerYear", 0),
        "carbon_offset": solar.get("carbonOffsetFactorKgPerMwh", 0),
        "panel_capacity_w": solar.get("panelCapacityWatts", 400),
        "panel_dimensions": {
            "height_m": solar.get("panelHeightMeters", 1.879),
            "width_m": solar.get("panelWidthMeters", 1.045),
        },
        "roof_segments": segments,
        "panels": panels,
        "configs": configs,
    }


@router.get("/panels")
def get_optimized_panels(
    lat: float = Query(...),
    lng: float = Query(...),
    count: int = Query(13, description="Number of panels to select"),
):
    """Get top N panels ranked by yearly energy production."""
    data = get_building_insights(lat, lng)
    panels = data.get("panels", [])

    # Sort by yearly energy, best first
    sorted_panels = sorted(panels, key=lambda p: p["yearly_energy_kwh"], reverse=True)
    selected = sorted_panels[:count]

    total_kwh = sum(p["yearly_energy_kwh"] for p in selected)

    return {
        "count": len(selected),
        "total_yearly_kwh": round(total_kwh, 1),
        "avg_kwh_per_panel": round(total_kwh / len(selected), 1) if selected else 0,
        "panels": selected,
        "all_available": len(panels),
    }


@router.get("/panels-grouped")
def get_panels_grouped(
    lat: float = Query(...),
    lng: float = Query(...),
    count: int = Query(13, description="Target number of panels"),
):
    """Get panels grouped by segment with spatial ordering and quality validation."""
    from engine.smart_placer import group_panels

    # Fetch full building data
    building_data = get_building_insights(lat, lng)

    result = group_panels(building_data, target_count=count, latitude=lat)

    return {
        "arrays": [
            {
                "array_id": a.array_id,
                "segment_index": a.segment_index,
                "azimuth_deg": a.azimuth_deg,
                "pitch_deg": a.pitch_deg,
                "num_panels": a.num_panels,
                "total_kwh": round(a.total_kwh, 1),
                "panels": [
                    {
                        "index": p.index,
                        "lat": p.lat,
                        "lng": p.lng,
                        "orientation": p.orientation,
                        "segment_index": p.segment_index,
                        "yearly_energy_kwh": p.yearly_energy_kwh,
                        "row": p.row,
                        "col": p.col,
                        "array_id": p.array_id,
                        "violations": p.violations,
                        "is_valid": p.is_valid,
                    }
                    for p in a.panels
                ],
            }
            for a in result.arrays
        ],
        "excluded_segments": result.excluded_segments,
        "total_panels": result.total_panels,
        "total_kwh": round(result.total_kwh, 1),
        "warnings": result.warnings,
    }


@router.get("/roof-analysis")
def get_roof_analysis(lat: float = Query(...), lng: float = Query(...)):
    """Analyze roof segments with solar scoring and obstruction detection."""
    from google_solar import GoogleSolarClient
    from engine.roof_analyzer import analyze_roof, get_building_dimensions

    api_key = os.environ.get("GOOGLE_SOLAR_API_KEY", "")
    client = GoogleSolarClient(api_key=api_key)
    insight = client.get_building_insight(lat=lat, lng=lng)

    segments = analyze_roof(insight)
    dimensions = get_building_dimensions(insight)

    return {
        "segments": [
            {
                "index": s.index,
                "pitch_deg": s.pitch_deg,
                "azimuth_deg": s.azimuth_deg,
                "direction": s.direction_label,
                "area_sqft": round(s.area_sqft, 0),
                "area_m2": round(s.area_m2, 1),
                "height_m": round(s.height_m, 1),
                "solar_score": s.solar_score,
                "obstruction_score": s.obstruction_score,
                "is_viable": s.is_viable,
                "panel_count": s.panel_count,
                "sunshine_hours": round(s.sunshine_hours_per_year, 0),
            }
            for s in segments
        ],
        "building_dimensions": dimensions,
        "total_segments": len(segments),
        "viable_segments": sum(1 for s in segments if s.is_viable),
    }


@router.get("/datalayers")
def get_data_layers(
    lat: float = Query(...),
    lng: float = Query(...),
    radius_m: float = Query(50, description="Radius in meters"),
):
    """Fetch GeoTIFF data layer URLs from Google Solar API."""
    api_key = os.environ.get("GOOGLE_SOLAR_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=400, detail="No API key configured")

    url = (
        f"https://solar.googleapis.com/v1/dataLayers:get"
        f"?location.latitude={lat}&location.longitude={lng}"
        f"&radiusMeters={radius_m}"
        f"&view=FULL_LAYERS"
        f"&requiredQuality=MEDIUM"
        f"&pixelSizeMeters=0.5"
        f"&key={api_key}"
    )
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=30, context=_ssl_ctx) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Data layers API error: {e}")

    return {
        "imagery_date": data.get("imageryDate", {}),
        "imagery_processed_date": data.get("imageryProcessedDate", {}),
        "dsm_url": data.get("dsmUrl", ""),
        "rgb_url": data.get("rgbUrl", ""),
        "mask_url": data.get("maskUrl", ""),
        "annual_flux_url": data.get("annualFluxUrl", ""),
        "monthly_flux_url": data.get("monthlyFluxUrl", ""),
        "hourly_shade_urls": data.get("hourlyShadeUrls", []),
    }


@router.get("/dsm-heights")
def get_dsm_heights(
    lat: float = Query(...),
    lng: float = Query(...),
    panel_lats: str = Query("", description="Comma-separated panel center latitudes"),
    panel_lngs: str = Query("", description="Comma-separated panel center longitudes"),
):
    """Get DSM height values at panel positions for 3D placement."""
    from engine.dsm_processor import fetch_dsm, analyze_building_dsm

    dsm = fetch_dsm(lat, lng)
    if not dsm:
        raise HTTPException(status_code=502, detail="Could not fetch DSM data")

    # Parse panel positions
    positions = []
    if panel_lats and panel_lngs:
        lats = [float(x) for x in panel_lats.split(",") if x.strip()]
        lngs = [float(x) for x in panel_lngs.split(",") if x.strip()]
        positions = list(zip(lats, lngs))

    analysis = analyze_building_dsm(dsm, lat, lng, positions)

    return {
        "building": {
            "ground_elevation_m": round(analysis.ground_elevation_m, 2),
            "eave_height_m": round(analysis.eave_height_m, 2),
            "ridge_height_m": round(analysis.ridge_height_m, 2),
            "building_height_m": round(analysis.building_height_m, 2),
        },
        "features": [
            {
                "type": f.type,
                "lat": f.lat,
                "lng": f.lng,
                "height_m": round(f.height_m, 2),
                "height_above_roof_m": round(f.height_above_roof_m, 2),
            }
            for f in analysis.roof_features
        ],
        "panel_heights": {str(k): round(v, 2) for k, v in analysis.panel_heights.items()},
    }


@router.get("/proxy-geotiff")
def proxy_geotiff(url: str = Query(..., description="GeoTIFF URL to proxy")):
    """Proxy a GeoTIFF download to avoid CORS issues in the browser."""
    api_key = os.environ.get("GOOGLE_SOLAR_API_KEY", "")

    # Ensure the URL is from Google's domain
    if "googleapis.com" not in url and "google.com" not in url:
        raise HTTPException(status_code=400, detail="Only Google API URLs are allowed")

    # Append API key if not present
    if "key=" not in url:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}key={api_key}"

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=60, context=_ssl_ctx) as resp:
            content = resp.read()
            content_type = resp.headers.get("Content-Type", "application/octet-stream")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"GeoTIFF fetch error: {e}")

    return Response(
        content=content,
        media_type=content_type,
        headers={"Access-Control-Allow-Origin": "*"},
    )


@router.get("/roof-geotiff")
def get_roof_from_geotiff(
    lat: float = Query(...),
    lng: float = Query(...),
    panel_width_ft: float = Query(3.46, description="Panel width in feet"),
    panel_height_ft: float = Query(6.26, description="Panel height in feet"),
    panel_wattage: int = Query(395, description="Panel wattage"),
    max_panels: int = Query(30, description="Max panels to place"),
    setback_ft: float = Query(3.0, description="Fire setback in feet"),
):
    """Get accurate roof geometry from GeoTIFF dataLayers + panel placement.

    This is the preferred endpoint for design — uses DSM mask for accurate
    roof polygons instead of buildingInsights bounding boxes.
    """
    api_key = os.environ.get("GOOGLE_SOLAR_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=400, detail="No API key configured")

    try:
        from engine.geotiff_roof import get_roof_geometry_from_geotiff
        from panel_placer import PanelSpec, PanelPlacer, PlacementConfig

        # Get roof faces + geographic geometry from GeoTIFF in one pass
        scene = get_roof_geometry_from_geotiff(lat, lng, api_key)
        roofs = scene.get("roof_faces", [])
        scale = float(scene.get("scale_pts_per_ft", 1.0))
        outline_ft = scene.get("building_outline_ft", [])
        outline_latlng = scene.get("building_outline_latlng", [])

        # Place panels using the selected panel dimensions
        ps = PanelSpec(
            name="Selected Panel",
            wattage=panel_wattage,
            width_ft=panel_width_ft,
            height_ft=panel_height_ft,
        )
        placer = PanelPlacer(
            panel=ps,
            config=PlacementConfig(
                max_panels=max_panels,
                setback_ft=setback_ft,
                orientation="portrait",
                latitude=lat,
            ),
        )
        placements = placer.place_on_roofs(roofs, scale)

        panel_data = []
        for result in placements:
            for p in result.panels:
                panel_data.append(
                    {
                        "id": p.id,
                        "center_x": round(p.center_x, 2),
                        "center_y": round(p.center_y, 2),
                        "width_pts": round(p.width_pts, 2),
                        "height_pts": round(p.height_pts, 2),
                        "rotation_deg": round(p.rotation_deg, 1),
                        "roof_id": p.roof_id,
                        "orientation": p.orientation,
                    }
                )

        total_panels = sum(r.total_panels for r in placements)

        return {
            "source": scene.get("source", "geotiff_dsm"),
            "roof_faces": scene.get("geo_roof_faces", []),
            "panels": panel_data,
            "total_panels": total_panels,
            "system_kw": round(total_panels * panel_wattage / 1000, 2),
            "scale_pts_per_ft": round(scale, 4),
            "building_outline_ft": outline_ft,
            "building_outline_latlng": outline_latlng,
            "centroid_latlng": scene.get("centroid_latlng"),
            "bounds_latlng": scene.get("bounds_latlng"),
            "camera_hint": scene.get("camera_hint"),
            "geometry": {
                "roof_face_count": len(scene.get("geo_roof_faces", [])),
                "usable_roof_face_count": sum(
                    1 for face in scene.get("geo_roof_faces", []) if face.get("usable_polygon_latlng")
                ),
                "outline_latlng": outline_latlng,
                "bounds_latlng": scene.get("bounds_latlng"),
                "centroid_latlng": scene.get("centroid_latlng"),
                "camera_hint": scene.get("camera_hint"),
            },
        }

    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(
            status_code=502,
            detail=f"GeoTIFF roof analysis failed: {e}. Falling back to buildingInsights.",
        )


@router.get("/terrain-data")
def get_terrain_data(
    lat: float = Query(...),
    lng: float = Query(...),
    radius: float = Query(50.0, description="Radius in meters (half-width of terrain area)"),
):
    """Get terrain heightmap data for THREE.js 3D viewer.

    Returns a downsampled DSM elevation grid (200×200) centered on the building,
    plus metadata for constructing a BufferGeometry mesh in the browser.
    Replicates OpenSolar's OsTerrain approach.
    """
    from engine.dsm_processor import fetch_dsm
    from engine.terrain_mesh import build_terrain_data

    dsm = fetch_dsm(lat, lng, radius_m=max(radius, 50) + 20)
    if not dsm:
        raise HTTPException(status_code=502, detail="Could not fetch DSM data")

    terrain = build_terrain_data(dsm, lat, lng, radius_m=radius)
    if not terrain:
        raise HTTPException(status_code=502, detail="Could not build terrain mesh data")

    return terrain


@router.get("/satellite-image")
def get_satellite_image(
    lat: float = Query(...),
    lng: float = Query(...),
    zoom: int = Query(20),
    w: int = Query(1024),
    h: int = Query(1024),
):
    """Get satellite imagery for terrain texture.

    Returns a JPEG image centered on the building, sized for use as a
    THREE.js MeshStandardMaterial texture on the terrain mesh.
    """
    api_key = os.environ.get("GOOGLE_SOLAR_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=400, detail="No API key configured")

    try:
        # Fix macOS Python SSL cert issue
        import ssl as _ssl

        _ctx = _ssl.create_default_context()
        _ctx.check_hostname = False
        _ctx.verify_mode = _ssl.CERT_NONE
        import satellite_fetch as _sf

        # Monkey-patch ssl context if satellite_fetch uses urllib
        _orig_urlopen = urllib.request.urlopen

        def _patched_urlopen(req, **kwargs):
            kwargs.setdefault("context", _ctx)
            return _orig_urlopen(req, **kwargs)

        urllib.request.urlopen = _patched_urlopen
        try:
            img_array = _sf.fetch_satellite_mosaic(lat=lat, lng=lng, api_key=api_key, zoom=zoom, out_w=w, out_h=h)
        finally:
            urllib.request.urlopen = _orig_urlopen
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Satellite image fetch failed: {e}")

    if img_array is None:
        raise HTTPException(status_code=502, detail="No satellite imagery returned")

    # Convert numpy RGB array to JPEG bytes
    from PIL import Image
    import io

    img = Image.fromarray(img_array)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    buf.seek(0)

    return Response(
        content=buf.read(),
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=86400"},
    )
