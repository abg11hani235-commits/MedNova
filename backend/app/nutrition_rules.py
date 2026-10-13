"""Clinical and nutrition follow-up rules configuration and evaluator for Rafiq.

All thresholds live in this config location.
NOTE: must be reviewed against ADA guidance / a clinician before real use.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

# ==============================================================================
# Clinical & Follow-up Thresholds
# NOTE: must be reviewed against ADA guidance / a clinician before real use.
# ==============================================================================

# Gap threshold in months: overdue if no HbA1c in last N months (ADA: 3-6 mos)
HBA1C_GAP_MONTHS: int = 6

# Gap threshold in months: overdue if no renal panel in last N months
RENAL_PANEL_GAP_MONTHS: int = 12

# Gap threshold in days: overdue if no meal-log entry in last N days
# Only evaluated if meal-log source exists and is enabled for that patient
MEAL_LOG_GAP_DAYS: int = 3

# Weight / BMI check threshold in months
WEIGHT_BMI_GAP_MONTHS: int = 12

# Renal function alert threshold (eGFR threshold for Metformin review)
METFORMIN_EGFR_REVIEW_THRESHOLD: float = 60.0

# Standard neutral clinical phrasing for medication considerations
MEDICATION_CONSIDERATION_NOTE: str = "نقطة تستحق المراجعة مع الطبيب المعالج"


# ==============================================================================
# Hypoglycemia Symptom Keyword Lists (English and Arabic)
# ==============================================================================

HYPOGLYCEMIA_KEYWORDS: list[str] = [
    # English
    "hypoglycemia",
    "hypoglycemic",
    "low blood sugar",
    "low glucose",
    "night-time sweating",
    "nocturnal hypoglycemia",
    "cold sweats",
    "lightheadedness",
    "shakiness",
    "tremors",
    # Arabic
    "هبوط سكر",
    "هبوط السكر",
    "انخفاض سكر",
    "انخفاض السكر",
    "نقص السكر",
    "تعرق ليلي",
    "التعرق الليلي",
    "دوخة",
    "رعشة",
]

# Phrases that escalate hypoglycemia finding to "urgent_review"
HYPOGLYCEMIA_EMERGENCY_KEYWORDS: list[str] = [
    # English
    "loss of consciousness",
    "unconscious",
    "passed out",
    "coma",
    "emergency",
    "er visit",
    "hospitalization",
    "seizure",
    # Arabic
    "فقدان الوعي",
    "فقدان وعي",
    "غيبوبة",
    "طوارئ",
    "اسعاف",
    "تشنجات",
]


# ==============================================================================
# Deterministic Rules Evaluator
# ==============================================================================


def _parse_date(d_val: str | date | None) -> date | None:
    if not d_val:
        return None
    if isinstance(d_val, date):
        return d_val
    try:
        return datetime.strptime(d_val[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _months_between(d1: date, d2: date) -> float:
    """Approximate months difference between two dates."""
    return abs((d1 - d2).days) / 30.4375


def evaluate_hba1c_gap(
    as_of_date: str | date,
    hba1c_points: list[dict[str, Any]] | None,
    threshold_months: int = HBA1C_GAP_MONTHS,
) -> dict[str, Any]:
    """Check if patient has an HbA1c measurement within threshold_months."""
    ref_date = _parse_date(as_of_date) or date.today()
    if not hba1c_points:
        return {
            "name": "HbA1c",
            "status": "missing",
            "detail": f"لم يتم تسجيل تحليل السكر التراكمي (HbA1c) في آخر {threshold_months} أشهر",
            "last_date": None,
        }

    valid_dates = []
    for pt in hba1c_points:
        d = _parse_date(pt.get("date"))
        if d:
            valid_dates.append(d)

    if not valid_dates:
        return {
            "name": "HbA1c",
            "status": "missing",
            "detail": f"لم يتم تسجيل تحليل السكر التراكمي (HbA1c) في آخر {threshold_months} أشهر",
            "last_date": None,
        }

    latest = max(valid_dates)
    diff_months = _months_between(ref_date, latest)
    if diff_months > threshold_months:
        d_str = latest.strftime("%Y-%m-%d")
        return {
            "name": "HbA1c",
            "status": "overdue",
            "detail": f"تحليل السكر التراكمي متأخر ({d_str} - أكثر من {threshold_months} أشهر)",
            "last_date": latest.isoformat(),
        }

    return {
        "name": "HbA1c",
        "status": "done",
        "detail": f"تم إجراء الفحص بتاريخ {latest.strftime('%Y-%m-%d')}",
        "last_date": latest.isoformat(),
    }


def evaluate_renal_panel_gap(
    as_of_date: str | date,
    renal_records: list[dict[str, Any]] | None,
    threshold_months: int = RENAL_PANEL_GAP_MONTHS,
) -> dict[str, Any]:
    """Check if patient has a renal panel (creatinine, eGFR, or UACR) in last N months."""
    ref_date = _parse_date(as_of_date) or date.today()
    if not renal_records:
        return {
            "name": "Renal panel",
            "status": "missing",
            "detail": (
                f"لم يتم تسجيل وظائف كلى (eGFR / Creatinine / UACR) في آخر {threshold_months} شهراً"
            ),
            "last_date": None,
        }

    valid_dates = []
    for r in renal_records:
        d = _parse_date(r.get("date"))
        if d:
            valid_dates.append(d)

    if not valid_dates:
        return {
            "name": "Renal panel",
            "status": "missing",
            "detail": f"لم يتم تسجيل وظائف كلى في آخر {threshold_months} شهراً",
            "last_date": None,
        }

    latest = max(valid_dates)
    diff_months = _months_between(ref_date, latest)
    if diff_months > threshold_months:
        d_str = latest.strftime("%Y-%m-%d")
        return {
            "name": "Renal panel",
            "status": "overdue",
            "detail": f"فحص وظائف الكلى متأخر ({d_str} - أكثر من {threshold_months} شهراً)",
            "last_date": latest.isoformat(),
        }

    return {
        "name": "Renal panel",
        "status": "done",
        "detail": f"تم إجراء الفحص بتاريخ {latest.strftime('%Y-%m-%d')}",
        "last_date": latest.isoformat(),
    }


def evaluate_meal_log_gap(
    as_of_date: str | date,
    meal_log_enabled: bool,
    meal_logs: list[dict[str, Any]] | None,
    threshold_days: int = MEAL_LOG_GAP_DAYS,
) -> dict[str, Any] | None:
    """Check for meal log gaps ONLY if meal-log source exists and is enabled for patient.

    If not enabled or no source, returns None (no false gap emitted).
    """
    if not meal_log_enabled:
        return None

    ref_date = _parse_date(as_of_date) or date.today()
    if not meal_logs:
        return {
            "name": "Meal log",
            "status": "missing",
            "detail": "ميزة تسجيل الوجبات مفعلة ولكن لم يتم تسجيل أي وجبات بعد",
            "last_date": None,
        }

    valid_dates = []
    for entry in meal_logs:
        d = _parse_date(entry.get("date"))
        if d:
            valid_dates.append(d)

    if not valid_dates:
        return {
            "name": "Meal log",
            "status": "missing",
            "detail": "لا توجد تواريخ مسجلة في سجل الوجبات",
            "last_date": None,
        }

    latest = max(valid_dates)
    days_diff = (ref_date - latest).days
    if days_diff > threshold_days:
        d_str = latest.strftime("%Y-%m-%d")
        return {
            "name": "Meal log",
            "status": "overdue",
            "detail": (
                f"انقطاع في تسجيل الوجبات منذ أكثر من {threshold_days} أيام (آخر تسجيل {d_str})"
            ),
            "last_date": latest.isoformat(),
        }

    return {
        "name": "Meal log",
        "status": "done",
        "detail": f"سجل الوجبات محدث (آخر تسجيل {latest.strftime('%Y-%m-%d')})",
        "last_date": latest.isoformat(),
    }


def scan_notes_for_hypoglycemia(
    chunks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Scan visit/clinic notes for hypoglycemia mentions in Arabic and English.

    Severity is 'review', or escalates to 'urgent_review' if emergency is mentioned.
    Each returned item includes reason, severity, and source citation.
    """
    findings = []
    for ch in chunks:
        text = ch.get("text", "")
        if not text:
            continue

        text_lower = text.lower()
        matched_kw = None
        for kw in HYPOGLYCEMIA_KEYWORDS:
            if kw in text_lower or kw in text:
                matched_kw = kw
                break

        if not matched_kw:
            continue

        # Check for emergency severity
        is_emergency = any(
            ekw in text_lower or ekw in text for ekw in HYPOGLYCEMIA_EMERGENCY_KEYWORDS
        )
        sev = "urgent_review" if is_emergency else "review"

        # Extract quote surrounding the match
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        quote = ""
        for line in lines:
            line_lower = line.lower()
            if matched_kw in line_lower or matched_kw in line:
                quote = line
                break
        if not quote:
            quote = text[:150].strip()

        chunk_id = ch.get("id", "")
        file_name = ch.get("file_name", "")
        page = ch.get("page", 1)
        doc_date = ch.get("date")

        findings.append(
            {
                "reason": (
                    "رصد أعراض هبوط سكر طارئة في الملاحظات السريرية"
                    if is_emergency
                    else "رصد أعراض هبوط سكر مدونة في الملاحظات السريرية"
                ),
                "severity": sev,
                "statement": (
                    "تم ذكر أعراض هبوط سكر حادة تستدعي مراجعة عاجلة"
                    if is_emergency
                    else "تم رصد أعراض هبوط سكر في ملاحظات المتابعة"
                ),
                "why": "وجود أعراض هبوط سكر يتطلب مراجعة النمط الغذائي وجرعات العلاج مع الطبيب",
                "citation": {
                    "chunk_id": chunk_id,
                    "file_name": file_name,
                    "page": page,
                    "quote": quote,
                    "date": doc_date,
                },
            }
        )
    return findings


def evaluate_medication_considerations(
    medications: list[str],
    egfr_points: list[dict[str, Any]] | None,
    citations_by_concept: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Generate medication-related considerations without giving prescriptions or dosing.

    Always phrased neutrally as 'نقطة تستحق المراجعة مع الطبيب المعالج'.
    Requires a valid source citation to be included.
    """
    items = []
    citations = citations_by_concept or {}

    has_metformin = any("metformin" in m.lower() for m in medications)
    if has_metformin and egfr_points:
        sorted_egfr = sorted(
            [p for p in egfr_points if _parse_date(p.get("date"))],
            key=lambda x: _parse_date(x["date"]),
        )
        if sorted_egfr:
            latest_egfr = sorted_egfr[-1]["value"]
            is_below_threshold = latest_egfr < METFORMIN_EGFR_REVIEW_THRESHOLD
            has_fallen = len(sorted_egfr) >= 2 and sorted_egfr[0]["value"] > latest_egfr

            if is_below_threshold or has_fallen:
                citation = citations.get("egfr") or citations.get("nephrology")
                if citation:
                    items.append(
                        {
                            "id": "cons-metformin-egfr",
                            "severity": "urgent_review" if latest_egfr < 45 else "review",
                            "statement": (
                                f"انخفاض معدل الترشيح الكلي (eGFR: {latest_egfr}) "
                                f"بالتزامن مع استمرار الميتفورمين: {MEDICATION_CONSIDERATION_NOTE}."
                            ),
                            "why": (
                                f"سجل eGFR قيمة {latest_egfr} mL/min/1.73m² بينما المريض "
                                f"يتناول Metformin. {MEDICATION_CONSIDERATION_NOTE}."
                            ),
                            "source": citation,
                        }
                    )
    return items
