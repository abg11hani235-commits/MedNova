"""Unit tests for shared normalization module (eval/normalize.py)."""

from eval.normalize import (
    matches_all_expected_values,
    try_parse_date,
    try_parse_number,
    value_matches,
)


def test_number_normalization():
    # 9, 9.0, 9.00 equivalence
    assert try_parse_number(9) == 9.0
    assert try_parse_number("9") == 9.0
    assert try_parse_number("9.0") == 9.0
    assert try_parse_number("9.00") == 9.0

    # Matching in text
    assert value_matches(9, "The score was 9.0 points.")
    assert value_matches("9.0", "The score was 9 points.")
    assert value_matches("9.00", "The score was 9.0.")
    assert value_matches("8.1", "HbA1c level is 8.1% on Sept 2025.")
    assert not value_matches(9, "The score was 19 points.")


def test_date_normalization():
    # Parsing dates across formats
    d1 = try_parse_date("2026-06-18")
    d2 = try_parse_date("18 Jun 2026")
    d3 = try_parse_date("Jun 18, 2026")
    assert d1 == d2 == d3
    assert d1.year == 2026 and d1.month == 6 and d1.day == 18

    # Value matching across formats in text
    text_eur = "Patient attended clinic on 18 Jun 2026 for follow-up."
    text_us = "Patient attended clinic on Jun 18, 2026 for follow-up."
    text_iso = "Patient attended clinic on 2026-06-18 for follow-up."

    assert value_matches("2026-06-18", text_eur)
    assert value_matches("2026-06-18", text_us)
    assert value_matches("18 Jun 2026", text_iso)
    assert value_matches("Jun 18, 2026", text_eur)

    # Edge dates in clinical records
    assert value_matches("2023-10-14", "Eye examination performed on 14 Oct 2023.")
    assert value_matches("2025-11-12", "Gliclazide was initiated on 12 Nov 2025.")


def test_text_and_multiple_values():
    assert value_matches("Atorvastatin", "Current medications include Atorvastatin 20mg daily.")
    assert value_matches("sweating", "Reports occasional nocturnal sweating.")
    assert matches_all_expected_values(["8.1", "2025-09-15"], "HbA1c was 8.1% on 15 Sep 2025.")
    assert not matches_all_expected_values(["8.1", "2026-01-01"], "HbA1c was 8.1% on 15 Sep 2025.")
