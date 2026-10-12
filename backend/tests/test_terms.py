"""Unit tests for medical terminology layer (app/terms)."""

from app.terms.terms import (
    CONCEPTS,
    detect_concepts,
    expand_query,
    normalize_arabic,
)


def test_concepts_loaded_with_needs_review():
    assert len(CONCEPTS) > 0
    # Check that Arabic terms have needs_review: True and code is empty string
    for concept in CONCEPTS:
        assert concept["code"] == ""
        for ar in concept.get("arabic_synonyms", []):
            assert ar.get("needs_review") is True


def test_arabic_normalization():
    # Diacritics (tashkeel) and tatweel
    tashkeel_text = "السُّكَّرُ التَّرَاكُمِيّـ"
    normalized = normalize_arabic(tashkeel_text)
    assert normalized == "السكر التراكمي"

    # Alef forms
    assert normalize_arabic("إنسولين") == "انسولين"
    assert normalize_arabic("أماريل") == "اماريل"

    # Taa marbuta and ya
    assert normalize_arabic("كلى") == "كلي"


def test_concept_detection_english():
    detected = detect_concepts("What was the last HbA1c value?")
    concept_ids = [c["id"] for c in detected]
    assert "hba1c" in concept_ids

    detected_egfr = detect_concepts("Check renal eGFR and creatinine")
    ids = [c["id"] for c in detected_egfr]
    assert "egfr" in ids
    assert "creatinine" in ids


def test_concept_detection_arabic_and_mixed():
    # Arabic question
    detected_ar = detect_concepts("ما هو السكر التراكمي الأخير للمريض؟")
    assert any(c["id"] == "hba1c" for c in detected_ar)

    # Mixed question
    detected_mixed = detect_concepts("فحص وظائف الكلى eGFR trend")
    assert any(c["id"] == "egfr" for c in detected_mixed)


def test_expand_query():
    expanded = expand_query("What is the last A1c?")
    assert "Glycated Hemoglobin (HbA1c)" in expanded or "HbA1c" in expanded

    # Arabic query expansion
    expanded_ar = expand_query("ما هو السكر التراكمي؟")
    assert "Glycated Hemoglobin" in expanded_ar or "HbA1c" in expanded_ar
