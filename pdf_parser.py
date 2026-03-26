"""
PDF / Planset Data Module
=========================
Data classes representing a planset document (pages, metadata).
Used as the interchange format between data sources and renderers.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np


@dataclass
class PageData:
    """One page of a planset."""

    page_number: int
    width: float  # points or pixels
    height: float
    scale_factor: float = 1.0
    raster_image: Optional[np.ndarray] = None  # H×W×3 BGR/RGB
    vector_elements: List[Dict] = field(default_factory=list)
    annotations: List[Dict] = field(default_factory=list)


@dataclass
class PlansetData:
    """Complete planset document."""

    filepath: str
    total_pages: int
    pages: List[PageData] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)
