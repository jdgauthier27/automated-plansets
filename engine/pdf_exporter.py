"""
PDF Exporter
=============
Converts the HTML planset to a printable PDF using Playwright (Chromium).
Each <div class="page"> becomes one PDF page at 17×11" landscape (tabloid).

Playwright was chosen over WeasyPrint because WeasyPrint requires native
Pango/Cairo libraries that are not reliably available on macOS.

Usage:
    from engine.pdf_exporter import export_planset_pdf
    pdf_path = export_planset_pdf("/path/to/planset.html", "/tmp/planset.pdf")
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def export_planset_pdf(
    html_path: str,
    output_pdf: str,
    page_size: str = "17x11",
) -> str:
    """
    Convert an HTML planset file to a multi-page PDF using Playwright.

    Args:
        html_path: Path to the source HTML planset file.
        output_pdf: Destination path for the generated PDF.
        page_size: "17x11" (tabloid landscape, default) or "24x36" (ARCH D).

    Returns:
        Absolute path to the generated PDF.

    Raises:
        FileNotFoundError: If html_path does not exist.
        RuntimeError: If PDF generation fails.
    """
    html_path = Path(html_path).resolve()
    if not html_path.exists():
        raise FileNotFoundError(f"HTML planset not found: {html_path}")

    output_pdf = Path(output_pdf).resolve()
    output_pdf.parent.mkdir(parents=True, exist_ok=True)

    # Page dimensions in inches
    if page_size == "24x36":
        width_in, height_in = 36.0, 24.0   # ARCH D landscape
    else:
        width_in, height_in = 17.0, 11.0   # Tabloid landscape (11"x17")

    # Convert inches → mm for Playwright's page size
    width_mm  = width_in  * 25.4
    height_mm = height_in * 25.4

    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "Playwright is not installed. Run: pip install playwright && python -m playwright install chromium"
        ) from exc

    file_url = html_path.as_uri()
    logger.info("Generating PDF: %s → %s", html_path, output_pdf)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()

        # Load the HTML file; wait until network is idle so images finish loading
        page.goto(file_url, wait_until="networkidle", timeout=60_000)

        # Inject print-mode CSS so the @media print rules activate
        page.add_style_tag(content="""
            #export-toolbar { display: none !important; }
            .page {
                margin: 0 !important;
                box-shadow: none !important;
                page-break-after: always;
                page-break-inside: avoid;
                overflow: hidden;
            }
        """)

        page.pdf(
            path=str(output_pdf),
            width=f"{width_mm}mm",
            height=f"{height_mm}mm",
            print_background=True,
            margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
        )
        browser.close()

    size_mb = output_pdf.stat().st_size / (1024 * 1024)
    logger.info("PDF written: %s (%.1f MB)", output_pdf, size_mb)

    return str(output_pdf)
