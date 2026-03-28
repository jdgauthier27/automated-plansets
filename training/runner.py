"""
Training Runner
================
Orchestrates the full training loop:
  1. Ingest reference planset
  2. Generate our planset for comparison
  3. Score and compare
  4. Identify gaps and generate improvements
  5. Log results

Usage:
    python -m training.runner --reference path/to/reference.pdf --our path/to/generated.html
    python -m training.runner --self-score path/to/generated.html
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from training.evaluator.content_extractor import extract_from_html, extract_from_pdf
from training.evaluator.quality_scorer import score_planset, compare_plansets
from training.evaluator.gap_analyzer import analyze_gaps

logger = logging.getLogger(__name__)

IMPROVEMENT_LOG = Path(__file__).parent / "feedback" / "improvement_log.json"


class TrainingRunner:
    """Orchestrates training cycles for planset quality improvement."""

    def __init__(self, auto_apply: bool = False):
        self.auto_apply = auto_apply
        self.history = self._load_history()

    def self_score(self, planset_path: str) -> dict:
        """Score a generated planset against the quality checklist."""
        logger.info("Self-scoring planset: %s", planset_path)
        analysis = extract_from_html(planset_path)
        report = score_planset(analysis)
        improvements = analyze_gaps(report)

        result = {
            "timestamp": datetime.now().isoformat(),
            "type": "self_score",
            "planset_path": planset_path,
            "total_pages": analysis.total_pages,
            "overall_score": report.overall_score,
            "completeness_score": report.completeness_score,
            "accuracy_score": report.accuracy_score,
            "compliance_score": report.compliance_score,
            "gaps_count": len(report.gaps),
            "improvements_count": len(improvements),
            "summary": report.summary,
            "gaps": [
                {
                    "category": g.category,
                    "severity": g.severity,
                    "description": g.description,
                    "suggestion": g.suggestion,
                }
                for g in report.gaps
            ],
            "improvements": [
                {
                    "id": imp.id,
                    "priority": imp.priority,
                    "category": imp.category,
                    "target_file": imp.target_file,
                    "description": imp.description,
                    "estimated_impact": imp.estimated_impact,
                }
                for imp in improvements
            ],
        }

        self._log_result(result)
        return result

    def compare_with_reference(self, our_path: str, reference_path: str) -> dict:
        """Compare our planset against a reference planset."""
        logger.info("Comparing: %s vs %s", our_path, reference_path)

        our_analysis = extract_from_html(our_path)

        if reference_path.endswith(".pdf"):
            ref_analysis = extract_from_pdf(reference_path)
        else:
            ref_analysis = extract_from_html(reference_path)

        report = compare_plansets(our_analysis, ref_analysis)
        improvements = analyze_gaps(report)

        result = {
            "timestamp": datetime.now().isoformat(),
            "type": "comparison",
            "our_path": our_path,
            "reference_path": reference_path,
            "our_pages": our_analysis.total_pages,
            "ref_pages": ref_analysis.total_pages,
            "overall_score": report.overall_score,
            "completeness_score": report.completeness_score,
            "accuracy_score": report.accuracy_score,
            "compliance_score": report.compliance_score,
            "gaps_count": len(report.gaps),
            "improvements_count": len(improvements),
            "summary": report.summary,
            "gaps": [
                {
                    "category": g.category,
                    "severity": g.severity,
                    "description": g.description,
                    "suggestion": g.suggestion,
                }
                for g in report.gaps
            ],
            "improvements": [
                {
                    "id": imp.id,
                    "priority": imp.priority,
                    "category": imp.category,
                    "target_file": imp.target_file,
                    "description": imp.description,
                    "estimated_impact": imp.estimated_impact,
                }
                for imp in improvements[:10]  # top 10
            ],
        }

        self._log_result(result)
        return result

    def run_training_cycle(self, reference_path: str, our_path: str) -> dict:
        """Run one full training cycle.

        1. Analyze reference
        2. Analyze our output
        3. Compare and score
        4. Generate improvement suggestions
        5. Log results
        """
        logger.info("=" * 60)
        logger.info("TRAINING CYCLE START")
        logger.info("=" * 60)

        result = self.compare_with_reference(our_path, reference_path)

        logger.info("Score: %.1f/100", result["overall_score"])
        logger.info("Gaps: %d", result["gaps_count"])
        logger.info("Top improvements:")
        for imp in result["improvements"][:5]:
            logger.info("  [%d] %s — %s", imp["priority"], imp["category"], imp["description"])

        logger.info("=" * 60)
        logger.info("TRAINING CYCLE COMPLETE — Results logged to %s", IMPROVEMENT_LOG)
        logger.info("=" * 60)

        return result

    def _load_history(self) -> list:
        if IMPROVEMENT_LOG.exists():
            with open(IMPROVEMENT_LOG) as f:
                return json.load(f)
        return []

    def _log_result(self, result: dict):
        self.history.append(result)
        IMPROVEMENT_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(IMPROVEMENT_LOG, "w") as f:
            json.dump(self.history, f, indent=2)


def main():
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    parser = argparse.ArgumentParser(description="Training loop for planset quality improvement")
    parser.add_argument("--self-score", type=str, help="Score a single planset against checklist")
    parser.add_argument("--reference", type=str, help="Reference planset (PDF or HTML)")
    parser.add_argument("--our", type=str, help="Our generated planset (HTML)")
    args = parser.parse_args()

    runner = TrainingRunner()

    if args.self_score:
        result = runner.self_score(args.self_score)
        print(f"\nScore: {result['overall_score']}/100")
        print(f"Summary: {result['summary']}")
        for gap in result["gaps"]:
            print(f"  [{gap['severity']}] {gap['description']}")

    elif args.reference and args.our:
        result = runner.run_training_cycle(args.reference, args.our)
        print(f"\nScore: {result['overall_score']}/100")
        print(f"Summary: {result['summary']}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
