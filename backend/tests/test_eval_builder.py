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


def test_stratified_sampling():
    import json

    from eval.run_eval import stratified_sample

    questions = []
    with open(QUESTIONS_FILE, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                questions.append(json.loads(line))

    sample20 = stratified_sample(questions, n=20, seed=42)
    assert len(sample20) == 20
    # Stratified guarantee: all 15 question types represented
    sampled_types = {q["type"] for q in sample20}
    all_types = {q["type"] for q in questions}
    assert sampled_types == all_types
    # Proportional patient distribution across all 10 patients
    sampled_pids = {q["patient_id"] for q in sample20}
    assert len(sampled_pids) == 10


def test_evidence_tokens_trend_derivation():
    from eval.run_eval import extract_evidence_tokens

    sample_trend = {
        "id": "q-1042-trend",
        "patient_id": "1042",
        "type": "trend",
        "expected_behavior": "answer",
        "expected_values": ["rising"],
    }
    gt_mock = {
        "1042": {
            "trends": {
                "hba1c": [
                    {"date": "2025-03-12", "value": 7.4},
                    {"date": "2026-06-18", "value": 8.9},
                ]
            }
        }
    }
    tokens = extract_evidence_tokens(sample_trend, gt_mock)
    assert tokens == [("7.4", False), ("8.9", False)]


def test_chunk_satisfies_token_with_date_metadata():
    from unittest.mock import MagicMock

    from eval.run_eval import chunk_satisfies_token

    chunk = MagicMock()
    chunk.file_id = "f-123"
    chunk.text = "Glycated Hemoglobin (HbA1c): 8.9%"

    f_obj = MagicMock()
    f_obj.date = "2026-06-18"
    files_map = {"f-123": f_obj}

    # Value token satisfied by text
    assert chunk_satisfies_token(chunk, "8.9", is_date=False, files_by_id=files_map) is True
    # Date token not in body text, but satisfied by file metadata date
    assert chunk_satisfies_token(chunk, "2026-06-18", is_date=True, files_by_id=files_map) is True
    # Different date token not satisfied
    assert chunk_satisfies_token(chunk, "2025-01-01", is_date=True, files_by_id=files_map) is False
