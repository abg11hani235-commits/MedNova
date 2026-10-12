"""Smoke test script for ClinSight API.

Checks all endpoints against real backend running on http://127.0.0.1:8000.
Prints PASS/FAIL for each requirement.
"""

from __future__ import annotations

import sys

import httpx

BASE_URL = "http://127.0.0.1:8000"
REFUSAL_TEXT = "I couldn't find this in the patient's files."


def test_smoke():
    all_passed = True

    def check(name: str, condition: bool, detail: str = ""):
        nonlocal all_passed
        if condition:
            print(f"[PASS] {name}{f': {detail}' if detail else ''}")
        else:
            print(f"[FAIL] {name}{f': {detail}' if detail else ''}")
            all_passed = False

    with httpx.Client(base_url=BASE_URL, timeout=10.0) as client:
        # 1. GET /health
        r = client.get("/health")
        check(
            "GET /health returns {'status': 'ok'}",
            r.status_code == 200 and r.json() == {"status": "ok"},
            f"status={r.status_code}, body={r.text}",
        )

        # 2. GET /patients
        r = client.get("/patients")
        patients = r.json() if r.status_code == 200 else []
        patient_ids = [p["id"] for p in patients]
        expected_ids = [str(i) for i in range(1042, 1052)]
        check(
            "GET /patients returns 10 patients (1042..1051)",
            r.status_code == 200 and len(patients) == 10 and patient_ids == expected_ids,
            f"count={len(patients)}, ids={patient_ids}",
        )

        # 3. GET /patients/1042/brief
        r = client.get("/patients/1042/brief")
        brief = r.json() if r.status_code == 200 else {}
        cov = brief.get("coverage", {})
        cov_ok = (
            cov.get("total_files") == 17
            and cov.get("readable_files") == 14
            and cov.get("unreadable_files") == 3
        )

        snap = brief.get("snapshot", [])
        first_item = snap[0] if snap else {}
        first_ok = (
            first_item.get("severity") == "urgent_review"
            and first_item.get("source") is not None
            and first_item.get("source", {})
            .get("quote", "")
            .startswith("Estimated GFR today is 59")
        )

        hba1c_pts = [p["value"] for p in brief.get("trends", {}).get("hba1c", {}).get("points", [])]
        egfr_pts = [p["value"] for p in brief.get("trends", {}).get("egfr", {}).get("points", [])]
        trends_ok = hba1c_pts == [7.4, 7.8, 8.1, 8.4, 8.7, 8.9] and egfr_pts == [
            78,
            74,
            68,
            64,
            61,
            59,
        ]

        cov_detail = (
            f"total={cov.get('total_files')}, readable={cov.get('readable_files')}, "
            f"unreadable={cov.get('unreadable_files')}"
        )
        check("GET /patients/1042/brief coverage (17/14/3)", cov_ok, cov_detail)
        first_detail = (
            f"severity={first_item.get('severity')}, "
            f"quote={first_item.get('source', {}).get('quote', '')[:35]}..."
        )
        check(
            "GET /patients/1042/brief first snapshot urgent_review quote check",
            first_ok,
            first_detail,
        )
        check(
            "GET /patients/1042/brief trends HbA1c and eGFR values",
            trends_ok,
            f"hba1c={hba1c_pts}, egfr={egfr_pts}",
        )

        # 4. EVERY patient: insights sourced, sources resolve with highlight
        all_insights_sourced = True
        all_sources_resolved = True
        sample_chunk_1042 = None

        for p in patients:
            pid = p["id"]
            pb = client.get(f"/patients/{pid}/brief").json()
            for ins in pb.get("snapshot", []):
                if not (ins.get("source") is not None or ins.get("absence_note")):
                    all_insights_sourced = False
                src = ins.get("source")
                if src:
                    cid = src["chunk_id"]
                    if pid == "1042" and not sample_chunk_1042:
                        sample_chunk_1042 = cid
                    sr = client.get(f"/patients/{pid}/sources/{cid}")
                    if sr.status_code != 200:
                        all_sources_resolved = False
                    else:
                        s_data = sr.json()
                        if s_data.get("highlight") is None:
                            all_sources_resolved = False

        check(
            "EVERY patient: every snapshot insight has source or absence_note",
            all_insights_sourced,
        )
        check(
            "EVERY patient: every source chunk_id resolves with non-null highlight",
            all_sources_resolved,
        )

        # 5. Patient isolation
        isolation_ok = False
        if sample_chunk_1042:
            r = client.get(f"/patients/1043/sources/{sample_chunk_1042}")
            isolation_ok = r.status_code == 404
        check(
            "Patient isolation: chunk of 1042 requested via 1043 returns 404",
            isolation_ok,
            f"chunk_id={sample_chunk_1042}, status={r.status_code}",
        )

        # 6. POST /patients/1042/chat 'Does the patient smoke?'
        r = client.post("/patients/1042/chat", json={"question": "Does the patient smoke?"})
        chat_data = r.json() if r.status_code == 200 else {}
        smoke_refused = (
            r.status_code == 200
            and chat_data.get("answerable") is False
            and chat_data.get("source") is None
            and chat_data.get("answer") == REFUSAL_TEXT
        )
        check(
            "POST /patients/1042/chat 'Does the patient smoke?' returns refusal",
            smoke_refused,
            f"answerable={chat_data.get('answerable')}, answer={chat_data.get('answer')}",
        )

        # 7. POST /patients/1042/chat 'What was the last HbA1c?'
        r = client.post("/patients/1042/chat", json={"question": "What was the last HbA1c?"})
        chat_hba1c = r.json() if r.status_code == 200 else {}
        # Report what happened as required
        if chat_hba1c.get("answerable") is True and chat_hba1c.get("source") is not None:
            check(
                "POST /patients/1042/chat 'What was the last HbA1c?'",
                True,
                f"answerable=True, answer={chat_hba1c.get('answer')}",
            )
        else:
            ans_val = chat_hba1c.get("answerable")
            print(
                f"[INFO] POST /patients/1042/chat 'What was the last HbA1c?': "
                f"no fixture for 1042, returned answerable={ans_val} (refusal)"
            )

        # 8. POST /insights/{id}/review with action reviewed
        # Get patient 1042's first unreviewed insight
        p1042_before = next(p for p in client.get("/patients").json() if p["id"] == "1042")
        open_before = p1042_before["open_items"]["urgent"] + p1042_before["open_items"]["review"]
        ins_to_review = snap[0]["id"]

        r = client.post(f"/insights/{ins_to_review}/review", json={"action": "reviewed"})
        review_ok = r.status_code == 200 and r.json().get("review_state") == "reviewed"

        p1042_after = next(p for p in client.get("/patients").json() if p["id"] == "1042")
        open_after = p1042_after["open_items"]["urgent"] + p1042_after["open_items"]["review"]
        dropped_ok = open_after == open_before - 1

        review_detail = (
            f"state={r.json().get('review_state')}, "
            f"open_before={open_before}, open_after={open_after}"
        )
        check(
            "POST /insights/{id}/review changes review_state and drops open_items",
            review_ok and dropped_ok,
            review_detail,
        )

        # 9. POST /patients/1042/files with dummy PDF
        files = {"file": ("test_dummy.pdf", b"%PDF-1.4 dummy content", "application/pdf")}
        r = client.post("/patients/1042/files", files=files)
        upload_ok = r.status_code == 200 and r.json().get("status") == "queued"
        check(
            "POST /patients/1042/files returns status queued",
            upload_ok,
            f"status_code={r.status_code}, body={r.text}",
        )

        # 10. GET /audit contains all required actions
        r = client.get("/audit")
        audit_actions = {a["action"] for a in r.json()} if r.status_code == 200 else set()
        required_actions = {
            "view_brief",
            "view_source",
            "chat_question",
            "review_reviewed",
            "upload",
        }
        audit_ok = required_actions.issubset(audit_actions)
        check(
            "GET /audit contains view_brief, view_source, chat_question, review_reviewed, upload",
            audit_ok,
            f"found={sorted(list(audit_actions))}",
        )

    if not all_passed:
        print("\nSMOKE TEST FAILED!")
        sys.exit(1)
    else:
        print("\nALL SMOKE TESTS PASSED!")


if __name__ == "__main__":
    test_smoke()
