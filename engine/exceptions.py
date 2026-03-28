"""Custom exceptions for the solar planset engine."""


class SolarAPIError(Exception):
    """General error communicating with the Google Solar API."""

    def __init__(self, message: str, status_code: int | None = None):
        self.status_code = status_code
        super().__init__(message)


class AddressNotSupportedError(SolarAPIError):
    """The Google Solar API has no data for the requested address.

    Raised when the API returns NOT_FOUND — typically for rural addresses,
    new construction, or areas without aerial imagery coverage.
    """

    def __init__(self, lat: float, lng: float):
        self.lat = lat
        self.lng = lng
        super().__init__(
            f"Google Solar API has no data for location ({lat}, {lng}). "
            "This address is not supported for automated design.",
            status_code=404,
        )


class InsufficientCoverageError(SolarAPIError):
    """The API returned data but not enough viable panel positions.

    Raised when buildingInsights returns successfully but the number of
    viable panels is too low to produce a meaningful design.
    """

    def __init__(self, available: int, required: int):
        self.available = available
        self.required = required
        super().__init__(
            f"Only {available} viable panel positions found, but {required} required.",
            status_code=None,
        )
