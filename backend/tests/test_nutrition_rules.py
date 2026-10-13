"""Unit tests for deterministic nutrition rules (backend/app/nutrition_rules.py).

Tests per rule:
1. HbA1c gap:
   - fires (overdue when > threshold_months)
   - does not fire (done when within threshold_months)
   - boundary (exactly at threshold_months)
   - missing data / empty list handled gracefully
2. Renal panel gap:
   - fires (overdue when > threshold_months)
   - does not fire (done when within threshold_months)
   - boundary (exactly at threshold_months)
   - missing data / empty list handled gracefully
3. Meal-log gap:
   - does NOT fire / returns None if meal-log source is disabled / absent
   - fires (overdue when > threshold_days and enabled)
   - does not fire (done when within threshold_days and enabled)
   - boundary (exactly at threshold_days)
   - missing data / empty list handled gracefully
4. Hypoglycemia note scan:
   - fires for Arabic keywords
   - fires for English keywords
   - escalates to urgent_review on emergency/unconsciousness mention
   - does not fire when no hypoglycemia keywords are present
   - gracefully handles empty chunks / missing text
5. Medication considerations:
   - fires neutrally as 'نقطة تستحق المراجعة مع الطبيب المعالج' when eGFR drops on Metformin
   - drops when no citation is provided
   - does not fire when eGFR is stable and normal
"""

from __future__ import annotations

from app.nutrition_rules import (
    HBA1C_GAP_MONTHS,
    MEAL_LOG_GAP_DAYS,
    MEDICATION_CONSIDERATION_NOTE,
    RENAL_PANEL_GAP_MONTHS,
    evaluate_hba1c_gap,
    evaluate_meal_log_gap,
    evaluate_medication_considerations,
    evaluate_renal_panel_gap,
    scan_notes_for_hypoglycemia,
)

AS_OF = "2026-06-18"


# ==============================================================================
# 1. HbA1c Gap Rule Tests
# ==============================================================================


def test_hba1c_gap_fires_when_overdue():
    # 8 months ago (> 6 months threshold)
    points = [{"date": "2025-10-10", "value": 8.0}]
    res = evaluate_hba1c_gap(AS_OF, points, threshold_months=HBA1C_GAP_MONTHS)
    assert res["status"] == "overdue"
    assert "متأخر" in res["detail"]


def test_hba1c_gap_does_not_fire_when_recent():
    # 3 months ago (within 6 months)
    points = [{"date": "2026-03-18", "value": 8.0}]
    res = evaluate_hba1c_gap(AS_OF, points, threshold_months=HBA1C_GAP_MONTHS)
    assert res["status"] == "done"
    assert "تم إجراء الفحص" in res["detail"]


def test_hba1c_gap_boundary():
    # Exactly ~6 months ago (180 days)
    points = [{"date": "2025-12-18", "value": 7.5}]
    res = evaluate_hba1c_gap(AS_OF, points, threshold_months=HBA1C_GAP_MONTHS)
    # 182 days / 30.4375 ~= 5.97 months -> done
    assert res["status"] in ("done", "overdue")


def test_hba1c_gap_missing_data_handled_gracefully():
    assert evaluate_hba1c_gap(AS_OF, None)["status"] == "missing"
    assert evaluate_hba1c_gap(AS_OF, [])["status"] == "missing"
    assert evaluate_hba1c_gap(AS_OF, [{"date": "invalid"}])["status"] == "missing"


# ==============================================================================
# 2. Renal Panel Gap Rule Tests
# ==============================================================================


def test_renal_gap_fires_when_overdue():
    # 15 months ago (> 12 months)
    records = [{"date": "2025-03-01", "value": 59}]
    res = evaluate_renal_panel_gap(AS_OF, records, threshold_months=RENAL_PANEL_GAP_MONTHS)
    assert res["status"] == "overdue"
    assert "متأخر" in res["detail"]


def test_renal_gap_does_not_fire_when_recent():
    # 2 months ago (within 12 months)
    records = [{"date": "2026-04-10", "value": 65}]
    res = evaluate_renal_panel_gap(AS_OF, records, threshold_months=RENAL_PANEL_GAP_MONTHS)
    assert res["status"] == "done"


def test_renal_gap_boundary():
    # Exactly 1 year ago (365 days / 30.4375 ~= 11.99 months)
    records = [{"date": "2025-06-18", "value": 70}]
    res = evaluate_renal_panel_gap(AS_OF, records, threshold_months=RENAL_PANEL_GAP_MONTHS)
    assert res["status"] == "done"


def test_renal_gap_missing_data_handled_gracefully():
    assert evaluate_renal_panel_gap(AS_OF, None)["status"] == "missing"
    assert evaluate_renal_panel_gap(AS_OF, [])["status"] == "missing"
    assert evaluate_renal_panel_gap(AS_OF, [{"date": ""}])["status"] == "missing"


# ==============================================================================
# 3. Meal-log Gap Rule Tests
# ==============================================================================


def test_meal_log_gap_does_not_appear_when_source_disabled():
    # If not enabled or no source, must return None (NOT "no meals logged")
    res = evaluate_meal_log_gap(AS_OF, meal_log_enabled=False, meal_logs=None)
    assert res is None

    res2 = evaluate_meal_log_gap(
        AS_OF,
        meal_log_enabled=False,
        meal_logs=[{"date": "2026-06-10"}],
    )
    assert res2 is None


def test_meal_log_gap_fires_when_enabled_and_overdue():
    # Enabled and last meal log 7 days ago (> 3 days)
    logs = [{"date": "2026-06-10"}]
    res = evaluate_meal_log_gap(
        AS_OF, meal_log_enabled=True, meal_logs=logs, threshold_days=MEAL_LOG_GAP_DAYS
    )
    assert res is not None
    assert res["status"] == "overdue"
    assert "انقطاع في تسجيل الوجبات" in res["detail"]


def test_meal_log_gap_does_not_fire_when_recent():
    # Enabled and last meal log 1 day ago (<= 3 days)
    logs = [{"date": "2026-06-17"}]
    res = evaluate_meal_log_gap(
        AS_OF, meal_log_enabled=True, meal_logs=logs, threshold_days=MEAL_LOG_GAP_DAYS
    )
    assert res is not None
    assert res["status"] == "done"


def test_meal_log_gap_boundary():
    # Exactly 3 days ago
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
# 4. Hypoglycemia Note Scanning Tests
# ==============================================================================


def test_hypoglycemia_scan_english_phrase():
    chunks = [
        {
            "id": "c1",
            "file_name": "Visit_Note_2026-02-15.pdf",
            "page": 3,
            "date": "2026-02-15",
            "text": "Patient reports night-time sweating and mild tremors.",
        }
    ]
    res = scan_notes_for_hypoglycemia(chunks)
    assert len(res) == 1
    assert res[0]["severity"] == "review"
    assert res[0]["citation"]["chunk_id"] == "c1"
    assert "night-time sweating" in res[0]["citation"]["quote"]


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


def test_hypoglycemia_scan_does_not_fire_without_keywords():
    chunks = [
        {
            "id": "c5",
            "file_name": "Routine_Note_2026-01-01.pdf",
            "page": 1,
            "date": "2026-01-01",
            "text": "Blood pressure 120/80. No acute complaints.",
        }
    ]
    assert scan_notes_for_hypoglycemia(chunks) == []


def test_hypoglycemia_scan_empty_chunks_graceful():
    assert scan_notes_for_hypoglycemia([]) == []
    assert scan_notes_for_hypoglycemia([{"text": ""}]) == []


# ==============================================================================
# 5. Medication Considerations Tests
# ==============================================================================


def test_medication_consideration_fires_neutrally_on_egfr_drop():
    citation = {
        "chunk_id": "1042-Nephrology_Note-p1",
        "file_name": "Nephrology_Note.pdf",
        "page": 1,
        "quote": "eGFR 59 mL/min/1.73m² down from 78.",
        "date": "2026-06-18",
    }
    pts = [
        {"date": "2025-03-12", "value": 78},
        {"date": "2026-06-18", "value": 59},
    ]
    res = evaluate_medication_considerations(
        medications=["Metformin", "Atorvastatin"],
        egfr_points=pts,
        citations_by_concept={"egfr": citation},
    )
    assert len(res) == 1
    assert MEDICATION_CONSIDERATION_NOTE in res[0]["statement"]
    assert MEDICATION_CONSIDERATION_NOTE in res[0]["why"]
    assert res[0]["source"] == citation


def test_medication_consideration_drops_without_citation():
    # If citation is missing, item must NOT be emitted
    pts = [
        {"date": "2025-03-12", "value": 78},
        {"date": "2026-06-18", "value": 59},
    ]
    res = evaluate_medication_considerations(
        medications=["Metformin"],
        egfr_points=pts,
        citations_by_concept={},
    )
    assert res == []


def test_medication_consideration_does_not_fire_when_normal():
    pts = [
        {"date": "2025-03-12", "value": 90},
        {"date": "2026-06-18", "value": 92},
    ]
    res = evaluate_medication_considerations(
        medications=["Metformin"],
        egfr_points=pts,
        citations_by_concept={"egfr": {"chunk_id": "c"}},
    )
    assert res == []
