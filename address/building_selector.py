"""
Building Selection & Confirmation
===================================
Uses Google Street View to let the operator visually confirm that the
Google Solar API's ``findClosest`` result is actually the *target* building
(not a neighbour).

Workflow:
  1. Geocode the address.
  2. Fetch a Street View image and present the URL to the user.
  3. Ask the user to confirm ("Is this the correct building?").
  4. If not, accept adjusted lat/lng and re-query.
  5. Once confirmed, fetch the full BuildingInsight from the Solar API.
"""

import base64
import logging
import sys
from typing import Optional, Tuple

from address.geocoder import GoogleGeocoder
from address.google_solar import GoogleSolarClient, BuildingInsight
from address.models import AddressValidation

logger = logging.getLogger(__name__)


class BuildingSelector:
    """
    Orchestrates address validation, Street View preview, and building
    confirmation against the Google Solar API.

    Usage (scripted):
        selector = BuildingSelector(api_key="…")
        validation = selector.validate_address("123 Rue Principale, Montréal")
        # show validation.street_view_url to the user …
        insight = selector.confirm_building(validation.lat, validation.lng)

    Usage (interactive CLI):
        lat, lng = selector.interactive_confirm("123 Rue Principale, Montréal")
    """

    def __init__(self, api_key: Optional[str] = None):
        self.geocoder = GoogleGeocoder(api_key=api_key)
        self.solar_client = GoogleSolarClient(api_key=api_key)

    # ── Public API ───────────────────────────────────────────────────────

    def validate_address(self, address: str) -> AddressValidation:
        """
        Geocode *address*, fetch a Street View image, and return an
        :class:`AddressValidation` bundle ready for the user to review.
        """
        geo = self.geocoder.geocode(address)
        lat, lng = geo["lat"], geo["lng"]
        formatted = geo["formatted_address"]

        # Fetch Street View image and encode for display / embedding
        try:
            sv_bytes = self.geocoder.get_street_view_image(lat, lng)
            sv_b64 = base64.b64encode(sv_bytes).decode("ascii")
        except RuntimeError:
            logger.warning("Street View image unavailable; continuing without it.")
            sv_b64 = ""

        sv_url = self.geocoder.get_street_view_url(lat, lng)

        return AddressValidation(
            lat=lat,
            lng=lng,
            formatted_address=formatted,
            street_view_b64=sv_b64,
            street_view_url=sv_url,
            confirmed=False,
        )

    def confirm_building(self, lat: float, lng: float) -> BuildingInsight:
        """
        Fetch the Google Solar BuildingInsight for the confirmed coordinates.
        """
        return self.solar_client.get_building_insight(lat=lat, lng=lng)

    def interactive_confirm(self, address: str) -> Tuple[float, float]:
        """
        CLI-based confirmation flow:
          1. Geocode the address.
          2. Print the Street View URL so the operator can open it.
          3. Ask whether the building shown is correct.
          4. If not, prompt for adjusted coordinates.
          5. Return the confirmed (lat, lng).
        """
        validation = self.validate_address(address)
        lat, lng = validation.lat, validation.lng

        print()
        print("=" * 60)
        print("  ADDRESS VALIDATION")
        print("=" * 60)
        print(f"  Address:   {validation.formatted_address}")
        print(f"  Lat/Lng:   {lat}, {lng}")
        print()
        print("  Open this link to see the Street View image:")
        print(f"  {validation.street_view_url}")
        print("=" * 60)
        print()

        while True:
            answer = input("Is this the correct building? [y/n]: ").strip().lower()

            if answer in ("y", "yes"):
                print(f"Building confirmed at ({lat}, {lng}).")
                return (lat, lng)

            if answer in ("n", "no"):
                print()
                print("Please provide adjusted coordinates.")
                try:
                    new_lat = float(input("  New latitude:  ").strip())
                    new_lng = float(input("  New longitude: ").strip())
                except (ValueError, EOFError):
                    print("Invalid input — keeping original coordinates.")
                    return (lat, lng)

                lat, lng = new_lat, new_lng

                # Show updated Street View for the new coordinates
                new_url = self.geocoder.get_street_view_url(lat, lng)
                print()
                print(f"  Updated Street View: {new_url}")
                print()
                continue

            print("  Please answer 'y' or 'n'.")
