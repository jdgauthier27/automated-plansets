"""
Proposal HTML Generator
========================
Generates a customer-facing 1-page landscape proposal as a standalone HTML page,
suitable for printing or conversion to PDF via Playwright.

Layout: Letter landscape (11" × 8.5")
  Left 40%:  System overview, environmental impact, financials
  Right 60%: Monthly production bar chart + annual summary
"""

from datetime import date


def render_proposal_html(proposal_data: dict) -> str:
    """
    Render a customer solar proposal as a self-contained HTML string.

    Args:
        proposal_data: dict with keys:
            address, company_name, system_size_kw, num_panels,
            panel_model, inverter_model, annual_production_kwh,
            annual_consumption_kwh, solar_offset_pct, total_cost_usd,
            cost_per_watt, co2_offset_lbs_per_year, trees_equivalent,
            payback_years, monthly_production (dict month->kwh)

    Returns:
        Standalone HTML string (no external dependencies).
    """
    d = proposal_data
    today = d.get("date", date.today().strftime("%B %d, %Y"))

    # Monthly production bar chart
    monthly = d.get("monthly_production", {})
    months_order = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    max_kwh = max(monthly.values()) if monthly else 1

    bar_cells = ""
    for m in months_order:
        kwh = monthly.get(m, 0)
        pct = round(kwh / max_kwh * 100) if max_kwh > 0 else 0
        bar_cells += f"""
        <div class="bar-col">
          <div class="bar-val">{kwh:,}</div>
          <div class="bar-wrap">
            <div class="bar" style="height:{pct}%"></div>
          </div>
          <div class="bar-label">{m}</div>
        </div>"""

    # Financial formatting
    total_cost = d.get("total_cost_usd", 0)
    cost_per_w = d.get("cost_per_watt", 0)
    payback = d.get("payback_years", 0)

    system_kw = d.get("system_size_kw", 0)
    num_panels = d.get("num_panels", 0)
    panel_model = d.get("panel_model", "—")
    inverter_model = d.get("inverter_model", "—")

    annual_prod = d.get("annual_production_kwh", 0)
    annual_cons = d.get("annual_consumption_kwh", 0)
    offset_pct = d.get("solar_offset_pct", 0)

    co2 = d.get("co2_offset_lbs_per_year", 0)
    trees = d.get("trees_equivalent", 0)

    company = d.get("company_name", "Solar Installer")
    address = d.get("address", "")

    # 25-year savings estimate (simple: annual_prod × $0.20/kWh × 25)
    rate_per_kwh = 0.20
    annual_savings = round(annual_prod * rate_per_kwh)
    lifetime_savings = annual_savings * 25

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Solar Installation Proposal — {address}</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

  @page {{
    size: 11in 8.5in landscape;
    margin: 0;
  }}

  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
    font-size: 10px;
    color: #1a1a2e;
    background: #fff;
    width: 11in;
    height: 8.5in;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }}

  /* ── Header ── */
  .header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: #1a1a2e;
    color: #fff;
    padding: 10px 20px;
    height: 52px;
    flex-shrink: 0;
  }}
  .header-company {{
    font-size: 14px;
    font-weight: 700;
    letter-spacing: 0.5px;
  }}
  .header-title {{
    font-size: 13px;
    font-weight: 600;
    color: #f0c040;
    text-transform: uppercase;
    letter-spacing: 1px;
  }}
  .header-date {{
    font-size: 10px;
    color: #aaa;
  }}

  /* ── Address strip ── */
  .address-strip {{
    background: #f0c040;
    color: #1a1a2e;
    text-align: center;
    font-size: 10px;
    font-weight: 700;
    padding: 4px 20px;
    letter-spacing: 0.3px;
    flex-shrink: 0;
  }}

  /* ── Main body ── */
  .main {{
    display: flex;
    flex: 1;
    overflow: hidden;
    gap: 0;
  }}

  /* ── Left column ── */
  .left {{
    width: 40%;
    padding: 14px 16px;
    border-right: 2px solid #e8e8f0;
    display: flex;
    flex-direction: column;
    gap: 12px;
    overflow: hidden;
  }}

  .section-title {{
    font-size: 9px;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: #666;
    border-bottom: 1.5px solid #1a1a2e;
    padding-bottom: 3px;
    margin-bottom: 6px;
  }}

  table.spec {{
    width: 100%;
    border-collapse: collapse;
  }}
  table.spec td {{
    padding: 3px 4px;
    font-size: 9.5px;
    vertical-align: top;
    border-bottom: 1px solid #f0f0f0;
  }}
  table.spec td:first-child {{
    color: #666;
    width: 52%;
  }}
  table.spec td:last-child {{
    font-weight: 600;
    color: #1a1a2e;
    text-align: right;
  }}

  .big-number {{
    font-size: 22px;
    font-weight: 800;
    color: #1a1a2e;
    line-height: 1;
  }}
  .big-label {{
    font-size: 8px;
    color: #888;
    margin-top: 1px;
  }}
  .kpi-row {{
    display: flex;
    gap: 10px;
    margin-bottom: 4px;
  }}
  .kpi {{
    flex: 1;
    background: #f8f8fc;
    border-radius: 6px;
    padding: 7px 8px;
    border: 1px solid #e8e8f0;
  }}

  .highlight-box {{
    background: #1a1a2e;
    color: #fff;
    border-radius: 8px;
    padding: 10px 14px;
    text-align: center;
  }}
  .highlight-box .big-number {{ color: #f0c040; }}
  .highlight-box .big-label {{ color: #aaa; }}

  /* ── Right column ── */
  .right {{
    flex: 1;
    padding: 14px 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    overflow: hidden;
  }}

  /* ── Bar chart ── */
  .chart-container {{
    flex: 1;
    display: flex;
    flex-direction: column;
    min-height: 0;
  }}
  .bars {{
    display: flex;
    align-items: flex-end;
    gap: 4px;
    flex: 1;
    padding: 0 4px;
    min-height: 0;
  }}
  .bar-col {{
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    height: 100%;
  }}
  .bar-val {{
    font-size: 7px;
    color: #888;
    text-align: center;
    margin-bottom: 2px;
    writing-mode: vertical-rl;
    transform: rotate(180deg);
    height: 28px;
    overflow: hidden;
  }}
  .bar-wrap {{
    flex: 1;
    width: 100%;
    display: flex;
    align-items: flex-end;
    background: #f5f5fa;
    border-radius: 3px 3px 0 0;
    overflow: hidden;
  }}
  .bar {{
    width: 100%;
    background: linear-gradient(to top, #1a1a2e, #3a5aad);
    border-radius: 3px 3px 0 0;
    min-height: 4px;
    transition: none;
  }}
  .bar-label {{
    font-size: 8px;
    color: #888;
    text-align: center;
    margin-top: 3px;
  }}

  /* Annual summary boxes */
  .summary-row {{
    display: flex;
    gap: 10px;
  }}
  .summary-box {{
    flex: 1;
    background: #f8f8fc;
    border: 1px solid #e8e8f0;
    border-radius: 8px;
    padding: 8px 10px;
    text-align: center;
  }}
  .summary-box.accent {{
    background: #1a1a2e;
    border-color: #1a1a2e;
    color: #fff;
  }}
  .summary-box.accent .big-label {{ color: #aaa; }}
  .summary-box.accent .big-number {{ color: #f0c040; }}
  .summary-box.green {{
    background: #f0faf0;
    border-color: #4caf50;
  }}
  .summary-box.green .big-number {{ color: #2e7d32; }}

  /* ── Footer ── */
  .footer {{
    background: #f8f8fc;
    border-top: 1px solid #e0e0e8;
    text-align: center;
    font-size: 8px;
    color: #aaa;
    padding: 5px 20px;
    flex-shrink: 0;
  }}
</style>
</head>
<body>

<!-- Header -->
<div class="header">
  <div class="header-company">{company}</div>
  <div class="header-title">Solar Installation Proposal</div>
  <div class="header-date">{today}</div>
</div>

<!-- Address strip -->
<div class="address-strip">{address}</div>

<!-- Main content -->
<div class="main">

  <!-- LEFT COLUMN -->
  <div class="left">

    <!-- System Overview -->
    <div>
      <div class="section-title">System Overview</div>
      <table class="spec">
        <tr><td>Number of Panels</td><td>{num_panels} panels</td></tr>
        <tr><td>System Size</td><td>{system_kw:.2f} kW DC</td></tr>
        <tr><td>Panel Model</td><td>{panel_model}</td></tr>
        <tr><td>Inverter Model</td><td>{inverter_model}</td></tr>
      </table>
    </div>

    <!-- Environmental Impact -->
    <div>
      <div class="section-title">Environmental Impact</div>
      <div class="kpi-row">
        <div class="kpi">
          <div class="big-number">{co2:,}</div>
          <div class="big-label">lbs CO₂ offset / year</div>
        </div>
        <div class="kpi">
          <div class="big-number">{trees:,}</div>
          <div class="big-label">tree equivalent</div>
        </div>
      </div>
    </div>

    <!-- Financials -->
    <div>
      <div class="section-title">Financial Summary</div>
      <table class="spec">
        <tr><td>Total System Cost</td><td>${total_cost:,.0f}</td></tr>
        <tr><td>Cost per Watt</td><td>${cost_per_w:.2f}/W</td></tr>
        <tr><td>Est. Annual Savings</td><td>${annual_savings:,}/yr</td></tr>
        <tr><td>25-Year Savings</td><td>${lifetime_savings:,}</td></tr>
      </table>
    </div>

    <!-- Payback highlight -->
    <div class="highlight-box">
      <div class="big-number">{payback:.1f} yrs</div>
      <div class="big-label">Estimated Payback Period</div>
    </div>

  </div>

  <!-- RIGHT COLUMN -->
  <div class="right">

    <!-- Monthly Production Chart -->
    <div class="chart-container">
      <div class="section-title">Monthly Solar Production (kWh)</div>
      <div class="bars">
        {bar_cells}
      </div>
    </div>

    <!-- Annual Summary -->
    <div class="summary-row">
      <div class="summary-box accent">
        <div class="big-number">{annual_prod:,}</div>
        <div class="big-label">Annual Production (kWh)</div>
      </div>
      <div class="summary-box">
        <div class="big-number">{annual_cons:,}</div>
        <div class="big-label">Annual Consumption (kWh)</div>
      </div>
      <div class="summary-box green">
        <div class="big-number">{offset_pct:.0f}%</div>
        <div class="big-label">Solar Offset</div>
      </div>
    </div>

  </div>
</div>

<!-- Footer -->
<div class="footer">
  This proposal is an estimate. Actual production may vary based on weather, shading, system losses, and utility rate changes. &nbsp;|&nbsp; {company}
</div>

</body>
</html>"""

    return html
