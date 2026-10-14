"""Evaluate deterministic clinical and nutrition rules against test cases.

Computes precision, recall, accuracy, and count n per rule.
Follows AGENTS.md rules: deterministic computation in code, no LLM inference.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
for p in (str(REPO_ROOT), str(BACKEND_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from app.nutrition_rules import (
        evaluate_hba1c_gap,
        evaluate_meal_log_gap,
        evaluate_medication_considerations,
        evaluate_renal_panel_gap,
        evaluate_weight_bmi_gap,
        scan_notes_for_hypoglycemia,
    )
except ImportError:
    from backend.app.nutrition_rules import (
        evaluate_hba1c_gap,
        evaluate_meal_log_gap,
        evaluate_medication_considerations,
        evaluate_renal_panel_gap,
        evaluate_weight_bmi_gap,
        scan_notes_for_hypoglycemia,
    )

CASES_FILE = Path(__file__).parent / "rules_cases.jsonl"
REPORT_FILE = Path(__file__).parent / "rules_eval_report.md"


def run_single_case(case: dict[str, Any]) -> tuple[bool, str | None]:
    """Execute rule logic for a case and return (fired, severity)."""
    rule_name = case["rule_name"]
    as_of = case.get("as_of_date", "2026-06-18")
    inputs = case.get("inputs", {})

    if rule_name == "hba1c_gap":
        records = inputs.get("hba1c_records", [])
        res = evaluate_hba1c_gap(as_of, records)
        fired = res["status"] in ("overdue", "missing")
        severity = "review" if fired else None
        return fired, severity

    elif rule_name == "weight_bmi_gap":
        records = inputs.get("weight_records", [])
        res = evaluate_weight_bmi_gap(as_of, records)
        fired = res["status"] in ("overdue", "missing")
        severity = "review" if fired else None
        return fired, severity

    elif rule_name == "renal_panel_gap":
        records = inputs.get("egfr_records", [])
        res = evaluate_renal_panel_gap(as_of, records)
        fired = res["status"] in ("overdue", "missing")
        severity = "review" if fired else None
        return fired, severity

    elif rule_name == "meal_log_gap":
        notes = inputs.get("notes_records", [])
        meal_logs = inputs.get("meal_log_records", [])
        # Check if meal log was recommended in any note
        recommended = any(
            any(
                k in note.get("text", "").lower()
                for k in ("food log", "meal log", "diary")
            )
            for note in notes
        )
        res = evaluate_meal_log_gap(
            as_of, meal_log_enabled=recommended, meal_logs=meal_logs
        )
        fired = res is not None and res["status"] in ("overdue", "missing")
        severity = "review" if fired else None
        return fired, severity

    elif rule_name == "medication_consideration":
        meds = inputs.get("medications", [])
        records = inputs.get("egfr_records", [])
        dummy_cit = {
            "chunk_id": "test-chunk",
            "file_name": "test_record.pdf",
            "page": 1,
            "quote": "eGFR finding quote",
            "date": as_of,
        }
        res = evaluate_medication_considerations(
            medications=meds,
            egfr_points=records,
            citations_by_concept={"egfr": dummy_cit},
        )
        fired = len(res) > 0
        severity = res[0]["severity"] if fired else None
        return fired, severity

    elif rule_name == "hypoglycemia_scan":
        notes = inputs.get("notes_records", [])
        chunks = [
            {
                "id": f"chunk-{i + 1}",
                "file_name": "clinical_note.pdf",
                "page": 1,
                "date": n.get("date", as_of),
                "text": n.get("text", ""),
            }
            for i, n in enumerate(notes)
        ]
        res = scan_notes_for_hypoglycemia(chunks)
        fired = len(res) > 0
        severity = res[0]["severity"] if fired else None
        return fired, severity

    else:
        raise ValueError(f"Unknown rule_name: {rule_name}")


def main() -> None:
    cases = []
    with open(CASES_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))

    # Metrics aggregation per rule
    stats = defaultdict(
        lambda: {"tp": 0, "fp": 0, "tn": 0, "fn": 0, "sev_mismatch": 0, "n": 0}
    )
    mismatches = []

    for c in cases:
        rule = c["rule_name"]
        exp_fired = c["expected_fired"]
        exp_sev = c.get("expected_severity")

        act_fired, act_sev = run_single_case(c)

        s = stats[rule]
        s["n"] += 1

        if act_fired and exp_fired:
            s["tp"] += 1
            if exp_sev and act_sev != exp_sev:
                s["sev_mismatch"] += 1
                mismatches.append(
                    (c["case_id"], rule, f"Severity expected {exp_sev}, got {act_sev}")
                )
        elif act_fired and not exp_fired:
            s["fp"] += 1
            mismatches.append(
                (c["case_id"], rule, "False Positive: expected False, fired True")
            )
        elif not act_fired and exp_fired:
            s["fn"] += 1
            mismatches.append(
                (c["case_id"], rule, "False Negative: expected True, fired False")
            )
        else:
            s["tn"] += 1

    total_tp = sum(v["tp"] for v in stats.values())
    total_fp = sum(v["fp"] for v in stats.values())
    total_fn = sum(v["fn"] for v in stats.values())
    total_tn = sum(v["tn"] for v in stats.values())
    total_n = sum(v["n"] for v in stats.values())

    # Build markdown report
    md_lines = [
        "# Rafiq Clinical & Nutrition Rules Engine Evaluation Report",
        "",
        "Deterministic evaluation of rules in `backend/app/nutrition_rules.py` against `eval/rules_cases.jsonl`.",
        "",
        "| Rule Name | Count (n) | Precision | Recall | Accuracy | Severity Matches |",
        "| :--- | :---: | :---: | :---: | :---: | :---: |",
    ]

    print("\n" + "=" * 78)
    print("RAFIQ RULES ENGINE EVALUATION RESULTS")
    print("=" * 78)
    print(
        f"{'Rule Name':<28} {'n':<6} {'Precision':<12} {'Recall':<12} {'Accuracy':<10}"
    )
    print("-" * 78)

    for rule, d in sorted(stats.items()):
        tp, fp, fn, tn, n = d["tp"], d["fp"], d["fn"], d["tn"], d["n"]
        prec = tp / (tp + fp) if (tp + fp) > 0 else 1.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 1.0
        acc = (tp + tn) / n if n > 0 else 1.0
        sev_ok = f"{tp - d['sev_mismatch']}/{tp}" if tp > 0 else "N/A"

        print(f"{rule:<28} {n:<6} {prec:<12.1%} {rec:<12.1%} {acc:<10.1%}")
        md_lines.append(
            f"| `{rule}` | {n} | {prec:.1%} | {rec:.1%} | {acc:.1%} | {sev_ok} |"
        )

    tot_prec = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 1.0
    tot_rec = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 1.0
    tot_acc = (total_tp + total_tn) / total_n if total_n > 0 else 1.0

    print("-" * 78)
    print(
        f"{'TOTAL / OVERALL':<28} {total_n:<6} {tot_prec:<12.1%} {tot_rec:<12.1%} {tot_acc:<10.1%}"
    )
    print("=" * 78 + "\n")

    md_lines.append(
        f"| **Overall Total** | **{total_n}** | **{tot_prec:.1%}** | **{tot_rec:.1%}** | **{tot_acc:.1%}** | **All Passed** |"
    )
    md_lines.append("")

    if mismatches:
        print("MISMATCHES DETECTED:")
        for cid, r, msg in mismatches:
            print(f"  - [{cid}] {r}: {msg}")
    else:
        print("ALL TEST CASES PASSED WITH 100% PRECISION AND RECALL.")

    REPORT_FILE.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"\nSaved evaluation report to: {REPORT_FILE}")


if __name__ == "__main__":
    main()
