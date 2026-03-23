---
name: validate
description: Run planset validation against the 17001 Escalon Dr reference baseline. Generates a full planset and checks all 11 quality criteria. Use after any code change to html_renderer.py, panel_placer.py, or engine/*.py.
---

# Validate Planset Against Reference

Run the full integration test for 17001 Escalon Dr, Encino, CA and report the validation score.

## Steps

1. Run this command from the project root (`solar_planset_tool/`):

```bash
cd "/Users/jdelafontaine/Quebec Solaire/Automated plans/solar_planset_tool" && python3 -c "
import sys, os
sys.path.insert(0, '.')
os.environ.setdefault('GOOGLE_SOLAR_API_KEY', '')

from catalog.loader import EquipmentCatalog
from models.project import ProjectSpec
from html_renderer import HtmlRenderer
from panel_placer import PanelSpec, PanelPlacer, PlacementConfig
from google_solar import GoogleSolarClient, solar_insight_to_roof_faces
from pdf_parser import PlansetData, PageData

cat = EquipmentCatalog()
panel = cat.get_panel('mission-solar-mse395')
inverter = cat.get_inverter('enphase-iq8plus')
racking = cat.get_racking('ironridge-xr10')
attachment = cat.auto_select_attachment('asphalt_shingle', 'ironridge-xr10')

project = ProjectSpec(
    address='17001 Escalon Dr, Encino, CA 91436',
    country='US', municipality='Encino',
    panel=panel, inverter=inverter, racking=racking, attachment=attachment,
    num_panels=30, building_width_ft=45, building_depth_ft=53,
    company_name='Advanced Conservation', street_name='ESCALON DR',
)

client = GoogleSolarClient(api_key=os.environ.get('GOOGLE_SOLAR_API_KEY', ''))
insight = client.get_building_insight(address=project.address)
roofs, scale = solar_insight_to_roof_faces(insight)
ps = PanelSpec(name=panel.model, wattage=panel.wattage_w, width_ft=panel.width_ft, height_ft=panel.height_ft)
placer = PanelPlacer(panel=ps, config=PlacementConfig(max_panels=30))
placements = placer.place_on_roofs(roofs, scale)
vp = PageData(page_number=1, width=792, height=612, scale_factor=scale)
pd_obj = PlansetData(filepath='test', total_pages=1, pages=[vp], metadata={})
renderer = HtmlRenderer(panel_spec=ps, project=project)
output = '/tmp/validate_planset.html'
renderer.render(pd_obj, placements, output, building_insight=insight)

from tests.reference_escalon_dr import validate_output
with open(output) as f:
    html = f.read()
results = validate_output(html)
total_panels = sum(r.total_panels for r in placements)
print(f'Validation Score: {results[\"_score\"]}')
print(f'Panels placed: {total_panels}/30')
for k, v in results.items():
    if not k.startswith('_'):
        print(f'  [{\"PASS\" if v else \"FAIL\"}] {k}')
if results['_pass_rate'] < 1.0:
    print('\\nACTION NEEDED: Fix failing checks before merging.')
else:
    print('\\nAll checks passing.')
"
```

2. Report the score to the user. If any checks fail, identify the root cause.

## Reference Data
- Address: 17001 Escalon Dr, Encino, CA 91436
- Equipment: 30x Mission MSE395SX9R (395W) + 30x Enphase IQ8PLUS + IronRidge XR10
- Expected: 11/11 checks, 30 panels placed
- Reference PDF: `~/Downloads/YifeiSun_RevB-correct panel layout.pdf`
- Reference test: `tests/reference_escalon_dr.py`
