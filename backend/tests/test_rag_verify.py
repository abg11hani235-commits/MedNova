"""Unit tests for deterministic citation verifier (app/rag/verify.py)."""

from app.constants import REFUSAL_TEXT
from app.models import Chunk
from app.rag.verify import apply_verifier, verify_claims


def make_chunk(cid: str, pid: str, text: str) -> Chunk:
    return Chunk(id=cid, patient_id=pid, file_id=f"{pid}-file", page=1, text=text)


def test_valid_claim():
    chunk = make_chunk(
        "c1",
        "1042",
        "Glycated Hemoglobin (HbA1c): 8.9% (Reference: <5.7%)",
    )
    chunks_map = {"c1": chunk}

    claims = [
        {
            "text": "The patient's last HbA1c is 8.9%.",
            "chunk_id": "c1",
            "quote": "Glycated Hemoglobin (HbA1c): 8.9%",
        }
    ]

    surviving, citations, valid = verify_claims("1042", claims, chunks_map)
    assert valid is True
    assert len(surviving) == 1
    assert len(citations) == 1
    assert citations[0]["chunk_id"] == "c1"

    res = apply_verifier(
        "1042", {"answerable": True, "answer": "Last HbA1c is 8.9%.", "claims": claims}, chunks_map
    )
    assert res["answerable"] is True
    assert res["answer"] == "Last HbA1c is 8.9%."


def test_wrong_patient_chunk():
    # Chunk belongs to patient 1043, but query is for 1042
    chunk = make_chunk(
        "c-other",
        "1043",
        "Glycated Hemoglobin (HbA1c): 7.2%",
    )
    chunks_map = {"c-other": chunk}

    claims = [
        {
            "text": "The patient's HbA1c is 7.2%.",
            "chunk_id": "c-other",
            "quote": "Glycated Hemoglobin (HbA1c): 7.2%",
        }
    ]

    surviving, citations, valid = verify_claims("1042", claims, chunks_map)
    assert valid is False
    assert len(surviving) == 0

    res = apply_verifier(
        "1042", {"answerable": True, "answer": "HbA1c is 7.2%.", "claims": claims}, chunks_map
    )
    assert res["answerable"] is False
    assert res["answer"] == REFUSAL_TEXT


def test_fabricated_quote():
    chunk = make_chunk(
        "c1",
        "1042",
        "Estimated GFR today is 59 mL/min/1.73m², down from 78.",
    )
    chunks_map = {"c1": chunk}

    # Quote does not appear in chunk text
    claims = [
        {
            "text": "eGFR is perfectly normal at 95.",
            "chunk_id": "c1",
            "quote": "Estimated GFR today is 95 mL/min",
        }
    ]

    surviving, citations, valid = verify_claims("1042", claims, chunks_map)
    assert valid is False
    assert len(surviving) == 0

    res = apply_verifier(
        "1042",
        {"answerable": True, "answer": "Normal at 95.", "claims": claims},
        chunks_map,
    )
    assert res["answerable"] is False
    assert res["answer"] == REFUSAL_TEXT


def test_wrong_number_in_claim():
    chunk = make_chunk(
        "c1",
        "1042",
        "Glycated Hemoglobin (HbA1c): 8.9%",
    )
    chunks_map = {"c1": chunk}

    # Claim introduces hallucinated number 11.5 not in quote or chunk
    claims = [
        {
            "text": "HbA1c reached a critical level of 11.5%.",
            "chunk_id": "c1",
            "quote": "Glycated Hemoglobin (HbA1c): 8.9%",
        }
    ]

    surviving, citations, valid = verify_claims("1042", claims, chunks_map)
    assert valid is False
    assert len(surviving) == 0

    res = apply_verifier(
        "1042",
        {"answerable": True, "answer": "HbA1c is 11.5%.", "claims": claims},
        chunks_map,
    )
    assert res["answerable"] is False
    assert res["answer"] == REFUSAL_TEXT


def test_check_credentials_logic(monkeypatch):
    from app.config import get_settings
    from app.rag.llm import check_credentials

    s = get_settings()
    monkeypatch.setattr(s, "llm_api_key", "")
    monkeypatch.setattr(s, "groq_api_key", "")
    ok, msg = check_credentials()
    assert not ok
    assert "Neither LLM_API_KEY nor GROQ_API_KEY" in msg
