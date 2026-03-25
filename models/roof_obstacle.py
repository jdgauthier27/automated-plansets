"""
RoofObstacle — Roof penetration obstacle with exclusion zone.

Per NEC 690.12, a minimum 18-inch clearance is required around roof obstacles
such as vents, skylights, chimneys, and HVAC equipment.

The width_ft and height_ft fields should already include the 18-inch clearance
on each side (i.e., actual_obstacle_width + 2 * 1.5 ft).
"""

from dataclasses import dataclass


@dataclass
class RoofObstacle:
    """A roof obstacle with its bounding exclusion zone.

    Coordinates are in the roof-local frame (feet from origin of the roof face).
    The placer maps these to page coordinates using the same pts_per_ft scale.

    Args:
        x_ft:          Center x position on roof face (ft from left edge).
        y_ft:          Center y position on roof face (ft from bottom edge).
        width_ft:      Total exclusion width including 18" clearance on each side.
        height_ft:     Total exclusion height including 18" clearance on each side.
        obstacle_type: One of 'vent', 'skylight', 'chimney', 'hvac'.
    """
    x_ft: float
    y_ft: float
    width_ft: float
    height_ft: float
    obstacle_type: str = "vent"
