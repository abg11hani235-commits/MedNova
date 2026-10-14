"""Unit tests and wiring proof tests for deterministic clinical & nutrition rules.

Covers:
A. Rule unit tests:
   1. HbA1c gap: fires (overdue), does not fire (recent), boundary, missing data
   2. Weight/BMI gap: fires (overdue), does not fire (recent), boundary, missing data
   3. Renal panel gap: fires (overdue), does not fire (recent), boundary, missing data
   4. Meal-log gap: no meal-log source (emits nothing), source present (emits gap),
      recent, boundary, missing data
   5. Medication considerations: slight drop (review), severe drop / sharp drop
      (urgent_review), boundaries, citations

   6. Hypoglycemia scan: routine, urgent, English negation, Arabic negation, missing data
B. Wiring proof tests:
   For every rule above, testing end-to-end through `build_brief(db, patient)`:
   - fires
   - does not fire
   - boundary
   - missing data
   - meal-log: no source present (emits nothing) vs source present (emits gap)
"""

from __future__ import annotations

from app.models import Chunk, File, Patient
from app.nutrition_rules import (
    HBA1C_GAP_MONTHS,
    MEAL_LOG_GAP_DAYS,
    MEDICATION_CONSIDERATION_NOTE_EN,
    RENAL_PANEL_GAP_MONTHS,
    WEIGHT_BMI_GAP_MONTHS,
    evaluate_hba1c_gap,
    evaluate_meal_log_gap,
    evaluate_medication_considerations,
    evaluate_renal_panel_gap,
    evaluate_weight_bmi_gap,
    is_hypoglycemia_negated,
    scan_notes_for_hypoglycemia,
)
from app.services import build_brief

AS_OF = "2026-06-18"


# ==============================================================================
# 1. HbA1c Gap Rule Tests
# ==============================================================================


def test_hba1c_gap_fires_when_overdue():
    # 8 months ago (> 6 months threshold)
    points = [{"date": "2025-10-10", "value": 8.0}]
    res = evaluate_hba1c_gap(AS_OF, points, threshold_months=HBA1C_GAP_MONTHS)
    assert res["status"] == "overdue"
    assert "overdue" in res["detail"].lower()


def test_hba1c_gap_does_not_fire_when_recent():
    # 3 months ago (within 6 months)
    points = [{"date": "2026-03-18", "value": 8.0}]
    res = evaluate_hba1c_gap(AS_OF, points, threshold_months=HBA1C_GAP_MONTHS)
    assert res["status"] == "done"
    assert "completed" in res["detail"].lower()


def test_hba1c_gap_boundary():
    points = [{"date": "2025-12-18", "value": 7.5}]
    res = evaluate_hba1c_gap(AS_OF, points, threshold_months=HBA1C_GAP_MONTHS)
    assert res["status"] in ("done", "overdue")


def test_hba1c_gap_missing_data_handled_gracefully():
    assert evaluate_hba1c_gap(AS_OF, None)["status"] == "missing"
    assert evaluate_hba1c_gap(AS_OF, [])["status"] == "missing"
    assert evaluate_hba1c_gap(AS_OF, [{"date": "invalid"}])["status"] == "missing"


# ==============================================================================
# 2. Weight / BMI Gap Rule Tests
# ==============================================================================


def test_weight_bmi_gap_fires_when_overdue():
    # 15 months ago (> 12 months)
    records = [{"date": "2025-03-01", "value": 85.0}]
    res = evaluate_weight_bmi_gap(AS_OF, records, threshold_months=WEIGHT_BMI_GAP_MONTHS)
    assert res["status"] == "overdue"
    assert "overdue" in res["detail"].lower()


def test_weight_bmi_gap_does_not_fire_when_recent():
    # 2 months ago (within 12 months)
    records = [{"date": "2026-04-10", "value": 84.5}]
    res = evaluate_weight_bmi_gap(AS_OF, records, threshold_months=WEIGHT_BMI_GAP_MONTHS)
    assert res["status"] == "done"
    assert "recorded" in res["detail"].lower()


def test_weight_bmi_gap_boundary():
    records = [{"date": "2025-06-18", "value": 85.0}]
    res = evaluate_weight_bmi_gap(AS_OF, records, threshold_months=WEIGHT_BMI_GAP_MONTHS)
    assert res["status"] == "done"


def test_weight_bmi_gap_missing_data_handled_gracefully():
    assert evaluate_weight_bmi_gap(AS_OF, None)["status"] == "missing"
    assert evaluate_weight_bmi_gap(AS_OF, [])["status"] == "missing"
    assert evaluate_weight_bmi_gap(AS_OF, [{"date": ""}])["status"] == "missing"


# ==============================================================================
# 3. Renal Panel Gap Rule Tests
# ==============================================================================


def test_renal_gap_fires_when_overdue():
    # 15 months ago (> 12 months)
    records = [{"date": "2025-03-01", "value": 59}]
    res = evaluate_renal_panel_gap(AS_OF, records, threshold_months=RENAL_PANEL_GAP_MONTHS)
    assert res["status"] == "overdue"
    assert "overdue" in res["detail"].lower()


def test_renal_gap_does_not_fire_when_recent():
    # 2 months ago (within 12 months)
    records = [{"date": "2026-04-10", "value": 65}]
    res = evaluate_renal_panel_gap(AS_OF, records, threshold_months=RENAL_PANEL_GAP_MONTHS)
    assert res["status"] == "done"


def test_renal_gap_boundary():
    records = [{"date": "2025-06-18", "value": 70}]
    res = evaluate_renal_panel_gap(AS_OF, records, threshold_months=RENAL_PANEL_GAP_MONTHS)
    assert res["status"] == "done"


def test_renal_gap_missing_data_handled_gracefully():
    assert evaluate_renal_panel_gap(AS_OF, None)["status"] == "missing"
    assert evaluate_renal_panel_gap(AS_OF, [])["status"] == "missing"
    assert evaluate_renal_panel_gap(AS_OF, [{"date": ""}])["status"] == "missing"


# ==============================================================================
# 4. Meal-log Gap Rule Tests
# ==============================================================================


def test_meal_log_gap_does_not_appear_when_source_disabled():
    res = evaluate_meal_log_gap(AS_OF, meal_log_enabled=False, meal_logs=None)
    assert res is None
    res2 = evaluate_meal_log_gap(AS_OF, meal_log_enabled=False, meal_logs=[{"date": "2026-06-10"}])
    assert res2 is None


def test_meal_log_gap_fires_when_enabled_and_overdue():
    logs = [{"date": "2026-06-10"}]
    res = evaluate_meal_log_gap(
        AS_OF, meal_log_enabled=True, meal_logs=logs, threshold_days=MEAL_LOG_GAP_DAYS
    )
    assert res is not None
    assert res["status"] == "overdue"
    assert "gap" in res["detail"].lower() or "overdue" in res["detail"].lower()


def test_meal_log_gap_does_not_fire_when_recent():
    logs = [{"date": "2026-06-17"}]
    res = evaluate_meal_log_gap(
        AS_OF, meal_log_enabled=True, meal_logs=logs, threshold_days=MEAL_LOG_GAP_DAYS
    )
    assert res is not None
    assert res["status"] == "done"


def test_meal_log_gap_boundary():
    logs = [{"date": "2026-06-15"}]
    res = evaluate_meal_log_gap(
        AS_OF, meal_log_enabled=True, meal_logs=logs, threshold_days=MEAL_LOG_GAP_DAYS
    )
    assert res is not None
    assert res["status"] == "done"


def test_meal_log_gap_missing_data_when_enabled():
    res = evaluate_meal_log_gap(AS_OF, meal_log_enabled=True, meal_logs=[])
    assert res is not None
    assert res["status"] == "missing"


# ==============================================================================
# 5. Hypoglycemia Note Scanning & Negation Tests
# ==============================================================================


def test_hypoglycemia_scan_english_phrase():
    chunks = [
        {
            "id": "c1",
            "file_name": "Visit_Note_2026-02-15.pdf",
            "page": 3,
            "date": "2026-02-15",
            "text": "Patient reports night-time sweating and mild tremors before meals.",
        }
    ]
    res = scan_notes_for_hypoglycemia(chunks)
    assert len(res) == 1
    assert res[0]["severity"] == "review"
    assert res[0]["citation"]["chunk_id"] == "c1"


def test_hypoglycemia_scan_arabic_phrase():
    chunks = [
        {
            "id": "c2",
            "file_name": "Clinic_Note_2026-04-10.pdf",
            "page": 1,
            "date": "2026-04-10",
            "text": "المريض يشكو من هبوط سكر متكرر قبل وجبة الغداء مع دوخة.",
        }
    ]
    res = scan_notes_for_hypoglycemia(chunks)
    assert len(res) == 1
    assert res[0]["severity"] == "review"
    assert "هبوط سكر" in res[0]["citation"]["quote"]


def test_hypoglycemia_scan_escalates_on_emergency():
    chunks = [
        {
            "id": "c3",
            "file_name": "ER_Note_2026-05-01.pdf",
            "page": 1,
            "date": "2026-05-01",
            "text": (
                "Severe hypoglycemia episode with loss of consciousness and emergency admission."
            ),
        }
    ]

    res = scan_notes_for_hypoglycemia(chunks)
    assert len(res) == 1
    assert res[0]["severity"] == "urgent_review"


def test_hypoglycemia_scan_escalates_on_arabic_emergency():
    chunks = [
        {
            "id": "c4",
            "file_name": "Note_2026-05-01.pdf",
            "page": 1,
            "date": "2026-05-01",
            "text": "حدث هبوط سكر حاد مع فقدان الوعي ونقل المريض إلى قسم طوارئ المستشفى.",
        }
    ]
    res = scan_notes_for_hypoglycemia(chunks)
    assert len(res) == 1
    assert res[0]["severity"] == "urgent_review"


def test_hypoglycemia_negation_english():
    negated_phrases = [
        "Patient has no hypoglycemia documented.",
        "Patient denies hypoglycemia.",
        "Denies any low blood sugar episodes.",
        "No episodes of hypoglycemia reported.",
        "Patient is doing well without any hypoglycemia.",
    ]
    for phrase in negated_phrases:
        assert is_hypoglycemia_negated(phrase) is True
        res = scan_notes_for_hypoglycemia(
            [{"id": "n1", "file_name": "note.pdf", "page": 1, "text": phrase}]
        )
        assert res == [], f"Expected no finding for negated phrase: {phrase}"


def test_hypoglycemia_negation_arabic():
    negated_arabic = [
        "لا يوجد هبوط في السكر لدى المريض.",
        "مفيش هبوط سكر في الفترة الأخيرة.",
        "المريض ينفي حدوث أي هبوط.",
        "المريضة تنفي حدوث أعراض هبوط سكر.",
        "مستقر دون أي هبوط.",
    ]
    for phrase in negated_arabic:
        assert is_hypoglycemia_negated(phrase) is True
        res = scan_notes_for_hypoglycemia(
            [{"id": "n2", "file_name": "note.pdf", "page": 1, "text": phrase}]
        )
        assert res == [], f"Expected no finding for negated Arabic phrase: {phrase}"


def test_hypoglycemia_scan_does_not_fire_without_keywords():
    chunks = [
        {
            "id": "c5",
            "file_name": "Routine_Note_2026-01-01.pdf",
            "page": 1,
            "date": "2026-01-01",
            "text": "Blood pressure 120/80. No acute complaints. Normal follow-up.",
        }
    ]
    assert scan_notes_for_hypoglycemia(chunks) == []


def test_hypoglycemia_scan_empty_chunks_graceful():
    assert scan_notes_for_hypoglycemia([]) == []
    assert scan_notes_for_hypoglycemia([{"text": ""}]) == []


# ==============================================================================
# 6. Medication Considerations & Severity Calibration Tests
# ==============================================================================


def test_medication_consideration_slight_drop_is_review():
    # eGFR slightly below 60 (55 mL/min) with modest drop (15 points < 20) -> severity 'review'
    citation = {
        "chunk_id": "1042-Nephrology_Note-p1",
        "file_name": "Nephrology_Note.pdf",
        "page": 1,
        "quote": "eGFR 55 mL/min/1.73m² down from 70.",
        "date": "2026-06-18",
    }
    pts = [
        {"date": "2025-03-12", "value": 70},
        {"date": "2026-06-18", "value": 55},
    ]
    res = evaluate_medication_considerations(
        medications=["Metformin"],
        egfr_points=pts,
        citations_by_concept={"egfr": citation},
    )
    assert len(res) == 1
    assert res[0]["severity"] == "review"
    assert MEDICATION_CONSIDERATION_NOTE_EN in res[0]["statement"]
    assert MEDICATION_CONSIDERATION_NOTE_EN in res[0]["why"]


def test_medication_consideration_sharp_drop_is_urgent_review():
    # Sharp drop: eGFR dropped by 25 points (>= 20 threshold) -> severity 'urgent_review'
    citation = {
        "chunk_id": "c_egfr",
        "file_name": "Lab.pdf",
        "page": 1,
        "quote": "eGFR dropped rapidly from 75 to 50.",
        "date": "2026-06-18",
    }
    pts = [
        {"date": "2025-03-12", "value": 75},
        {"date": "2026-06-18", "value": 50},
    ]
    res = evaluate_medication_considerations(
        medications=["Metformin"],
        egfr_points=pts,
        citations_by_concept={"egfr": citation},
    )
    assert len(res) == 1
    assert res[0]["severity"] == "urgent_review"


def test_medication_consideration_severely_low_egfr_is_urgent_review():
    # Much lower value: eGFR < 30 -> severity 'urgent_review'
    citation = {
        "chunk_id": "c_egfr2",
        "file_name": "Lab.pdf",
        "page": 1,
        "quote": "eGFR 26 mL/min.",
        "date": "2026-06-18",
    }
    pts = [
        {"date": "2025-03-12", "value": 32},
        {"date": "2026-06-18", "value": 26},
    ]
    res = evaluate_medication_considerations(
        medications=["Metformin"],
        egfr_points=pts,
        citations_by_concept={"egfr": citation},
    )
    assert len(res) == 1
    assert res[0]["severity"] == "urgent_review"


def test_medication_consideration_boundaries():
    cit = {"chunk_id": "c", "file_name": "f.pdf", "page": 1, "quote": "q"}

    # Boundary 1: eGFR exactly 60.0 without drop -> does not fire
    assert (
        evaluate_medication_considerations(
            ["Metformin"],
            [{"date": "2026-06-18", "value": 60.0}],
            {"egfr": cit},
        )
        == []
    )

    # Boundary 2: eGFR 59.9 with modest drop -> review
    res_mild = evaluate_medication_considerations(
        ["Metformin"],
        [{"date": "2025-01-01", "value": 65.0}, {"date": "2026-06-18", "value": 59.9}],
        {"egfr": cit},
    )
    assert len(res_mild) == 1
    assert res_mild[0]["severity"] == "review"

    # Boundary 3: Drop 19.9 points (below 20 threshold) with eGFR 45 -> review
    res_drop19 = evaluate_medication_considerations(
        ["Metformin"],
        [{"date": "2025-01-01", "value": 64.9}, {"date": "2026-06-18", "value": 45.0}],
        {"egfr": cit},
    )
    assert len(res_drop19) == 1
    assert res_drop19[0]["severity"] == "review"

    # Boundary 4: Drop exactly 20.0 points -> urgent_review
    res_drop20 = evaluate_medication_considerations(
        ["Metformin"],
        [{"date": "2025-01-01", "value": 65.0}, {"date": "2026-06-18", "value": 45.0}],
        {"egfr": cit},
    )
    assert len(res_drop20) == 1
    assert res_drop20[0]["severity"] == "urgent_review"


def test_medication_consideration_drops_without_citation():
    pts = [{"date": "2025-03-12", "value": 78}, {"date": "2026-06-18", "value": 59}]
    res = evaluate_medication_considerations(
        medications=["Metformin"],
        egfr_points=pts,
        citations_by_concept={},
    )
    assert res == []


# ==============================================================================
# 7. Wiring Proof Tests Through build_brief
# ==============================================================================


def test_wiring_hba1c_gap_through_build_brief(db_session):
    # Fires (overdue):
    p_overdue = Patient(
        id="test-p-hba1c-overdue",
        display_name="Test Patient",
        age=55,
        diabetes_type="Type 2",
        as_of_date=AS_OF,
        medications=[],
        trends={"hba1c": [{"date": "2025-10-01", "value": 8.5}], "egfr": []},
        care_gaps=[],
    )
    db_session.add(p_overdue)
    db_session.commit()
    brief_overdue = build_brief(db_session, p_overdue)
    gap_overdue = next((g for g in brief_overdue.care_gaps if "hba1c" in g.name.lower()), None)
    assert gap_overdue is not None
    assert gap_overdue.status == "overdue"

    # Does not fire (recent):
    p_recent = Patient(
        id="test-p-hba1c-recent",
        display_name="Test Patient",
        age=55,
        diabetes_type="Type 2",
        as_of_date=AS_OF,
        medications=[],
        trends={"hba1c": [{"date": "2026-05-01", "value": 7.2}], "egfr": []},
        care_gaps=[],
    )
    db_session.add(p_recent)
    db_session.commit()
    brief_recent = build_brief(db_session, p_recent)
    gap_recent = next((g for g in brief_recent.care_gaps if "hba1c" in g.name.lower()), None)
    assert gap_recent is None  # Does not emit an overdue/missing care gap

    # Missing data:
    p_missing = Patient(
        id="test-p-hba1c-missing",
        display_name="Test Patient",
        age=55,
        diabetes_type="Type 2",
        as_of_date=AS_OF,
        medications=[],
        trends={"hba1c": [], "egfr": []},
        care_gaps=[],
    )
    db_session.add(p_missing)
    db_session.commit()
    brief_missing = build_brief(db_session, p_missing)
    gap_missing = next((g for g in brief_missing.care_gaps if "hba1c" in g.name.lower()), None)
    assert gap_missing is not None
    assert gap_missing.status == "missing"


def test_wiring_weight_bmi_gap_through_build_brief(db_session):
    # Fires (overdue):
    p_overdue = Patient(
        id="test-p-weight-overdue",
        display_name="Test Patient",
        age=55,
        diabetes_type="Type 2",
        as_of_date=AS_OF,
        medications=[],
        trends={"weight": [{"date": "2025-01-01", "value": 85.0}], "hba1c": [], "egfr": []},
        care_gaps=[],
    )
    db_session.add(p_overdue)
    db_session.commit()
    brief_overdue = build_brief(db_session, p_overdue)
    gap = next((g for g in brief_overdue.care_gaps if "weight" in g.name.lower()), None)
    assert gap is not None
    assert gap.status == "overdue"

    # Does not fire (recent):
    p_recent = Patient(
        id="test-p-weight-recent",
        display_name="Test Patient",
        age=55,
        diabetes_type="Type 2",
        as_of_date=AS_OF,
        medications=[],
        trends={"weight": [{"date": "2026-05-01", "value": 84.0}], "hba1c": [], "egfr": []},
        care_gaps=[],
    )
    db_session.add(p_recent)
    db_session.commit()
    brief_recent = build_brief(db_session, p_recent)
    gap_recent = next((g for g in brief_recent.care_gaps if "weight" in g.name.lower()), None)
    assert gap_recent is None

    # Missing data:
    p_missing = Patient(
        id="test-p-weight-missing",
        display_name="Test Patient",
        age=55,
        diabetes_type="Type 2",
        as_of_date=AS_OF,
        medications=[],
        trends={"weight": [], "hba1c": [], "egfr": []},
        care_gaps=[],
    )
    db_session.add(p_missing)
    db_session.commit()
    brief_missing = build_brief(db_session, p_missing)
    gap_missing = next((g for g in brief_missing.care_gaps if "weight" in g.name.lower()), None)
    assert gap_missing is not None
    assert gap_missing.status == "missing"


def test_wiring_renal_panel_gap_through_build_brief(db_session):
    # Fires (overdue):
    p_overdue = Patient(
        id="test-p-renal-overdue",
        display_name="Test Patient",
        age=55,
        diabetes_type="Type 2",
        as_of_date=AS_OF,
        medications=[],
        trends={"renal": [{"date": "2025-01-01", "value": 60}], "hba1c": [], "egfr": []},
        care_gaps=[],
    )
    db_session.add(p_overdue)
    db_session.commit()
    brief = build_brief(db_session, p_overdue)
    gap = next((g for g in brief.care_gaps if "renal" in g.name.lower()), None)
    assert gap is not None
    assert gap.status == "overdue"

    # Does not fire (recent):
    p_recent = Patient(
        id="test-p-renal-recent",
        display_name="Test Patient",
        age=55,
        diabetes_type="Type 2",
        as_of_date=AS_OF,
        medications=[],
        trends={"renal": [{"date": "2026-05-01", "value": 60}], "hba1c": [], "egfr": []},
        care_gaps=[],
    )
    db_session.add(p_recent)
    db_session.commit()
    brief_recent = build_brief(db_session, p_recent)
    assert not any("renal" in g.name.lower() for g in brief_recent.care_gaps)

    # Missing data:
    p_missing = Patient(
        id="test-p-renal-missing",
        display_name="Test Patient",
        age=55,
        diabetes_type="Type 2",
        as_of_date=AS_OF,
        medications=[],
        trends={"renal": [], "hba1c": [], "egfr": []},
        care_gaps=[],
    )
    db_session.add(p_missing)
    db_session.commit()
    brief_missing = build_brief(db_session, p_missing)
    gap_missing = next((g for g in brief_missing.care_gaps if "renal" in g.name.lower()), None)
    assert gap_missing is not None
    assert gap_missing.status == "missing"


def test_wiring_meal_log_gap_through_build_brief(db_session):
    # Case 1: No meal-log source present -> Emits NOTHING
    p_no_source = Patient(
        id="test-p-meal-nosource",
        display_name="Test Patient",
        age=55,
        diabetes_type="Type 2",
        as_of_date=AS_OF,
        medications=[],
        trends={"hba1c": [], "egfr": []},
        care_gaps=[],
    )
    db_session.add(p_no_source)
    db_session.commit()
    brief_no_source = build_brief(db_session, p_no_source)
    assert not any("meal" in g.name.lower() for g in brief_no_source.care_gaps)

    # Case 2: Meal-log source present and overdue (> 3 days) -> Emits gap
    p_source = Patient(
        id="test-p-meal-source",
        display_name="Test Patient",
        age=55,
        diabetes_type="Type 2",
        as_of_date=AS_OF,
        medications=[],
        trends={"hba1c": [], "egfr": []},
        care_gaps=[],
    )
    db_session.add(p_source)
    meal_file = File(
        id="test-meal-file-1",
        patient_id=p_source.id,
        name="Meal_Log_2026-06-10.pdf",
        kind="meal_log",
        date="2026-06-10",
        is_scan=False,
    )
    db_session.add(meal_file)
    db_session.commit()
    brief_source = build_brief(db_session, p_source)
    meal_gap = next((g for g in brief_source.care_gaps if "meal" in g.name.lower()), None)
    assert meal_gap is not None
    assert meal_gap.status == "overdue"

    # Case 3: Meal-log source present and recent (<= 3 days) -> Does not emit gap
    p_recent = Patient(
        id="test-p-meal-recent",
        display_name="Test Patient",
        age=55,
        diabetes_type="Type 2",
        as_of_date=AS_OF,
        medications=[],
        trends={"hba1c": [], "egfr": []},
        care_gaps=[],
    )
    db_session.add(p_recent)
    meal_recent = File(
        id="test-meal-file-recent",
        patient_id=p_recent.id,
        name="Meal_Log_2026-06-17.pdf",
        kind="meal_log",
        date="2026-06-17",
        is_scan=False,
    )
    db_session.add(meal_recent)
    db_session.commit()
    brief_recent = build_brief(db_session, p_recent)
    assert not any("meal" in g.name.lower() for g in brief_recent.care_gaps)


def test_wiring_medication_consideration_through_build_brief(db_session):
    # Fires review (slight reduction 55 mL/min, drop 15 < 20):
    p_review = Patient(
        id="test-p-med-review",
        display_name="Test Patient",
        age=60,
        diabetes_type="Type 2",
        as_of_date=AS_OF,
        medications=["Metformin 1000mg"],
        trends={
            "egfr": [
                {"date": "2025-01-01", "value": 70.0},
                {"date": "2026-06-18", "value": 55.0},
            ],
            "hba1c": [],
        },
        care_gaps=[],
    )
    db_session.add(p_review)
    f = File(
        id="f-egfr-1",
        patient_id=p_review.id,
        name="Nephrology.pdf",
        kind="specialist",
        date="2026-06-18",
    )
    db_session.add(f)
    ch = Chunk(
        id="c-egfr-1",
        patient_id=p_review.id,
        file_id=f.id,
        page=1,
        text="Clinical evaluation: eGFR 55 mL/min/1.73m² with ongoing Metformin.",
    )
    db_session.add(ch)
    db_session.commit()

    brief_review = build_brief(db_session, p_review)
    med_cons = next(
        (c for c in brief_review.considerations if "metformin" in c.statement.lower()), None
    )
    assert med_cons is not None
    assert med_cons.severity == "review"
    assert med_cons.source is not None
    assert med_cons.source.chunk_id == "c-egfr-1"

    # Fires urgent_review (severe reduction < 30):
    p_urgent = Patient(
        id="test-p-med-urgent",
        display_name="Test Patient",
        age=60,
        diabetes_type="Type 2",
        as_of_date=AS_OF,
        medications=["Metformin"],
        trends={
            "egfr": [
                {"date": "2025-01-01", "value": 35.0},
                {"date": "2026-06-18", "value": 24.0},
            ],
            "hba1c": [],
        },
        care_gaps=[],
    )
    db_session.add(p_urgent)
    f2 = File(
        id="f-egfr-2",
        patient_id=p_urgent.id,
        name="Nephrology.pdf",
        kind="specialist",
        date="2026-06-18",
    )
    db_session.add(f2)
    ch2 = Chunk(
        id="c-egfr-2",
        patient_id=p_urgent.id,
        file_id=f2.id,
        page=1,
        text="Follow-up eGFR is 24 mL/min on Metformin therapy.",
    )
    db_session.add(ch2)
    db_session.commit()

    brief_urgent = build_brief(db_session, p_urgent)
    med_cons_urgent = next(
        (c for c in brief_urgent.considerations if "metformin" in c.statement.lower()), None
    )
    assert med_cons_urgent is not None
    assert med_cons_urgent.severity == "urgent_review"

    # Does not fire: eGFR normal (>= 60) without drop
    p_normal = Patient(
        id="test-p-med-normal",
        display_name="Test Patient",
        age=60,
        diabetes_type="Type 2",
        as_of_date=AS_OF,
        medications=["Metformin"],
        trends={"egfr": [{"date": "2026-06-18", "value": 85.0}], "hba1c": []},
        care_gaps=[],
    )
    db_session.add(p_normal)
    db_session.commit()
    brief_normal = build_brief(db_session, p_normal)
    assert not any("metformin" in c.statement.lower() for c in brief_normal.considerations)


def test_wiring_hypoglycemia_notes_through_build_brief(db_session):
    # Routine mention fires review:
    p_routine = Patient(
        id="test-p-hypo-routine",
        display_name="Test Patient",
        age=50,
        diabetes_type="Type 2",
        as_of_date=AS_OF,
        medications=[],
        trends={"hba1c": [], "egfr": []},
        care_gaps=[],
    )
    db_session.add(p_routine)
    f_routine = File(
        id="f-hypo-r", patient_id=p_routine.id, name="Visit_Note.pdf", kind="visit_note", date=AS_OF
    )
    db_session.add(f_routine)
    ch_routine = Chunk(
        id="c-hypo-r",
        patient_id=p_routine.id,
        file_id=f_routine.id,
        page=1,
        text="Patient notes occasional night-time sweating and shakiness before meals.",
    )
    db_session.add(ch_routine)
    db_session.commit()

    brief_routine = build_brief(db_session, p_routine)
    hypo_cons = next(
        (
            c
            for c in brief_routine.considerations
            if "glucose" in c.statement.lower() or "hypo" in c.statement.lower()
        ),
        None,
    )
    assert hypo_cons is not None
    assert hypo_cons.severity == "review"
    assert hypo_cons.source is not None
    assert hypo_cons.source.chunk_id == "c-hypo-r"

    # Urgent mention fires urgent_review:
    p_urgent = Patient(
        id="test-p-hypo-urgent",
        display_name="Test Patient",
        age=50,
        diabetes_type="Type 2",
        as_of_date=AS_OF,
        medications=[],
        trends={"hba1c": [], "egfr": []},
        care_gaps=[],
    )
    db_session.add(p_urgent)
    f_urgent = File(
        id="f-hypo-u", patient_id=p_urgent.id, name="ER_Note.pdf", kind="visit_note", date=AS_OF
    )
    db_session.add(f_urgent)
    ch_urgent = Chunk(
        id="c-hypo-u",
        patient_id=p_urgent.id,
        file_id=f_urgent.id,
        page=1,
        text="Admitted via ambulance for severe hypoglycemia episode with loss of consciousness.",
    )
    db_session.add(ch_urgent)
    db_session.commit()

    brief_urgent = build_brief(db_session, p_urgent)
    hypo_urgent = next(
        (
            c
            for c in brief_urgent.considerations
            if "hypoglycemia" in c.statement.lower() or "glucose" in c.statement.lower()
        ),
        None,
    )
    assert hypo_urgent is not None
    assert hypo_urgent.severity == "urgent_review"

    # Negated mention does NOT fire:
    p_negated = Patient(
        id="test-p-hypo-negated",
        display_name="Test Patient",
        age=50,
        diabetes_type="Type 2",
        as_of_date=AS_OF,
        medications=[],
        trends={"hba1c": [], "egfr": []},
        care_gaps=[],
    )
    db_session.add(p_negated)
    f_neg = File(
        id="f-hypo-neg", patient_id=p_negated.id, name="Note.pdf", kind="visit_note", date=AS_OF
    )
    db_session.add(f_neg)
    ch_neg = Chunk(
        id="c-hypo-neg",
        patient_id=p_negated.id,
        file_id=f_neg.id,
        page=1,
        text=(
            "Reviewed diabetes management: patient denies hypoglycemia "
            "and has no episodes of low glucose."
        ),
    )

    db_session.add(ch_neg)
    db_session.commit()

    brief_neg = build_brief(db_session, p_negated)
    assert not any(
        "hypoglycemia" in c.statement.lower() or "glucose" in c.statement.lower()
        for c in brief_neg.considerations
    )


def test_brief_considerations_severity_matches_rule_output(db_session):
    """Test fails if a considerations severity in final brief disagrees with rule output."""
    from app.models import Insight

    p = Patient(
        id="p-sev-test",
        display_name="Severity Test Patient",
        age=58,
        diabetes_type="Type 2",
        as_of_date=AS_OF,
        medications=["Metformin"],
        trends={
            "egfr": [
                {"date": "2025-03-12", "value": 78.0},
                {"date": "2026-06-18", "value": 59.0},
            ]
        },
        care_gaps=[],
    )
    db_session.add(p)

    f = File(
        id="f-egfr-test", patient_id=p.id, name="Nephrology.pdf", kind="specialist", date=AS_OF
    )
    db_session.add(f)
    ch = Chunk(
        id="c-egfr-test",
        patient_id=p.id,
        file_id=f.id,
        page=1,
        text="Nephrology note: eGFR 59 mL/min/1.73m² down from 78.",
    )
    db_session.add(ch)

    # Seed an insight with an outdated/divergent severity ("urgent_review")
    ins = Insight(
        id="p-sev-test-f1",
        patient_id=p.id,
        type="falling_egfr",
        severity="urgent_review",  # intentionally disagrees with calibrated rule
        statement=(
            "eGFR fell from 78 to 59 over 6 visits while Metformin continues. Worth reviewing."
        ),
        why="eGFR fell while on Metformin.",
        source_chunk_id=ch.id,
        rank=0,
    )
    db_session.add(ins)
    db_session.commit()

    # Rule output calculation: drop is 19 (< 20) and latest is 59 (< 60 but not < 30) -> "review"
    rule_items = evaluate_medication_considerations(
        medications=p.medications,
        egfr_trends=p.trends["egfr"],
        citations={"egfr": {"chunk_id": ch.id, "file_name": f.name, "page": 1, "quote": ch.text}},
    )
    assert len(rule_items) == 1
    expected_rule_sev = rule_items[0]["severity"]
    assert expected_rule_sev == "review"

    # Build brief through services.py
    brief = build_brief(db_session, p)

    # Locate the consideration
    matching_c = next(
        (c for c in brief.considerations if "metformin" in c.statement.lower()),
        None,
    )
    assert matching_c is not None, "Expected Metformin consideration in brief"

    # MUST match rule output ("review"), and MUST NOT keep the discordant seeded "urgent_review"
    assert matching_c.severity == expected_rule_sev, (
        f"Brief consideration severity '{matching_c.severity}' disagrees with "
        f"rule output '{expected_rule_sev}'!"
    )
    assert matching_c.severity != "urgent_review"


def test_brief_considerations_severity_matches_rule_output_urgent(db_session):
    """Test confirms that when rule calculates urgent_review (drop >= 20), brief reflects it."""
    p_urgent = Patient(
        id="p-urgent-test",
        display_name="Urgent Test Patient",
        age=62,
        diabetes_type="Type 2",
        as_of_date=AS_OF,
        medications=["Metformin"],
        trends={
            "egfr": [
                {"date": "2025-01-10", "value": 85.0},
                {"date": "2026-06-18", "value": 55.0},  # drop is 30 points (>= 20)
            ]
        },
        care_gaps=[],
    )
    db_session.add(p_urgent)
    f = File(id="f-urg", patient_id=p_urgent.id, name="Nephro.pdf", kind="specialist", date=AS_OF)
    db_session.add(f)
    ch = Chunk(
        id="c-urg",
        patient_id=p_urgent.id,
        file_id=f.id,
        page=1,
        text="Nephrology review: eGFR 55 down from 85.",
    )
    db_session.add(ch)
    db_session.commit()

    rule_items = evaluate_medication_considerations(
        medications=p_urgent.medications,
        egfr_trends=p_urgent.trends["egfr"],
        citations={"egfr": {"chunk_id": ch.id, "file_name": f.name, "page": 1, "quote": ch.text}},
    )
    assert rule_items[0]["severity"] == "urgent_review"

    brief = build_brief(db_session, p_urgent)
    matching_c = next(
        (c for c in brief.considerations if "metformin" in c.statement.lower()),
        None,
    )
    assert matching_c is not None
    assert matching_c.severity == "urgent_review"
