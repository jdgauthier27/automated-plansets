"""Parcel boundary fetcher — returns lot polygon for property plans.

Fallback chain:
1. Regrid API (if REGRID_API_KEY set) — most comprehensive US parcel data
2. OpenStreetMap Overpass API (free, partial coverage)
3. None (caller falls back to estimated rectangle)
"""

import os
import math
import logging
from typing import List, Dict, Optional

import urllib.request
import json
import ssl

logger = logging.getLogger(__name__)

# Disable SSL verification for macOS Python 3.12+ compatibility
_ctx = ssl._create_unverified_context()


def fetch_parcel_boundary(
    lat: float,
    lng: float,
    api_key: Optional[str] = None,
) -> Optional[List[Dict[str, float]]]:
    """Fetch parcel boundary polygon for a given lat/lng.

    Returns list of {lat, lng} dicts forming a closed polygon,
    or None if no boundary found.

    Fallback chain:
    1. County ArcGIS REST services (free, no key, good coverage)
    2. Regrid API (if key provided)
    3. OpenStreetMap Overpass (free, spotty coverage)
    """
    # Try county ArcGIS first (free, no key needed)
    result = _fetch_county_arcgis(lat, lng)
    if result:
        return result

    # Try Regrid if key available
    regrid_key = api_key or os.environ.get("REGRID_API_KEY", "")
    if regrid_key:
        result = _fetch_regrid(lat, lng, regrid_key)
        if result:
            return result

    # Fall back to OpenStreetMap
    result = _fetch_osm(lat, lng)
    if result:
        return result

    return None


def _fetch_county_arcgis(lat: float, lng: float) -> Optional[List[Dict[str, float]]]:
    """Fetch parcel from county ArcGIS REST services (free, no API key).

    Many US counties expose parcel data through public ArcGIS REST endpoints.
    This tries a set of known county services based on approximate location.
    """
    # Known county ArcGIS parcel endpoints (add more as needed)
    # Format: (name, url_template, geometry_type)
    # The URL uses an envelope query around the point
    services = [
        # LA County (covers Encino, Sherman Oaks, etc.)
        (
            "LA County",
            "https://public.gis.lacounty.gov/public/rest/services/LACounty_Cache/LACounty_Parcel/MapServer/0/query",
            "esriGeometryPoint",
        ),
        # Orange County CA
        (
            "Orange County",
            "https://services.arcgis.com/LjHKtM8ymFuwSfDv/arcgis/rest/services/OC_Parcels/FeatureServer/0/query",
            "esriGeometryPoint",
        ),
    ]

    for name, base_url, geom_type in services:
        try:
            # Try both GeoJSON and ESRI JSON formats
            for fmt in ["geojson", "json"]:
                params = {
                    "geometry": f"{lng},{lat}",
                    "geometryType": geom_type,
                    "spatialRel": "esriSpatialRelIntersects",
                    "returnGeometry": "true",
                    "f": fmt,
                    "inSR": "4326",
                    "outSR": "4326",
                }
                query_str = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
                url = f"{base_url}?{query_str}"

                req = urllib.request.Request(url, headers={"Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=30, context=_ctx) as resp:
                    data = json.loads(resp.read())

                features = data.get("features", [])
                if not features:
                    continue

                geometry = features[0].get("geometry", {})

                # Handle GeoJSON format
                geo_type = geometry.get("type", "")
                if geo_type == "Polygon":
                    coords = geometry["coordinates"][0]
                    result = [{"lat": c[1], "lng": c[0]} for c in coords]
                    logger.info("Parcel found via %s (GeoJSON): %d vertices", name, len(result))
                    return result
                elif geo_type == "MultiPolygon":
                    largest = max(geometry["coordinates"], key=lambda ring: len(ring[0]))
                    result = [{"lat": c[1], "lng": c[0]} for c in largest[0]]
                    logger.info("Parcel found via %s (GeoJSON Multi): %d vertices", name, len(result))
                    return result

                # Handle ESRI JSON format (rings)
                rings = geometry.get("rings", [])
                if rings and len(rings[0]) >= 3:
                    result = [{"lat": pt[1], "lng": pt[0]} for pt in rings[0]]
                    logger.info("Parcel found via %s (ESRI): %d vertices", name, len(result))
                    return result

        except Exception as e:
            logger.debug("County ArcGIS %s failed: %s", name, e)
            continue

    return None


def _fetch_regrid(lat: float, lng: float, api_key: str) -> Optional[List[Dict[str, float]]]:
    """Fetch parcel from Regrid (formerly Loveland) API.

    API docs: https://regrid.com/api
    Endpoint: GET /api/v2/parcels/point?lat=X&lon=Y&token=KEY
    Returns GeoJSON with parcel polygon.
    """
    try:
        url = (
            f"https://app.regrid.com/api/v2/parcels/point"
            f"?lat={lat}&lon={lng}&token={api_key}"
            f"&return_geometry=true&limit=1"
        )
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10, context=_ctx) as resp:
            data = json.loads(resp.read())

        features = data.get("parcels", {}).get("features", [])
        if not features:
            return None

        geometry = features[0].get("geometry", {})
        if geometry.get("type") != "Polygon":
            return None

        coords = geometry["coordinates"][0]  # outer ring
        return [{"lat": c[1], "lng": c[0]} for c in coords]

    except Exception as e:
        logger.debug("Regrid API failed: %s", e)
        return None


def _fetch_osm(lat: float, lng: float) -> Optional[List[Dict[str, float]]]:
    """Fetch parcel boundary from OpenStreetMap via Overpass API.

    Searches for landuse=residential or boundary=lot ways near the point.
    Free, no API key, but coverage is spotty.
    """
    try:
        # Search for the nearest parcel/lot polygon within 50m
        query = f"""
        [out:json][timeout:10];
        (
          way["landuse"="residential"](around:50,{lat},{lng});
          way["boundary"="lot"](around:50,{lat},{lng});
          relation["landuse"="residential"](around:50,{lat},{lng});
        );
        out body;
        >;
        out skel qt;
        """
        url = "https://overpass-api.de/api/interpreter"
        post_data = f"data={urllib.parse.quote(query)}".encode("utf-8")
        req = urllib.request.Request(url, data=post_data)
        with urllib.request.urlopen(req, timeout=15, context=_ctx) as resp:
            data = json.loads(resp.read())

        elements = data.get("elements", [])
        if not elements:
            return None

        # Build node lookup
        nodes = {}
        ways = []
        for el in elements:
            if el["type"] == "node":
                nodes[el["id"]] = {"lat": el["lat"], "lng": el["lon"]}
            elif el["type"] == "way" and "nodes" in el:
                ways.append(el)

        if not ways:
            return None

        # Find the way whose centroid is closest to our point
        best_way = None
        best_dist = float("inf")
        for way in ways:
            way_nodes = [nodes[nid] for nid in way["nodes"] if nid in nodes]
            if len(way_nodes) < 3:
                continue
            cx = sum(n["lat"] for n in way_nodes) / len(way_nodes)
            cy = sum(n["lng"] for n in way_nodes) / len(way_nodes)
            dist = math.sqrt((cx - lat) ** 2 + (cy - lng) ** 2)
            if dist < best_dist:
                best_dist = dist
                best_way = way_nodes

        if best_way and len(best_way) >= 3:
            return best_way

        return None

    except Exception as e:
        logger.debug("OSM Overpass failed: %s", e)
        return None


import urllib.parse  # noqa: E402 (needed for query encoding)
