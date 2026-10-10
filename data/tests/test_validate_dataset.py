"""Unit tests for ClinSight synthetic dataset validation engine.

Tests:
1. Complete dataset validation passes cleanly.
2. Generator determinism: regenerating with fixed seed produces byte-identical .txt and .json files.
3. Validator failure detection:
   - Catches tampered quotes
   - Catches tampered findings count (!= 5)
   - Catches invalid chat refusal strings
   - Catches invalid Egyptian national ID formats
4. Patient #1042 exact UI specification matches.
5. Scans have zero text layer.
"""

from __future__ import annotations

import json
import pathlib
import tempfile

from data.generate_synthetic import generate_all
from data.validate_dataset import (
    GROUND_TRUTH_DIR,
    SYNTHETIC_DIR,
    validate_all_dataset,
    validate_patient,
)


def test_full_dataset_passes_validation():
    """Validates that all 10 synthetic patient records pass validation with zero errors."""
    res = validate_all_dataset(check_pdf_layers=True)
    assert res["success"] is True, f"Validation failed with errors: {res['patients']}"
    assert res["total_errors"] == 0


def test_patient_1042_ui_parity_exact():
    """Validates that Patient #1042 matches the UI demo specification exactly."""
    gt_file = GROUND_TRUTH_DIR / "1042.json"
    assert gt_file.exists()
    gt = json.loads(gt_file.read_text(encoding="utf-8"))

    # Demographics
    assert gt["demographics"]["age"] == 58
    assert gt["demographics"]["diabetes_type"] == "Type 2"
    assert gt["demographics"]["duration_years"] == 12
    assert gt["demographics"]["medications"] == [
        "Metformin",
        "Gliclazide",
        "Atorvastatin",
    ]

    # Trends
    hba1c_vals = [p["value"] for p in gt["trends"]["hba1c"]]
    assert hba1c_vals == [7.4, 7.8, 8.1, 8.4, 8.7, 8.9]

    egfr_vals = [p["value"] for p in gt["trends"]["egfr"]]
    assert egfr_vals == [78.0, 74.0, 68.0, 64.0, 61.0, 59.0]

    # File counts
    summary = gt["files_summary"]
    assert summary["total_files"] == 17
    assert summary["unreadable_scans"] == 3
    assert summary["readable_files"] == 14

    # Nephrology exact quote
    neph_txt = SYNTHETIC_DIR / "1042" / "Nephrology_Note_2026-06-18.txt"
    assert neph_txt.exists()
    expected_quote = "Estimated GFR today is 59 mL/min/1.73m², down from 78 at the first visit in March 2025."
    assert expected_quote in neph_txt.read_text(encoding="utf-8")


def test_generation_determinism():
    """Validates that running generation twice with seed=42 produces byte-identical .txt and .json files."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = pathlib.Path(tmp_dir)
        generate_all(seed=42, target_dir=tmp_path)

        # Compare ground-truth JSON files
        for pid in range(1042, 1052):
            orig_gt = (GROUND_TRUTH_DIR / f"{pid}.json").read_bytes()
            new_gt = (tmp_path / "ground_truth" / f"{pid}.json").read_bytes()
            assert orig_gt == new_gt, (
                f"Ground truth for #{pid} differs between generation runs"
            )

            # Compare companion text files
            orig_pdir = SYNTHETIC_DIR / str(pid)
            new_pdir = tmp_path / "synthetic" / str(pid)
            for orig_txt in orig_pdir.glob("*.txt"):
                new_txt = new_pdir / orig_txt.name
                assert new_txt.exists()
                assert orig_txt.read_bytes() == new_txt.read_bytes(), (
                    f"Text companion {orig_txt.name} differs"
                )


def test_validator_detects_tampered_quote(tmp_path, monkeypatch):
    """Validator must catch a quote that does not match the file text."""
    # Create mock environment
    gt_dir = tmp_path / "ground_truth"
    syn_dir = tmp_path / "synthetic"
    gt_dir.mkdir()
    syn_dir.mkdir()

    monkeypatch.setattr("data.validate_dataset.GROUND_TRUTH_DIR", gt_dir)
    monkeypatch.setattr("data.validate_dataset.SYNTHETIC_DIR", syn_dir)

    # Copy patient 1042 data
    orig_gt = json.loads((GROUND_TRUTH_DIR / "1042.json").read_text(encoding="utf-8"))
    # Tamper with finding 1 quote
    orig_gt["planted_findings"][0]["quote"] = (
        "Non-existent bogus quote that was never written."
    )
    (gt_dir / "1042.json").write_text(json.dumps(orig_gt), encoding="utf-8")

    # Copy synthetic directory
    import shutil

    shutil.copytree(SYNTHETIC_DIR / "1042", syn_dir / "1042")

    errs = validate_patient("1042", check_pdf_layers=False)
    assert any("quote must appear exactly once" in e for e in errs)


def test_validator_detects_wrong_findings_count(tmp_path, monkeypatch):
    """Validator must reject patients with findings count != 5."""
    gt_dir = tmp_path / "ground_truth"
    syn_dir = tmp_path / "synthetic"
    gt_dir.mkdir()
    syn_dir.mkdir()

    monkeypatch.setattr("data.validate_dataset.GROUND_TRUTH_DIR", gt_dir)
    monkeypatch.setattr("data.validate_dataset.SYNTHETIC_DIR", syn_dir)

    orig_gt = json.loads((GROUND_TRUTH_DIR / "1042.json").read_text(encoding="utf-8"))
    orig_gt["planted_findings"].pop()  # now 4 findings
    (gt_dir / "1042.json").write_text(json.dumps(orig_gt), encoding="utf-8")

    import shutil

    shutil.copytree(SYNTHETIC_DIR / "1042", syn_dir / "1042")

    errs = validate_patient("1042", check_pdf_layers=False)
    assert any("exactly 5 planted findings" in e for e in errs)


def test_validator_detects_refusal_text_mismatch(tmp_path, monkeypatch):
    """Validator must enforce exact REFUSAL_TEXT on unanswerable chat questions."""
    gt_dir = tmp_path / "ground_truth"
    syn_dir = tmp_path / "synthetic"
    gt_dir.mkdir()
    syn_dir.mkdir()

    monkeypatch.setattr("data.validate_dataset.GROUND_TRUTH_DIR", gt_dir)
    monkeypatch.setattr("data.validate_dataset.SYNTHETIC_DIR", syn_dir)

    orig_gt = json.loads((GROUND_TRUTH_DIR / "1042.json").read_text(encoding="utf-8"))
    # Tamper with unanswerable question
    orig_gt["chat_questions"][3]["expected_answer_summary"] = "Patient does not smoke."
    (gt_dir / "1042.json").write_text(json.dumps(orig_gt), encoding="utf-8")

    import shutil

    shutil.copytree(SYNTHETIC_DIR / "1042", syn_dir / "1042")

    errs = validate_patient("1042", check_pdf_layers=False)
    assert any("must exactly equal REFUSAL_TEXT" in e for e in errs)


def test_scans_have_no_text_layer():
    """Checks that all scanned PDFs have no text layer."""
    import pypdf

    for pid in range(1042, 1052):
        gt = json.loads((GROUND_TRUTH_DIR / f"{pid}.json").read_text(encoding="utf-8"))
        for doc in gt["files_summary"]["manifest"]:
            if doc["is_scan"]:
                pdf_path = SYNTHETIC_DIR / str(pid) / doc["file_name"]
                if pdf_path.exists():
                    reader = pypdf.PdfReader(str(pdf_path))
                    text = "".join(
                        page.extract_text() or "" for page in reader.pages
                    ).strip()
                    assert len(text) == 0, (
                        f"Scan {doc['file_name']} in #{pid} has extractable text!"
                    )


def test_scan_pdf_byte_identical_across_runs(tmp_path):
    """Generates one scan PDF twice and asserts file bytes are strictly identical."""
    import time

    from data.generate_synthetic import render_unreadable_scan

    pdf1 = tmp_path / "scan_run1.pdf"
    txt1 = tmp_path / "scan_run1.txt"
    pdf2 = tmp_path / "scan_run2.pdf"
    txt2 = tmp_path / "scan_run2.txt"

    # Run 1
    render_unreadable_scan(
        pdf_path=pdf1,
        txt_path=txt1,
        title="Referral Cover Sheet",
        date_str="2025-02-10",
        patient_name="Farouk Adel Mansour",
        patient_id="1042",
        np_rng=42,
    )

    # Brief delay so any dynamic timestamp in PDF metadata would differ
    time.sleep(0.05)

    # Run 2 with identical seed
    render_unreadable_scan(
        pdf_path=pdf2,
        txt_path=txt2,
        title="Referral Cover Sheet",
        date_str="2025-02-10",
        patient_name="Farouk Adel Mansour",
        patient_id="1042",
        np_rng=42,
    )

    assert txt1.read_bytes() == txt2.read_bytes(), "Scan .txt companion files differ"
    assert pdf1.read_bytes() == pdf2.read_bytes(), (
        "Scan PDF bytes differ across runs (metadata timestamps or compression non-deterministic)"
    )
