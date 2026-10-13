import json
import os
import tempfile
from pathlib import Path

os.environ["STORAGE_PATH"] = tempfile.mkdtemp(prefix="rafiq-storage-")
os.environ["DATABASE_URL"] = "sqlite://"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.config import ROOT, get_settings  # noqa: E402
from app.constants import REFUSAL_TEXT  # noqa: E402
from app.db import get_db, make_engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402
from app.seed import seed_all  # noqa: E402

get_settings.cache_clear()


QUOTE = "Estimated GFR today is 59 mL/min/1.73m², down from 78 at the first visit in March 2025."
REFUSAL = REFUSAL_TEXT


def _trend(key: str, values: list[float], unit: str) -> list[dict]:
    dates = ["2026-01-10", "2026-03-18", "2026-06-18"]
    return [
        {"date": d, "label": d[5:7] + "/" + d[2:4], "value": v, "unit": unit}
        for d, v in zip(dates, values, strict=False)
    ]


def build_fixture(root: Path) -> Path:
    """A tiny dataset in the same shape as /data (two fictional patients)."""
    (root / "ground_truth").mkdir(parents=True)
    gt1 = {
        "patient_id": "9001",
        "as_of_date": "2026-06-18",
        "demographics": {
            "age": 58,
            "diabetes_type": "Type 2",
            "duration_years": 12,
            "medications": ["Metformin"],
        },
        "planted_findings": [
            {
                "id": "F1",
                "type": "falling_egfr",
                "severity": "urgent_review",
                "statement": "eGFR fell from 78 to 59 over 3 visits. Worth reviewing.",
                "source_file": "Nephrology_Note_2026-06-18.pdf",
                "page": 1,
                "quote": QUOTE,
            },
            {
                "id": "F2",
                "type": "rising_hba1c",
                "severity": "review",
                "statement": "HbA1c has risen across 3 visits. Worth reviewing.",
                "source_file": "Lab_Report_2026-06-18.pdf",
                "page": 2,
                "quote": "HbA1c: 8.9%",
            },
            {
                "id": "F3",
                "type": "missing_uacr",
                "severity": "review",
                "statement": "No urine albumin-creatinine ratio found in the last 12 months.",
                "source_file": None,
                "page": None,
                "quote": None,
            },
        ],
        "care_gaps": [
            {
                "name": "Retinal exam",
                "status": "overdue",
                "evidence": "Eye report 2023",
                "absence_note": None,
            },
            {
                "name": "Foot exam",
                "status": "done",
                "evidence": "Foot examination completed.",
                "absence_note": None,
            },
            {
                "name": "Urine albumin-creatinine ratio (UACR)",
                "status": "missing",
                "evidence": None,
                "absence_note": "No record in 12 months",
            },
        ],
        "trends": {
            "hba1c": _trend("hba1c", [8.1, 8.5, 8.9], "%"),
            "egfr": _trend("egfr", [78, 66, 59], "mL/min/1.73m²"),
        },
        "chat_questions": [
            {
                "question": "What was the last HbA1c?",
                "answerable": True,
                "expected_answer_summary": "8.9% on 18 Jun 2026.",
                "source_file": "Lab_Report_2026-06-18.pdf",
                "page": 2,
            },
            {
                "question": "Does the patient smoke?",
                "answerable": False,
                "expected_answer_summary": REFUSAL,
                "source_file": None,
                "page": None,
            },
        ],
    }
    gt2 = {
        "patient_id": "9002",
        "as_of_date": "2026-06-18",
        "demographics": {
            "age": 46,
            "diabetes_type": "Type 1",
            "duration_years": 20,
            "medications": ["Insulin"],
        },
        "planted_findings": [
            {
                "id": "F1",
                "type": "rising_hba1c",
                "severity": "review",
                "statement": "HbA1c is above range. Worth reviewing.",
                "source_file": "Lab_Report_2026-05-01.pdf",
                "page": 1,
                "quote": "HbA1c: 9.1%",
            },
        ],
        "care_gaps": [],
        "trends": {"hba1c": _trend("hba1c", [8.8, 9.0, 9.1], "%"), "egfr": []},
        "chat_questions": [],
    }
    for gt in (gt1, gt2):
        (root / "ground_truth" / f"{gt['patient_id']}.json").write_text(
            json.dumps(gt), encoding="utf-8"
        )
    d1, d2 = root / "synthetic" / "9001", root / "synthetic" / "9002"
    d1.mkdir(parents=True)
    d2.mkdir(parents=True)
    (d1 / "Nephrology_Note_2026-06-18.txt").write_text(
        f"=== PAGE 1 ===\nReason for visit: follow-up.\n{QUOTE}\n", encoding="utf-8"
    )
    (d1 / "Lab_Report_2026-06-18.txt").write_text(
        "=== PAGE 1 ===\nGlucose 120\n=== PAGE 2 ===\nHbA1c: 8.9%\neGFR: 59\n", encoding="utf-8"
    )
    (d1 / "Scanned_Referral_Cover_Sheet.txt").write_text(
        "=== PAGE 1 ===\n[UNREADABLE SCANNED DOCUMENT - OCR REQUIRED]\n", encoding="utf-8"
    )
    (d2 / "Lab_Report_2026-05-01.txt").write_text("=== PAGE 1 ===\nHbA1c: 9.1%\n", encoding="utf-8")
    return root


@pytest.fixture()
def db_session(tmp_path):
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    seed_all(session, build_fixture(tmp_path / "data"))
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def client(db_session):
    def override():
        yield db_session

    app.dependency_overrides[get_db] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def real_data_dir():
    d = ROOT / "data"
    if not (d / "ground_truth" / "1042.json").exists():
        pytest.skip("synthetic dataset not found in /data")
    return d
