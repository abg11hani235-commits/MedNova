"""Clinical and nutrition follow-up rules configuration and evaluator for Rafiq.

All thresholds live in this config location.
NOTE: must be reviewed against ADA guidance / a clinician before real use.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

# ==============================================================================
# Clinical & Follow-up Thresholds
# NOTE: must be reviewed against ADA guidance / a clinician before real use.
# ==============================================================================

# Gap threshold in months: overdue if no HbA1c in last N months (ADA: 3-6 mos)
# Clinician to confirm before real clinical use.
HBA1C_GAP_MONTHS: int = 6

# Gap threshold in months: overdue if no renal panel in last N months
# Clinician to confirm before real clinical use.
RENAL_PANEL_GAP_MONTHS: int = 12

# Gap threshold in days: overdue if no meal-log entry in last N days
# Only evaluated if meal-log source exists and is enabled for that patient
# Clinician to confirm before real clinical use.
MEAL_LOG_GAP_DAYS: int = 3

# Weight / BMI check threshold in months
# Clinician to confirm before real clinical use.
WEIGHT_BMI_GAP_MONTHS: int = 12

# Renal function alert thresholds for Metformin review
# Clinician to confirm before real clinical use:
# - eGFR < 60 mL/min/1.73m² (mild-to-moderate impairment): severity "review"
# - eGFR < 30 mL/min/1.73m² (severe reduction / sharp drop): severity "urgent_review"
# - sharp drop: eGFR drop >= 20 mL/min/1.73m² between visits: severity "urgent_review"
METFORMIN_EGFR_REVIEW_THRESHOLD: float = 60.0
METFORMIN_EGFR_URGENT_THRESHOLD: float = 30.0
EGFR_SHARP_DROP_THRESHOLD: float = 20.0

# Standard neutral clinical phrasing for medication considerations (English in UI)
MEDICATION_CONSIDERATION_NOTE_EN: str = "worth reviewing with the treating physician"
MEDICATION_CONSIDERATION_NOTE: str = MEDICATION_CONSIDERATION_NOTE_EN


# ==============================================================================
# Hypoglycemia Symptom Keyword Lists & Negation Patterns
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

# Negation prefixes / phrases in English and Arabic
# When a note matches one of these negation patterns in the same sentence/clause,
# the hypoglycemia finding must NOT fire.
HYPOGLYCEMIA_NEGATION_PATTERNS: list[str] = [
    # English
    r"\bno\s+(?:documented\s+|reported\s+|recurrent\s+|recent\s+|acute\s+)?hypoglycemia\b",
    (
        r"\bdenies\s+(?:any\s+)?"
        r"(?:hypoglycemia|low\s+blood\s+sugar|low\s+glucose|night-time\s+sweating|shakiness|tremors)\b"
    ),
    r"\bno\s+episodes\s+of\s+(?:hypoglycemia|low\s+glucose|low\s+blood\s+sugar)\b",
    r"\bno\s+(?:low\s+glucose|low\s+blood\s+sugar|night-time\s+sweating|cold\s+sweats)\b",
    r"\bwithout\s+(?:any\s+)?(?:hypoglycemia|episodes\s+of\s+low\s+sugar)\b",
    # Arabic
    r"(?:لا\s+يوجد|لا\s+توجد)\s+(?:اي\s+)?(?:هبوط|اعراض\s+هبوط|نقص\s+سكر|انخفاض\s+سكر)",
    r"(?:مفيش|مافيش)\s+(?:اي\s+)?(?:هبوط|اعراض\s+هبوط|سكر\s+واطي|رعشة)",
    r"ينفي\s+(?:حدوث\s+)?(?:اي\s+)?(?:هبوط|اعراض\s+هبوط|نقص\s+سكر)",
    r"تنفي\s+(?:حدوث\s+)?(?:اي\s+)?(?:هبوط|اعراض\s+هبوط|نقص\s+سكر)",
    r"دون\s+(?:اي\s+)?(?:هبوط|اعراض\s+هبوط)",
]

# Phrases that escalate hypoglycemia finding to "urgent_review"
# Clinician to confirm before real clinical use.
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
    hba1c_points: list[dict[str, Any]] | None = None,
    threshold_months: int = HBA1C_GAP_MONTHS,
    *,
    hba1c_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Check if patient has an HbA1c measurement within threshold_months."""
    pts = hba1c_points if hba1c_points is not None else (hba1c_records or [])
    ref_date = _parse_date(as_of_date) or date.today()
    if not pts:
        return {
            "name": "HbA1c",
            "status": "missing",
            "detail": f"No HbA1c test recorded in the last {threshold_months} months.",
            "last_date": None,
        }

    valid_dates = []
    for pt in pts:
        d = _parse_date(pt.get("date"))
        if d:
            valid_dates.append(d)

    if not valid_dates:
        return {
            "name": "HbA1c",
            "status": "missing",
            "detail": f"No HbA1c test recorded in the last {threshold_months} months.",
            "last_date": None,
        }

    latest = max(valid_dates)
    diff_months = _months_between(ref_date, latest)
    d_str = latest.strftime("%Y-%m-%d")
    if diff_months > threshold_months:
        return {
            "name": "HbA1c",
            "status": "overdue",
            "detail": (
                f"HbA1c test overdue (last recorded on {d_str}, > {threshold_months} months ago)."
            ),
            "last_date": latest.isoformat(),
        }

    return {
        "name": "HbA1c",
        "status": "done",
        "detail": f"HbA1c test completed on {d_str}.",
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
            "detail": f"No renal panel recorded in the last {threshold_months} months.",
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
            "detail": f"No renal panel recorded in the last {threshold_months} months.",
            "last_date": None,
        }

    latest = max(valid_dates)
    diff_months = _months_between(ref_date, latest)
    d_str = latest.strftime("%Y-%m-%d")
    if diff_months > threshold_months:
        return {
            "name": "Renal panel",
            "status": "overdue",
            "detail": (
                f"Renal panel overdue (last recorded on {d_str}, > {threshold_months} months ago)."
            ),
            "last_date": latest.isoformat(),
        }

    return {
        "name": "Renal panel",
        "status": "done",
        "detail": f"Renal panel completed on {d_str}.",
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
            "detail": "Meal-log tracking is enabled but no meal entries have been recorded yet.",
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
            "detail": "No valid dates found in meal-log records.",
            "last_date": None,
        }

    latest = max(valid_dates)
    days_diff = (ref_date - latest).days
    d_str = latest.strftime("%Y-%m-%d")
    if days_diff > threshold_days:
        return {
            "name": "Meal log",
            "status": "overdue",
            "detail": (
                f"Meal logging gap: no meals logged for > {threshold_days} days (last log {d_str})."
            ),
            "last_date": latest.isoformat(),
        }

    return {
        "name": "Meal log",
        "status": "done",
        "detail": f"Meal logging is up-to-date (last log {d_str}).",
        "last_date": latest.isoformat(),
    }


def evaluate_weight_bmi_gap(
    as_of_date: str | date,
    weight_records: list[dict[str, Any]] | None,
    threshold_months: int = WEIGHT_BMI_GAP_MONTHS,
) -> dict[str, Any]:
    """Check if patient has weight/BMI recorded within threshold_months."""
    ref_date = _parse_date(as_of_date) or date.today()
    if not weight_records:
        return {
            "name": "Weight/BMI",
            "status": "missing",
            "detail": (
                f"No weight or BMI measurement recorded in the last {threshold_months} months."
            ),
            "last_date": None,
        }

    valid_dates = []
    for r in weight_records:
        d = _parse_date(r.get("date"))
        if d:
            valid_dates.append(d)

    if not valid_dates:
        return {
            "name": "Weight/BMI",
            "status": "missing",
            "detail": (
                f"No weight or BMI measurement recorded in the last {threshold_months} months."
            ),
            "last_date": None,
        }

    latest = max(valid_dates)
    diff_months = _months_between(ref_date, latest)
    d_str = latest.strftime("%Y-%m-%d")
    if diff_months > threshold_months:
        return {
            "name": "Weight/BMI",
            "status": "overdue",
            "detail": (
                f"Weight/BMI measurement overdue (last recorded on {d_str}, "
                f"> {threshold_months} months ago)."
            ),
            "last_date": latest.isoformat(),
        }

    return {
        "name": "Weight/BMI",
        "status": "done",
        "detail": f"Weight/BMI recorded on {d_str}.",
        "last_date": latest.isoformat(),
    }


def is_hypoglycemia_negated(text: str) -> bool:
    """Return True if hypoglycemia keywords appear only within negated phrases."""
    text_clean = re.sub(r"[إأآ]", "ا", text).lower()
    for neg_pat in HYPOGLYCEMIA_NEGATION_PATTERNS:
        pat_clean = re.sub(r"[إأآ]", "ا", neg_pat)
        if re.search(pat_clean, text_clean, re.IGNORECASE):
            return True
    return False


def scan_notes_for_hypoglycemia(
    chunks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Scan visit/clinic notes for hypoglycemia mentions in Arabic and English.

    Severity rules:
    - Negated notes ("no hypoglycemia", "denies hypoglycemia"): ignored (returns []).
    - Emergency / loss of consciousness / coma: 'urgent_review'.
    - Routine / symptomatic mention: 'review'.
    Each returned item includes reason, severity, statement, why, and citation.
    """
    findings = []
    for ch in chunks:
        text = ch.get("text", "")
        if not text:
            continue

        text_lower = text.lower()

        # Check for presence of any hypoglycemia keyword
        matched_kw = None
        for kw in HYPOGLYCEMIA_KEYWORDS:
            if kw in text_lower or kw in text:
                matched_kw = kw
                break

        if not matched_kw:
            continue

        # Check if the mention is negated
        if is_hypoglycemia_negated(text):
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

        chunk_id = ch.get("chunk_id") or ch.get("id", "")
        file_name = ch.get("file_name", "")
        page = ch.get("page", 1)
        doc_date = ch.get("date")

        findings.append(
            {
                "reason": (
                    "Emergency hypoglycemia symptoms documented in clinical notes"
                    if is_emergency
                    else "Hypoglycemia symptoms documented in clinical notes"
                ),
                "severity": sev,
                "statement": (
                    (
                        "Severe hypoglycemia event documented in clinical notes. "
                        "Urgent review recommended."
                    )
                    if is_emergency
                    else "Low glucose symptoms documented in follow-up notes. Review recommended."
                ),
                "why": (
                    (
                        "Severe hypoglycemia episode reported in records; "
                        "requires urgent review with physician."
                    )
                    if is_emergency
                    else (
                        "Documented low glucose symptoms; worth reviewing meal timing "
                        "and medication plan with clinician."
                    )
                ),
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
    egfr_points: list[dict[str, Any]] | None = None,
    citations_by_concept: dict[str, dict[str, Any]] | None = None,
    *,
    egfr_trends: list[dict[str, Any]] | None = None,
    citations: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Generate medication-related considerations without giving prescriptions or dosing.

    Severity rules (clinician to confirm):
    - Slight eGFR reduction below 60 (e.g. 50-59): severity 'review'.
    - Severe reduction (< 30) OR sharp drop (>= 20 points drop): severity 'urgent_review'.
    Always phrased neutrally as 'worth reviewing with the treating physician'.
    Requires a valid source citation to be included.
    """
    items = []
    cits = citations_by_concept if citations_by_concept is not None else (citations or {})
    points = egfr_points if egfr_points is not None else (egfr_trends or [])

    has_metformin = any("metformin" in m.lower() for m in medications)
    if has_metformin and points:
        sorted_egfr = sorted(
            [p for p in points if _parse_date(p.get("date"))],
            key=lambda x: _parse_date(x["date"]),
        )
        if sorted_egfr:
            latest_egfr = sorted_egfr[-1]["value"]
            first_egfr = sorted_egfr[0]["value"]
            drop_amount = first_egfr - latest_egfr if len(sorted_egfr) >= 2 else 0.0

            is_below_review = latest_egfr < METFORMIN_EGFR_REVIEW_THRESHOLD
            has_fallen = len(sorted_egfr) >= 2 and drop_amount > 0

            if is_below_review or has_fallen:
                citation = cits.get("egfr") or cits.get("nephrology")
                if citation:
                    # Severity determination:
                    # eGFR < 30 OR sharp drop >= 20 points -> urgent_review
                    # eGFR slightly below 60 without sharp drop -> review
                    is_urgent = (
                        latest_egfr < METFORMIN_EGFR_URGENT_THRESHOLD
                        or drop_amount >= EGFR_SHARP_DROP_THRESHOLD
                    )
                    sev = "urgent_review" if is_urgent else "review"

                    items.append(
                        {
                            "id": "cons-metformin-egfr",
                            "severity": sev,
                            "statement": (
                                f"eGFR recorded at {latest_egfr} mL/min/1.73m² with ongoing "
                                f"Metformin: {MEDICATION_CONSIDERATION_NOTE_EN}."
                            ),
                            "why": (
                                f"eGFR recorded at {latest_egfr} mL/min/1.73m² while the "
                                "patient is prescribed Metformin. This is "
                                f"{MEDICATION_CONSIDERATION_NOTE_EN}."
                            ),
                            "source": citation,
                        }
                    )

    return items
