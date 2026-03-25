"""
PDF Exporter
=============
Converts the HTML planset to a printable PDF using Playwright (Chromium).
Each <div class="page"> becomes one PDF page.

Default page size follows the HTML's own @page CSS (currently 11"×8.5" landscape
= letter landscape). Pass page_size="tabloid" or "24x36" to override.

Playwright was chosen over WeasyPrint because WeasyPrint requires native
Pango/Cairo libraries that are not reliably available on macOS.

Usage:
    from engine.pdf_exporter import export_planset_pdf
    pdf_path = export_planset_pdf("/path/to/planset.html", "/tmp/planset.pdf")
    pdf_path = export_planset_pdf("/path/to/planset.html", "/tmp/planset.pdf", page_size="tabloid")
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def export_planset_pdf(
    html_path: str,
    output_pdf: str,
    page_size: str = "css",
) -> str:
    """
    Convert an HTML planset file to a multi-page PDF using Playwright.

    Args:
        html_path: Path to the source HTML planset file.
        output_pdf: Destination path for the generated PDF.
        page_size: One of:
            "css"      — respect the HTML's own @page CSS (default; currently 11"x8.5" landscape)
            "tabloid"  — 11"x17" landscape (ANSI B)
            "24x36"    — 24"x36" landscape (ARCH D)

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

    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "Playwright is not installed. Run: pip install playwright && python -m playwright install chromium"
        ) from exc

    file_url = html_path.as_uri()
    logger.info("Generating PDF: %s → %s (page_size=%s)", html_path, output_pdf, page_size)

    # Build kwargs for page.pdf()
    pdf_kwargs: dict = {
        "path": str(output_pdf),
        "print_background": True,
        "margin": {"top": "0", "right": "0", "bottom": "0", "left": "0"},
    }

    if page_size == "css":
        # Let Playwright use whatever @page rule the HTML declares
        pdf_kwargs["prefer_css_page_size"] = True
    elif page_size == "tabloid":
        # 11" × 17" landscape = 279.4 mm × 431.8 mm
        pdf_kwargs["width"] = "431.8mm"
        pdf_kwargs["height"] = "279.4mm"
    elif page_size == "24x36":
        # 24" × 36" landscape = 609.6 mm × 914.4 mm
        pdf_kwargs["width"] = "914.4mm"
        pdf_kwargs["height"] = "609.6mm"
    else:
        # Fallback: trust CSS
        pdf_kwargs["prefer_css_page_size"] = True

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()

        # Load the HTML file; networkidle ensures all images/SVGs are rendered
        page.goto(file_url, wait_until="networkidle", timeout=60_000)

        # Hide the interactive toolbar before printing
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

        page.pdf(**pdf_kwargs)
        browser.close()

    size_mb = output_pdf.stat().st_size / (1024 * 1024)
    logger.info("PDF written: %s (%.1f MB)", output_pdf, size_mb)

    return str(output_pdf)
