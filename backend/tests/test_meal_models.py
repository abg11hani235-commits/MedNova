from datetime import UTC, datetime

from app.models import (
    CAIRO_TZ,
    MealItem,
    MealLog,
    Patient,
    get_cairo_date,
    get_cairo_datetime,
)
from app.services import build_brief


def test_cairo_date_computation_boundaries():
    """Test message timestamp at 23:30 and 00:30 Cairo time."""
    # Note: On 2026-10-14, Cairo is UTC+3 (EEST, daylight saving time ends late October)
    # 2026-10-14 20:30 UTC -> 2026-10-14 23:30 Cairo
    dt_2330_cairo = datetime(2026, 10, 14, 23, 30, tzinfo=CAIRO_TZ)
    # 2026-10-15 00:30 Cairo
    dt_0030_cairo = datetime(2026, 10, 15, 0, 30, tzinfo=CAIRO_TZ)

    # Date string must reflect local day in Africa/Cairo
    assert get_cairo_date(dt_2330_cairo) == "2026-10-14"
    assert get_cairo_date(dt_0030_cairo) == "2026-10-15"

    # From UTC equivalents
    utc_2330 = dt_2330_cairo.astimezone(UTC)
    utc_0030 = dt_0030_cairo.astimezone(UTC)
    assert get_cairo_date(utc_2330) == "2026-10-14"
    assert get_cairo_date(utc_0030) == "2026-10-15"

    # Datetime localized
    cairo_dt = get_cairo_datetime(utc_2330)
    assert cairo_dt.hour == 23 and cairo_dt.minute == 30
    assert cairo_dt.tzinfo is not None


def test_meal_log_and_items_persistence(db_session):
    p = Patient(
        id="p-meal-test-1",
        display_name="Meal Test Patient",
        age=50,
        diabetes_type="Type 2",
        as_of_date="2026-06-18",
        medications=["Metformin"],
        trends={},
        care_gaps=[],
    )
    db_session.add(p)
    db_session.commit()

    ml = MealLog(
        id="ml-001",
        patient_id=p.id,
        local_date="2026-06-18",
        meal_type="breakfast",
        raw_text="رغيف عيش بلدي وبيضتين مسلوقين",
        status="parsed",
    )
    item1 = MealItem(
        food_id="food-aish-baladi",
        food_name_ar="عيش بلدي",
        food_name_en="Baladi Bread",
        quantity=1.0,
        unit="رغيف",
        grams=130.0,
        kcal=260.0,
        protein_g=9.0,
        carbs_g=52.0,
        fat_g=1.5,
        fiber_g=4.0,
        match_method="exact_alias",
        match_score=1.0,
        confirmed=True,
    )
    item2 = MealItem(
        food_id="food-boiled-egg",
        food_name_ar="بيض مسلوق",
        food_name_en="Boiled Egg",
        quantity=2.0,
        unit="بيضة",
        grams=100.0,
        kcal=140.0,
        protein_g=12.0,
        carbs_g=1.0,
        fat_g=10.0,
        fiber_g=0.0,
        match_method="exact_alias",
        match_score=1.0,
        confirmed=True,
    )
    ml.items.extend([item1, item2])
    db_session.add(ml)
    db_session.commit()

    # Query back
    fetched = db_session.get(MealLog, "ml-001")
    assert fetched is not None
    assert fetched.patient_id == p.id
    assert len(fetched.items) == 2
    assert fetched.items[0].food_id == "food-aish-baladi"
    assert fetched.items[1].quantity == 2.0


def test_emergency_symptom_flag_reads_into_urgent_review_in_brief(db_session):
    p = Patient(
        id="p-emerg-test",
        display_name="Emergency Symptom Patient",
        age=55,
        diabetes_type="Type 2",
        as_of_date="2026-06-18",
        medications=[],
        trends={},
        care_gaps=[],
    )
    db_session.add(p)
    db_session.commit()

    # Log with emergency symptom flag
    ml_emerg = MealLog(
        id="ml-emerg-99",
        patient_id=p.id,
        local_date="2026-06-18",
        meal_type="dinner",
        raw_text="حاسس بإغماء وهبوط سكر شديد بعد العشا",
        status="emergency",
        safety_flag="emergency_symptom",
    )
    db_session.add(ml_emerg)
    db_session.commit()

    brief = build_brief(db_session, p)
    # Emergency symptom MUST appear in considerations with severity "urgent_review"
    emerg_cons = next(
        (c for c in brief.considerations if c.id == "cons-emergency-ml-emerg-99"), None
    )
    assert emerg_cons is not None, "Emergency meal log must produce a consideration in brief"
    assert emerg_cons.severity == "urgent_review"
    assert "حاسس بإغماء وهبوط سكر شديد بعد العشا" in emerg_cons.why
    assert emerg_cons.source is not None
    assert emerg_cons.source.file_name == "Patient Meal Chat"
    assert emerg_cons.source.quote == ml_emerg.raw_text
    assert emerg_cons.source.date == "2026-06-18"


def test_meal_log_gap_flips_when_patient_meals_exist(db_session):
    p = Patient(
        id="p-gap-flip",
        display_name="Gap Flip Patient",
        age=60,
        diabetes_type="Type 2",
        as_of_date="2026-06-18",
        medications=[],
        trends={},
        care_gaps=[{"name": "Meal log", "status": "missing", "evidence": None}],
    )
    db_session.add(p)
    db_session.commit()

    # Before meals: meal gap is missing
    brief_before = build_brief(db_session, p)
    meal_gap_before = next((g for g in brief_before.care_gaps if "meal" in g.name.lower()), None)
    assert meal_gap_before is not None
    assert meal_gap_before.status == "missing"

    # After adding a meal log dated today (2026-06-18):
    ml = MealLog(
        id="ml-gap-1",
        patient_id=p.id,
        local_date="2026-06-18",
        meal_type="lunch",
        raw_text="كشري وطبق سلطة",
        status="parsed",
    )
    db_session.add(ml)
    db_session.commit()

    brief_after = build_brief(db_session, p)
    meal_gap_after = next((g for g in brief_after.care_gaps if "meal" in g.name.lower()), None)
    assert meal_gap_after is not None
    assert meal_gap_after.status == "done"
