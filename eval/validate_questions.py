"""Validate evaluation questions set (eval/validate_questions.py).

Checks:
1. Every gold chunk id exists in the synthetic dataset.
2. For questions with expected_behavior == 'answer', gold_chunk_ids must not be empty.
3. Expected values must never equal patient id.
4. Expected values must not appear in the header/prefix of every chunk for that patient.
5. For factual answer questions, every expected value must appear in at least one GOLD chunk (using shared normalization).
6. Prints counts per question type and all offending question IDs on failure.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from app.constants import REFUSAL_TEXT

from eval.build_questions import load_all_chunks
from eval.normalize import value_matches

DEFAULT_QUESTIONS_FILE = ROOT / "eval" / "questions.jsonl"


def validate_questions(questions_path: Path | str = DEFAULT_QUESTIONS_FILE) -> bool:
    q_path = Path(questions_path)
    if not q_path.exists():
        print(f"[ERROR] Questions file {q_path} does not exist.", file=sys.stderr)
        return False

    chunks = load_all_chunks()
    # Group chunk ids by patient
    patient_chunks: dict[str, list[str]] = defaultdict(list)
    for cid in chunks:
        pid = cid.split("-")[0]
        patient_chunks[pid].append(cid)

    type_counts = Counter()
    behavior_counts = Counter()
    errors: list[str] = []
    offending_qids: set[str] = set()

    total_questions = 0

    with open(q_path, encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            total_questions += 1
            q = json.loads(line)

            qid = q.get("id", f"line-{line_num}")
            pid = str(q.get("patient_id", "")).strip()
            qtype = q.get("type", "unknown")
            behavior = q.get("expected_behavior", "unknown")
            expected_vals = q.get("expected_values", [])
            gold_chunks = q.get("gold_chunk_ids", [])

            type_counts[qtype] += 1
            behavior_counts[behavior] += 1

            # 1. Check every gold chunk exists
            for cid in gold_chunks:
                if cid not in chunks:
                    errors.append(
                        f"[{qid}] Gold chunk '{cid}' does not exist in dataset."
                    )
                    offending_qids.add(qid)

            # 2. Check gold_chunk_ids is non-empty for answerable questions
            if behavior == "answer" and not gold_chunks:
                errors.append(
                    f"[{qid}] gold_chunk_ids is empty for an answerable question."
                )
                offending_qids.add(qid)

            # 3. Check expected values do not equal patient ID
            for val in expected_vals:
                val_str = str(val).strip()
                if pid and val_str == pid:
                    errors.append(
                        f"[{qid}] Expected value '{val_str}' equals patient id '{pid}'."
                    )
                    offending_qids.add(qid)

            # 4. Check expected value does not appear in header/prefix of every chunk
            p_cids = patient_chunks.get(pid, [])
            if p_cids and behavior == "answer":
                for val in expected_vals:
                    val_str = str(val).strip()
                    if val_str and val_str != REFUSAL_TEXT:
                        in_all = all(value_matches(val_str, chunks[c]) for c in p_cids)
                        if in_all:
                            errors.append(
                                f"[{qid}] Expected value '{val_str}' appears in header/prefix "
                                f"of every chunk ({len(p_cids)} chunks) for patient {pid}."
                            )
                            offending_qids.add(qid)

            # 5. Check expected values appear in GOLD chunk text (not just any chunk)
            if behavior == "answer" and gold_chunks and qtype != "trend":
                combined_gold_text = " ".join(
                    chunks[cid] for cid in gold_chunks if cid in chunks
                )
                for val in expected_vals:
                    val_clean = str(val).strip()
                    if not value_matches(val_clean, combined_gold_text):
                        errors.append(
                            f"[{qid}] Expected value '{val_clean}' not found in "
                            f"gold chunks {gold_chunks} text."
                        )
                        offending_qids.add(qid)

    print("==================================================")
    print(f"       VALIDATION SUMMARY: {q_path.name}")
    print("==================================================")
    print(f"Total Questions: {total_questions}\n")
    print("Counts by Type:")
    for t, cnt in sorted(type_counts.items()):
        print(f"  {t:<20} : {cnt}")

    print("\nCounts by Expected Behavior:")
    for b, cnt in sorted(behavior_counts.items()):
        print(f"  {b:<20} : {cnt}")

    if errors:
        print(
            f"\n[FAIL] Found {len(errors)} validation errors across {len(offending_qids)} questions:",
            file=sys.stderr,
        )
        print(f"Offending Question IDs ({len(offending_qids)}):", file=sys.stderr)
        for offending in sorted(offending_qids):
            print(f"  - {offending}", file=sys.stderr)
        print("\nError Details:", file=sys.stderr)
        for err in errors[:15]:
            print(f"  * {err}", file=sys.stderr)
        if len(errors) > 15:
            print(f"  ... and {len(errors) - 15} more errors.", file=sys.stderr)
        return False

    print(
        "\n[SUCCESS] All checks passed: valid gold chunks, values in gold text, no patient ID or header matches!"
    )
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate evaluation question set.")
    parser.add_argument(
        "file",
        nargs="?",
        default=str(DEFAULT_QUESTIONS_FILE),
        help="Questions jsonl file",
    )
    args = parser.parse_args()

    ok = validate_questions(args.file)
    sys.exit(0 if ok else 1)
