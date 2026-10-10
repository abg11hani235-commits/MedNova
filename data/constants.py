from __future__ import annotations

import time

# Clinical baseline evaluation date
AS_OF_DATE: str = "2026-06-18"

# Fixed PDF metadata timestamp for deterministic builds (2026-06-18 00:00:00 UTC)
FIXED_PDF_TIMESTAMP: time.struct_time = time.strptime(
    f"{AS_OF_DATE} 00:00:00", "%Y-%m-%d %H:%M:%S"
)


# Exact refusal text mandated by AGENTS.md Rule 3 and evaluation spec (straight apostrophe)
REFUSAL_TEXT: str = "I couldn't find this in the patient's files."

# Allowed planted finding categories
PLANTED_FINDING_TYPES: list[str] = [
    "rising_hba1c",
    "falling_egfr",
    "overdue_retinal_exam",
    "missing_uacr",
    "hypoglycemia_symptoms",
    "medication_changed_no_followup",
    "missed_foot_exam",
    "lipid_panel_overdue",
]

# Allowed severity levels
SEVERITY_LEVELS: list[str] = [
    "info",
    "review",
    "urgent_review",
]

# Standard Care Gap checklist names
CARE_GAP_NAMES: list[str] = [
    "Retinal exam",
    "Foot exam",
    "Urine albumin-creatinine ratio",
    "Lipid panel",
]

# Allowed care gap statuses
CARE_GAP_STATUSES: list[str] = [
    "done",
    "overdue",
    "missing",
]
