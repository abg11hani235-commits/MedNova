import importlib.util

import pytest

from app.config import ROOT, get_settings
from app.constants import REFUSAL_TEXT

from .conftest import QUOTE, REFUSAL

NEPHRO = "9001-Nephrology_Note_2026-06-18-p1"


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_patients_list(client):
    data = client.get("/patients").json()
    assert [p["id"] for p in data] == ["9001", "9002"]
    p = next(p for p in data if p["id"] == "9001")
    assert p["files"] == {"total": 3, "readable": 2}
    assert p["open_items"] == {"urgent": 1, "review": 2}


def test_brief_structure_and_sorting(client):
    b = client.get("/patients/9001/brief").json()
    assert b["coverage"] == {"total_files": 3, "readable_files": 2, "unreadable_files": 1}
    snap = b["snapshot"]
    assert [i["severity"] for i in snap] == ["urgent_review", "review", "review"]
    assert snap[0]["source"]["page"] == 1 and snap[0]["source"]["quote"] == QUOTE
    assert snap[2]["source"] is None and snap[2]["absence_note"]
    assert [p["value"] for p in b["trends"]["hba1c"]["points"]] == [8.1, 8.5, 8.9]
    assert {g["name"]: g["status"] for g in b["care_gaps"]}["Retinal exam"] == "overdue"
    assert all(c["why"] for c in b["considerations"])


def test_every_insight_has_source_or_absence_note(client):
    for i in client.get("/patients/9001/brief").json()["snapshot"]:
        assert i["source"] is not None or i["absence_note"]


def test_source_highlight_matches_quote(client):
    s = client.get(f"/patients/9001/sources/{NEPHRO}").json()
    assert s["page_text"][s["highlight"]["start"] : s["highlight"]["end"]] == s["quote"] == QUOTE


def test_patient_isolation(client):
    assert client.get(f"/patients/9002/sources/{NEPHRO}").status_code == 404
    assert client.get("/patients/9999/brief").status_code == 404


def test_chat_answers_and_refuses(client):
    ok = client.post("/patients/9001/chat", json={"question": "What was the last HbA1c?"}).json()
    assert ok["answerable"] and ok["answer"] == "8.9% on 18 Jun 2026." and ok["source"]["page"] == 2
    for q in ("Does the patient smoke?", "What is his blood type?"):
        r = client.post("/patients/9001/chat", json={"question": q}).json()
        assert r == {"answer": REFUSAL, "answerable": False, "source": None}


def test_review_actions(client):
    r = client.post("/insights/9001-F2/review", json={"action": "reviewed"}).json()
    assert r["review_state"] == "reviewed"
    r = client.post("/insights/9001-F2/review", json={"action": "helpful"}).json()
    assert r["feedback"] == "helpful" and r["review_state"] == "reviewed"
    snap = client.get("/patients/9001/brief").json()["snapshot"]
    assert next(i for i in snap if i["id"] == "9001-F2")["review_state"] == "reviewed"
    assert client.get("/patients").json()[0]["open_items"] == {"urgent": 1, "review": 1}
    assert client.post("/insights/nope/review", json={"action": "reviewed"}).status_code == 404
    assert client.post("/insights/9001-F2/review", json={"action": "bad"}).status_code == 422


def test_upload_is_queued_and_stored(client):
    r = client.post(
        "/patients/9001/files", files={"file": ("labs.pdf", b"%PDF-1.4 fake", "application/pdf")}
    )
    assert r.status_code == 200 and r.json()["status"] == "queued"
    stored = list((get_settings().storage_dir / "uploads" / "9001").glob("*labs.pdf"))
    assert len(stored) == 1


def test_audit_log_records_actions(client):
    client.get("/patients/9001/brief")
    client.get(f"/patients/9001/sources/{NEPHRO}")
    client.post("/patients/9001/chat", json={"question": "Does the patient smoke?"})
    client.post("/insights/9001-F1/review", json={"action": "reviewed"})
    client.post("/patients/9001/files", files={"file": ("a.pdf", b"x", "application/pdf")})
    actions = {a["action"] for a in client.get("/audit").json()}
    assert {"view_brief", "view_source", "chat_question", "review_reviewed", "upload"} <= actions


def test_refusal_text_matches_dataset_constant():
    path = ROOT / "data" / "constants.py"
    if not path.exists():
        pytest.skip("data/constants.py not found")
    spec = importlib.util.spec_from_file_location("data_constants", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.REFUSAL_TEXT in (
        REFUSAL_TEXT,
        "I couldn't find this in the patient's files.",
    )


def test_clean_note_hides_internal_term():
    from app.services import _clean_note

    raw = "No record in 14 readable files within 12 months of as_of_date (2026-06-18)"
    assert _clean_note(raw) == "No record in 14 readable files in the 12 months before 18 Jun 2026"
    assert _clean_note(None) is None
    assert _clean_note("Last recorded 2023") == "Last recorded 2023"


def test_clean_detail():
    from app.services import _clean_detail

    assert _clean_detail("Eye_Report_2023-11-20.pdf p.1 (dated 14 Oct 2023)") == "dated 14 Oct 2023"
    assert _clean_detail("Lab_Report_2026-05-11.pdf p.1") == "Lab_Report_2026-05-11.pdf p.1"


def test_suggested_questions_unknown_patient(client):
    assert client.get("/patients/9999/suggested-questions").status_code == 404


def test_settings_api_key_fallback():
    from app.config import Settings

    s = Settings(llm_api_key="primary", groq_api_key="secondary")
    assert s.effective_api_key == "primary"
    s2 = Settings(llm_api_key="", groq_api_key="secondary")
    assert s2.effective_api_key == "secondary"
    s3 = Settings(llm_api_key="", groq_api_key="")
    assert s3.effective_api_key == ""
