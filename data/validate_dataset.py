"""Comprehensive dataset validation engine for ClinSight synthetic diabetes data.

Validates schema adherence, quote exactness, clinical trends consistency,
absence rules, UI parity for Patient #1042, refusal benchmarks,
and PDF text layers according to AGENTS.md and evaluation specifications.
"""

from __future__ import annotations

import datetime
import json
import pathlib
import sys
from typing import Any

import pypdf

from data.constants import (
    AS_OF_DATE,
    CARE_GAP_NAMES,
    CARE_GAP_STATUSES,
    PLANTED_FINDING_TYPES,
    REFUSAL_TEXT,
    SEVERITY_LEVELS,
)

DATA_DIR = pathlib.Path(__file__).resolve().parent
SYNTHETIC_DIR = DATA_DIR / "synthetic"
GROUND_TRUTH_DIR = DATA_DIR / "ground_truth"


class ValidationError(Exception):
    """Raised when validation fails."""


def parse_page_texts(txt_path: pathlib.Path) -> dict[int, str]:
    """Parses companion .txt file into a mapping of page_number -> page_text."""
    if not txt_path.exists():
        raise ValidationError(f"Companion text file missing: {txt_path}")

    content = txt_path.read_text(encoding="utf-8")
    pages: dict[int, str] = {}
    current_page = 0
    current_lines: list[str] = []

    for line in content.splitlines():
        if line.startswith("=== PAGE ") and line.endswith(" ==="):
            if current_page > 0:
                pages[current_page] = "\n".join(current_lines)
                current_lines = []
            try:
                current_page = int(line[9:-4].strip())
            except ValueError:
                current_page += 1
        else:
            current_lines.append(line)

    if current_page > 0:
        pages[current_page] = "\n".join(current_lines)

    return pages


def validate_patient(patient_id: str, check_pdf_layers: bool = True) -> list[str]:
    """Validates a single patient's ground truth and synthetic files.

    Returns a list of error messages (empty if valid).
    """
    errors: list[str] = []
    gt_file = GROUND_TRUTH_DIR / f"{patient_id}.json"
    p_dir = SYNTHETIC_DIR / patient_id

    if not gt_file.exists():
        return [f"Ground truth file missing: {gt_file}"]
    if not p_dir.exists():
        return [f"Synthetic patient directory missing: {p_dir}"]

    try:
        with open(gt_file, encoding="utf-8") as f:
            gt: dict[str, Any] = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return [f"Failed to parse JSON in {gt_file}: {e}"]

    # 1. Base schema & as_of_date
    if gt.get("patient_id") != patient_id:
        errors.append(
            f"patient_id mismatch: expected {patient_id}, got {gt.get('patient_id')}"
        )

    if gt.get("as_of_date") != AS_OF_DATE:
        errors.append(
            f"as_of_date mismatch: expected {AS_OF_DATE}, got {gt.get('as_of_date')}"
        )

    as_of = datetime.date.fromisoformat(AS_OF_DATE)
    one_year_prior = as_of - datetime.timedelta(days=365)

    # 2. Demographics & Egyptian identifiers
    demo = gt.get("demographics", {})
    age = demo.get("age", 0)
    if not (39 <= age <= 72):
        errors.append(f"Age {age} outside expected range [39, 72]")

    diabetes_type = demo.get("diabetes_type")
    if diabetes_type not in ["Type 1", "Type 2"]:
        errors.append(f"Invalid diabetes_type: {diabetes_type}")

    meds = demo.get("medications", [])
    if diabetes_type == "Type 1":
        has_insulin = any("insulin" in m.lower() for m in meds)
        has_oral_contraindicated = any(
            "metformin" in m.lower() or "gliclazide" in m.lower() for m in meds
        )
        if not has_insulin:
            errors.append(f"Type 1 patient #{patient_id} must be on insulin")
        if has_oral_contraindicated:
            errors.append(
                f"Type 1 patient #{patient_id} should not be prescribed Metformin or Gliclazide"
            )

    nid = str(demo.get("fake_national_id", ""))
    if len(nid) != 14 or not nid.startswith("9") or not nid.isdigit():
        errors.append(f"Fake national ID '{nid}' must be 14 digits starting with 9")

    phone = str(demo.get("fake_phone", ""))
    if not phone.startswith("01"):
        errors.append(
            f"Fake phone '{phone}' must match Egyptian mobile format (01X XXXX XXXX)"
        )

    # 3. Files Summary & Scans
    files_summary = gt.get("files_summary", {})
    manifest = files_summary.get("manifest", [])
    total_files = len(manifest)

    if not (12 <= total_files <= 17):
        errors.append(f"Total files {total_files} outside range [12, 17]")

    scans = [m for m in manifest if m.get("is_scan", False)]
    if not (2 <= len(scans) <= 3):
        errors.append(f"Unreadable scans count {len(scans)} outside range [2, 3]")

    scan_filenames = {s["file_name"] for s in scans}

    # 4. Planted Findings (exactly 5)
    findings = gt.get("planted_findings", [])
    if len(findings) != 5:
        errors.append(
            f"Patient must have exactly 5 planted findings, found {len(findings)}"
        )

    for f_idx, finding in enumerate(findings, start=1):
        f_type = finding.get("type")
        if f_type not in PLANTED_FINDING_TYPES:
            errors.append(f"Finding {f_idx}: invalid type '{f_type}'")

        sev = finding.get("severity")
        if sev not in SEVERITY_LEVELS:
            errors.append(f"Finding {f_idx}: invalid severity '{sev}'")

        src_file = finding.get("source_file")
        page = finding.get("page")
        quote = finding.get("quote")

        # Scan isolation rule: Scans must NEVER be source of any finding or quote
        if src_file and src_file in scan_filenames:
            errors.append(
                f"Finding {f_idx}: Scanned file '{src_file}' used as finding source (forbidden)"
            )

        # Absence finding
        if src_file is None:
            if quote is not None or page is not None:
                errors.append(f"Finding {f_idx} (absence): quote and page must be null")
        else:
            # Documented finding
            if not quote or not page:
                errors.append(
                    f"Finding {f_idx}: documented finding requires non-empty quote and page"
                )
                continue

            # Verify quotes are in English files only
            if "Arabic" in src_file or "AR" in src_file:
                errors.append(
                    f"Finding {f_idx}: quote placed in Arabic file '{src_file}' (forbidden)"
                )

            # Check text companion
            txt_file = p_dir / (src_file.replace(".pdf", ".txt"))
            if not txt_file.exists():
                errors.append(f"Finding {f_idx}: text file '{txt_file.name}' not found")
                continue

            pages_dict = parse_page_texts(txt_file)
            if page not in pages_dict:
                errors.append(
                    f"Finding {f_idx}: page {page} not found in '{txt_file.name}' (pages: {list(pages_dict.keys())})"
                )
                continue

            page_content = pages_dict[page]
            quote_count = page_content.count(quote)
            if quote_count != 1:
                errors.append(
                    f"Finding {f_idx}: quote must appear exactly once on page {page} of '{src_file}'. "
                    f"Found {quote_count} occurrences. Quote: '{quote[:40]}...'"
                )

    # 5. Care Gaps & Absence Checks
    care_gaps = gt.get("care_gaps", [])
    for cg in care_gaps:
        cg_name = cg.get("name")
        cg_status = cg.get("status")
        if cg_name not in CARE_GAP_NAMES:
            errors.append(f"Unknown care gap name: {cg_name}")
        if cg_status not in CARE_GAP_STATUSES:
            errors.append(f"Unknown care gap status: {cg_status}")

        # Missing UACR check
        if cg_name == "Urine albumin-creatinine ratio" and cg_status == "missing":
            # Verify no readable file within 12 months contains UACR
            for doc in manifest:
                if doc["is_scan"]:
                    continue
                try:
                    doc_date = datetime.date.fromisoformat(doc["date"])
                except ValueError:
                    continue

                if one_year_prior <= doc_date <= as_of:
                    doc_txt = p_dir / doc["file_name"].replace(".pdf", ".txt")
                    if doc_txt.exists():
                        content = doc_txt.read_text(encoding="utf-8").lower()
                        if any(
                            term in content
                            for term in [
                                "uacr",
                                "urine albumin-creatinine",
                                "microalbumin",
                            ]
                        ):
                            errors.append(
                                f"UACR is marked missing, but '{doc['file_name']}' dated {doc_date} mentions albumin/UACR."
                            )

        # Overdue retinal exam check
        if cg_name == "Retinal exam" and cg_status == "overdue":
            # Verify no eye report within 12 months
            for doc in manifest:
                if doc["is_scan"]:
                    continue
                try:
                    doc_date = datetime.date.fromisoformat(doc["date"])
                except ValueError:
                    continue

                if one_year_prior <= doc_date <= as_of and (
                    "eye" in doc["file_name"].lower()
                    or "retin" in doc["file_name"].lower()
                ):
                    errors.append(
                        f"Retinal exam marked overdue, but recent eye document '{doc['file_name']}' exists on {doc_date}."
                    )

    # 6. Trends Cross-Validation with Lab Reports
    trends = gt.get("trends", {})
    hba1c_pts = trends.get("hba1c", [])
    egfr_pts = trends.get("egfr", [])

    if len(hba1c_pts) < 6:
        errors.append(
            f"HbA1c trend must have at least 6 points, found {len(hba1c_pts)}"
        )
    if len(egfr_pts) < 6:
        errors.append(f"eGFR trend must have at least 6 points, found {len(egfr_pts)}")

    for pt in hba1c_pts:
        d_str = pt["date"]
        val = pt["value"]
        lab_txt = p_dir / f"Lab_Report_{d_str}.txt"
        if lab_txt.exists():
            content = lab_txt.read_text(encoding="utf-8")
            if f"{val}%" not in content and f"{val}" not in content:
                errors.append(
                    f"HbA1c value {val}% for date {d_str} not found in {lab_txt.name}"
                )

    for pt in egfr_pts:
        d_str = pt["date"]
        val = int(pt["value"]) if pt["value"].is_integer() else pt["value"]
        # Can be in Lab Report or Nephrology Note
        matched = False
        for f_cand in [
            p_dir / f"Lab_Report_{d_str}.txt",
            p_dir / f"Nephrology_Note_{d_str}.txt",
        ]:
            if f_cand.exists():
                content = f_cand.read_text(encoding="utf-8")
                if str(val) in content:
                    matched = True
                    break
        if not matched:
            errors.append(
                f"eGFR value {val} for date {d_str} not found in corresponding lab or nephrology report"
            )

    # 7. Chat Questions & Refusal Benchmark
    chat_qs = gt.get("chat_questions", [])
    if len(chat_qs) < 6:
        errors.append(f"Chat questions count must be at least 6, found {len(chat_qs)}")

    unanswerable_count = 0
    for q_idx, q in enumerate(chat_qs, start=1):
        ans = q.get("answerable")
        expected_ans = q.get("expected_answer_summary", "")

        if ans is False:
            unanswerable_count += 1
            if expected_ans != REFUSAL_TEXT:
                errors.append(
                    f"Chat question {q_idx} marked unanswerable must exactly equal REFUSAL_TEXT ('{REFUSAL_TEXT}'). "
                    f"Got: '{expected_ans}'"
                )
            if q.get("source_file") is not None or q.get("page") is not None:
                errors.append(
                    f"Chat question {q_idx} unanswerable must have null source_file and page"
                )
        else:
            if not q.get("source_file") or not q.get("page"):
                errors.append(
                    f"Chat question {q_idx} answerable must have source_file and page"
                )

    if unanswerable_count < 4:
        errors.append(
            f"Patient must have at least 4 unanswerable chat questions, found {unanswerable_count}"
        )

    # 8. Patient #1042 UI Demo Parity Exact Checks
    if patient_id == "1042":
        if demo.get("age") != 58 or demo.get("duration_years") != 12:
            errors.append("Patient #1042: age must be 58 and duration 12 years")
        if demo.get("medications") != ["Metformin", "Gliclazide", "Atorvastatin"]:
            errors.append("Patient #1042: medications mismatch")

        expected_hba1c = [7.4, 7.8, 8.1, 8.4, 8.7, 8.9]
        actual_hba1c = [p["value"] for p in hba1c_pts]
        if actual_hba1c != expected_hba1c:
            errors.append(
                f"Patient #1042 HbA1c mismatch: expected {expected_hba1c}, got {actual_hba1c}"
            )

        expected_egfr = [78.0, 74.0, 68.0, 64.0, 61.0, 59.0]
        actual_egfr = [p["value"] for p in egfr_pts]
        if actual_egfr != expected_egfr:
            errors.append(
                f"Patient #1042 eGFR mismatch: expected {expected_egfr}, got {actual_egfr}"
            )

        if total_files != 17 or len(scans) != 3:
            errors.append(
                f"Patient #1042 must have exactly 17 files with 3 scans (got {total_files} files, {len(scans)} scans)"
            )

        neph_txt = p_dir / "Nephrology_Note_2026-06-18.txt"
        if not neph_txt.exists():
            errors.append("Patient #1042 Nephrology_Note_2026-06-18.txt missing")
        else:
            content = neph_txt.read_text(encoding="utf-8")
            target_neph_quote = "Estimated GFR today is 59 mL/min/1.73m², down from 78 at the first visit in March 2025."
            if target_neph_quote not in content:
                errors.append(
                    f"Patient #1042 Nephrology note missing UI demo sentence: '{target_neph_quote}'"
                )

    # 9. Optional PDF Text Layer Extraction Check
    if check_pdf_layers:
        for doc in manifest:
            pdf_path = p_dir / doc["file_name"]
            if not pdf_path.exists():
                continue

            try:
                reader = pypdf.PdfReader(str(pdf_path))
                extracted = "".join(
                    page.extract_text() or "" for page in reader.pages
                ).strip()

                if doc["is_scan"]:
                    if len(extracted) > 0:
                        errors.append(
                            f"Scanned PDF '{doc['file_name']}' has a text layer of length {len(extracted)} (expected 0)"
                        )
                else:
                    if len(extracted) < 20:
                        errors.append(
                            f"Readable PDF '{doc['file_name']}' yielded suspiciously short text ({len(extracted)} chars)"
                        )
            except (pypdf.errors.PdfReadError, OSError) as e:
                errors.append(f"Error inspecting PDF '{doc['file_name']}': {e}")

    return errors


def validate_all_dataset(check_pdf_layers: bool = True) -> dict[str, Any]:
    """Validates all 10 synthetic patients."""
    all_results: dict[str, list[str]] = {}
    total_errors = 0

    patient_ids = [str(i) for i in range(1042, 1052)]
    for pid in patient_ids:
        errs = validate_patient(pid, check_pdf_layers=check_pdf_layers)
        all_results[pid] = errs
        total_errors += len(errs)

    return {
        "success": total_errors == 0,
        "total_errors": total_errors,
        "patients": all_results,
    }


if __name__ == "__main__":
    print("Running ClinSight synthetic dataset validation...")
    res = validate_all_dataset(check_pdf_layers=True)
    if res["success"]:
        print("ALL 10 PATIENTS PASSED VALIDATION WITH 0 ERRORS!")
        sys.exit(0)
    else:
        print(f"VALIDATION FAILED with {res['total_errors']} errors:")
        for pid, errs in res["patients"].items():
            if errs:
                print(f"\n[Patient #{pid}]:")
                for e in errs:
                    print(f"  - {e}")
        sys.exit(1)
