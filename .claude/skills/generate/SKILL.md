---
name: generate
description: Generate a complete solar planset for a given address. Uses GeoTIFF roof extraction, rotated panel placement, and dynamic equipment catalog. Pass an address as the argument.
---

# Generate Solar Planset

Generate a complete permit-ready solar planset for a given address using the full pipeline.

## Arguments
- First argument: the address (e.g., "17001 Escalon Dr, Encino, CA 91436")
- Optional: panel count, panel model, inverter model

## Steps

1. Parse the address from the user's input.

2. Determine the country from the address:
   - If contains state abbreviation (CA, TX, NY, etc.) or "USA" → country = "US"
   - If contains province (QC, ON, BC, etc.) or "Canada" → country = "CA"

3. Try GeoTIFF-based roof extraction first (requires GOOGLE_SOLAR_API_KEY):
```python
from engine.geotiff_roof import get_roof_faces_from_geotiff, get_building_outline
roofs, scale = get_roof_faces_from_geotiff(lat, lng, api_key)
outline = get_building_outline(lat, lng, api_key)
```

4. Fall back to buildingInsights if GeoTIFF fails:
```python
from google_solar import GoogleSolarClient, solar_insight_to_roof_faces
client = GoogleSolarClient(api_key=api_key)
insight = client.get_building_insight(address=address)
roofs, scale = solar_insight_to_roof_faces(insight)
```

5. Load equipment from catalog (default or user-specified):
```python
from catalog.loader import EquipmentCatalog
cat = EquipmentCatalog()
panel = cat.get_panel('mission-solar-mse395')  # or user choice
inverter = cat.get_inverter('enphase-iq8plus')  # or user choice
racking = cat.get_racking('ironridge-xr10')
attachment = cat.auto_select_attachment('asphalt_shingle', racking.id)
```

6. Place panels using the rotated grid placer:
```python
from panel_placer import PanelSpec, PanelPlacer, PlacementConfig
ps = PanelSpec(name=panel.model, wattage=panel.wattage_w, width_ft=panel.width_ft, height_ft=panel.height_ft)
placer = PanelPlacer(panel=ps, config=PlacementConfig(max_panels=30, setback_ft=3, orientation='portrait'))
placements = placer.place_on_roofs(roofs, scale)
```

7. Build ProjectSpec and render:
```python
from models.project import ProjectSpec
from html_renderer import HtmlRenderer
project = ProjectSpec(address=address, country=country, ...)
renderer = HtmlRenderer(panel_spec=ps, project=project)
renderer.render(pd_obj, placements, output_path, building_insight=insight)
```

8. Report results: panel count, system size (kW), output file path.

## Equipment Catalog IDs
- Panels: `longi-himo7-455`, `canadian-solar-hiku7-440`, `mission-solar-mse395`
- Inverters: `solis-s6-eh1p5k`, `hoymiles-hms-800`, `enphase-iq8plus`
- Racking: `ironridge-xr10`, `k2-crossrail-48x`

## Output
- HTML planset saved to `/tmp/planset_<address_slug>.html`
- Open in browser to review before PDF conversion
