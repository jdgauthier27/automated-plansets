"""
Address Validation API
======================
Endpoints for geocoding, Street View confirmation, satellite view, and Solar API data.
"""

import base64
import os
import ssl
import urllib.request
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/address", tags=["Address Validation"])

_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE


class AddressValidateRequest(BaseModel):
    address: str


class AddressValidateResponse(BaseModel):
    lat: float
    lng: float
    formatted_address: str
    street_view_b64: Optional[str] = None
    satellite_b64: Optional[str] = None
    street_view_url: str = ""


class AddressConfirmRequest(BaseModel):
    lat: float
    lng: float
    address: str


def _fetch_satellite_image(lat: float, lng: float, api_key: str, zoom: int = 20) -> Optional[bytes]:
    """Fetch a satellite image from Google Maps Static API."""
    url = (
        f"https://maps.googleapis.com/maps/api/staticmap"
        f"?center={lat},{lng}&zoom={zoom}&size=640x480&scale=2"
        f"&maptype=satellite&key={api_key}"
    )
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=15, context=_ssl_ctx) as resp:
            return resp.read()
    except Exception:
        return None


def _fetch_roadmap_image(lat: float, lng: float, api_key: str, zoom: int = 18) -> Optional[bytes]:
    """Fetch a roadmap overview with a marker from Google Maps Static API."""
    url = (
        f"https://maps.googleapis.com/maps/api/staticmap"
        f"?center={lat},{lng}&zoom={zoom}&size=640x480&scale=2"
        f"&maptype=hybrid&markers=color:red%7C{lat},{lng}"
        f"&key={api_key}"
    )
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=15, context=_ssl_ctx) as resp:
            return resp.read()
    except Exception:
        return None


@router.post("/validate", response_model=AddressValidateResponse)
def validate_address(req: AddressValidateRequest):
    """Geocode an address and return Street View + satellite images for confirmation."""
    try:
        from address.geocoder import GoogleGeocoder
        api_key = os.environ.get("GOOGLE_SOLAR_API_KEY", "")
        geocoder = GoogleGeocoder(api_key=api_key)

        result = geocoder.geocode(req.address)
        lat, lng = result["lat"], result["lng"]

        sv_b64 = None
        sat_b64 = None
        sv_url = ""

        if api_key:
            # Street View
            try:
                sv_bytes = geocoder.get_street_view_image(lat, lng)
                sv_b64 = base64.b64encode(sv_bytes).decode("utf-8")
            except Exception:
                pass
            sv_url = geocoder.get_street_view_url(lat, lng)

            # Satellite/hybrid map overview with marker
            map_bytes = _fetch_roadmap_image(lat, lng, api_key)
            if map_bytes:
                sat_b64 = base64.b64encode(map_bytes).decode("utf-8")

        return AddressValidateResponse(
            lat=lat, lng=lng,
            formatted_address=result.get("formatted_address", req.address),
            street_view_b64=sv_b64,
            satellite_b64=sat_b64,
            street_view_url=sv_url,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/satellite")
def get_satellite_image(lat: float, lng: float, zoom: int = 20):
    """Return a satellite image for the interactive map picker."""
    from fastapi.responses import Response
    api_key = os.environ.get("GOOGLE_SOLAR_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=400, detail="No API key configured")
    img_bytes = _fetch_roadmap_image(lat, lng, api_key, zoom=zoom)
    if not img_bytes:
        raise HTTPException(status_code=500, detail="Failed to fetch satellite image")
    return Response(content=img_bytes, media_type="image/png")


@router.post("/confirm")
def confirm_building(req: AddressConfirmRequest):
    """Fetch Google Solar API data for confirmed coordinates."""
    try:
        from address.google_solar import GoogleSolarClient
        api_key = os.environ.get("GOOGLE_SOLAR_API_KEY", "")
        client = GoogleSolarClient(api_key=api_key)
        insight = client.get_building_insight(
            address=req.address, lat=req.lat, lng=req.lng
        )
        return {
            "address": insight.address,
            "lat": insight.lat, "lng": insight.lng,
            "imagery_quality": insight.imagery_quality,
            "roof_segments": len(insight.roof_segments),
            "max_panels": insight.max_panels,
            "max_kw": insight.max_kw,
            "max_annual_kwh": insight.max_annual_kwh,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
