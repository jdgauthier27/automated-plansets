"""
Page builder modules — one per planset sheet.
==============================================

Each module exposes a single top-level ``build_*`` function that returns
an HTML ``<div class="page">`` string containing the full SVG for that sheet.

15-page reference structure:
  cover_page.py            -> build_cover_page                  (T-00)
  electrical_notes.py      -> build_electrical_notes_page       (G-01)
  site_plan_vector.py      -> build_site_plan_page              (A-101)
  racking_plan.py          -> build_racking_plan_page           (A-102)
  string_plan.py           -> build_string_plan_page            (A-103)
  mounting_details.py      -> build_mounting_details_page       (A-104)
  single_line_diagram.py   -> build_single_line_diagram         (E-601)
  electrical_calcs.py      -> build_electrical_calcs_page       (E-602)
  signage.py               -> build_signage_page                (E-603)
  placard_house.py         -> build_placard_house_page          (E-604)
  module_datasheet.py      -> build_module_datasheet_page       (R-001)
  inverter_datasheet.py    -> build_inverter_datasheet_page     (R-002)
  combiner_datasheet.py    -> build_combiner_datasheet_page     (R-003)
  racking_datasheet.py     -> build_racking_datasheet_page      (R-004)
  attachment_datasheet.py  -> build_attachment_datasheet_page   (R-005)

Helper modules (not standalone pages):
  site_plan_satellite.py   -> build_site_plan_satellite         (used by site_plan_vector)
  single_line_tables.py    -> (tables used by single_line_diagram)
  racking_plan_details.py  -> build_racking_bottom_band         (used by racking_plan)
"""

from renderer.page_builders.cover_page import build_cover_page
from renderer.page_builders.electrical_notes import build_electrical_notes_page
from renderer.page_builders.site_plan_vector import build_site_plan_page
from renderer.page_builders.racking_plan import build_racking_plan_page
from renderer.page_builders.string_plan import build_string_plan_page
from renderer.page_builders.mounting_details import build_mounting_details_page
from renderer.page_builders.single_line_diagram import build_single_line_diagram
from renderer.page_builders.electrical_calcs import build_electrical_calcs_page
from renderer.page_builders.signage import build_signage_page
from renderer.page_builders.placard_house import build_placard_house_page
from renderer.page_builders.module_datasheet import build_module_datasheet_page
from renderer.page_builders.inverter_datasheet import build_inverter_datasheet_page
from renderer.page_builders.combiner_datasheet import build_combiner_datasheet_page
from renderer.page_builders.racking_datasheet import build_racking_datasheet_page
from renderer.page_builders.attachment_datasheet import build_attachment_datasheet_page

__all__ = [
    "build_cover_page",
    "build_electrical_notes_page",
    "build_site_plan_page",
    "build_racking_plan_page",
    "build_string_plan_page",
    "build_mounting_details_page",
    "build_single_line_diagram",
    "build_electrical_calcs_page",
    "build_signage_page",
    "build_placard_house_page",
    "build_module_datasheet_page",
    "build_inverter_datasheet_page",
    "build_combiner_datasheet_page",
    "build_racking_datasheet_page",
    "build_attachment_datasheet_page",
]
