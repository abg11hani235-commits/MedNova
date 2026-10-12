"""Unit tests for de-identification (AGENTS rule 6)."""

import json
from pathlib import Path

from app.deid import deidentify


def test_national_id_replaced():
    raw = "Patient national ID is 95801010101042 verified by nurse."
    result = deidentify(raw)
    assert "[ID]" in result
    assert "95801010101042" not in result
    assert result == "Patient national ID is [ID] verified by nurse."


def test_egyptian_phone_formats():
    phones = [
        "010 0000 1042",
        "011-1234-5678",
        "01234567890",
        "+20 10 0000 1042",
        "+201512345678",
        "+20 010 1234 5678",
    ]
    for p in phones:
        raw = f"Contact patient at {p} for confirmation."
        result = deidentify(raw)
        assert "[PHONE]" in result, f"Failed to deidentify phone: {p}"
        assert p not in result, f"Phone leaked in output: {p}"


def test_exact_demographics_replaced():
    demographics = {
        "fake_name": "Farouk Adel Mansour",
        "fake_phone": "010 0000 1042",
        "fake_national_id": "95801010101042",
        "fake_address": "14 Al-Tayaran St, Nasr City, Cairo (Demo Clinic)",
    }
    raw = (
        "Patient: Farouk Adel Mansour\n"
        "Address: 14 Al-Tayaran St, Nasr City, Cairo (Demo Clinic)\n"
        "Phone: 010 0000 1042\n"
        "ID: 95801010101042\n"
    )
    result = deidentify(raw, demographics)
    assert "Farouk Adel Mansour" not in result
    assert "14 Al-Tayaran St" not in result
    assert "[NAME]" in result
    assert "[ADDRESS]" in result
    assert "[PHONE]" in result
    assert "[ID]" in result


def test_clinical_content_preserved():
    clinical_text = (
        "BP: 134/82 mmHg. HbA1c: 8.9% on 2026-06-18. "
        "Estimated GFR today is 59 mL/min/1.73m², down from 78. "
        "Patient prescribed Metformin 1000mg twice daily and Atorvastatin 20mg."
    )
    result = deidentify(clinical_text)
    assert result == clinical_text


def test_clinical_values_and_dates_stay_unchanged():
    """Specific regression test for user requirements: '1.73m²', '18 Jun 2026', '8.9%', 'mL/min'."""
    snippets = [
        "1.73m²",
        "18 Jun 2026",
        "8.9%",
        "mL/min",
        "eGFR 58 mL/min/1.73m² recorded on 18 Jun 2026 with HbA1c 8.9%",
        "18-06-2026 visit: eGFR 58 mL/min/1.73m², HbA1c 8.9%",
    ]
    for s in snippets:
        assert deidentify(s) == s, f"Clinical string altered: {s} -> {deidentify(s)}"


def test_all_ground_truth_finding_quotes_survive_unchanged():
    """Verify that every ground-truth planted finding quote survives deidentification untouched."""
    gt_dir = Path(__file__).resolve().parents[2] / "data" / "ground_truth"
    assert gt_dir.exists(), f"Ground truth directory not found: {gt_dir}"

    quotes_tested = 0
    for gt_file in gt_dir.glob("*.json"):
        with open(gt_file, encoding="utf-8") as f:
            data = json.load(f)

        demographics = data.get("demographics", {})
        findings = data.get("planted_findings", [])

        for finding in findings:
            quote = finding.get("quote")
            if quote:
                deidentified = deidentify(quote, demographics)
                assert deidentified == quote, (
                    f"Finding quote was altered in {gt_file.name} finding {finding.get('id')}:\n"
                    f"Original: {quote}\n"
                    f"Deidentified: {deidentified}"
                )
                quotes_tested += 1

    assert quotes_tested > 0, "No finding quotes were found to test."
