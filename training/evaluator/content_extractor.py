"""
Content Extractor
=================
Extracts structured data from planset PDFs (or HTML files).
Classifies content blocks and builds a PlansetAnalysis.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PageAnalysis:
    """Analysis of a single planset page."""

    page_number: int = 0
    page_type: str = ""  # "cover", "site_plan", "sld", "datasheet", etc.
    title: str = ""
    sheet_id: str = ""  # "PV-1", "PV-4", etc.
    has_title_block: bool = False
    tables: List[Dict] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    equipment_refs: List[str] = field(default_factory=list)
    code_refs: List[str] = field(default_factory=list)
    dimensions_present: bool = False
    has_north_arrow: bool = False
    has_scale_bar: bool = False
    text_blocks: List[str] = field(default_factory=list)


@dataclass
class PlansetAnalysis:
    """Complete analysis of a reference planset."""

    source_path: str = ""
    total_pages: int = 0
    pages: List[PageAnalysis] = field(default_factory=list)
    equipment_found: Dict[str, str] = field(default_factory=dict)
    codes_referenced: List[str] = field(default_factory=list)
    jurisdiction: str = ""
    quality_indicators: Dict[str, bool] = field(default_factory=dict)


# Page type classification patterns
PAGE_TYPE_PATTERNS = {
    "cover": ["cover", "title sheet", "general notes", "sheet index"],
    "property_plan": ["property plan", "lot plan", "survey", "parcel"],
    "site_plan": ["site plan", "roof plan", "aerial", "satellite"],
    "racking_plan": ["racking", "framing plan", "mounting layout"],
    "single_line": ["single line", "single-line", "sld", "one-line", "electrical schematic"],
    "electrical_calcs": ["electrical calc", "design calc", "conductor schedule"],
    "mounting_details": ["mounting detail", "cross section", "attachment detail"],
    "signage": ["signage", "placard", "label", "safety sign", "warning label"],
    "circuit_map": ["circuit map", "string plan", "wiring diagram"],
    "module_datasheet": ["module data", "panel spec", "module spec", "pv module"],
    "racking_datasheet": ["racking data", "rail spec", "mounting spec"],
    "attachment_datasheet": ["attachment data", "flashfoot", "roof attachment", "mount spec"],
}


def classify_page(text: str) -> str:
    """Classify a page type from its text content."""
    text_lower = text.lower()
    for page_type, patterns in PAGE_TYPE_PATTERNS.items():
        for pattern in patterns:
            if pattern in text_lower:
                return page_type
    return "unknown"


def extract_from_html(html_path: str) -> PlansetAnalysis:
    """Extract structured content from a generated HTML planset.

    This analyzes our own output to enable comparison with references.
    """
    path = Path(html_path)
    if not path.exists():
        raise FileNotFoundError(f"Planset not found: {html_path}")

    html_content = path.read_text(encoding="utf-8")
    analysis = PlansetAnalysis(source_path=html_path)

    # Split by page breaks (our HTML uses page-break-after or specific div markers)
    # Each page is wrapped in a div with class containing "page" or has page-break
    pages = re.split(r'<div[^>]*class="[^"]*page[^"]*"[^>]*>', html_content)
    if len(pages) <= 1:
        # Try splitting by page-break-after
        pages = re.split(r"page-break-after:\s*always", html_content)

    analysis.total_pages = max(1, len(pages) - 1)  # first split is header

    for i, page_html in enumerate(pages[1:], 1):
        page = PageAnalysis(page_number=i)

        # Extract text content (strip HTML tags)
        text = re.sub(r"<[^>]+>", " ", page_html)
        text = re.sub(r"\s+", " ", text).strip()

        # Classify page type
        page.page_type = classify_page(text)

        # Find sheet ID (e.g., "PV-1", "S-2", "E-601")
        sheet_match = re.search(r"(PV-\d+\.?\d*|S-\d+|E-\d+|T-\d+|A-\d+)", text)
        if sheet_match:
            page.sheet_id = sheet_match.group(1)

        # Check for title block
        page.has_title_block = bool(re.search(r"DRAWN BY|SHEET|REVISION", text, re.IGNORECASE))

        # Find equipment references
        equipment_patterns = [
            r"LONGi\s+Hi-MO\s+\d+",
            r"Canadian\s+Solar\s+\w+",
            r"Enphase\s+IQ\d+\w*",
            r"Hoymiles\s+HMS-?\d+",
            r"Solis\s+S\d+",
            r"IronRidge\s+XR\d+",
            r"K2\s+CrossRail",
            r"FlashFoot\d*",
        ]
        for pattern in equipment_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            page.equipment_refs.extend(matches)

        # Find code references
        code_patterns = [
            r"CEC\s+(CSA\s+)?C22\.\d+",
            r"NEC\s+\d+",
            r"NFPA\s+70",
            r"IFC\s+\d+",
            r"UL\s+\d+",
            r"IEEE\s+\d+",
            r"CEC\s+Rule\s+\d+-\d+",
            r"NEC\s+\d+\.\d+",
        ]
        for pattern in code_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            page.code_refs.extend(matches)

        # Extract notes
        note_matches = re.findall(r"\d+\.\s+[A-Z][^.]+\.", text)
        page.notes = note_matches[:20]  # cap at 20

        page.text_blocks = [text[:500]]  # first 500 chars for context

        analysis.pages.append(page)

    # Aggregate equipment and codes across all pages
    all_equipment = set()
    all_codes = set()
    for page in analysis.pages:
        all_equipment.update(page.equipment_refs)
        all_codes.update(page.code_refs)

    analysis.equipment_found = {eq: "detected" for eq in all_equipment}
    analysis.codes_referenced = sorted(all_codes)

    # Quality indicators
    page_types_found = {p.page_type for p in analysis.pages}
    analysis.quality_indicators = {
        "has_cover": "cover" in page_types_found,
        "has_site_plan": "site_plan" in page_types_found,
        "has_sld": "single_line" in page_types_found,
        "has_electrical_calcs": "electrical_calcs" in page_types_found,
        "has_signage": "signage" in page_types_found,
        "has_module_datasheet": "module_datasheet" in page_types_found,
        "has_racking_datasheet": "racking_datasheet" in page_types_found,
        "has_title_blocks": all(p.has_title_block for p in analysis.pages),
        "page_count_adequate": analysis.total_pages >= 11,
    }

    logger.info(
        "Analyzed planset: %d pages, %d equipment refs, %d code refs",
        analysis.total_pages,
        len(all_equipment),
        len(all_codes),
    )

    return analysis


def extract_from_pdf(pdf_path: str) -> PlansetAnalysis:
    """Extract structured content from a reference PDF planset.

    Requires PyMuPDF (fitz) for PDF text extraction.
    Falls back to basic analysis if not available.
    """
    analysis = PlansetAnalysis(source_path=pdf_path)

    try:
        import fitz  # PyMuPDF

        doc = fitz.open(pdf_path)
        analysis.total_pages = len(doc)

        for i, page in enumerate(doc):
            text = page.get_text()
            page_analysis = PageAnalysis(page_number=i + 1)
            page_analysis.page_type = classify_page(text)

            # Find sheet ID
            sheet_match = re.search(r"(PV-\d+\.?\d*|S-\d+|E-\d+)", text)
            if sheet_match:
                page_analysis.sheet_id = sheet_match.group(1)

            page_analysis.has_title_block = bool(re.search(r"DRAWN BY|SHEET", text, re.IGNORECASE))
            page_analysis.text_blocks = [text[:500]]
            analysis.pages.append(page_analysis)

        doc.close()

    except ImportError:
        logger.warning("PyMuPDF (fitz) not installed — PDF extraction limited. Install with: pip install PyMuPDF")
        analysis.total_pages = 0

    return analysis
