"""Unit tests for deterministic facts extractor and clinical router (app/rag/facts.py)."""

from pathlib import Path

from app.constants import REFUSAL_TEXT
from app.models import Chunk
from app.rag.facts import answer_from_facts, extract_patient_facts
from app.seed import chunk_id, split_pages


def _load_1042_chunks() -> list[Chunk]:
    chunks: list[Chunk] = []
    data_dir = Path(__file__).resolve().parents[2] / "data" / "synthetic" / "1042"
    for f in sorted(data_dir.glob("*.txt")):
        if f.stem.startswith("Scanned_"):
            continue
        text = f.read_text(encoding="utf-8")
        for page_num, page_text in split_pages(text):
            cid = chunk_id("1042", f.stem, page_num)
            chunks.append(
                Chunk(
                    id=cid,
                    patient_id="1042",
                    file_id=f"1042-{f.stem}",
                    page=page_num,
                    text=page_text,
                )
            )
    return chunks


def test_facts_extractor_patient_1042():
    """Verify that facts extractor on patient 1042 extracts exact HbA1c and eGFR sequences."""
    chunks = _load_1042_chunks()
    assert len(chunks) > 0, "No chunks found for patient 1042."

    facts = extract_patient_facts(chunks)

    # 1. Verify HbA1c values: [7.4, 7.8, 8.1, 8.4, 8.7, 8.9]
    hba1c_facts = sorted([f for f in facts if f.concept == "hba1c"], key=lambda x: x.date)
    hba1c_values = [f.value for f in hba1c_facts]
    assert hba1c_values == [7.4, 7.8, 8.1, 8.4, 8.7, 8.9], (
        f"Unexpected HbA1c values: {hba1c_values}"
    )

    for f in hba1c_facts:
        assert f.quote != "", "Quote must not be empty"
        assert f.date != "", "Date must not be empty"
        assert f.chunk_id != "", "Chunk ID must not be empty"

    # 2. Verify eGFR values: [78, 74, 68, 64, 61, 59]
    egfr_facts = sorted([f for f in facts if f.concept == "egfr"], key=lambda x: x.date)
    egfr_values = [f.value for f in egfr_facts]
    assert egfr_values == [78, 74, 68, 64, 61, 59], f"Unexpected eGFR values: {egfr_values}"

    for f in egfr_facts:
        assert f.quote != "", "Quote must not be empty"
        assert f.date != "", "Date must not be empty"
        assert f.chunk_id != "", "Chunk ID must not be empty"


def test_facts_router_queries():
    chunks = _load_1042_chunks()
    facts = extract_patient_facts(chunks)

    # Test last_value in English (decides purely from question text)
    ans_last = answer_from_facts("1042", "What is the last HbA1c?", facts, chunks)
    assert ans_last is not None
    assert ans_last["answerable"] is True
    assert "8.9" in ans_last["answer"]
    assert len(ans_last["citations"]) == 1

    # Test last_value in Arabic (decides purely from question text)
    ans_last_ar = answer_from_facts("1042", "ما هي آخر قراءة مسجلة لـ HbA1c للمريض؟", facts, chunks)
    assert ans_last_ar is not None
    assert ans_last_ar["answerable"] is True
    assert "8.9" in ans_last_ar["answer"]

    # Test trend (decides purely from question text)
    ans_trend = answer_from_facts("1042", "What is the trend of HbA1c?", facts, chunks)
    assert ans_trend is not None
    assert "rising" in ans_trend["answer"]
    assert len(ans_trend["citations"]) == 2

    # Test absence (UACR is missing for patient 1042, decides purely from question text)
    ans_absent = answer_from_facts("1042", "What is the UACR value?", facts, chunks)
    assert ans_absent is not None
    assert ans_absent["answerable"] is False
    assert REFUSAL_TEXT in ans_absent["answer"]
    assert "Searched for UACR" in ans_absent["answer"]
