"""
Planset Renderer (PDF Output)
==============================
Converts the HTML planset to PDF format using weasyprint or similar.
Currently a stub — HTML is the primary output format.

Future: install weasyprint and render HTML → PDF for AHJ submission.
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def render_pdf(html_path: str, output_path: Optional[str] = None) -> str:
    """
    Convert an HTML planset to PDF.

    Requires weasyprint: pip install weasyprint

    Args:
        html_path: Path to the HTML planset file
        output_path: Path for PDF output (default: same name with .pdf)

    Returns:
        Path to the generated PDF file
    """
    if output_path is None:
        output_path = str(Path(html_path).with_suffix(".pdf"))

    try:
        from weasyprint import HTML

        HTML(filename=html_path).write_pdf(output_path)
        logger.info("Generated PDF: %s", output_path)
        return output_path
    except ImportError:
        logger.warning(
            "weasyprint not installed. Install with: pip install weasyprint\nHTML planset saved at: %s", html_path
        )
        return html_path
    except Exception as e:
        logger.error("PDF generation failed: %s", e)
        return html_path
