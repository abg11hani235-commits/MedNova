"""Runs only when the synthetic dataset exists in /data (not in CI without it)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.db import get_db, make_engine
from app.main import app
from app.models import Base
from app.seed import seed_all


@pytest.fixture()
def real_client(real_data_dir):
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    seed_all(session, real_data_dir)

    def override():
        yield session

    app.dependency_overrides[get_db] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    session.close()


def test_all_ten_patients_seeded(real_client):
    ids = [p["id"] for p in real_client.get("/patients").json()]
    assert ids == [str(i) for i in range(1042, 1052)]


def test_patient_1042_matches_ui_demo(real_client):
    b = real_client.get("/patients/1042/brief").json()
    assert b["coverage"] == {"total_files": 17, "readable_files": 14, "unreadable_files": 3}
    assert [p["value"] for p in b["trends"]["hba1c"]["points"]] == [7.4, 7.8, 8.1, 8.4, 8.7, 8.9]
    assert [p["value"] for p in b["trends"]["egfr"]["points"]] == [78, 74, 68, 64, 61, 59]
    assert b["snapshot"][0]["severity"] == "urgent_review"
    assert "Estimated GFR today is 59" in b["snapshot"][0]["source"]["quote"]


def test_every_sourced_finding_resolves_to_a_chunk(real_client):
    for p in real_client.get("/patients").json():
        for i in real_client.get(f"/patients/{p['id']}/brief").json()["snapshot"]:
            assert i["source"] is not None or i["absence_note"], (p["id"], i["id"])
            if i["source"]:
                s = real_client.get(f"/patients/{p['id']}/sources/{i['source']['chunk_id']}").json()
                assert s["highlight"] is not None, (p["id"], i["id"])


def test_unanswerable_questions_are_refused(real_client):
    r = real_client.post("/patients/1042/chat", json={"question": "Does the patient smoke?"}).json()
    assert r["answerable"] is False and r["source"] is None


def test_suggested_questions(real_client):
    for pid in ("1042", "1044"):
        res = real_client.get(f"/patients/{pid}/suggested-questions")
        assert res.status_code == 200
        items = res.json()
        assert len(items) == 3
        assert all(isinstance(q, str) and q.strip() for q in items)
    assert real_client.get("/patients/9999/suggested-questions").status_code == 404
