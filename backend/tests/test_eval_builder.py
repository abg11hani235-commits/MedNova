"""Unit tests for evaluation question builder and validator (eval/build_questions.py)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from eval.build_questions import load_all_chunks  # noqa: E402
from eval.validate_questions import validate_questions  # noqa: E402

QUESTIONS_FILE = ROOT / "eval" / "questions.jsonl"


def test_eval_questions_exist_and_validate():
    assert QUESTIONS_FILE.exists(), "eval/questions.jsonl does not exist."
    is_valid = validate_questions()
    assert is_valid is True, "validate_questions() failed."


def test_all_chunks_loaded():
    chunks = load_all_chunks()
    assert len(chunks) > 0, "No chunks were loaded from synthetic dataset."
    # Ensure patient 1042 chunks are present
    p1042_chunks = [cid for cid in chunks if cid.startswith("1042-")]
    assert len(p1042_chunks) > 0


def test_holdout_questions_validate():
    holdout_file = ROOT / "eval" / "holdout_questions.jsonl"
    assert holdout_file.exists(), "eval/holdout_questions.jsonl does not exist."
    assert validate_questions(holdout_file) is True


def test_validator_fails_on_patient_id(tmp_path):
    import json

    bad_file = tmp_path / "bad.jsonl"
    bad_q = {
        "id": "q-bad-pid",
        "patient_id": "1042",
        "type": "exam_date_eye",
        "expected_behavior": "answer",
        "expected_values": ["1042"],
        "gold_chunk_ids": ["1042-Eye_Report_2023-10-14-p1"],
    }
    bad_file.write_text(json.dumps(bad_q) + "\n", encoding="utf-8")
    assert validate_questions(bad_file) is False


def test_validator_fails_on_missing_gold_chunks(tmp_path):
    import json

    bad_file = tmp_path / "bad.jsonl"
    bad_q = {
        "id": "q-bad-gold",
        "patient_id": "1042",
        "type": "exam_date_eye",
        "expected_behavior": "answer",
        "expected_values": ["2023-10-14"],
        "gold_chunk_ids": [],
    }
    bad_file.write_text(json.dumps(bad_q) + "\n", encoding="utf-8")
    assert validate_questions(bad_file) is False
