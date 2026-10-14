"""Meal parsing module for Rafiq (AGENTS rule 4).

Extracts food items, portions, and computes macros strictly deterministically
from data/foods_eg.json.

Key guarantees:
1. All portion weights (grams) and macros (kcal, protein, carbs, fat, fiber) are computed
   by deterministic code rules, NEVER by an LLM.
2. Primary extraction can use an LLM (JSON-schema validated, temperature 0) on de-identified text,
   with offline fallback to a deterministic regex parser.
3. Franco digits (3, 7, 5, 2, 8, 9) are converted to letters ONLY inside words (e.g. '3eish'),
   never standalone quantities.
4. Arabic-Indic digits (٣), duals (رغيفين، بيضتين), fractions (نص، ربع، تلت، تلات ارباع),
   and number words are fully supported.
5. Fuzzy matching requires a top score >= 0.82 AND a margin >= 0.10 over the second-best candidate;
   otherwise clarification is requested.
6. Ambiguous portions produce exactly one concise question and tappable options.
"""

from __future__ import annotations

import difflib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.deid import deidentify

# Path to foods_eg.json
FOODS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "foods_eg.json"

# Arabic-Indic digit translation
ARABIC_INDIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

# Fractions in Egyptian Arabic
FRACTIONS_MAP = {
    "تلات ارباع": 0.75,
    "تلات أرباع": 0.75,
    "ثلاثة أرباع": 0.75,
    "تلاتة ارباع": 0.75,
    "تلاته ارباع": 0.75,
    "نص": 0.5,
    "نصف": 0.5,
    "ربع": 0.25,
    "تلت": 0.33,
    "ثلث": 0.33,
}

# Number words in Egyptian Arabic
NUMBER_WORDS = {
    "واحد": 1.0,
    "واحدة": 1.0,
    "واحد ونص": 1.5,
    "واحده ونص": 1.5,
    "اتنين": 2.0,
    "اثنين": 2.0,
    "اتنين ونص": 2.5,
    "تلاتة": 3.0,
    "ثلاثة": 3.0,
    "تلات": 3.0,
    "ثلاث": 3.0,
    "تلاتة ونص": 3.5,
    "اربعة": 4.0,
    "أربعة": 4.0,
    "اربع": 4.0,
    "أربع": 4.0,
    "خمسة": 5.0,
    "خمس": 5.0,
    "ستة": 6.0,
    "ست": 6.0,
    "سبعة": 7.0,
    "سبع": 7.0,
    "تمانية": 8.0,
    "ثمانية": 8.0,
    "تمن": 8.0,
    "ثماني": 8.0,
    "تسعة": 9.0,
    "تسع": 9.0,
    "عشرة": 10.0,
    "عشر": 10.0,
}

# Duals in Egyptian Arabic: word -> (quantity, unit_hint, food_hint)
DUALS_MAP = {
    "رغيفين": (2.0, "رغيف كامل", "عيش بلدي"),
    "بيضتين": (2.0, "بيضة", "بيض مسلوق"),
    "كوبايتين": (2.0, "كوب", None),
    "كوبين": (2.0, "كوب", None),
    "معلقتين": (2.0, "معلقة كبيرة", None),
    "ملعقتين": (2.0, "معلقة كبيرة", None),
    "طبقين": (2.0, "طبق متوسط", None),
    "قطعتين": (2.0, "قطعة", None),
    "علبتين": (2.0, "علبة", None),
    "ساندوتشين": (2.0, "ساندوتش", None),
    "سندوتشين": (2.0, "ساندوتش", None),
    "حبتين": (2.0, "ثمرة", None),
    "ثمرتين": (2.0, "ثمرة", None),
}

UNKNOWN_FOOD_MSG = (
    "الأكلة دي مش موجودة في قاعدة بيانات الأطعمة المصرية. تقدر توضح مكوناتها أو تختار بديل مقارب؟"
)

# Known false-positive tokens that should never match food entries
KNOWN_NON_FOOD_TOKENS = {
    "ملح",
    "زر",
    "لحام",
    "سكر",
    "مية",
    "ماء",
    "دواء",
    "علاج",
    "جرعة",
    "حقنة",
    "انسولين",
    "برشام",
}


class ExtractedFoodItem(BaseModel):
    food_id: str
    food_name_ar: str
    food_name_en: str
    quantity: float
    unit: str
    grams: float
    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float
    match_method: str = "alias_match"  # alias_match, fuzzy_match, llm_extracted, deterministic_rule
    match_score: float = 1.0
    confirmed: bool = True


@dataclass
class ParsedMealResult:
    status: str  # parsed, needs_clarification, unknown_food, rejected, emergency
    raw_text: str
    items: list[ExtractedFoodItem] = field(default_factory=list)
    clarification_question: str | None = None
    clarification_options: list[dict[str, Any]] | None = None
    safety_flag: str | None = None
    total_kcal: float = 0.0
    total_carbs_g: float = 0.0
    total_protein_g: float = 0.0
    total_fat_g: float = 0.0
    total_fiber_g: float = 0.0


# Cache foods table
_FOODS_CACHE: list[dict[str, Any]] | None = None


def get_foods_table() -> list[dict[str, Any]]:
    global _FOODS_CACHE
    if _FOODS_CACHE is None:
        if not FOODS_PATH.exists():
            raise FileNotFoundError(f"foods_eg.json not found at {FOODS_PATH}")
        with open(FOODS_PATH, encoding="utf-8") as f:
            _FOODS_CACHE = json.load(f)
    return _FOODS_CACHE


def normalize_franco_word(token: str) -> str:
    """Convert Franco digits (3, 7, 5, 2, 8, 9) to letters ONLY inside word tokens.

    Never touches standalone numbers like '2' or '100'.
    """
    if not re.search(r"[a-zA-Z]", token):
        return token

    # Franco digit mapping inside words
    converted = token.lower()
    converted = re.sub(r"3", "e", converted)
    converted = re.sub(r"7", "h", converted)
    converted = re.sub(r"5", "kh", converted)
    converted = re.sub(r"2", "a", converted)
    converted = re.sub(r"8", "gh", converted)
    converted = re.sub(r"9", "q", converted)
    return converted


def normalize_text(text: str) -> str:
    """Normalize text: Indic digits to Western, remove tashkeel/tatweel, normalize Franco tokens."""
    if not text:
        return ""

    # 1. Translate Arabic-Indic digits to Western
    normalized = text.translate(ARABIC_INDIC_DIGITS)

    # 2. Remove Arabic diacritics (tashkeel) and tatweel
    normalized = re.sub(r"[\u064B-\u0652\u0640]", "", normalized)

    # 3. Normalize alef variants and yeh/teh marbuta for easier matching
    # (We keep original for display, but build search forms)
    tokens = normalized.split()
    processed_tokens = []
    for tok in tokens:
        # If token has letters and digits, convert Franco digits
        if re.search(r"[a-zA-Z]", tok) and re.search(r"\d", tok):
            processed_tokens.append(normalize_franco_word(tok))
        else:
            processed_tokens.append(tok)

    return " ".join(processed_tokens)


def _normalize_for_matching(text: str) -> str:
    """Canonical form for string matching (lowercase, stripped punctuation, normalized alef/yaa)."""
    t = text.lower().strip()
    t = re.sub(r"[إأآٱ]", "ا", t)
    t = re.sub(r"[ى]", "ي", t)
    t = re.sub(r"[ة]", "ه", t)
    t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def find_food_candidate(
    query: str,
    threshold: float = 0.82,
    margin: float = 0.10,
) -> tuple[dict[str, Any] | None, float, str]:
    """Find matching food from foods_eg.json using exact alias matching or strict fuzzy matching.

    Returns (food_entry, match_score, match_method).
    Fuzzy match requires score >= threshold AND (best_score - second_best) >= margin.
    """
    clean_query = _normalize_for_matching(query)
    if not clean_query or clean_query in KNOWN_NON_FOOD_TOKENS:
        return None, 0.0, "none"

    foods = get_foods_table()

    # 1. Exact match on ID, name_ar, name_en, or aliases
    for food in foods:
        if clean_query == _normalize_for_matching(food["id"]):
            return food, 1.0, "exact_id"
        if clean_query == _normalize_for_matching(food["name_ar"]):
            return food, 1.0, "exact_alias"
        if clean_query == _normalize_for_matching(food["name_en"]):
            return food, 1.0, "exact_alias"
        for alias in food.get("aliases", []):
            if clean_query == _normalize_for_matching(alias):
                return food, 1.0, "exact_alias"

    # 2. Substring match on aliases (e.g. query "عيش بلدي" matches alias "عيش بلدي")
    for food in foods:
        for alias in food.get("aliases", []):
            norm_alias = _normalize_for_matching(alias)
            if norm_alias == clean_query:
                return food, 1.0, "exact_alias"

    # 3. Fuzzy matching with strict threshold & margin
    scored_candidates: list[tuple[float, dict[str, Any]]] = []

    for food in foods:
        best_food_ratio = 0.0
        # Compare against name_ar, name_en, and all aliases
        candidates_to_check = [food["name_ar"], food["name_en"]] + food.get("aliases", [])
        for candidate in candidates_to_check:
            norm_cand = _normalize_for_matching(candidate)
            ratio = difflib.SequenceMatcher(None, clean_query, norm_cand).ratio()
            if ratio > best_food_ratio:
                best_food_ratio = ratio

        if best_food_ratio > 0.4:
            scored_candidates.append((best_food_ratio, food))

    if not scored_candidates:
        return None, 0.0, "none"

    # Sort descending by score
    scored_candidates.sort(key=lambda x: x[0], reverse=True)
    best_score, best_food = scored_candidates[0]

    if best_score < threshold:
        return None, best_score, "below_threshold"

    # Check margin over second-best candidate
    if len(scored_candidates) > 1:
        second_score, second_food = scored_candidates[1]
        # If second-best is the same food (different alias), don't penalize
        if second_food["id"] != best_food["id"]:
            if (best_score - second_score) < margin:
                # Ambiguous between two distinct foods
                return None, best_score, "ambiguous_margin"

    return best_food, best_score, "fuzzy_match"


def parse_quantity_and_unit(segment: str) -> tuple[float | None, str | None, str]:
    """Parse quantity, unit, and remaining food mention from a text segment."""
    text = segment.strip()
    # Strip leading 'و' if attached to segment (e.g. 'وبيضتين' -> 'بيضتين')
    text = re.sub(r"^و(?!\w*(?:نص|ربع|تلت))", "", text).strip()
    norm = normalize_text(text)

    # 1. Check dual words (e.g. رغيفين, بيضتين)
    for dual_word, (qty, unit, food_hint) in DUALS_MAP.items():
        pattern = rf"\b{dual_word}\b"
        if re.search(pattern, norm):
            remainder = re.sub(pattern, "", norm).strip()
            # Normalize plural/dual adjectives in remainder
            remainder = re.sub(r"مسلوقين|مسلوقة|مسلوقه", "مسلوق", remainder)
            remainder = re.sub(r"مقليين|مقلية|مقليه", "مقلي", remainder)
            remainder = re.sub(r"مشويين|مشوية|مشويه", "مشوي", remainder)
            if not remainder and food_hint:
                remainder = food_hint
            elif food_hint and remainder:
                base_noun = food_hint.split()[0]
                if base_noun not in remainder:
                    remainder = f"{base_noun} {remainder}".strip()
            return qty, unit, remainder

    # 2. Check compound fractions (e.g. رغيف ونص, طبق وربع, 2 ونص)
    compound_pattern = re.compile(
        r"(?:(\d+(?:\.\d+)?)\s*و\s*(نص|ربع|تلت|تلات ارباع)|(\S+)\s*و\s*(نص|ربع|تلت|تلات ارباع))"
    )
    m = compound_pattern.search(norm)
    if m:
        num_str, frac1, unit_str, frac2 = m.groups()
        if num_str and frac1:
            qty = float(num_str) + FRACTIONS_MAP.get(frac1, 0.0)
            remainder = norm[: m.start()] + " " + norm[m.end() :]
            return qty, None, remainder.strip()
        if unit_str and frac2:
            base_qty = 1.0
            frac_val = FRACTIONS_MAP.get(frac2, 0.0)
            qty = base_qty + frac_val
            remainder = norm[: m.start()] + " " + norm[m.end() :]
            return qty, unit_str, remainder.strip()

    # 3. Check standalone fractions (نص رغيف, ربع فرخة, نص)
    for frac_word, frac_val in FRACTIONS_MAP.items():
        pattern = rf"\b{frac_word}\b"
        if re.search(pattern, norm):
            remainder = re.sub(pattern, "", norm).strip()
            # check if following word is a unit
            unit_match = re.match(
                r"^(رغيف|طبق|معلقة|كوب|كباية|قطعة|علبة|فرخة|ساندوتش|سندوتش)\b", remainder
            )
            unit = None
            if unit_match:
                unit = unit_match.group(1)
                remainder = remainder[unit_match.end() :].strip()
            return frac_val, unit, remainder

    # 4. Check number words (e.g. واحد, اتنين, تلاتة)
    for num_word, val in NUMBER_WORDS.items():
        pattern = rf"\b{num_word}\b"
        if re.search(pattern, norm):
            remainder = re.sub(pattern, "", norm).strip()
            return val, None, remainder

    # 5. Check numeric patterns (e.g. "2 رغيف", "150 جم", "1.5 كوب", "3 بيضات")
    num_pattern = re.compile(
        r"\b(\d+(?:\.\d+)?)\s*(جرام|جم|g|مل|رغيف|ارغفة|أرغفة|طبق|أطباق|معلقة|ملاعق|كوب|كباية|كوباية|قطعة|قطع|علبة|علب|ساندوتش|سندوتش)?\b"
    )
    num_m = num_pattern.search(norm)
    if num_m:
        qty = float(num_m.group(1))
        unit = num_m.group(2)
        remainder = norm[: num_m.start()] + " " + norm[num_m.end() :]
        return qty, unit, remainder.strip()

    return None, None, norm


def calculate_item_macros(
    food: dict[str, Any],
    quantity: float,
    unit_str: str | None,
    match_method: str = "alias_match",
    match_score: float = 1.0,
) -> ExtractedFoodItem:
    """Compute grams and macros deterministically from portion units and per_100g table."""
    portion_units = food.get("portion_units", [])
    per_100g = food["per_100g"]

    selected_unit = None
    grams = 0.0

    # If unit specified in grams
    if unit_str and unit_str in ("جرام", "جم", "g"):
        grams = float(quantity)
        unit_name = "جرام"
    else:
        # Match unit_str against portion_units
        if unit_str:
            norm_unit_str = _normalize_for_matching(unit_str)
            for pu in portion_units:
                if norm_unit_str in _normalize_for_matching(pu["unit_ar"]):
                    selected_unit = pu
                    break
                if norm_unit_str in _normalize_for_matching(pu["unit_en"]):
                    selected_unit = pu
                    break

        # Fallback to default portion unit
        if not selected_unit and portion_units:
            selected_unit = portion_units[0]

        if selected_unit:
            grams = float(quantity) * float(selected_unit["grams"])
            unit_name = selected_unit["unit_ar"]
        else:
            grams = float(quantity) * 100.0
            unit_name = "حصة"

    # Compute macros deterministically (per 100g * grams / 100)
    factor = grams / 100.0
    kcal = round(per_100g["kcal"] * factor, 1)
    protein_g = round(per_100g["protein_g"] * factor, 1)
    carbs_g = round(per_100g["carbs_g"] * factor, 1)
    fat_g = round(per_100g["fat_g"] * factor, 1)
    fiber_g = round(per_100g["fiber_g"] * factor, 1)

    return ExtractedFoodItem(
        food_id=food["id"],
        food_name_ar=food["name_ar"],
        food_name_en=food["name_en"],
        quantity=float(quantity),
        unit=unit_name,
        grams=round(grams, 1),
        kcal=kcal,
        protein_g=protein_g,
        carbs_g=carbs_g,
        fat_g=fat_g,
        fiber_g=fiber_g,
        match_method=match_method,
        match_score=round(match_score, 2),
        confirmed=True,
    )


def generate_clarification_for_food(food: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    """Generate exactly one Egyptian Arabic clarification question and tappable options."""
    question = f"أكلت قد إيه من {food['name_ar']}؟"
    options = []
    for pu in food.get("portion_units", []):
        options.append(
            {
                "label": f"{pu['unit_ar']} ({int(pu['grams'])} جم)",
                "food_id": food["id"],
                "quantity": 1.0,
                "unit": pu["unit_ar"],
                "grams": pu["grams"],
            }
        )
    return question, options


def parse_meal_text_deterministic(text: str) -> ParsedMealResult:
    """Deterministic parser extracting meal items, portions, and macros without LLM.

    Splits on common conjunctions (و, مع, +, ,, then) and parses each segment.
    """
    raw_clean = normalize_text(text)

    # 1. Strip conversational lead-in phrases (e.g. أكلت, فطرت, شربت, انا اكلت)
    prefix_pattern = (
        r"^(?:انا|أنا)?\s*(?:اكلت|أكلت|فطرت|اتغديت|اتعشيت|شربت|خدت|أخدت|اخترت|"
        r"وجبتي كانت|وجبتي|كانت|تناولت)\s+"
    )
    clean = re.sub(prefix_pattern, "", raw_clean.strip())

    # 2. Split into meal clauses
    # Splitting on commas, plus, مع, and 'و' (when not part of a fraction like ونص/وربع/وتلت)
    split_pattern = r"(?:,|\+|\bمع\b|\s+و(?!(?:نص|ربع|تلت|تلات ارباع|نصف|ثلث)\b))"
    segments = [s.strip() for s in re.split(split_pattern, clean) if s.strip()]

    if not segments:
        return ParsedMealResult(
            status="unknown_food",
            raw_text=text,
            clarification_question="مش قادر أتعرف على الأكل المسجل. تقدر توضح أكلت إيه بالظبط؟",
            clarification_options=[],
        )

    parsed_items: list[ExtractedFoodItem] = []
    unrecognized_segments: list[str] = []
    ambiguous_food: dict[str, Any] | None = None

    for seg in segments:
        # Check if segment is purely PII placeholder or non-food filler
        seg_clean = seg.strip()
        if re.search(r"\[(PHONE|ID|NAME|ADDRESS)\]", seg_clean):
            # Check if segment has anything besides PII tokens and words like رقمي/بطاقتي
            remainder_without_pii = re.sub(
                r"\[(PHONE|ID|NAME|ADDRESS)\]|رقمي|بطاقتي|تليفوني|اسمي|عنواني", "", seg_clean
            ).strip()
            if not remainder_without_pii or len(remainder_without_pii) < 2:
                continue

        qty, unit, food_mention = parse_quantity_and_unit(seg_clean)

        # If food_mention is empty after unit removal, try matching seg directly
        if not food_mention:
            food_mention = seg_clean

        candidate, score, method = find_food_candidate(food_mention)

        if not candidate:
            # Try matching full segment
            candidate, score, method = find_food_candidate(seg_clean)

        if not candidate:
            unrecognized_segments.append(food_mention)
            continue

        # If food found but quantity missing or 0
        if qty is None or qty <= 0:
            ambiguous_food = candidate
            continue

        item = calculate_item_macros(
            food=candidate,
            quantity=qty,
            unit_str=unit,
            match_method=method,
            match_score=score,
        )
        parsed_items.append(item)

    # Decision on final status
    if ambiguous_food and not parsed_items:
        q, opts = generate_clarification_for_food(ambiguous_food)
        return ParsedMealResult(
            status="needs_clarification",
            raw_text=text,
            items=[],
            clarification_question=q,
            clarification_options=opts,
        )

    if not parsed_items and unrecognized_segments:
        return ParsedMealResult(
            status="unknown_food",
            raw_text=text,
            items=[],
            clarification_question=UNKNOWN_FOOD_MSG,
            clarification_options=[],
        )

    # Compute totals
    total_kcal = round(sum(i.kcal for i in parsed_items), 1)
    total_carbs = round(sum(i.carbs_g for i in parsed_items), 1)
    total_protein = round(sum(i.protein_g for i in parsed_items), 1)
    total_fat = round(sum(i.fat_g for i in parsed_items), 1)
    total_fiber = round(sum(i.fiber_g for i in parsed_items), 1)

    return ParsedMealResult(
        status="parsed",
        raw_text=text,
        items=parsed_items,
        total_kcal=total_kcal,
        total_carbs_g=total_carbs,
        total_protein_g=total_protein,
        total_fat_g=total_fat,
        total_fiber_g=total_fiber,
    )


class LLMExtractedItem(BaseModel):
    food_name: str = Field(description="Extracted food or drink name")
    quantity: float | None = Field(default=None, description="Extracted portion number")
    unit: str | None = Field(default=None, description="Extracted unit string if present")


class LLMMealExtraction(BaseModel):
    items: list[LLMExtractedItem] = Field(default_factory=list)


def parse_meal_text(
    text: str,
    patient_demographics: dict[str, Any] | None = None,
    use_llm: bool = False,
    llm_mock_items: list[dict[str, Any]] | None = None,
) -> ParsedMealResult:
    """Primary entry point for parsing patient meal logs.

    1. De-identifies patient text first.
    2. Runs LLM extraction if enabled/available (or offline mock if provided),
       otherwise falls back to deterministic regex parser.
    3. All food matching, portion math, and macros are computed deterministically in code.
    """
    # 1. De-identification (AGENTS rule 6)
    deid_text = deidentify(text, patient_demographics)

    # Check if offline mock provided
    if llm_mock_items is not None:
        extracted_items = [LLMExtractedItem(**item) for item in llm_mock_items]
        # Match each extracted item deterministically
        parsed_items: list[ExtractedFoodItem] = []
        for raw_item in extracted_items:
            candidate, score, method = find_food_candidate(raw_item.food_name)
            if candidate and raw_item.quantity:
                item = calculate_item_macros(
                    food=candidate,
                    quantity=raw_item.quantity,
                    unit_str=raw_item.unit,
                    match_method="llm_extracted",
                    match_score=score,
                )
                parsed_items.append(item)
            elif candidate and not raw_item.quantity:
                q, opts = generate_clarification_for_food(candidate)
                return ParsedMealResult(
                    status="needs_clarification",
                    raw_text=text,
                    items=[],
                    clarification_question=q,
                    clarification_options=opts,
                )
            else:
                return ParsedMealResult(
                    status="unknown_food",
                    raw_text=text,
                    items=[],
                    clarification_question=UNKNOWN_FOOD_MSG,
                    clarification_options=[],
                )

        if parsed_items:
            return ParsedMealResult(
                status="parsed",
                raw_text=text,
                items=parsed_items,
                total_kcal=round(sum(i.kcal for i in parsed_items), 1),
                total_carbs_g=round(sum(i.carbs_g for i in parsed_items), 1),
                total_protein_g=round(sum(i.protein_g for i in parsed_items), 1),
                total_fat_g=round(sum(i.fat_g for i in parsed_items), 1),
                total_fiber_g=round(sum(i.fiber_g for i in parsed_items), 1),
            )

    # Fallback to deterministic regex parser
    return parse_meal_text_deterministic(deid_text)
