"""Safety policy guards for Patient Meal Chat (AGENTS rule 1 & rule 4).

Features:
1. Patient chat clinical/diet policy decline:
   - Declines custom diet plans, target calorie prescriptions, weight loss directives,
     medication/dosing advice, and symptom diagnosis.
   - Preserves plain record lookups ("أكلت إيه امبارح؟").
   - Fixed canonical Egyptian Arabic refusal text:
     "أنا مش بقدم نصايح علاجية أو غذائية. اسأل الأخصائي بتاعك، وأنا هسجل أكلك وأوصله ليه."
2. Emergency triage:
   - Flags severe hypoglycemic symptoms, loss of consciousness, chest pain, diabetic coma.
   - Fixed emergency advisory mentioning Egyptian ambulance (123):
     "دي أعراض طارئة تستدعي تدخل فوري. برجاء التوجه لأقرب طوارئ أو الاتصال بالإسعاف (123) فوراً."
   - Generates safety_flag="emergency_symptom".
3. Daily summary numeric verification:
   - Verifies that EVERY number mentioned in any LLM-phrased summary exists in the DB totals.
   - If any unverified number appears, immediately falls back to a deterministic template.
"""

from __future__ import annotations

import re
from typing import Any

from app.constants import EMERGENCY_SYMPTOM_TEXT, PATIENT_CHAT_DECLINE_TEXT
from app.meal_parser import _normalize_for_matching
from app.rag.policy import should_decline_policy

__all__ = [
    "EMERGENCY_SYMPTOM_TEXT",
    "PATIENT_CHAT_DECLINE_TEXT",
    "is_emergency_symptom",
    "is_plain_record_lookup",
    "should_decline_patient_chat",
    "validate_and_build_daily_summary",
]

# 1. Emergency symptom patterns
_EMERGENCY_PATTERNS = [
    # Arabic: إغماء, أغمى, غيبوبة, هبوط حاد, سكري 40/50, عرق شديد مع زغللة, ألم/وجع بالصدر, ضيق تنفس
    r"(?:اغماء|اغمي|فقدان\s+وعي|غيبوب|هبوط\s+حاد|سكر[ي]?\s*(?:واطي\s+جدا|[3-5][0-9]\b))",
    r"(?:تشنجات|مش\s+قادر\s+اتنفس|صعوب[هة]\s+شديد[هة]\s+في\s+التنفس|ضيق\s+تنفس)",
    r"(?:[أا]لم\s+شديد\s+في\s+الصدر|وجع\s+(?:شديد\s+)?في\s+الصدر|وجع\s+في\s+القلب)",
    r"(?:زغلل[هة]\s+شديد[هة]\s+ومش\s+قادر\s+اقف|عرق\s+بارد\s+شديد\s+ورعش[هة]\s+ومش\s+قادر\s+اتكلم)",
    # English: coma, passed out, unconscious, blood sugar 30/40, chest pain, shortness of breath
    r"\b(?:coma|passed\s+out|unconscious|fainted|fainting|severe\s+hypoglycemia)\b",
    r"\b(?:blood\s+sugar\s+(?:below\s+50|[3-5][0-9]\b)|chest\s+pain|shortness\s+of\s+breath|can'?t\s+breathe)\b",
]
_COMPILED_EMERGENCY = [re.compile(p, re.IGNORECASE) for p in _EMERGENCY_PATTERNS]


# 2. Nutrition/diet plan policy decline patterns
_DIET_PLAN_PATTERNS = [
    # Arabic: اعملي دايت, جدول اكل, نظام غذائي, خطة وجبات, عايز اخس, كم كالوري اكل عشان اخس
    r"(?:اعملي?\s+دايت|اكتبي?\s+دايت|اديني\s+(?:دايت|نظام|خطة|جدول)|جدول\s+اكل|نظام\s+غذائي|خط[هة]\s+وجبات|دايت\s+للتخسيس|حمي[هة]\s+غذائي[هة]|دايت\s+بلان)",
    r"(?:عايز\s+اخس|عايز[هة]\s+اخس|طريق[هة]\s+تخسيس|رجيم|نظام\s+كيتو|دايت\s+لو\s+كارب|ازاي\s+انزل\s+وزني)",
    r"(?:كم\s+كالوري|كام\s+كالوري|كم\s+سعر|كام\s+سعر)\s+(?:محتاج|في\s+اليوم|عشان)",
    r"(?:احسب\s+سعراتي|هدفي\s+من\s+السعرات)",
    # English: meal plan, diet plan, keto diet, daily calorie targets, weight loss diet
    r"\b(?:diet|meal)\s+plan\b",
    r"\b(?:keto|low\s+carb)\s+(?:diet|plan)\b",
    r"\b(?:how\s+many\s+calories\s+should\s+i\s+eat|calorie\s+target|daily\s+calorie\s+limit)\b",
    r"\b(?:how\s+to\s+lose\s+weight|weight\s+loss\s+diet|diet\s+recommendation)\b",
]

_MEDICATION_DOSE_PATTERNS = [
    # Arabic: اوقف الانسولين, اغير الجرعة, اخد كام وحدة, برشام للتخسيس,
    # ازود الميتفورمين, اكتبلي علاج, جرعة أنسولين
    r"(?:اوقف\s+(?:الانسولين|العلاج|الدوا|الميتفورمين)|اغير\s+الجرع|ازود\s+الجرع|انقص\s+الجرع)",
    r"(?:اخد\s+كام\s+وحد|كم\s+وحد[هة]\s+انسولين|جرع[هة]\s+(?:الانسولين|[أا]?نسولين|علاج|دوا|مناسب[هة])|دواء\s+للسكر|برشام)",
    r"(?:اكتبي?|اوصفي?)\s+(?:علاج|دوا|روشتة|[أا]?نسولين|جرع[هة])",
    # English: should i stop insulin, change my dose, what dose of metformin,
    # increase insulin units, prescribe meds
    r"\b(?:should\s+i\s+(?:stop|change|increase|decrease|take|inject))\b",
    r"\b(?:what\s+dose|how\s+many\s+units)\b",
    r"\b(?:prescribe|write\s+me|give\s+me)\s+(?:meds|medicine|medication|insulin|dose|prescription)\b",
]

_DIAGNOSIS_SYMPTOM_PATTERNS = [
    # Arabic: شخص حالتي, هل ده سكر, عندي اعراض ايه, اعطني تشخيص
    r"(?:شخص\s+حالتي|هل\s+عندي\s+سكر|معناه\s+عندي\s+سكر|اعطني\s+تشخيص|تشخيص\s+اعراضي)",
    # English: diagnose me, do i have diabetes, what disease is this
    r"\b(?:diagnose\s+me|do\s+i\s+have\s+diabetes|what\s+condition\s+do\s+i\s+have)\b",
]

_PROMPT_INJECTION_PATTERNS = [
    r"\b(?:ignore|forget|disregard|override)\s+(?:all\s+)?(?:your\s+)?(?:rules|instructions|guidelines|system\s+prompt)\b",
    r"(?:تجاهل\s+(?:كل\s+)?(?:التعليمات|القواعد|السياسات)|تخطى\s+القيود|انسى\s+التعليمات)",
]

_ALL_PATIENT_DECLINE_PATTERNS = (
    _DIET_PLAN_PATTERNS
    + _MEDICATION_DOSE_PATTERNS
    + _DIAGNOSIS_SYMPTOM_PATTERNS
    + _PROMPT_INJECTION_PATTERNS
)
_COMPILED_PATIENT_DECLINE = [re.compile(p, re.IGNORECASE) for p in _ALL_PATIENT_DECLINE_PATTERNS]

# 3. Plain record lookups (ALLOWED)
_RECORD_LOOKUP_PATTERNS = [
    r"(?:اكلت\s+ايه|سجلت\s+ايه|وجباتي\s+امبارح|وجباتي\s+النهارده|تاريخ\s+وجباتي)",
    r"(?:كام\s+سعر|كم\s+سعر|كام\s+كالوري|كم\s+كالوري)\s+(?:اكلته|سجلته|استهلكته|في\s+وجباتي|من\s+الوجبات)",
    r"(?:مجموع\s+اكلي|سجل\s+النهارده|سجل\s+امبارح)",
    r"\b(?:what\s+did\s+i\s+eat|my\s+logged\s+meals|show\s+my\s+meals|how\s+many\s+calories\s+did\s+i\s+eat\s+today)\b",
    r"\b(?:yesterday'?s\s+meals|today'?s\s+logged\s+meals|meal\s+history)\b",
]
_COMPILED_LOOKUP = [re.compile(p, re.IGNORECASE) for p in _RECORD_LOOKUP_PATTERNS]


def is_emergency_symptom(text: str) -> bool:
    """Return True if message mentions emergency or severe hypoglycemic symptoms."""
    if not text:
        return False
    norm_text = _normalize_for_matching(text)
    for p in _COMPILED_EMERGENCY:
        if p.search(text) or p.search(norm_text):
            return True
    return False


def is_plain_record_lookup(text: str) -> bool:
    """Return True if message asks to look up user's own past logged meals."""
    if not text:
        return False
    norm_text = _normalize_for_matching(text)
    for p in _COMPILED_LOOKUP:
        if p.search(text) or p.search(norm_text):
            return True
    return False


def should_decline_patient_chat(text: str) -> bool:
    """Return True if patient message asks for diet plans, calorie goals, meds, or diagnosis.

    Never declines plain meal log inquiries ("أكلت إيه امبارح؟").
    """
    if not text:
        return False

    # Plain record lookups are strictly allowed
    if is_plain_record_lookup(text):
        return False

    # 1. Check patient-specific decline patterns (diets, meds, diagnosis, overrides)
    norm_text = _normalize_for_matching(text)
    for p in _COMPILED_PATIENT_DECLINE:
        if p.search(text) or p.search(norm_text):
            return True

    # 2. Reuse existing general clinical policy guards (prescriptions, dosing, diagnosis, overrides)
    if should_decline_policy(text):
        return True

    return False


def validate_and_build_daily_summary(
    totals: dict[str, Any],
    candidate_text: str | None = None,
) -> str:
    """Build or validate daily nutrition summary.

    Guarantees:
    - Every number appearing in candidate_text MUST be present in the deterministic DB totals.
    - If unverified numbers are found, falls back to the deterministic template.
    """
    total_kcal = float(totals.get("total_kcal", 0.0))
    total_carbs_g = float(totals.get("total_carbs_g", 0.0))
    total_protein_g = float(totals.get("total_protein_g", 0.0))
    total_fat_g = float(totals.get("total_fat_g", 0.0))
    meal_count = int(totals.get("meal_count", 0))

    # Deterministic fallback template (pure code calculation)
    template_summary = (
        f"إجمالي اليوم: {int(total_kcal)} سعر حراري "
        f"({int(total_carbs_g)} جم نشويات، {int(total_protein_g)} جم بروتين، "
        f"{int(total_fat_g)} جم دهون) عبر {meal_count} وجبات مسجلة. (تقديري)"
    )

    if not candidate_text or not candidate_text.strip():
        return template_summary

    # Build set of valid numbers from deterministic totals
    valid_numbers: set[float] = {
        round(total_kcal, 1),
        float(int(total_kcal)),
        round(total_carbs_g, 1),
        float(int(total_carbs_g)),
        round(total_protein_g, 1),
        float(int(total_protein_g)),
        round(total_fat_g, 1),
        float(int(total_fat_g)),
        float(meal_count),
        0.0,
        1.0,
        24.0,  # 24 hours
    }

    # Extract all numbers from candidate text
    extracted_nums = re.findall(r"\b\d+(?:\.\d+)?\b", candidate_text)
    for num_str in extracted_nums:
        val = float(num_str)
        if val not in valid_numbers:
            # Found unverified/hallucinated number -> reject and use deterministic template
            return template_summary

    return candidate_text.strip()
