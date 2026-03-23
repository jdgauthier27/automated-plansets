"""
Gap Analyzer
=============
Analyzes quality gaps and produces actionable improvement recommendations.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List

from training.evaluator.quality_scorer import QualityReport, GapItem

logger = logging.getLogger(__name__)


@dataclass
class Improvement:
    """A concrete improvement action to apply."""
    id: str
    priority: int           # 1=highest
    category: str           # "add_page", "add_content", "fix_layout", "add_notes"
    target_file: str        # which page builder or template to modify
    description: str
    details: str            # specific change to make
    estimated_impact: float # expected score improvement (0-15)


def analyze_gaps(report: QualityReport) -> List[Improvement]:
    """Convert quality gaps into concrete improvement actions.

    Args:
        report: QualityReport from the quality scorer.

    Returns:
        List of Improvement actions sorted by priority.
    """
    improvements = []
    priority = 1

    for gap in report.gaps:
        if gap.severity == "critical":
            imp = _gap_to_improvement(gap, priority)
            imp.estimated_impact = 15.0
            improvements.append(imp)
            priority += 1

    for gap in report.gaps:
        if gap.severity == "major":
            imp = _gap_to_improvement(gap, priority)
            imp.estimated_impact = 8.0
            improvements.append(imp)
            priority += 1

    for gap in report.gaps:
        if gap.severity == "minor":
            imp = _gap_to_improvement(gap, priority)
            imp.estimated_impact = 3.0
            improvements.append(imp)
            priority += 1

    logger.info("Generated %d improvement actions from %d gaps",
                len(improvements), len(report.gaps))
    return improvements


def _gap_to_improvement(gap: GapItem, priority: int) -> Improvement:
    """Convert a single gap into an improvement action."""
    category = "add_content"
    target_file = "renderer/page_builders/"

    if "Missing" in gap.description and "page" in gap.description.lower():
        category = "add_page"
    elif "code reference" in gap.description.lower():
        category = "add_notes"
        target_file = "jurisdiction/"
    elif "equipment" in gap.description.lower():
        category = "add_content"
        target_file = "catalog/"
    elif "title block" in gap.description.lower():
        category = "fix_layout"
        target_file = "renderer/title_block.py"

    return Improvement(
        id=f"imp-{priority:03d}",
        priority=priority,
        category=category,
        target_file=target_file,
        description=gap.description,
        details=gap.suggestion or f"Address: {gap.description}",
        estimated_impact=0,
    )
