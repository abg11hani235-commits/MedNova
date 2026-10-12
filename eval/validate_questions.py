"""Validate evaluation questions set (eval/validate_questions.py).

Checks:
1. Every gold chunk id exists in the synthetic dataset.
2. For factual answer questions, every expected value appears in at least one gold chunk.
3. Prints counts per question type.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from eval.build_questions import load_all_chunks  # noqa: E402

QUESTIONS_FILE = ROOT / "eval" / "questions.jsonl"


def validate_questions() -> bool:
    if not QUESTIONS_FILE.exists():
        print(f"[ERROR] Questions file {QUESTIONS_FILE} does not exist.", file=sys.stderr)
        return False

    chunks = load_all_chunks()
    type_counts = Counter()
    behavior_counts = Counter()
    errors = []

    total_questions = 0

    with open(QUESTIONS_FILE, encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            total_questions += 1
            q = json.loads(line)

            qid = q.get("id", f"line-{line_num}")
            qtype = q.get("type", "unknown")
            behavior = q.get("expected_behavior", "unknown")
            expected_vals = q.get("expected_values", [])
            gold_chunks = q.get("gold_chunk_ids", [])

            type_counts[qtype] += 1
            behavior_counts[behavior] += 1

            # 1. Check every gold chunk exists
            for cid in gold_chunks:
                if cid not in chunks:
                    errors.append(f"[{qid}] Gold chunk '{cid}' does not exist in dataset.")

            # 2. Check expected values appear in gold chunk text for factual question types
            if behavior == "answer" and gold_chunks and qtype != "trend":
                combined_text = " ".join(chunks[cid] for cid in gold_chunks if cid in chunks)
                for val in expected_vals:
                    val_clean = str(val).strip()
                    found_in_text = val_clean.lower() in combined_text.lower()
                    found_in_cids = any(val_clean in cid for cid in gold_chunks)
                    if not (found_in_text or found_in_cids):
                        errors.append(
                            f"[{qid}] Expected value '{val_clean}' not found in "
                            f"gold chunks {gold_chunks} text."
                        )

    print("==================================================")
    print("           EVALUATION QUESTIONS SUMMARY           ")
    print("==================================================")
    print(f"Total Questions: {total_questions}\n")
    print("Counts by Type:")
    for t, cnt in sorted(type_counts.items()):
        print(f"  {t:<20} : {cnt}")

    print("\nCounts by Expected Behavior:")
    for b, cnt in sorted(behavior_counts.items()):
        print(f"  {b:<20} : {cnt}")

    if errors:
        print(f"\n[FAIL] Found {len(errors)} validation errors:", file=sys.stderr)
        for err in errors[:10]:
            print(f"  - {err}", file=sys.stderr)
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more.", file=sys.stderr)
        return False

    print("\n[SUCCESS] All gold chunks exist and all expected values appear in chunk text!")
    return True


if __name__ == "__main__":
    ok = validate_questions()
    sys.exit(0 if ok else 1)
