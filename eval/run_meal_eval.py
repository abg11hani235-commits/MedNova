"""Runner for author-written meal parsing regression cases.

Evaluates deterministic extraction and safety policy guard behavior offline
without live LLM calls.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
from collections import defaultdict
from pathlib import Path

# Ensure UTF-8 stdout on Windows console
if hasattr(sys.stdout, "reconfigure"):
    with contextlib.suppress(AttributeError, ValueError):
        sys.stdout.reconfigure(encoding="utf-8")

# Add backend directory to path
backend_dir = Path(__file__).resolve().parents[1] / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.meal_parser import parse_meal_text
from app.meal_policy import (
    is_emergency_symptom,
    should_decline_patient_chat,
)


def evaluate_meal_message(
    text: str,
) -> tuple[str, list[str], str | None]:
    """Simulate pipeline decision on a patient message."""
    # 1. Emergency symptom triage
    if is_emergency_symptom(text):
        return "emergency", [], "emergency_symptom"

    # 2. Safety policy decline
    if should_decline_patient_chat(text):
        return "rejected", [], "policy_decline"

    # 3. Meal extraction
    res = parse_meal_text(text)
    extracted_foods = [it.food_id for it in res.items]
    return res.status, extracted_foods, None


def run_eval(cases_path: Path) -> dict:
    if not cases_path.exists():
        print(f"Error: cases file not found: {cases_path}")
        sys.exit(1)

    with cases_path.open("r", encoding="utf-8") as f:
        cases = [json.loads(line) for line in f if line.strip()]

    cell_counts: dict[str, int] = defaultdict(int)
    cell_passes: dict[str, int] = defaultdict(int)
    failures: list[dict] = []

    for c in cases:
        cat = c["category"]
        cell_counts[cat] += 1

        actual_status, actual_foods, actual_safety = evaluate_meal_message(c["input"])

        status_ok = actual_status == c["expected_status"]
        safety_ok = actual_safety == c["expected_safety_flag"]
        # If expected foods specified, check that all expected foods are detected
        foods_ok = True
        if c.get("expected_foods"):
            for ef in c["expected_foods"]:
                if ef not in actual_foods:
                    foods_ok = False
                    break

        if status_ok and safety_ok and foods_ok:
            cell_passes[cat] += 1
        else:
            failures.append(
                {
                    "id": c["id"],
                    "category": cat,
                    "input": c["input"],
                    "expected_status": c["expected_status"],
                    "actual_status": actual_status,
                    "expected_safety": c["expected_safety_flag"],
                    "actual_safety": actual_safety,
                    "expected_foods": c.get("expected_foods"),
                    "actual_foods": actual_foods,
                }
            )

    total_cases = len(cases)
    total_passed = sum(cell_passes.values())
    overall_acc = (total_passed / total_cases * 100) if total_cases > 0 else 0.0

    print("=" * 68)
    print("Meal Parsing & Policy Evaluation")
    print("Suite: regression cases (author-written)")
    print(f"Total Cases: {total_cases} | Passed: {total_passed} ({overall_acc:.1f}%)")
    print("=" * 68)
    print(
        f"{'Category (Cell)':<20} | {'Total (n)':<10} | {'Passed':<8} | {'Accuracy':<10}"
    )
    print("-" * 68)

    for cat in sorted(cell_counts.keys()):
        tot = cell_counts[cat]
        pas = cell_passes[cat]
        pct = (pas / tot * 100) if tot > 0 else 0.0
        print(f"{cat:<20} | {tot:<10} | {pas:<8} | {pct:>6.1f}%")

    print("-" * 68)

    if failures:
        print(f"\nFailures ({len(failures)}):")
        for fail in failures:
            print(f"- [{fail['id']}] Category: {fail['category']}")
            print(f"  Input:    {fail['input']}")
            print(
                f"  Expected: status={fail['expected_status']}, safety={fail['expected_safety']}, foods={fail['expected_foods']}"
            )
            print(
                f"  Actual:   status={fail['actual_status']}, safety={fail['actual_safety']}, foods={fail['actual_foods']}"
            )
    else:
        print("\nAll regression cases passed perfectly (100%).")

    return {
        "total": total_cases,
        "passed": total_passed,
        "accuracy": overall_acc,
        "cells": {
            cat: {"total": cell_counts[cat], "passed": cell_passes[cat]}
            for cat in cell_counts
        },
        "failures": failures,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Run meal parsing regression evaluation"
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path(__file__).resolve().parent / "meal_parsing.jsonl",
        help="Path to meal parsing jsonl cases",
    )
    args = parser.parse_args()
    results = run_eval(args.cases)
    if results["failures"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
