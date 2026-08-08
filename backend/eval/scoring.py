"""
Eval harness — runs the rule engine against synthetic fixtures and
computes precision, recall, and F1.
"""
from __future__ import annotations
import os
import sys
from pathlib import Path
from typing import List

# Allow importing from backend root when run as a script
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from analysis.parser.ast_parser import analyse_file

# ── Ground truth: expected rule_ids per fixture ──────────────────────────────
FIXTURES_DIR = _ROOT.parent / "fixtures"

GROUND_TRUTH: dict[str, set[str]] = {
    "pr_001_hardcoded_secret.py": {"SEC001"},
    "pr_002_sql_injection.py":    {"SEC003"},
    "pr_003_long_method.py":      {"CS001"},
    "pr_004_n_plus_one.py":       {"CS001"},      # long method wrapping the loop
    "pr_005_layer_violation.py":  {"CS004"},      # unusual import
}


def run_eval() -> List[dict]:
    results = []
    for fixture_name, expected_rules in GROUND_TRUTH.items():
        fixture_path = FIXTURES_DIR / fixture_name
        if not fixture_path.exists():
            continue

        source = fixture_path.read_text(encoding="utf-8")
        findings = analyse_file(source, str(fixture_path))

        found_rules = {f.rule_id for f in findings}
        tp = len(expected_rules & found_rules)
        fp = len(found_rules - expected_rules)
        fn = len(expected_rules - found_rules)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1        = (2 * precision * recall / (precision + recall)
                     if (precision + recall) > 0 else 0.0)

        results.append({
            "fixture_name": fixture_name,
            "precision":    round(precision, 4),
            "recall":       round(recall, 4),
            "f1":           round(f1, 4),
            "true_positives":  tp,
            "false_positives": fp,
            "false_negatives": fn,
        })
        print(f"[EVAL] {fixture_name}: P={precision:.2f} R={recall:.2f} F1={f1:.2f}")

    return results


if __name__ == "__main__":
    print("Running eval harness…")
    for r in run_eval():
        print(r)
