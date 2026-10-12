"""Shared normalization module (eval/normalize.py).

Used symmetrically by eval/validate_questions.py and eval/run_eval.py.
Rules:
- Numbers compare as numbers: 9, 9.0 and 9.00 are equal.
- Dates accept ISO (2026-06-18), European (18 Jun 2026) and US (Jun 18, 2026).
- Text compares case-insensitively with whitespace normalized.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

MONTH_REGEX_STR = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"

DATE_ISO_PATTERN = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")
DATE_EUR_PATTERN = re.compile(
    rf"\b(\d{{1,2}})\s+({MONTH_REGEX_STR})\s+(\d{{4}})\b", re.IGNORECASE
)
DATE_US_PATTERN = re.compile(
    rf"\b({MONTH_REGEX_STR})\s+(\d{{1,2}}),?\s+(\d{{4}})\b", re.IGNORECASE
)
NUMBER_PATTERN = re.compile(r"(?<![a-zA-Z0-9])(\d+(?:\.\d+)?)(?![0-9])")


def try_parse_date(val: str) -> date | None:
    """Attempt to parse a date string in ISO, European, or US formats."""
    s = val.strip()
    m = DATE_ISO_PATTERN.fullmatch(s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None

    m = DATE_EUR_PATTERN.fullmatch(s)
    if m:
        day = int(m.group(1))
        mon_str = m.group(2).lower()
        mon = MONTHS.get(mon_str)
        year = int(m.group(3))
        if mon:
            try:
                return date(year, mon, day)
            except ValueError:
                return None

    m = DATE_US_PATTERN.fullmatch(s)
    if m:
        mon_str = m.group(1).lower()
        mon = MONTHS.get(mon_str)
        day = int(m.group(2))
        year = int(m.group(3))
        if mon:
            try:
                return date(year, mon, day)
            except ValueError:
                return None

    return None


def extract_dates(text: str) -> list[date]:
    """Find all dates mentioned in text in ISO, European, or US formats."""
    results: list[date] = []

    for m in DATE_ISO_PATTERN.finditer(text):
        try:
            results.append(date(int(m.group(1)), int(m.group(2)), int(m.group(3))))
        except ValueError:
            pass

    for m in DATE_EUR_PATTERN.finditer(text):
        try:
            day = int(m.group(1))
            mon = MONTHS.get(m.group(2).lower())
            year = int(m.group(3))
            if mon:
                results.append(date(year, mon, day))
        except ValueError:
            pass

    for m in DATE_US_PATTERN.finditer(text):
        try:
            mon = MONTHS.get(m.group(1).lower())
            day = int(m.group(2))
            year = int(m.group(3))
            if mon:
                results.append(date(year, mon, day))
        except ValueError:
            pass

    return results


def try_parse_number(val: Any) -> float | None:
    """Attempt to parse a number (int, float, or numeric string)."""
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        s = val.strip()
        if re.fullmatch(r"^-?\d+(?:\.\d+)?$", s):
            try:
                return float(s)
            except ValueError:
                return None
    return None


def extract_numbers(text: str) -> list[float]:
    """Extract standalone numbers from text."""
    nums: list[float] = []
    for m in NUMBER_PATTERN.finditer(text):
        try:
            nums.append(float(m.group(1)))
        except ValueError:
            pass
    return nums


def value_matches(expected: Any, target_text: str) -> bool:
    """Check if expected value matches or appears in target_text.

    Supports:
    - Number comparison: 9 == 9.0 == 9.00
    - Date comparison: 2026-06-18 == '18 Jun 2026' == 'Jun 18, 2026'
    - Text substring comparison (case-insensitive)
    """
    if expected is None:
        return False

    expected_str = str(expected).strip()

    # 1. Date comparison
    exp_date = try_parse_date(expected_str)
    if exp_date is not None:
        target_dates = extract_dates(target_text)
        if exp_date in target_dates:
            return True
        return exp_date.isoformat() in target_text

    # 2. Number comparison
    exp_num = try_parse_number(expected)
    if exp_num is not None:
        target_nums = extract_numbers(target_text)
        for t_num in target_nums:
            if abs(t_num - exp_num) < 1e-5:
                return True
        return False

    # 3. Textual substring match (case-insensitive)
    exp_clean = " ".join(expected_str.lower().split())
    tgt_clean = " ".join(target_text.lower().split())
    return exp_clean in tgt_clean


def matches_all_expected_values(expected_values: list[Any], target_text: str) -> bool:
    """Return True if all expected values match within target_text."""
    if not expected_values:
        return True
    return all(value_matches(val, target_text) for val in expected_values)
