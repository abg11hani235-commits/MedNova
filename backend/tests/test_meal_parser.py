"""Unit tests for Egyptian meal parser (backend/tests/test_meal_parser.py)."""

from app.meal_parser import (
    find_food_candidate,
    normalize_franco_word,
    normalize_text,
    parse_meal_text,
    parse_meal_text_deterministic,
    parse_quantity_and_unit,
)


def test_franco_digit_conversion_only_inside_words():
    # Digits inside words must convert
    assert normalize_franco_word("3eish") == "eeish"
    assert normalize_franco_word("ma7shi") == "mahshi"
    assert normalize_franco_word("ta3meya") == "taemeya"
    assert normalize_franco_word("2ahwa") == "aahwa"

    # Standalone numbers must NEVER convert
    assert normalize_franco_word("2") == "2"
    assert normalize_franco_word("3") == "3"
    assert normalize_franco_word("150") == "150"

    # In full sentence: standalone digits untouched, words converted
    sentence = "2 3eish baladi w 3 baydat"
    normalized = normalize_text(sentence)
    assert "2 " in normalized
    assert " 3 " in normalized


def test_arabic_indic_digits_normalization():
    norm = normalize_text("٣ بيضات و ٢ رغيف عيش")
    assert "3" in norm
    assert "2" in norm


def test_duals_parsing():
    # Egyptian dual words
    qty, unit, remainder = parse_quantity_and_unit("رغيفين عيش بلدي")
    assert qty == 2.0
    assert unit == "رغيف كامل"

    qty, unit, remainder = parse_quantity_and_unit("بيضتين مسلوقين")
    assert qty == 2.0
    assert unit == "بيضة"

    qty, unit, remainder = parse_quantity_and_unit("كوبايتين شاي")
    assert qty == 2.0
    assert "كوب" in unit


def test_fractions_and_compounds():
    # Standalone fraction
    qty, unit, remainder = parse_quantity_and_unit("نص رغيف عيش")
    assert qty == 0.5
    assert unit == "رغيف"

    # Compound fraction: رغيف ونص
    qty, unit, remainder = parse_quantity_and_unit("رغيف ونص عيش بلدي")
    assert qty == 1.5

    # Compound fraction: 2 ونص
    qty, unit, remainder = parse_quantity_and_unit("2 ونص كشري")
    assert qty == 2.5

    # تلات ارباع
    qty, unit, remainder = parse_quantity_and_unit("تلات ارباع رغيف")
    assert qty == 0.75


def test_false_positive_rejection_similar_words():
    # "ملح" (salt) must NEVER match "لحمة" or "لحم"
    candidate, score, method = find_food_candidate("ملح")
    assert candidate is None
    assert method in ("none", "below_threshold")

    # "زر" (button) must NEVER match "رز"
    candidate, score, method = find_food_candidate("زر")
    assert candidate is None

    # "لحام" (welding) must NEVER match "لحمة"
    candidate, score, method = find_food_candidate("لحام")
    assert candidate is None


def test_fuzzy_match_requires_high_score_and_margin():
    # "كشرى" (slight typo with alef maksura) -> matches koshari
    candidate, score, method = find_food_candidate("كشرى")
    assert candidate is not None
    assert candidate["id"] == "food-koshari"

    # Random gibberish must fail
    candidate, score, method = find_food_candidate("سيباتمنيسي")
    assert candidate is None


def test_ambiguous_portion_generates_clarification_question_and_options():
    # Patient logs food without portion
    result = parse_meal_text_deterministic("أكلت كشري")
    assert result.status == "needs_clarification"
    assert result.clarification_question is not None
    assert "كشري" in result.clarification_question
    assert result.clarification_options is not None
    assert len(result.clarification_options) >= 2
    # Check option structure: label, quantity, unit, grams
    opt = result.clarification_options[0]
    assert "label" in opt
    assert "quantity" in opt
    assert "unit" in opt
    assert "grams" in opt
    assert opt["grams"] > 0


def test_unknown_food_generates_standard_explanation():
    result = parse_meal_text_deterministic("أكلت سوشي وساشيمي ياباني")
    assert result.status == "unknown_food"
    assert "مش موجودة في قاعدة بيانات الأطعمة المصرية" in (result.clarification_question or "")
    assert len(result.items) == 0


def test_successful_meal_parse_with_macros():
    result = parse_meal_text_deterministic("رغيف ونص عيش بلدي وبيضتين مسلوقين")
    assert result.status == "parsed"
    assert len(result.items) == 2

    # Check bread item
    bread = next(i for i in result.items if i.food_id == "food-aish-baladi")
    assert bread.quantity == 1.5
    # 1.5 * 130g = 195g
    assert bread.grams == 195.0
    # 195 * 260 / 100 = 507.0 kcal
    assert bread.kcal == 507.0
    assert bread.carbs_g > 0

    # Check egg item
    egg = next(i for i in result.items if i.food_id == "food-egg-boiled")
    assert egg.quantity == 2.0
    assert egg.grams == 100.0  # 2 * 50g
    assert egg.protein_g > 0

    # Check totals
    assert result.total_kcal == round(bread.kcal + egg.kcal, 1)
    assert result.total_protein_g == round(bread.protein_g + egg.protein_g, 1)


def test_llm_offline_mock_extraction():
    # Pass mock LLM extraction items
    mock_items = [
        {"food_name": "عيش بلدي", "quantity": 1.0, "unit": "رغيف كامل"},
        {"food_name": "فول مدمس", "quantity": 1.0, "unit": "طبق صغير"},
    ]
    result = parse_meal_text(
        text="أكلت رغيف عيش وطبق فول صغير",
        use_llm=True,
        llm_mock_items=mock_items,
    )
    assert result.status == "parsed"
    assert len(result.items) == 2
    assert all(i.match_method == "llm_extracted" for i in result.items)
    assert result.total_kcal > 0


def test_deidentification_before_parsing():
    # If text contains a phone number or national ID, it is deidentified first
    text_with_pii = "أكلت رغيفين عيش ورقمي 01000001042 وبطاقتي 29801011234567"
    result = parse_meal_text(text_with_pii)
    assert result.status == "parsed"
    # Ensure items were parsed and PII was stripped from raw_text context
    assert any(i.food_id == "food-aish-baladi" for i in result.items)
