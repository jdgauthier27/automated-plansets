"""
Page builder modules — one per planset sheet.
==============================================

Each module exposes a single top-level ``build_*`` function that returns
an HTML ``<div class="page">`` string containing the full SVG for that sheet.

Extracted modules:
  cover_page.py            -> build_cover_page                  (PV-1 / T-00)
  cover_sheet.py           -> build_cover_sheet_page            (A-100)
  property_plan.py         -> build_property_plan_page          (PV-2 / A-101)
  site_plan.py             -> build_site_plan_page              (PV-3)
  racking_plan.py          -> build_racking_plan_page           (PV-3.1 / A-102)
  single_line_diagram.py   -> build_single_line_diagram         (PV-4 / E-601)
  electrical_calcs.py      -> build_electrical_calcs_page       (PV-4.1)
  mounting_details.py      -> build_mounting_details_page       (PV-5)
  signage.py               -> build_signage_page                (PV-6)
  placard_house.py         -> build_placard_house_page          (PV-6.1)
  string_plan.py           -> build_string_plan_page            (PV-7)
  module_datasheet.py      -> build_module_datasheet_page       (PV-8.1)
  racking_datasheet.py     -> build_racking_datasheet_page      (PV-8.2)
  attachment_datasheet.py  -> build_attachment_datasheet_page    (PV-8.3)
  single_line_a200.py      -> build_single_line_diagram_page    (A-200)
  electrical_details.py    -> build_electrical_details_page      (A-300)
"""

from renderer.page_builders.cover_page import build_cover_page
from renderer.page_builders.cover_sheet import build_cover_sheet_page
from renderer.page_builders.property_plan import build_property_plan_page
from renderer.page_builders.site_plan import build_site_plan_page
from renderer.page_builders.racking_plan import build_racking_plan_page
from renderer.page_builders.single_line_diagram import build_single_line_diagram
from renderer.page_builders.electrical_calcs import build_electrical_calcs_page
from renderer.page_builders.mounting_details import build_mounting_details_page
from renderer.page_builders.signage import build_signage_page
from renderer.page_builders.placard_house import build_placard_house_page
from renderer.page_builders.string_plan import build_string_plan_page
from renderer.page_builders.module_datasheet import build_module_datasheet_page
from renderer.page_builders.racking_datasheet import build_racking_datasheet_page
from renderer.page_builders.attachment_datasheet import build_attachment_datasheet_page
from renderer.page_builders.single_line_a200 import build_single_line_diagram_page
from renderer.page_builders.electrical_details import build_electrical_details_page

__all__ = [
    "build_cover_page",
    "build_cover_sheet_page",
    "build_property_plan_page",
    "build_site_plan_page",
    "build_racking_plan_page",
    "build_single_line_diagram",
    "build_electrical_calcs_page",
    "build_mounting_details_page",
    "build_signage_page",
    "build_placard_house_page",
    "build_string_plan_page",
    "build_module_datasheet_page",
    "build_racking_datasheet_page",
    "build_attachment_datasheet_page",
    "build_single_line_diagram_page",
    "build_electrical_details_page",
]
