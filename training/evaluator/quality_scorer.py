"""
Quality Scorer
==============
Scores a generated planset against a reference planset or quality checklist.
Produces a QualityReport with specific gap items and suggested fixes.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from training.evaluator.content_extractor import PlansetAnalysis

logger = logging.getLogger(__name__)


@dataclass
class GapItem:
    """A specific quality gap identified during comparison."""
    category: str           # "completeness", "accuracy", "layout", "compliance"
    severity: str           # "critical", "major", "minor"
    description: str
    page: Optional[str] = None  # which page is affected
    suggestion: str = ""


@dataclass
class QualityReport:
    """Quality assessment result."""
    overall_score: float = 0.0          # 0-100
    completeness_score: float = 0.0     # 0-100
    accuracy_score: float = 0.0         # 0-100
    compliance_score: float = 0.0       # 0-100
    gaps: List[GapItem] = field(default_factory=list)
    summary: str = ""


# Required pages for a complete planset
REQUIRED_PAGES = [
    "cover", "site_plan", "single_line", "electrical_calcs",
    "signage", "module_datasheet", "racking_datasheet",
]

# Required quality indicators
QUALITY_CHECKLIST = {
    "has_cover": ("Cover page present", 10),
    "has_site_plan": ("Site plan with panel layout", 15),
    "has_sld": ("Single-line diagram", 15),
    "has_electrical_calcs": ("Electrical calculations page", 15),
    "has_signage": ("Safety signage/labels page", 10),
    "has_module_datasheet": ("Module specification datasheet", 10),
    "has_racking_datasheet": ("Racking specification datasheet", 5),
    "has_title_blocks": ("Title blocks on all pages", 10),
    "page_count_adequate": ("Minimum 11 pages", 10),
}


def score_planset(analysis: PlansetAnalysis) -> QualityReport:
    """Score a planset based on quality checklist.

    Args:
        analysis: PlansetAnalysis from content extractor.

    Returns:
        QualityReport with scores and specific gaps.
    """
    report = QualityReport()

    # ── Completeness scoring ────────────────────────────────────────────
    completeness_points = 0
    completeness_max = 0
    for indicator, (desc, points) in QUALITY_CHECKLIST.items():
        completeness_max += points
        if analysis.quality_indicators.get(indicator, False):
            completeness_points += points
        else:
            report.gaps.append(GapItem(
                category="completeness",
                severity="major" if points >= 10 else "minor",
                description=f"Missing: {desc}",
                suggestion=f"Add {desc.lower()} to the planset.",
            ))
    report.completeness_score = (completeness_points / completeness_max * 100) if completeness_max > 0 else 0

    # ── Compliance scoring ──────────────────────────────────────────────
    code_refs = set(analysis.codes_referenced)
    compliance_checks = {
        "CEC or NEC referenced": any("CEC" in c or "NEC" in c or "NFPA" in c for c in code_refs),
        "Fire code referenced": any("IFC" in c for c in code_refs),
        "Equipment standards (UL)": any("UL" in c for c in code_refs),
    }
    compliance_pass = sum(1 for v in compliance_checks.values() if v)
    compliance_total = len(compliance_checks)
    report.compliance_score = (compliance_pass / compliance_total * 100) if compliance_total > 0 else 0

    for check, passes in compliance_checks.items():
        if not passes:
            report.gaps.append(GapItem(
                category="compliance",
                severity="major",
                description=f"Missing code reference: {check}",
                suggestion=f"Add {check} references to governing codes section.",
            ))

    # ── Accuracy scoring ────────────────────────────────────────────────
    # Check that equipment specs are consistent across pages
    equipment = analysis.equipment_found
    if len(equipment) > 0:
        report.accuracy_score = 90.0  # base score when equipment is referenced
    else:
        report.accuracy_score = 50.0
        report.gaps.append(GapItem(
            category="accuracy",
            severity="critical",
            description="No equipment references found in planset",
            suggestion="Ensure panel, inverter, and racking models appear on relevant pages.",
        ))

    # ── Overall score ───────────────────────────────────────────────────
    report.overall_score = round(
        report.completeness_score * 0.4 +
        report.accuracy_score * 0.3 +
        report.compliance_score * 0.3,
        1
    )

    # Summary
    critical = sum(1 for g in report.gaps if g.severity == "critical")
    major = sum(1 for g in report.gaps if g.severity == "major")
    minor = sum(1 for g in report.gaps if g.severity == "minor")
    report.summary = (
        f"Score: {report.overall_score}/100 "
        f"({critical} critical, {major} major, {minor} minor gaps)"
    )

    logger.info("Quality score: %.1f/100 — %s", report.overall_score, report.summary)
    return report


def compare_plansets(generated: PlansetAnalysis, reference: PlansetAnalysis) -> QualityReport:
    """Compare a generated planset against a reference planset.

    Identifies content present in the reference but missing from generated.
    """
    report = score_planset(generated)

    # Compare page types
    gen_types = {p.page_type for p in generated.pages}
    ref_types = {p.page_type for p in reference.pages}
    missing_types = ref_types - gen_types - {"unknown"}

    for ptype in missing_types:
        report.gaps.append(GapItem(
            category="completeness",
            severity="major",
            description=f"Reference has '{ptype}' page but generated planset does not",
            suggestion=f"Add a {ptype.replace('_', ' ')} page to the planset.",
        ))

    # Compare page counts
    if generated.total_pages < reference.total_pages:
        report.gaps.append(GapItem(
            category="completeness",
            severity="minor",
            description=f"Generated has {generated.total_pages} pages vs reference {reference.total_pages}",
            suggestion="Consider adding additional detail pages.",
        ))

    # Compare equipment coverage
    ref_equipment = set(reference.equipment_found.keys())
    gen_equipment = set(generated.equipment_found.keys())
    for eq in ref_equipment - gen_equipment:
        report.gaps.append(GapItem(
            category="accuracy",
            severity="minor",
            description=f"Reference mentions '{eq}' but generated does not",
        ))

    # Recalculate overall score
    critical = sum(1 for g in report.gaps if g.severity == "critical")
    major = sum(1 for g in report.gaps if g.severity == "major")
    penalty = critical * 15 + major * 5
    report.overall_score = max(0, report.overall_score - penalty)
    report.summary = (
        f"Comparison score: {report.overall_score:.1f}/100 "
        f"({critical} critical, {major} major, {len(report.gaps) - critical - major} minor gaps)"
    )

    return report
