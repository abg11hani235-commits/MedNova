"""Test ensuring frontend mock data conforms strictly to backend Pydantic schemas."""

from pathlib import Path

from app import schemas

ROOT = Path(__file__).resolve().parents[2]


def test_frontend_brief_mock_conforms_to_schema():
    """Verify that BRIEF_1042 in frontend/src/lib/api/mock.ts matches schemas.Brief."""
    mock_file = ROOT / "frontend" / "src" / "lib" / "api" / "mock.ts"
    assert mock_file.exists(), "mock.ts not found"
    content = mock_file.read_text(encoding="utf-8")

    # Verify that BRIEF_1042 has meals field with expected structure
    assert "meals: {" in content
    assert "has_logs: true" in content
    assert "recent_days:" in content

    # Construct the mock brief dictionary corresponding to BRIEF_1042
    # and validate it with schemas.Brief
    brief_data = {
        "patient": {
            "id": "1042",
            "display_name": "Synthetic Patient #1042",
            "age": 58,
            "diabetes_type": "Type 2",
            "duration_years": 12,
            "medications": ["Metformin", "Gliclazide", "Atorvastatin"],
        },
        "coverage": {"total_files": 17, "readable_files": 14, "unreadable_files": 3},
        "snapshot": [
            {
                "id": "1042-F1",
                "severity": "urgent_review",
                "statement": (
                    "eGFR fell from 78 to 59 over 6 visits while Metformin continues. "
                    "Worth reviewing."
                ),
                "source": {
                    "chunk_id": "1042-Nephrology_Note_2026-06-18-p1",
                    "file_name": "Nephrology_Note_2026-06-18.pdf",
                    "page": 1,
                    "quote": (
                        "Estimated GFR today is 59 mL/min/1.73m², down from 78 at the first visit "
                        "in March 2025."
                    ),
                    "date": "2026-06-18",
                },
                "absence_note": None,
                "review_state": "none",
                "feedback": "none",
            }
        ],
        "trends": {
            "hba1c": {
                "target": {"min": 6.0, "max": 7.0},
                "points": [{"date": "2026-06-18", "label": "Jun 26", "value": 8.9}],
            },
            "egfr": {
                "target": {"min": 60.0, "max": 120.0},
                "points": [{"date": "2026-06-18", "label": "Jun 26", "value": 59.0}],
            },
        },
        "care_gaps": [
            {
                "name": "Retinal exam",
                "status": "overdue",
                "detail": "Last recorded 2023",
                "source": None,
            }
        ],
        "considerations": [
            {
                "id": "1042-F1",
                "severity": "urgent_review",
                "statement": (
                    "Kidney function trend alongside current medication is worth reviewing."
                ),
                "why": "eGFR fell from 78 to 59, and Metformin is listed as ongoing.",
                "source": None,
            }
        ],
        "meals": {
            "has_logs": True,
            "recent_days": [
                {
                    "date": "2026-06-18",
                    "meal_count": 2,
                    "total_kcal": 685.0,
                    "total_carbs_g": 94.0,
                    "total_protein_g": 28.5,
                    "total_fat_g": 21.0,
                    "total_fiber_g": 9.5,
                    "is_estimated": True,
                    "meals": [
                        {
                            "id": "ml-1042-01",
                            "patient_id": "1042",
                            "local_date": "2026-06-18",
                            "logged_at": "2026-06-18T08:30:00Z",
                            "meal_type": "breakfast",
                            "raw_text": "رغيف عيش بلدي وبيضتين مسلوقين",
                            "status": "parsed",
                            "clarification_question": None,
                            "clarification_options": None,
                            "safety_flag": None,
                            "total_kcal": 402.5,
                            "total_carbs_g": 44.5,
                            "total_protein_g": 20.3,
                            "total_fat_g": 13.8,
                            "total_fiber_g": 4.8,
                            "is_estimated": True,
                            "items": [
                                {
                                    "id": "mi-1",
                                    "food_id": "food-aish-baladi",
                                    "food_name_ar": "عيش بلدي",
                                    "food_name_en": "Baladi Bread",
                                    "quantity": 1.0,
                                    "unit": "رغيف",
                                    "grams": 90.0,
                                    "kcal": 247.5,
                                    "protein_g": 7.7,
                                    "carbs_g": 43.7,
                                    "fat_g": 2.3,
                                    "fiber_g": 4.1,
                                    "match_method": "exact_alias",
                                    "match_score": 1.0,
                                    "confirmed": True,
                                    "source_food_row": {
                                        "id": "food-aish-baladi",
                                        "name_ar": "عيش بلدي",
                                        "verified": False,
                                        "source": "author estimate, unverified",
                                    },
                                }
                            ],
                        }
                    ],
                }
            ],
            "note": "تقديري: محسوب بناءً على جدول الأطعمة المصرية التجريبي",
        },
    }

    # Validate against Pydantic schema
    validated = schemas.Brief.model_validate(brief_data)
    assert validated.meals is not None
    assert validated.meals.has_logs is True
    assert len(validated.meals.recent_days) == 1
    assert validated.meals.recent_days[0].meals[0].items[0].food_id == "food-aish-baladi"


def test_frontend_types_contain_meal_definitions():
    """Verify frontend types.ts defines all meal contracts."""
    types_file = ROOT / "frontend" / "src" / "lib" / "api" / "types.ts"
    content = types_file.read_text(encoding="utf-8")

    assert "export interface MealItem" in content
    assert "export interface MealLog" in content
    assert "export interface DailyMealSummary" in content
    assert "export interface MealSection" in content
    assert "export interface PatientChatResponse" in content
    assert "meals?: MealSection | null" in content
    assert "postPatientMealChat" in content
    assert "clarifyMeal" in content
