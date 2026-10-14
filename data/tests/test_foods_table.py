"""Tests for Egyptian food composition table integrity."""

import json
from pathlib import Path


def test_foods_eg_table_integrity():
    foods_path = Path(__file__).resolve().parent.parent / "foods_eg.json"
    assert foods_path.exists(), "foods_eg.json must exist in data/"

    with open(foods_path, encoding="utf-8") as f:
        foods = json.load(f)

    assert isinstance(foods, list)
    assert len(foods) >= 30, f"Expected at least 30 foods, got {len(foods)}"

    seen_ids = set()
    for food in foods:
        assert "id" in food, "Every food must have an id"
        food_id = food["id"]
        assert food_id not in seen_ids, f"Duplicate food id: {food_id}"
        seen_ids.add(food_id)

        assert food.get("verified") is False, f"Item {food_id} must have verified: false"
        assert (
            food.get("source") == "author estimate, unverified"
        ), f"Item {food_id} must have source 'author estimate, unverified'"

        assert food.get("name_ar"), f"Item {food_id} missing name_ar"
        assert food.get("name_en"), f"Item {food_id} missing name_en"
        assert isinstance(food.get("aliases"), list) and len(food["aliases"]) > 0

        # Portion units
        portion_units = food.get("portion_units")
        assert isinstance(portion_units, list) and len(portion_units) > 0
        for pu in portion_units:
            assert "unit_ar" in pu and "unit_en" in pu and "grams" in pu
            assert pu["grams"] > 0, f"Unit {pu} in {food_id} must have positive grams"

        # Macros
        per_100g = food.get("per_100g")
        assert isinstance(per_100g, dict)
        for nutrient in ("kcal", "protein_g", "carbs_g", "fat_g", "fiber_g"):
            assert nutrient in per_100g, f"Nutrient {nutrient} missing in {food_id}"
            assert per_100g[nutrient] >= 0, f"Nutrient {nutrient} negative in {food_id}"
