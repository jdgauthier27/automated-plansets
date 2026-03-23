"""
Page builder modules — one per planset sheet.
==============================================

Each module exposes a single top-level ``build_*`` function that returns
an HTML ``<div class="page">`` string containing the full SVG for that sheet.

Modules will be added incrementally as methods are extracted from
html_renderer.py:

  cover.py              -> build_cover_page          (PV-1)
  property_plan.py      -> build_property_plan_page  (PV-2)
  site_plan.py          -> build_site_plan_page      (PV-3)
  site_plan_satellite.py-> build_site_plan_satellite  (PV-3 alt)
  racking_plan.py       -> build_racking_plan_page   (PV-3.1)
  string_plan.py        -> build_string_plan_page    (PV-7)
  single_line.py        -> build_single_line_diagram (PV-4)
  electrical_calcs.py   -> build_electrical_calcs     (PV-4.1)
  signage.py            -> build_signage_page        (PV-5/PV-6)
  placard_house.py      -> build_placard_house_page  (PV-6.1)
  mounting_details.py   -> build_mounting_details     (PV-5)
  module_datasheet.py   -> build_module_datasheet     (PV-8.1)
  racking_datasheet.py  -> build_racking_datasheet    (PV-8.2)
  attachment_datasheet.py -> build_attachment_datasheet (PV-8.3)
"""
