"""De-identification module (AGENTS rule 6).

Replaces Egyptian 14-digit national IDs, Egyptian mobile numbers,
and patient demographics with placeholders [NAME] [PHONE] [ID] [ADDRESS].
Preserves clinical values, dates, drug names, and finding quotes untouched.
"""

from __future__ import annotations

import re
from typing import Any

# Egyptian 14-digit national IDs (often starts with 2 or 3, or 9 in synthetic demo data)
NATIONAL_ID_REGEX = re.compile(r"\b\d{14}\b")

# Egyptian mobile numbers: 010, 011, 012, 015 with 8 trailing digits
# (optional spaces/dashes, optional +20/0020)
# Matches 010 0000 1042, 011-1234-5678, +20 10 1234 5678, +2001012345678, 01234567890
EGYPT_PHONE_REGEX = re.compile(r"(?<!\d)(?:(?:\+20|0020)[\s-]?)?0?1[0125](?:[\s-]?\d){8}(?!\d)")


def deidentify(text: str, known_values: dict[str, Any] | None = None) -> str:
    """De-identify text by replacing PII with placeholders.

    Known values from patient ground-truth demographics (fake_name, fake_phone,
    fake_national_id, fake_address) are replaced first.
    General patterns (14-digit IDs, Egyptian mobile phones) are replaced next.
    Clinical text (numbers, dates, units, drug names) remains unaltered.
    """
    if not text:
        return ""

    result = text

    if known_values:
        demographics = known_values.get("demographics")
        if not isinstance(demographics, dict):
            demographics = {}

        address = (
            known_values.get("fake_address")
            or known_values.get("address")
            or demographics.get("fake_address")
        )
        name = (
            known_values.get("fake_name")
            or known_values.get("name")
            or demographics.get("fake_name")
        )
        phone = (
            known_values.get("fake_phone")
            or known_values.get("phone")
            or demographics.get("fake_phone")
        )
        national_id = (
            known_values.get("fake_national_id")
            or known_values.get("fake_id")
            or known_values.get("national_id")
            or demographics.get("fake_national_id")
        )

        if address and str(address).strip():
            result = result.replace(str(address).strip(), "[ADDRESS]")

        if name and str(name).strip():
            result = result.replace(str(name).strip(), "[NAME]")

        if phone and str(phone).strip():
            result = result.replace(str(phone).strip(), "[PHONE]")

        if national_id and str(national_id).strip():
            result = result.replace(str(national_id).strip(), "[ID]")

    # Replace Egyptian 14-digit national IDs
    result = NATIONAL_ID_REGEX.sub("[ID]", result)

    # Replace Egyptian mobile numbers
    result = EGYPT_PHONE_REGEX.sub("[PHONE]", result)

    return result
