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
