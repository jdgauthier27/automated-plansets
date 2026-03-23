"""
Google Geocoding & Street View Helper
======================================
Geocodes addresses and fetches Street View images to let the user
visually confirm that the correct building was identified.

Uses urllib.request to match the existing codebase style (no external
HTTP libraries).
"""

import json
import logging
import math
import os
import ssl
import urllib.parse
import urllib.request
from typing import Dict, Optional

# Create an SSL context that doesn't verify certificates
# (workaround for macOS Python missing root certs)
_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE

logger = logging.getLogger(__name__)


class GoogleGeocoder:
    """
    Wraps the Google Geocoding API and Google Street View Static API.

    Usage:
        geo = GoogleGeocoder(api_key="YOUR_KEY")
        result = geo.geocode("123 Rue Principale, Montréal, QC")
        jpeg_bytes = geo.get_street_view_image(result["lat"], result["lng"])
    """

    GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
    STREET_VIEW_URL = "https://maps.googleapis.com/maps/api/streetview"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GOOGLE_SOLAR_API_KEY")
        if not self.api_key:
            logger.warning("No API key provided — geocoding and Street View will fail.")

    # ── Geocoding ────────────────────────────────────────────────────────

    def geocode(self, address: str) -> Dict:
        """
        Geocode an address string.

        Returns:
            dict with keys: lat, lng, formatted_address
        Raises:
            ValueError: if the address cannot be geocoded.
        """
        encoded = urllib.parse.quote(address)
        url = f"{self.GEOCODE_URL}?address={encoded}&key={self.api_key}"

        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=15, context=_ssl_ctx) as resp:
                data = json.loads(resp.read().decode())
        except Exception as e:
            logger.error("Geocoding request failed: %s", e)
            raise ValueError(f"Could not geocode address: {address}") from e

        results = data.get("results")
        if not results:
            status = data.get("status", "UNKNOWN")
            raise ValueError(
                f"Geocoding returned no results for '{address}' (status={status})"
            )

        first = results[0]
        loc = first["geometry"]["location"]
        return {
            "lat": loc["lat"],
            "lng": loc["lng"],
            "formatted_address": first.get("formatted_address", address),
        }

    # ── Street View ──────────────────────────────────────────────────────

    def get_street_view_image(
        self,
        lat: float,
        lng: float,
        heading: Optional[float] = None,
        fov: int = 90,
        pitch: int = 10,
        size: str = "600x400",
    ) -> bytes:
        """
        Fetch a Street View JPEG image for the given coordinates.

        If *heading* is not specified, a default heading pointing from the
        nearest road toward the building (roughly north) is calculated.
        This is a simple heuristic — for most residential streets the camera
        looks toward the house from the road.

        Returns:
            JPEG image bytes.
        Raises:
            RuntimeError: on HTTP / network errors.
        """
        if heading is None:
            heading = self._auto_heading(lat, lng)

        url = self._build_street_view_url(lat, lng, heading, fov, pitch, size)

        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=20, context=_ssl_ctx) as resp:
                return resp.read()
        except Exception as e:
            logger.error("Street View request failed: %s", e)
            raise RuntimeError(f"Could not fetch Street View image: {e}") from e

    def get_street_view_url(
        self,
        lat: float,
        lng: float,
        heading: Optional[float] = None,
    ) -> str:
        """
        Return a Street View Static API URL suitable for opening in a browser.
        """
        if heading is None:
            heading = self._auto_heading(lat, lng)
        return self._build_street_view_url(lat, lng, heading)

    # ── Internal helpers ─────────────────────────────────────────────────

    def _build_street_view_url(
        self,
        lat: float,
        lng: float,
        heading: float,
        fov: int = 90,
        pitch: int = 10,
        size: str = "600x400",
    ) -> str:
        """Assemble the full Street View Static API URL."""
        return (
            f"{self.STREET_VIEW_URL}"
            f"?location={lat},{lng}"
            f"&heading={heading}"
            f"&fov={fov}"
            f"&pitch={pitch}"
            f"&size={size}"
            f"&key={self.api_key}"
        )

    @staticmethod
    def _auto_heading(lat: float, lng: float) -> float:
        """
        Estimate a reasonable camera heading when none is provided.

        Heuristic: most residential streets in Quebec run roughly east-west,
        so houses face north or south.  We default to heading=0 (north) for
        addresses in the northern hemisphere, which makes the camera look
        *toward* the south-facing front of a typical Quebec house.

        A more sophisticated version could query the Roads API to find the
        true road bearing, but this simple default works well enough for the
        confirmation step.
        """
        # Point camera roughly toward the building from the street.
        # For Quebec (northern hemisphere), streets often run E-W;
        # default heading = 0 (looking north toward the house front).
        # If the address is unusual the user can always adjust.
        return 0.0
