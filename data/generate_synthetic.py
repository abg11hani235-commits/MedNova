"""Deterministic synthetic diabetes patient dataset generator for ClinSight.

Generates 10 fictional diabetes patient charts (IDs #1042 - #1051) with PDFs,
plain-text validation companions (.txt), and ground-truth JSON files.
Strictly adheres to AGENTS.md, Egyptian fake identifiers, UI parity specs,
and evaluation benchmark requirements.
"""

from __future__ import annotations

import functools
import json
import pathlib
import random
import shutil
from typing import Any

import arabic_reshaper
import numpy as np
from bidi.algorithm import get_display
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from data.constants import (
    AS_OF_DATE,
    REFUSAL_TEXT,
)

# Root directories
DATA_DIR = pathlib.Path(__file__).resolve().parent
FONTS_DIR = DATA_DIR / "fonts"
SYNTHETIC_DIR = DATA_DIR / "synthetic"
GROUND_TRUTH_DIR = DATA_DIR / "ground_truth"

# Font registration
ARABIC_FONT_PATH = FONTS_DIR / "IBMPlexSansArabic-Regular.ttf"
if ARABIC_FONT_PATH.exists():
    pdfmetrics.registerFont(TTFont("IBMPlexSansArabic", str(ARABIC_FONT_PATH)))


class DocumentBuilder:
    """Helper to build multi-page PDFs and matching .txt companion files."""

    def __init__(self, pdf_path: pathlib.Path, txt_path: pathlib.Path):
        self.pdf_path = pdf_path
        self.txt_path = txt_path
        self.pages_text: list[list[str]] = []
        self.current_page_text: list[str] = []

    def start_page(self) -> None:
        if self.current_page_text:
            self.pages_text.append(self.current_page_text)
            self.current_page_text = []

    def add_line(self, line: str) -> None:
        self.current_page_text.append(line)

    def finalize_pages(self) -> None:
        if self.current_page_text:
            self.pages_text.append(self.current_page_text)
            self.current_page_text = []

    def write_txt(self) -> None:
        self.finalize_pages()
        with open(self.txt_path, "w", encoding="utf-8") as f:
            for idx, page_lines in enumerate(self.pages_text, start=1):
                f.write(f"=== PAGE {idx} ===\n")
                f.writelines(f"{line}\n" for line in page_lines)
                f.write("\n")

    def render_pdf(self, is_arabic: bool = False) -> None:
        self.finalize_pages()
        c = canvas.Canvas(
            str(self.pdf_path), pagesize=letter, invariant=True, pageCompression=0
        )
        c.setTitle(self.pdf_path.stem)
        c.setAuthor("ClinSight Synthetic System")

        width, height = letter
        margin_x = 54.0
        line_height = 14.0

        for page_num, page_lines in enumerate(self.pages_text, start=1):
            y = height - 54.0

            if is_arabic and ARABIC_FONT_PATH.exists():
                c.setFont("IBMPlexSansArabic", 10)
            else:
                c.setFont("Helvetica", 10)

            for line in page_lines:
                if y < 54.0:
                    c.showPage()
                    y = height - 54.0
                    if is_arabic and ARABIC_FONT_PATH.exists():
                        c.setFont("IBMPlexSansArabic", 10)
                    else:
                        c.setFont("Helvetica", 10)

                if is_arabic:
                    try:
                        reshaped = arabic_reshaper.reshape(line)
                        bidi_text = get_display(reshaped)
                        c.drawRightString(width - margin_x, y, bidi_text)
                    except Exception:  # noqa: BLE001
                        c.drawString(margin_x, y, line)
                else:
                    c.drawString(margin_x, y, line)

                y -= line_height

            # Page footer
            c.setFont("Helvetica", 8)
            footer_text = (
                f"Page {page_num} of {len(self.pages_text)} - ClinSight Synthetic Chart"
            )
            c.drawCentredString(width / 2.0, 30.0, footer_text)
            c.showPage()

        c.save()


def render_unreadable_scan(
    pdf_path: pathlib.Path,
    txt_path: pathlib.Path,
    title: str,
    date_str: str,
    patient_name: str,
    patient_id: str,
    np_rng: np.random.Generator,
) -> None:
    """Renders a degraded, image-only scanned document without an extractable text layer."""
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("=== PAGE 1 ===\n")
        f.write("[SCANNED UNREADABLE DOCUMENT - IMAGE ONLY, OCR COULD NOT PROCESS]\n")
        f.write(f"Document Type: {title}\n")
        f.write(f"Date: {date_str}\n")
        f.write(f"Patient Ref: #{patient_id} ({patient_name})\n")
        f.write(
            "Quality Notice: Document illegible due to severe scan degradation and transmission artifacts.\n"
        )

    img_w, img_h = 600, 800
    img = Image.new("L", (img_w, img_h), color=250)
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype(str(ARABIC_FONT_PATH), 14)
        small_font = ImageFont.truetype(str(ARABIC_FONT_PATH), 10)
    except OSError:
        font = ImageFont.load_default()
        small_font = font

    draw.text(
        (40, 40), f"*** TRANSMISSION ARCHIVE: {title.upper()} ***", fill=50, font=font
    )
    draw.text(
        (40, 65),
        f"DATE: {date_str}   PATIENT REF: #{patient_id}",
        fill=80,
        font=small_font,
    )
    draw.line([(40, 85), (560, 85)], fill=100, width=2)

    for i in range(15):
        y = 110 + i * 28
        line_pattern = "##### [ILLEGIBLE ARCHIVE SEGMENT] " * 3
        draw.text((40, y), line_pattern[:45], fill=120, font=small_font)

    streak_x = int(np_rng.integers(100, 500))
    draw.line([(streak_x, 0), (streak_x, img_h)], fill=200, width=1)

    arr = np.array(img, dtype=np.float32)
    noise = np_rng.normal(0, 18, arr.shape)
    arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
    noisy_img = Image.fromarray(arr)

    angle = float(np_rng.uniform(-1.5, 1.5))
    rotated_img = noisy_img.rotate(
        angle, resample=Image.Resampling.BILINEAR, fillcolor=255
    )

    rotated_img.save(str(pdf_path), "PDF")


def _add_manifest_entry(
    manifest: list[dict[str, Any]],
    file_name: str,
    title: str,
    doc_date: str,
    page_cnt: int,
    is_scan: bool,
) -> None:
    manifest.append(
        {
            "file_name": file_name,
            "title": title,
            "date": doc_date,
            "page_count": page_cnt,
            "is_scan": is_scan,
        }
    )


def generate_all(
    seed: int = 42, target_dir: pathlib.Path | None = None
) -> dict[str, Any]:
    """Generates synthetic dataset deterministically."""
    random.seed(seed)
    np_rng = np.random.default_rng(seed)

    base_syn = target_dir / "synthetic" if target_dir else SYNTHETIC_DIR
    base_gt = target_dir / "ground_truth" if target_dir else GROUND_TRUTH_DIR

    base_syn.mkdir(parents=True, exist_ok=True)
    base_gt.mkdir(parents=True, exist_ok=True)

    summary_records: list[dict[str, Any]] = []

    patients_def = [
        # Patient #1042 (Type 2, Age 58) - EXACT UI DEMO MATCH
        {
            "id": "1042",
            "name": "Farouk Adel Mansour",
            "name_ar": "فاروق عادل منصور",
            "age": 58,
            "type": "Type 2",
            "duration": 12,
            "meds": ["Metformin", "Gliclazide", "Atorvastatin"],
            "national_id": "95801010101042",
            "phone": "010 0000 1042",
            "address": "14 Al-Tayaran St, Nasr City, Cairo (Demo Clinic)",
            "visits": [
                ("2025-03-12", "Mar 2025", 7.4, 78.0),
                ("2025-06-18", "Jun 2025", 7.8, 74.0),
                ("2025-09-15", "Sep 2025", 8.1, 68.0),
                ("2025-12-10", "Dec 2025", 8.4, 64.0),
                ("2026-03-18", "Mar 2026", 8.7, 61.0),
                ("2026-06-18", "Jun 2026", 8.9, 59.0),
            ],
            "scan_count": 3,
            "planted_findings": [
                {
                    "id": "f-1042-01",
                    "type": "falling_egfr",
                    "severity": "urgent_review",
                    "statement": "eGFR fell from 78 to 59 over 6 visits while Metformin continues. Worth reviewing.",
                    "source_file": "Nephrology_Note_2026-06-18.pdf",
                    "page": 1,
                    "quote": "Estimated GFR today is 59 mL/min/1.73m², down from 78 at the first visit in March 2025.",
                    "expected_chunk_hint": "Estimated GFR today is 59 mL/min/1.73m², down from 78 at the first visit in March 2025. Patient continues Metformin and Gliclazide as before.",
                },
                {
                    "id": "f-1042-02",
                    "type": "rising_hba1c",
                    "severity": "review",
                    "statement": "HbA1c has risen across 6 visits (7.4 to 8.9). Worth reviewing.",
                    "source_file": "Lab_Report_2026-06-18.pdf",
                    "page": 2,
                    "quote": "Glycated Hemoglobin (HbA1c): 8.9%",
                    "expected_chunk_hint": "Glycated Hemoglobin (HbA1c): 8.9%",
                },
                {
                    "id": "f-1042-03",
                    "type": "missing_uacr",
                    "severity": "review",
                    "statement": "No urine albumin-creatinine ratio found in the last 12 months.",
                    "source_file": None,
                    "page": None,
                    "quote": None,
                    "expected_chunk_hint": "Absence of urine albumin-creatinine ratio test in all readable files within 12 months.",
                },
                {
                    "id": "f-1042-04",
                    "type": "hypoglycemia_symptoms",
                    "severity": "review",
                    "statement": "Night-time low glucose symptoms mentioned in a visit note.",
                    "source_file": "Visit_Note_2026-02-15.pdf",
                    "page": 3,
                    "quote": "Patient reports occasional episodes of night-time sweating and lightheadedness consistent with mild nocturnal low glucose symptoms.",
                    "expected_chunk_hint": "Patient reports occasional episodes of night-time sweating and lightheadedness consistent with mild nocturnal low glucose symptoms.",
                },
                {
                    "id": "f-1042-05",
                    "type": "overdue_retinal_exam",
                    "severity": "review",
                    "statement": "Retinal exam overdue. Last recorded 2023. Worth reviewing.",
                    "source_file": "Eye_Report_2023-10-14.pdf",
                    "page": 1,
                    "quote": "Dilated retinal examination completed on 14 Oct 2023. Next annual retinal screen due in 12 months.",
                    "expected_chunk_hint": "Dilated retinal examination completed on 14 Oct 2023. Next annual retinal screen due in 12 months.",
                },
            ],
            "care_gaps": [
                {
                    "name": "Retinal exam",
                    "status": "overdue",
                    "evidence": "Eye_Report_2023-10-14.pdf p.1 (dated 14 Oct 2023)",
                    "absence_note": None,
                },
                {
                    "name": "Foot exam",
                    "status": "done",
                    "evidence": "Clinic_Note_2026-03-18.pdf p.2 (Foot examination completed this year)",
                    "absence_note": None,
                },
                {
                    "name": "Urine albumin-creatinine ratio",
                    "status": "missing",
                    "evidence": None,
                    "absence_note": "No record in 14 readable files within 12 months of as_of_date (2026-06-18)",
                },
                {
                    "name": "Lipid panel",
                    "status": "done",
                    "evidence": "Lab_Report_2026-03-18.pdf p.4 (Lipid panel completed this year)",
                    "absence_note": None,
                },
            ],
            "chat_questions": [
                {
                    "question": "When was the medication last changed?",
                    "answerable": True,
                    "expected_answer_summary": "Gliclazide was added on 12 Nov 2025. No later changes are documented.",
                    "source_file": "Visit_Note_2025-11-12.pdf",
                    "page": 2,
                },
                {
                    "question": "What was the last HbA1c?",
                    "answerable": True,
                    "expected_answer_summary": "8.9% on 18 Jun 2026.",
                    "source_file": "Lab_Report_2026-06-18.pdf",
                    "page": 2,
                },
                {
                    "question": "When was the last retinal examination completed?",
                    "answerable": True,
                    "expected_answer_summary": "Dilated retinal examination was completed on 14 Oct 2023.",
                    "source_file": "Eye_Report_2023-10-14.pdf",
                    "page": 1,
                },
                {
                    "question": "Does the patient smoke?",
                    "answerable": False,
                    "expected_answer_summary": REFUSAL_TEXT,
                    "source_file": None,
                    "page": None,
                },
                {
                    "question": "What is the patient's family history of premature heart disease?",
                    "answerable": False,
                    "expected_answer_summary": REFUSAL_TEXT,
                    "source_file": None,
                    "page": None,
                },
                {
                    "question": "Which health insurance company covers the patient's prescriptions?",
                    "answerable": False,
                    "expected_answer_summary": REFUSAL_TEXT,
                    "source_file": None,
                    "page": None,
                },
                {
                    "question": "Does the patient have a documented allergy to penicillin?",
                    "answerable": False,
                    "expected_answer_summary": REFUSAL_TEXT,
                    "source_file": None,
                    "page": None,
                },
            ],
        },
        # Patient #1043 (Type 1, Age 46) - on Insulin only
        {
            "id": "1043",
            "name": "Nadia Tarek Soliman",
            "name_ar": "نادية طارق سليمان",
            "age": 46,
            "type": "Type 1",
            "duration": 8,
            "meds": ["Insulin Glargine", "Insulin Lispro"],
            "national_id": "97802020201043",
            "phone": "011 0000 1043",
            "address": "22 El-Galaa St, Dokki, Giza (Demo Health Center)",
            "visits": [
                ("2025-04-08", "Apr 2025", 7.9, 96.0),
                ("2025-07-12", "Jul 2025", 8.2, 95.0),
                ("2025-10-15", "Oct 2025", 8.5, 94.0),
                ("2026-01-10", "Jan 2026", 8.8, 95.0),
                ("2026-04-10", "Apr 2026", 9.1, 93.0),
                ("2026-06-02", "Jun 2026", 9.4, 94.0),
            ],
            "scan_count": 2,
            "planted_findings": [
                {
                    "id": "f-1043-01",
                    "type": "rising_hba1c",
                    "severity": "review",
                    "statement": "HbA1c has risen across 6 visits (7.9 to 9.4). Worth reviewing.",
                    "source_file": "Lab_Report_2026-06-02.pdf",
                    "page": 2,
                    "quote": "Glycated Hemoglobin (HbA1c): 9.4%",
                    "expected_chunk_hint": "Glycated Hemoglobin (HbA1c): 9.4%",
                },
                {
                    "id": "f-1043-02",
                    "type": "hypoglycemia_symptoms",
                    "severity": "review",
                    "statement": "Recurrent daytime hypoglycemia symptoms mentioned in visit note.",
                    "source_file": "Visit_Note_2026-04-10.pdf",
                    "page": 2,
                    "quote": "Patient experiences recurring daytime tremors and hypoglycemia symptoms before meals.",
                    "expected_chunk_hint": "Patient experiences recurring daytime tremors and hypoglycemia symptoms before meals.",
                },
                {
                    "id": "f-1043-03",
                    "type": "overdue_retinal_exam",
                    "severity": "review",
                    "statement": "Retinal exam overdue; last recorded Jan 2024. Worth reviewing.",
                    "source_file": "Eye_Report_2024-01-15.pdf",
                    "page": 1,
                    "quote": "Annual retinal screening completed on 15 Jan 2024. Next review due in 12 months.",
                    "expected_chunk_hint": "Annual retinal screening completed on 15 Jan 2024. Next review due in 12 months.",
                },
                {
                    "id": "f-1043-04",
                    "type": "missed_foot_exam",
                    "severity": "review",
                    "statement": "Diabetic foot examination was missed during recent evaluation.",
                    "source_file": "Visit_Note_2026-06-02.pdf",
                    "page": 1,
                    "quote": "Annual diabetic foot examination was missed due to patient time constraints.",
                    "expected_chunk_hint": "Annual diabetic foot examination was missed due to patient time constraints.",
                },
                {
                    "id": "f-1043-05",
                    "type": "lipid_panel_overdue",
                    "severity": "review",
                    "statement": "Lipid panel is overdue; none recorded in past 12 months.",
                    "source_file": "Lab_Report_2024-08-10.pdf",
                    "page": 1,
                    "quote": "Lipid panel last recorded on 10 Aug 2024.",
                    "expected_chunk_hint": "Lipid panel last recorded on 10 Aug 2024.",
                },
            ],
            "care_gaps": [
                {
                    "name": "Retinal exam",
                    "status": "overdue",
                    "evidence": "Eye_Report_2024-01-15.pdf p.1",
                    "absence_note": None,
                },
                {
                    "name": "Foot exam",
                    "status": "missing",
                    "evidence": "Visit_Note_2026-06-02.pdf p.1",
                    "absence_note": None,
                },
                {
                    "name": "Urine albumin-creatinine ratio",
                    "status": "done",
                    "evidence": "Lab_Report_2026-06-02.pdf p.1",
                    "absence_note": None,
                },
                {
                    "name": "Lipid panel",
                    "status": "overdue",
                    "evidence": "Lab_Report_2024-08-10.pdf p.1",
                    "absence_note": None,
                },
            ],
            "chat_questions": [
                {
                    "question": "What is the latest HbA1c result?",
                    "answerable": True,
                    "expected_answer_summary": "9.4% on 02 Jun 2026.",
                    "source_file": "Lab_Report_2026-06-02.pdf",
                    "page": 2,
                },
                {
                    "question": "What insulin regimen is prescribed?",
                    "answerable": True,
                    "expected_answer_summary": "Insulin Glargine and Insulin Lispro.",
                    "source_file": "Visit_Note_2026-06-02.pdf",
                    "page": 1,
                },
                {
                    "question": "Does the patient consume alcohol?",
                    "answerable": False,
                    "expected_answer_summary": REFUSAL_TEXT,
                    "source_file": None,
                    "page": None,
                },
                {
                    "question": "Has the patient received the annual influenza vaccine?",
                    "answerable": False,
                    "expected_answer_summary": REFUSAL_TEXT,
                    "source_file": None,
                    "page": None,
                },
                {
                    "question": "Does the patient smoke cigarettes?",
                    "answerable": False,
                    "expected_answer_summary": REFUSAL_TEXT,
                    "source_file": None,
                    "page": None,
                },
                {
                    "question": "What health insurance plan does the patient possess?",
                    "answerable": False,
                    "expected_answer_summary": REFUSAL_TEXT,
                    "source_file": None,
                    "page": None,
                },
            ],
        },
        # Patient #1044 (Type 2, Age 67)
        {
            "id": "1044",
            "name": "Ibrahim Samir El-Kady",
            "name_ar": "إبراهيم سمير القاضي",
            "age": 67,
            "type": "Type 2",
            "duration": 15,
            "meds": ["Metformin", "Sitagliptin", "Empagliflozin"],
            "national_id": "95703030301044",
            "phone": "012 0000 1044",
            "address": "7 Abbasia Square, Cairo (Synthetic Clinic)",
            "visits": [
                ("2025-03-20", "Mar 2025", 7.3, 72.0),
                ("2025-06-25", "Jun 2025", 7.4, 67.0),
                ("2025-10-14", "Oct 2025", 7.2, 61.0),
                ("2025-12-28", "Dec 2025", 7.3, 56.0),
                ("2026-03-15", "Mar 2026", 7.5, 52.0),
                ("2026-05-11", "May 2026", 7.4, 48.0),
            ],
            "scan_count": 2,
            "planted_findings": [
                {
                    "id": "f-1044-01",
                    "type": "falling_egfr",
                    "severity": "urgent_review",
                    "statement": "eGFR fell from 72 to 48 over 6 visits. Worth reviewing.",
                    "source_file": "Nephrology_Note_2026-05-11.pdf",
                    "page": 1,
                    "quote": "Estimated GFR is 48 mL/min/1.73m², reflecting a progressive decline from 72.",
                    "expected_chunk_hint": "Estimated GFR is 48 mL/min/1.73m², reflecting a progressive decline from 72.",
                },
                {
                    "id": "f-1044-02",
                    "type": "medication_changed_no_followup",
                    "severity": "review",
                    "statement": "Empagliflozin dosage adjusted without documented follow-up. Worth reviewing.",
                    "source_file": "Visit_Note_2025-10-14.pdf",
                    "page": 2,
                    "quote": "Empagliflozin dosage adjusted to 25 mg daily without subsequent follow-up assessment.",
                    "expected_chunk_hint": "Empagliflozin dosage adjusted to 25 mg daily without subsequent follow-up assessment.",
                },
                {
                    "id": "f-1044-03",
                    "type": "missing_uacr",
                    "severity": "review",
                    "statement": "No urine albumin-creatinine ratio found in the last 12 months.",
                    "source_file": None,
                    "page": None,
                    "quote": None,
                    "expected_chunk_hint": "Absence of UACR result across last 12 months.",
                },
                {
                    "id": "f-1044-04",
                    "type": "overdue_retinal_exam",
                    "severity": "review",
                    "statement": "Retinal exam overdue; last recorded Nov 2023. Worth reviewing.",
                    "source_file": "Eye_Report_2023-11-20.pdf",
                    "page": 1,
                    "quote": "Retinal exam completed on 20 Nov 2023 with mild non-proliferative changes.",
                    "expected_chunk_hint": "Retinal exam completed on 20 Nov 2023 with mild non-proliferative changes.",
                },
                {
                    "id": "f-1044-05",
                    "type": "missed_foot_exam",
                    "severity": "review",
                    "statement": "Diabetic foot examination not performed during latest visit.",
                    "source_file": "Clinic_Note_2026-05-11.pdf",
                    "page": 1,
                    "quote": "Comprehensive foot examination was not performed during this visit.",
                    "expected_chunk_hint": "Comprehensive foot examination was not performed during this visit.",
                },
            ],
            "care_gaps": [
                {
                    "name": "Retinal exam",
                    "status": "overdue",
                    "evidence": "Eye_Report_2023-11-20.pdf p.1",
                    "absence_note": None,
                },
                {
                    "name": "Foot exam",
                    "status": "missing",
                    "evidence": "Clinic_Note_2026-05-11.pdf p.1",
                    "absence_note": None,
                },
                {
                    "name": "Urine albumin-creatinine ratio",
                    "status": "missing",
                    "evidence": None,
                    "absence_note": "No record in readable files within 12 months",
                },
                {
                    "name": "Lipid panel",
                    "status": "done",
                    "evidence": "Lab_Report_2026-05-11.pdf p.1",
                    "absence_note": None,
                },
            ],
            "chat_questions": [
                {
                    "question": "What is the most recent eGFR measurement?",
                    "answerable": True,
                    "expected_answer_summary": "48 mL/min/1.73m² on 11 May 2026.",
                    "source_file": "Nephrology_Note_2026-05-11.pdf",
                    "page": 1,
                },
                {
                    "question": "What dose of Empagliflozin was prescribed?",
                    "answerable": True,
                    "expected_answer_summary": "25 mg daily on 14 Oct 2025.",
                    "source_file": "Visit_Note_2025-10-14.pdf",
                    "page": 2,
                },
                {
                    "question": "Does the patient smoke tobacco?",
                    "answerable": False,
                    "expected_answer_summary": REFUSAL_TEXT,
                    "source_file": None,
                    "page": None,
                },
                {
                    "question": "Does the patient use a hearing aid?",
                    "answerable": False,
                    "expected_answer_summary": REFUSAL_TEXT,
                    "source_file": None,
                    "page": None,
                },
                {
                    "question": "When was the patient's last dental visit?",
                    "answerable": False,
                    "expected_answer_summary": REFUSAL_TEXT,
                    "source_file": None,
                    "page": None,
                },
                {
                    "question": "What is the patient's daily caffeine consumption?",
                    "answerable": False,
                    "expected_answer_summary": REFUSAL_TEXT,
                    "source_file": None,
                    "page": None,
                },
            ],
        },
        # Patient #1045 (Type 2, Age 39)
        {
            "id": "1045",
            "name": "Dina Sherif Radwan",
            "name_ar": "دينا شريف رضوان",
            "age": 39,
            "type": "Type 2",
            "duration": 4,
            "meds": ["Metformin", "Dulaglutide"],
            "national_id": "98504040401045",
            "phone": "015 0000 1045",
            "address": "9 Palestine St, Maadi, Cairo (Fictional Facility)",
            "visits": [
                ("2025-04-14", "Apr 2025", 6.8, 102.0),
                ("2025-07-20", "Jul 2025", 7.3, 100.0),
                ("2025-11-04", "Nov 2025", 7.7, 98.0),
                ("2026-01-18", "Jan 2026", 8.2, 99.0),
                ("2026-03-29", "Mar 2026", 8.6, 97.0),
                ("2026-05-29", "May 2026", 9.0, 96.0),
            ],
            "scan_count": 2,
            "planted_findings": [
                {
                    "id": "f-1045-01",
                    "type": "rising_hba1c",
                    "severity": "review",
                    "statement": "HbA1c has risen across 6 visits (6.8 to 9.0). Worth reviewing.",
                    "source_file": "Lab_Report_2026-05-29.pdf",
                    "page": 2,
                    "quote": "Glycated Hemoglobin (HbA1c): 9.0%",
                    "expected_chunk_hint": "Glycated Hemoglobin (HbA1c): 9.0%",
                },
                {
                    "id": "f-1045-02",
                    "type": "medication_changed_no_followup",
                    "severity": "review",
                    "statement": "Dulaglutide initiated without documented follow-up. Worth reviewing.",
                    "source_file": "Visit_Note_2025-11-04.pdf",
                    "page": 2,
                    "quote": "Dulaglutide initiated at 0.75 mg weekly without documented follow-up.",
                    "expected_chunk_hint": "Dulaglutide initiated at 0.75 mg weekly without documented follow-up.",
                },
                {
                    "id": "f-1045-03",
                    "type": "missing_uacr",
                    "severity": "review",
                    "statement": "No urine albumin-creatinine ratio found in the last 12 months.",
                    "source_file": None,
                    "page": None,
                    "quote": None,
                    "expected_chunk_hint": "Absence of UACR result across last 12 months.",
                },
                {
                    "id": "f-1045-04",
                    "type": "overdue_retinal_exam",
                    "severity": "review",
                    "statement": "Retinal exam overdue; last recorded Feb 2024. Worth reviewing.",
                    "source_file": "Eye_Report_2024-02-18.pdf",
                    "page": 1,
                    "quote": "Routine dilated eye exam performed on 18 Feb 2024. No microaneurysms noted.",
                    "expected_chunk_hint": "Routine dilated eye exam performed on 18 Feb 2024. No microaneurysms noted.",
                },
                {
                    "id": "f-1045-05",
                    "type": "lipid_panel_overdue",
                    "severity": "review",
                    "statement": "Lipid panel is overdue; none recorded in past 12 months.",
                    "source_file": "Lab_Report_2024-09-12.pdf",
                    "page": 1,
                    "quote": "Fasting lipid profile last completed on 12 Sep 2024.",
                    "expected_chunk_hint": "Fasting lipid profile last completed on 12 Sep 2024.",
                },
            ],
            "care_gaps": [
                {
                    "name": "Retinal exam",
                    "status": "overdue",
                    "evidence": "Eye_Report_2024-02-18.pdf p.1",
                    "absence_note": None,
                },
                {
                    "name": "Foot exam",
                    "status": "done",
                    "evidence": "Clinic_Note_2026-05-29.pdf p.1",
                    "absence_note": None,
                },
                {
                    "name": "Urine albumin-creatinine ratio",
                    "status": "missing",
                    "evidence": None,
                    "absence_note": "No record in readable files within 12 months",
                },
                {
                    "name": "Lipid panel",
                    "status": "overdue",
                    "evidence": "Lab_Report_2024-09-12.pdf p.1",
                    "absence_note": None,
                },
            ],
            "chat_questions": [
                {
                    "question": "What was the latest HbA1c value?",
                    "answerable": True,
                    "expected_answer_summary": "9.0% on 29 May 2026.",
                    "source_file": "Lab_Report_2026-05-29.pdf",
                    "page": 2,
                },
                {
                    "question": "What dose of Dulaglutide was started?",
                    "answerable": True,
                    "expected_answer_summary": "0.75 mg weekly on 04 Nov 2025.",
                    "source_file": "Visit_Note_2025-11-04.pdf",
                    "page": 2,
                },
                {
                    "question": "Does the patient smoke?",
                    "answerable": False,
                    "expected_answer_summary": REFUSAL_TEXT,
                    "source_file": None,
                    "page": None,
                },
                {
                    "question": "What is the patient's occupation?",
                    "answerable": False,
                    "expected_answer_summary": REFUSAL_TEXT,
                    "source_file": None,
                    "page": None,
                },
                {
                    "question": "Is there a family history of stroke?",
                    "answerable": False,
                    "expected_answer_summary": REFUSAL_TEXT,
                    "source_file": None,
                    "page": None,
                },
                {
                    "question": "When was the last COVID booster vaccine received?",
                    "answerable": False,
                    "expected_answer_summary": REFUSAL_TEXT,
                    "source_file": None,
                    "page": None,
                },
            ],
        },
        # Patient #1046 (Type 2, Age 72)
        {
            "id": "1046",
            "name": "Hussein Kamel Abdel-Aziz",
            "name_ar": "حسين كامل عبد العزيز",
            "age": 72,
            "type": "Type 2",
            "duration": 20,
            "meds": ["Metformin", "Glimepiride", "Linagliptin"],
            "national_id": "95205050501046",
            "phone": "010 0000 1046",
            "address": "31 Ramses St, Downtown Cairo (Demo Clinic)",
            "visits": [
                ("2025-03-10", "Mar 2025", 7.8, 64.0),
                ("2025-06-12", "Jun 2025", 7.7, 59.0),
                ("2025-09-18", "Sep 2025", 7.9, 54.0),
                ("2025-11-20", "Nov 2025", 7.8, 49.0),
                ("2026-01-22", "Jan 2026", 8.0, 44.0),
                ("2026-04-20", "Apr 2026", 7.9, 38.0),
            ],
            "scan_count": 2,
            "planted_findings": [
                {
                    "id": "f-1046-01",
                    "type": "falling_egfr",
                    "severity": "urgent_review",
                    "statement": "Renal filtration rate deteriorated to eGFR 38 mL/min/1.73m². Worth reviewing.",
                    "source_file": "Nephrology_Note_2026-04-20.pdf",
                    "page": 1,
                    "quote": "Renal filtration rate has deteriorated to eGFR 38 mL/min/1.73m².",
                    "expected_chunk_hint": "Renal filtration rate has deteriorated to eGFR 38 mL/min/1.73m².",
                },
                {
                    "id": "f-1046-02",
                    "type": "hypoglycemia_symptoms",
                    "severity": "review",
                    "statement": "Morning hypoglycemia symptoms noted in clinical encounter.",
                    "source_file": "Visit_Note_2026-01-22.pdf",
                    "page": 2,
                    "quote": "Patient describes recurrent morning dizziness and shakiness consistent with hypoglycemia.",
                    "expected_chunk_hint": "Patient describes recurrent morning dizziness and shakiness consistent with hypoglycemia.",
                },
                {
                    "id": "f-1046-03",
                    "type": "missed_foot_exam",
                    "severity": "review",
                    "statement": "Diabetic foot examination deferred during encounter.",
                    "source_file": "Clinic_Note_2026-04-20.pdf",
                    "page": 1,
                    "quote": "Visual inspection and monofilament foot assessment deferred due to bandage.",
                    "expected_chunk_hint": "Visual inspection and monofilament foot assessment deferred due to bandage.",
                },
                {
                    "id": "f-1046-04",
                    "type": "overdue_retinal_exam",
                    "severity": "review",
                    "statement": "Retinal exam overdue; last recorded Sep 2023. Worth reviewing.",
                    "source_file": "Eye_Report_2023-09-10.pdf",
                    "page": 1,
                    "quote": "Annual retinal photography archived on 10 Sep 2023.",
                    "expected_chunk_hint": "Annual retinal photography archived on 10 Sep 2023.",
                },
                {
                    "id": "f-1046-05",
                    "type": "lipid_panel_overdue",
                    "severity": "review",
                    "statement": "Lipid panel overdue; none recorded within past 12 months.",
                    "source_file": "Lab_Report_2024-07-05.pdf",
                    "page": 1,
                    "quote": "Comprehensive lipid panel last evaluated on 05 Jul 2024.",
                    "expected_chunk_hint": "Comprehensive lipid panel last evaluated on 05 Jul 2024.",
                },
            ],
            "care_gaps": [
                {
                    "name": "Retinal exam",
                    "status": "overdue",
                    "evidence": "Eye_Report_2023-09-10.pdf p.1",
                    "absence_note": None,
                },
                {
                    "name": "Foot exam",
                    "status": "missing",
                    "evidence": "Clinic_Note_2026-04-20.pdf p.1",
                    "absence_note": None,
                },
                {
                    "name": "Urine albumin-creatinine ratio",
                    "status": "done",
                    "evidence": "Lab_Report_2026-04-20.pdf p.1",
                    "absence_note": None,
                },
                {
                    "name": "Lipid panel",
                    "status": "overdue",
                    "evidence": "Lab_Report_2024-07-05.pdf p.1",
                    "absence_note": None,
                },
            ],
            "chat_questions": [
                {
                    "question": "What was the most recent eGFR value?",
                    "answerable": True,
                    "expected_answer_summary": "38 mL/min/1.73m² on 20 Apr 2026.",
                    "source_file": "Nephrology_Note_2026-04-20.pdf",
                    "page": 1,
                },
                {
                    "question": "What oral antidiabetic medications are prescribed?",
                    "answerable": True,
                    "expected_answer_summary": "Metformin, Glimepiride, and Linagliptin.",
                    "source_file": "Visit_Note_2026-01-22.pdf",
                    "page": 1,
                },
                {
                    "question": "Does the patient smoke?",
                    "answerable": False,
                    "expected_answer_summary": REFUSAL_TEXT,
                    "source_file": None,
                    "page": None,
                },
                {
                    "question": "What is the patient's marital status?",
                    "answerable": False,
                    "expected_answer_summary": REFUSAL_TEXT,
                    "source_file": None,
                    "page": None,
                },
                {
                    "question": "Has a formal fall risk assessment been completed?",
                    "answerable": False,
                    "expected_answer_summary": REFUSAL_TEXT,
                    "source_file": None,
                    "page": None,
                },
                {
                    "question": "Which eye surgery hospital did the patient visit previously?",
                    "answerable": False,
                    "expected_answer_summary": REFUSAL_TEXT,
                    "source_file": None,
                    "page": None,
                },
            ],
        },
        # Patient #1047 (Type 2, Age 52)
        {
            "id": "1047",
            "name": "Layla Mahmoud Zahran",
            "name_ar": "ليلى محمود زهران",
            "age": 52,
            "type": "Type 2",
            "duration": 9,
            "meds": ["Metformin", "Dapagliflozin"],
            "national_id": "97206060601047",
            "phone": "011 0000 1047",
            "address": "18 Makram Ebeid, Nasr City, Cairo (Fictional Hospital)",
            "visits": [
                ("2025-04-02", "Apr 2025", 7.5, 82.0),
                ("2025-06-20", "Jun 2025", 7.8, 77.0),
                ("2025-09-08", "Sep 2025", 8.2, 71.0),
                ("2025-12-05", "Dec 2025", 8.5, 66.0),
                ("2026-03-02", "Mar 2026", 8.8, 62.0),
                ("2026-05-18", "May 2026", 9.2, 57.0),
            ],
            "scan_count": 2,
            "planted_findings": [
                {
                    "id": "f-1047-01",
                    "type": "rising_hba1c",
                    "severity": "review",
                    "statement": "HbA1c has risen across 6 visits (7.5 to 9.2). Worth reviewing.",
                    "source_file": "Lab_Report_2026-05-18.pdf",
                    "page": 2,
                    "quote": "Glycated Hemoglobin (HbA1c): 9.2%",
                    "expected_chunk_hint": "Glycated Hemoglobin (HbA1c): 9.2%",
                },
                {
                    "id": "f-1047-02",
                    "type": "falling_egfr",
                    "severity": "review",
                    "statement": "Estimated GFR dropped from 82 to 57 across visits. Worth reviewing.",
                    "source_file": "Nephrology_Note_2026-05-18.pdf",
                    "page": 1,
                    "quote": "Estimated GFR is 57 mL/min/1.73m², dropping from baseline 82.",
                    "expected_chunk_hint": "Estimated GFR is 57 mL/min/1.73m², dropping from baseline 82.",
                },
                {
                    "id": "f-1047-03",
                    "type": "medication_changed_no_followup",
                    "severity": "review",
                    "statement": "Dapagliflozin started without follow-up renal monitoring. Worth reviewing.",
                    "source_file": "Visit_Note_2025-12-05.pdf",
                    "page": 2,
                    "quote": "Dapagliflozin started at 10 mg without documented repeat renal chemistry.",
                    "expected_chunk_hint": "Dapagliflozin started at 10 mg without documented repeat renal chemistry.",
                },
                {
                    "id": "f-1047-04",
                    "type": "missing_uacr",
                    "severity": "review",
                    "statement": "No urine albumin-creatinine ratio found in the last 12 months.",
                    "source_file": None,
                    "page": None,
                    "quote": None,
                    "expected_chunk_hint": "Absence of UACR result across last 12 months.",
                },
                {
                    "id": "f-1047-05",
                    "type": "missed_foot_exam",
                    "severity": "review",
                    "statement": "Diabetic foot examination was omitted during evaluation.",
                    "source_file": "Clinic_Note_2026-05-18.pdf",
                    "page": 1,
                    "quote": "Foot examination was omitted during this quarterly evaluation.",
                    "expected_chunk_hint": "Foot examination was omitted during this quarterly evaluation.",
                },
            ],
            "care_gaps": [
                {
                    "name": "Retinal exam",
                    "status": "done",
                    "evidence": "Eye_Report_2025-12-05.pdf p.1",
                    "absence_note": None,
                },
                {
                    "name": "Foot exam",
                    "status": "missing",
                    "evidence": "Clinic_Note_2026-05-18.pdf p.1",
                    "absence_note": None,
                },
                {
                    "name": "Urine albumin-creatinine ratio",
                    "status": "missing",
                    "evidence": None,
                    "absence_note": "No record in readable files within 12 months",
                },
                {
                    "name": "Lipid panel",
                    "status": "done",
                    "evidence": "Lab_Report_2026-05-18.pdf p.1",
                    "absence_note": None,
                },
            ],
            "chat_questions": [
                {
                    "question": "What is the latest HbA1c measurement?",
                    "answerable": True,
                    "expected_answer_summary": "9.2% on 18 May 2026.",
                    "source_file": "Lab_Report_2026-05-18.pdf",
                    "page": 2,
                },
                {
                    "question": "What dose of Dapagliflozin was initiated?",
                    "answerable": True,
                    "expected_answer_summary": "10 mg daily on 05 Dec 2025.",
                    "source_file": "Visit_Note_2025-12-05.pdf",
                    "page": 2,
                },
                {
                    "question": "Does the patient smoke?",
                    "answerable": False,
                    "expected_answer_summary": REFUSAL_TEXT,
                    "source_file": None,
                    "page": None,
                },
                {
                    "question": "When was the last colonoscopy completed?",
                    "answerable": False,
                    "expected_answer_summary": REFUSAL_TEXT,
                    "source_file": None,
                    "page": None,
                },
                {
                    "question": "Does the patient use dietary herbal supplements?",
                    "answerable": False,
                    "expected_answer_summary": REFUSAL_TEXT,
                    "source_file": None,
                    "page": None,
                },
                {
                    "question": "What is the patient's international travel history?",
                    "answerable": False,
                    "expected_answer_summary": REFUSAL_TEXT,
                    "source_file": None,
                    "page": None,
                },
            ],
        },
        # Patient #1048 (Type 1, Age 42) - on Insulin only
        {
            "id": "1048",
            "name": "Youssef Ashraf El-Banna",
            "name_ar": "يوسف أشرف البنا",
            "age": 42,
            "type": "Type 1",
            "duration": 14,
            "meds": ["Insulin Glargine", "Insulin Aspart"],
            "national_id": "98207070701048",
            "phone": "012 0000 1048",
            "address": "5 El-Horreya Ave, Heliopolis, Cairo (Synthetic Center)",
            "visits": [
                ("2025-04-18", "Apr 2025", 7.6, 92.0),
                ("2025-07-25", "Jul 2025", 7.9, 90.0),
                ("2025-10-30", "Oct 2025", 8.3, 91.0),
                ("2026-01-14", "Jan 2026", 8.6, 89.0),
                ("2026-03-25", "Mar 2026", 8.9, 90.0),
                ("2026-06-08", "Jun 2026", 9.3, 88.0),
            ],
            "scan_count": 2,
            "planted_findings": [
                {
                    "id": "f-1048-01",
                    "type": "hypoglycemia_symptoms",
                    "severity": "urgent_review",
                    "statement": "Severe nocturnal hypoglycemia episode reported. Worth reviewing.",
                    "source_file": "Visit_Note_2026-03-25.pdf",
                    "page": 2,
                    "quote": "Severe nocturnal hypoglycemia episode reported with confusion requiring third-party assistance.",
                    "expected_chunk_hint": "Severe nocturnal hypoglycemia episode reported with confusion requiring third-party assistance.",
                },
                {
                    "id": "f-1048-02",
                    "type": "rising_hba1c",
                    "severity": "review",
                    "statement": "HbA1c has risen across 6 visits (7.6 to 9.3). Worth reviewing.",
                    "source_file": "Lab_Report_2026-06-08.pdf",
                    "page": 2,
                    "quote": "Glycated Hemoglobin (HbA1c): 9.3%",
                    "expected_chunk_hint": "Glycated Hemoglobin (HbA1c): 9.3%",
                },
                {
                    "id": "f-1048-03",
                    "type": "overdue_retinal_exam",
                    "severity": "review",
                    "statement": "Retinal exam overdue; last recorded Mar 2024. Worth reviewing.",
                    "source_file": "Eye_Report_2024-03-02.pdf",
                    "page": 1,
                    "quote": "Fundus examination recorded on 02 Mar 2024 showing no retinopathy.",
                    "expected_chunk_hint": "Fundus examination recorded on 02 Mar 2024 showing no retinopathy.",
                },
                {
                    "id": "f-1048-04",
                    "type": "missing_uacr",
                    "severity": "review",
                    "statement": "No urine albumin-creatinine ratio found in the last 12 months.",
                    "source_file": None,
                    "page": None,
                    "quote": None,
                    "expected_chunk_hint": "Absence of UACR test in past 12 months.",
                },
                {
                    "id": "f-1048-05",
                    "type": "lipid_panel_overdue",
                    "severity": "review",
                    "statement": "Lipid panel overdue; none recorded in past 12 months.",
                    "source_file": "Lab_Report_2024-10-15.pdf",
                    "page": 1,
                    "quote": "Lipid evaluation last documented on 15 Oct 2024.",
                    "expected_chunk_hint": "Lipid evaluation last documented on 15 Oct 2024.",
                },
            ],
            "care_gaps": [
                {
                    "name": "Retinal exam",
                    "status": "overdue",
                    "evidence": "Eye_Report_2024-03-02.pdf p.1",
                    "absence_note": None,
                },
                {
                    "name": "Foot exam",
                    "status": "done",
                    "evidence": "Clinic_Note_2026-06-08.pdf p.1",
                    "absence_note": None,
                },
                {
                    "name": "Urine albumin-creatinine ratio",
                    "status": "missing",
                    "evidence": None,
                    "absence_note": "No record in readable files within 12 months",
                },
                {
                    "name": "Lipid panel",
                    "status": "overdue",
                    "evidence": "Lab_Report_2024-10-15.pdf p.1",
                    "absence_note": None,
                },
            ],
            "chat_questions": [
                {
                    "question": "What insulin products are used?",
                    "answerable": True,
                    "expected_answer_summary": "Insulin Glargine and Insulin Aspart.",
                    "source_file": "Visit_Note_2026-06-08.pdf",
                    "page": 1,
                },
                {
                    "question": "What was the latest HbA1c value?",
                    "answerable": True,
                    "expected_answer_summary": "9.3% on 08 Jun 2026.",
                    "source_file": "Lab_Report_2026-06-08.pdf",
                    "page": 2,
                },
                {
                    "question": "Does the patient smoke?",
                    "answerable": False,
                    "expected_answer_summary": REFUSAL_TEXT,
                    "source_file": None,
                    "page": None,
                },
                {
                    "question": "Does the patient have a gluten allergy?",
                    "answerable": False,
                    "expected_answer_summary": REFUSAL_TEXT,
                    "source_file": None,
                    "page": None,
                },
                {
                    "question": "What is the serial number of the patient's insulin pump?",
                    "answerable": False,
                    "expected_answer_summary": REFUSAL_TEXT,
                    "source_file": None,
                    "page": None,
                },
                {
                    "question": "What is the patient's current eyeglass prescription?",
                    "answerable": False,
                    "expected_answer_summary": REFUSAL_TEXT,
                    "source_file": None,
                    "page": None,
                },
            ],
        },
        # Patient #1049 (Type 2, Age 63)
        {
            "id": "1049",
            "name": "Samira Gamal Helmy",
            "name_ar": "سميرة جمال حلمي",
            "age": 63,
            "type": "Type 2",
            "duration": 11,
            "meds": ["Metformin", "Pioglitazone"],
            "national_id": "96108080801049",
            "phone": "015 0000 1049",
            "address": "12 Ahmed Orabi St, Mohandessin, Giza (Demo Clinic)",
            "visits": [
                ("2025-03-28", "Mar 2025", 7.2, 76.0),
                ("2025-07-02", "Jul 2025", 7.1, 70.0),
                ("2025-09-25", "Sep 2025", 7.3, 65.0),
                ("2025-11-18", "Nov 2025", 7.4, 59.0),
                ("2026-02-12", "Feb 2026", 7.2, 54.0),
                ("2026-05-04", "May 2026", 7.3, 49.0),
            ],
            "scan_count": 2,
            "planted_findings": [
                {
                    "id": "f-1049-01",
                    "type": "falling_egfr",
                    "severity": "urgent_review",
                    "statement": "eGFR fell from 76 to 49 over 6 visits. Worth reviewing.",
                    "source_file": "Nephrology_Note_2026-05-04.pdf",
                    "page": 1,
                    "quote": "Glomerular filtration rate decreased to eGFR 49 mL/min/1.73m².",
                    "expected_chunk_hint": "Glomerular filtration rate decreased to eGFR 49 mL/min/1.73m².",
                },
                {
                    "id": "f-1049-02",
                    "type": "medication_changed_no_followup",
                    "severity": "review",
                    "statement": "Pioglitazone increased to 30 mg daily without routine follow-up. Worth reviewing.",
                    "source_file": "Visit_Note_2025-11-18.pdf",
                    "page": 2,
                    "quote": "Pioglitazone increased to 30 mg daily without routine liver enzyme monitoring.",
                    "expected_chunk_hint": "Pioglitazone increased to 30 mg daily without routine liver enzyme monitoring.",
                },
                {
                    "id": "f-1049-03",
                    "type": "hypoglycemia_symptoms",
                    "severity": "review",
                    "statement": "Mild hypoglycemia symptoms reported in visit note.",
                    "source_file": "Visit_Note_2026-02-12.pdf",
                    "page": 2,
                    "quote": "Patient mentions occasional sweating and lightheadedness in late afternoons.",
                    "expected_chunk_hint": "Patient mentions occasional sweating and lightheadedness in late afternoons.",
                },
                {
                    "id": "f-1049-04",
                    "type": "missed_foot_exam",
                    "severity": "review",
                    "statement": "Diabetic foot examination was not performed during encounter.",
                    "source_file": "Clinic_Note_2026-05-04.pdf",
                    "page": 1,
                    "quote": "Diabetic foot screen not documented for current encounter.",
                    "expected_chunk_hint": "Diabetic foot screen not documented for current encounter.",
                },
                {
                    "id": "f-1049-05",
                    "type": "missing_uacr",
                    "severity": "review",
                    "statement": "No urine albumin-creatinine ratio found in the last 12 months.",
                    "source_file": None,
                    "page": None,
                    "quote": None,
                    "expected_chunk_hint": "Absence of UACR result across last 12 months.",
                },
            ],
            "care_gaps": [
                {
                    "name": "Retinal exam",
                    "status": "done",
                    "evidence": "Eye_Report_2026-02-12.pdf p.1",
                    "absence_note": None,
                },
                {
                    "name": "Foot exam",
                    "status": "missing",
                    "evidence": "Clinic_Note_2026-05-04.pdf p.1",
                    "absence_note": None,
                },
                {
                    "name": "Urine albumin-creatinine ratio",
                    "status": "missing",
                    "evidence": None,
                    "absence_note": "No record in readable files within 12 months",
                },
                {
                    "name": "Lipid panel",
                    "status": "done",
                    "evidence": "Lab_Report_2026-05-04.pdf p.1",
                    "absence_note": None,
                },
            ],
            "chat_questions": [
                {
                    "question": "What is the most recent eGFR value?",
                    "answerable": True,
                    "expected_answer_summary": "49 mL/min/1.73m² on 04 May 2026.",
                    "source_file": "Nephrology_Note_2026-05-04.pdf",
                    "page": 1,
                },
                {
                    "question": "What dose of Pioglitazone is prescribed?",
                    "answerable": True,
                    "expected_answer_summary": "30 mg daily on 18 Nov 2025.",
                    "source_file": "Visit_Note_2025-11-18.pdf",
                    "page": 2,
                },
                {
                    "question": "Does the patient have a smoking history?",
                    "answerable": False,
                    "expected_answer_summary": REFUSAL_TEXT,
                    "source_file": None,
                    "page": None,
                },
                {
                    "question": "What is the patient's weekly exercise frequency?",
                    "answerable": False,
                    "expected_answer_summary": REFUSAL_TEXT,
                    "source_file": None,
                    "page": None,
                },
                {
                    "question": "Does the patient own household pets?",
                    "answerable": False,
                    "expected_answer_summary": REFUSAL_TEXT,
                    "source_file": None,
                    "page": None,
                },
                {
                    "question": "What is the patient's ABO blood type?",
                    "answerable": False,
                    "expected_answer_summary": REFUSAL_TEXT,
                    "source_file": None,
                    "page": None,
                },
            ],
        },
        # Patient #1050 (Type 2, Age 51)
        {
            "id": "1050",
            "name": "Amr Nabil Fakhry",
            "name_ar": "عمرو نبيل فخري",
            "age": 51,
            "type": "Type 2",
            "duration": 7,
            "meds": ["Metformin", "Semaglutide"],
            "national_id": "97309090901050",
            "phone": "010 0000 1050",
            "address": "40 Port Said St, Al-Shatby, Alexandria (Fictional Clinic)",
            "visits": [
                ("2025-04-22", "Apr 2025", 7.1, 88.0),
                ("2025-07-16", "Jul 2025", 7.5, 87.0),
                ("2025-10-08", "Oct 2025", 7.9, 85.0),
                ("2025-12-20", "Dec 2025", 8.3, 86.0),
                ("2026-03-10", "Mar 2026", 8.7, 84.0),
                ("2026-06-10", "Jun 2026", 9.1, 85.0),
            ],
            "scan_count": 2,
            "planted_findings": [
                {
                    "id": "f-1050-01",
                    "type": "rising_hba1c",
                    "severity": "review",
                    "statement": "HbA1c has risen across 6 visits (7.1 to 9.1). Worth reviewing.",
                    "source_file": "Lab_Report_2026-06-10.pdf",
                    "page": 2,
                    "quote": "Glycated Hemoglobin (HbA1c): 9.1%",
                    "expected_chunk_hint": "Glycated Hemoglobin (HbA1c): 9.1%",
                },
                {
                    "id": "f-1050-02",
                    "type": "overdue_retinal_exam",
                    "severity": "review",
                    "statement": "Retinal exam overdue; last recorded Apr 2024. Worth reviewing.",
                    "source_file": "Eye_Report_2024-04-12.pdf",
                    "page": 1,
                    "quote": "Retinal photography performed on 12 Apr 2024.",
                    "expected_chunk_hint": "Retinal photography performed on 12 Apr 2024.",
                },
                {
                    "id": "f-1050-03",
                    "type": "missing_uacr",
                    "severity": "review",
                    "statement": "No urine albumin-creatinine ratio found in the last 12 months.",
                    "source_file": None,
                    "page": None,
                    "quote": None,
                    "expected_chunk_hint": "Absence of UACR result across last 12 months.",
                },
                {
                    "id": "f-1050-04",
                    "type": "missed_foot_exam",
                    "severity": "review",
                    "statement": "Comprehensive foot assessment omitted this visit.",
                    "source_file": "Clinic_Note_2026-06-10.pdf",
                    "page": 1,
                    "quote": "Comprehensive foot assessment omitted this visit.",
                    "expected_chunk_hint": "Comprehensive foot assessment omitted this visit.",
                },
                {
                    "id": "f-1050-05",
                    "type": "lipid_panel_overdue",
                    "severity": "review",
                    "statement": "Lipid panel is overdue; none recorded in past 12 months.",
                    "source_file": "Lab_Report_2024-11-20.pdf",
                    "page": 1,
                    "quote": "Fasting lipid panel last verified on 20 Nov 2024.",
                    "expected_chunk_hint": "Fasting lipid panel last verified on 20 Nov 2024.",
                },
            ],
            "care_gaps": [
                {
                    "name": "Retinal exam",
                    "status": "overdue",
                    "evidence": "Eye_Report_2024-04-12.pdf p.1",
                    "absence_note": None,
                },
                {
                    "name": "Foot exam",
                    "status": "missing",
                    "evidence": "Clinic_Note_2026-06-10.pdf p.1",
                    "absence_note": None,
                },
                {
                    "name": "Urine albumin-creatinine ratio",
                    "status": "missing",
                    "evidence": None,
                    "absence_note": "No record in readable files within 12 months",
                },
                {
                    "name": "Lipid panel",
                    "status": "overdue",
                    "evidence": "Lab_Report_2024-11-20.pdf p.1",
                    "absence_note": None,
                },
            ],
            "chat_questions": [
                {
                    "question": "What is the latest HbA1c result?",
                    "answerable": True,
                    "expected_answer_summary": "9.1% on 10 Jun 2026.",
                    "source_file": "Lab_Report_2026-06-10.pdf",
                    "page": 2,
                },
                {
                    "question": "What medications are prescribed for diabetes?",
                    "answerable": True,
                    "expected_answer_summary": "Metformin and Semaglutide.",
                    "source_file": "Visit_Note_2026-06-10.pdf",
                    "page": 1,
                },
                {
                    "question": "Does the patient smoke?",
                    "answerable": False,
                    "expected_answer_summary": REFUSAL_TEXT,
                    "source_file": None,
                    "page": None,
                },
                {
                    "question": "Has the patient had previous abdominal surgeries?",
                    "answerable": False,
                    "expected_answer_summary": REFUSAL_TEXT,
                    "source_file": None,
                    "page": None,
                },
                {
                    "question": "Are there driving license vision restrictions recorded?",
                    "answerable": False,
                    "expected_answer_summary": REFUSAL_TEXT,
                    "source_file": None,
                    "page": None,
                },
                {
                    "question": "Who is the patient's current employer?",
                    "answerable": False,
                    "expected_answer_summary": REFUSAL_TEXT,
                    "source_file": None,
                    "page": None,
                },
            ],
        },
        # Patient #1051 (Type 2, Age 69)
        {
            "id": "1051",
            "name": "Mona Raafat El-Shazly",
            "name_ar": "منى رأفت الشاذلي",
            "age": 69,
            "type": "Type 2",
            "duration": 16,
            "meds": ["Metformin", "Glimepiride", "Atorvastatin"],
            "national_id": "95510101001051",
            "phone": "011 0000 1051",
            "address": "8 Corniche El-Nile, Garden City, Cairo (Synthetic Center)",
            "visits": [
                ("2025-03-16", "Mar 2025", 7.6, 69.0),
                ("2025-07-02", "Jul 2025", 7.9, 63.0),
                ("2025-09-14", "Sep 2025", 8.2, 58.0),
                ("2025-11-10", "Nov 2025", 8.5, 53.0),
                ("2026-03-04", "Mar 2026", 8.8, 49.0),
                ("2026-05-25", "May 2026", 9.2, 44.0),
            ],
            "scan_count": 2,
            "planted_findings": [
                {
                    "id": "f-1051-01",
                    "type": "falling_egfr",
                    "severity": "urgent_review",
                    "statement": "Serum eGFR declined to 44 mL/min/1.73m² under ongoing treatment. Worth reviewing.",
                    "source_file": "Nephrology_Note_2026-05-25.pdf",
                    "page": 1,
                    "quote": "Serum eGFR declined to 44 mL/min/1.73m² under ongoing treatment.",
                    "expected_chunk_hint": "Serum eGFR declined to 44 mL/min/1.73m² under ongoing treatment.",
                },
                {
                    "id": "f-1051-02",
                    "type": "rising_hba1c",
                    "severity": "review",
                    "statement": "HbA1c has risen across 6 visits (7.6 to 9.2). Worth reviewing.",
                    "source_file": "Lab_Report_2026-05-25.pdf",
                    "page": 2,
                    "quote": "Glycated Hemoglobin (HbA1c): 9.2%",
                    "expected_chunk_hint": "Glycated Hemoglobin (HbA1c): 9.2%",
                },
                {
                    "id": "f-1051-03",
                    "type": "hypoglycemia_symptoms",
                    "severity": "review",
                    "statement": "Hypoglycemia episodes noted in clinician record.",
                    "source_file": "Visit_Note_2026-03-04.pdf",
                    "page": 2,
                    "quote": "Patient relates episodes of profuse diaphoresis and trembling before lunch.",
                    "expected_chunk_hint": "Patient relates episodes of profuse diaphoresis and trembling before lunch.",
                },
                {
                    "id": "f-1051-04",
                    "type": "medication_changed_no_followup",
                    "severity": "review",
                    "statement": "Glimepiride increased to 4 mg daily without scheduling safety check. Worth reviewing.",
                    "source_file": "Visit_Note_2025-12-18.pdf",
                    "page": 2,
                    "quote": "Glimepiride increased to 4 mg daily without scheduling safety check.",
                    "expected_chunk_hint": "Glimepiride increased to 4 mg daily without scheduling safety check.",
                },
                {
                    "id": "f-1051-05",
                    "type": "overdue_retinal_exam",
                    "severity": "review",
                    "statement": "Retinal exam overdue; last recorded Dec 2023. Worth reviewing.",
                    "source_file": "Eye_Report_2023-12-08.pdf",
                    "page": 1,
                    "quote": "Dilated eye examination dated 08 Dec 2023 without acute retinopathy.",
                    "expected_chunk_hint": "Dilated eye examination dated 08 Dec 2023 without acute retinopathy.",
                },
            ],
            "care_gaps": [
                {
                    "name": "Retinal exam",
                    "status": "overdue",
                    "evidence": "Eye_Report_2023-12-08.pdf p.1",
                    "absence_note": None,
                },
                {
                    "name": "Foot exam",
                    "status": "done",
                    "evidence": "Clinic_Note_2026-05-25.pdf p.1",
                    "absence_note": None,
                },
                {
                    "name": "Urine albumin-creatinine ratio",
                    "status": "done",
                    "evidence": "Lab_Report_2026-05-25.pdf p.1",
                    "absence_note": None,
                },
                {
                    "name": "Lipid panel",
                    "status": "done",
                    "evidence": "Lab_Report_2026-05-25.pdf p.2",
                    "absence_note": None,
                },
            ],
            "chat_questions": [
                {
                    "question": "What is the latest eGFR value?",
                    "answerable": True,
                    "expected_answer_summary": "44 mL/min/1.73m² on 25 May 2026.",
                    "source_file": "Nephrology_Note_2026-05-25.pdf",
                    "page": 1,
                },
                {
                    "question": "What was the latest HbA1c result?",
                    "answerable": True,
                    "expected_answer_summary": "9.2% on 25 May 2026.",
                    "source_file": "Lab_Report_2026-05-25.pdf",
                    "page": 2,
                },
                {
                    "question": "Does the patient smoke?",
                    "answerable": False,
                    "expected_answer_summary": REFUSAL_TEXT,
                    "source_file": None,
                    "page": None,
                },
                {
                    "question": "Has the patient received the flu vaccine this year?",
                    "answerable": False,
                    "expected_answer_summary": REFUSAL_TEXT,
                    "source_file": None,
                    "page": None,
                },
                {
                    "question": "What is the dose of the patient's calcium supplement?",
                    "answerable": False,
                    "expected_answer_summary": REFUSAL_TEXT,
                    "source_file": None,
                    "page": None,
                },
                {
                    "question": "Which preferred pharmacy is listed in the patient's record?",
                    "answerable": False,
                    "expected_answer_summary": REFUSAL_TEXT,
                    "source_file": None,
                    "page": None,
                },
            ],
        },
    ]

    for p_def in patients_def:
        pid = p_def["id"]
        p_dir = base_syn / pid
        if p_dir.exists():
            shutil.rmtree(p_dir)
        p_dir.mkdir(parents=True, exist_ok=True)

        manifest: list[dict[str, Any]] = []
        arabic_notes_count = 0
        register_doc = functools.partial(_add_manifest_entry, manifest)

        if pid == "1042":
            # 1. Eye report (2023-10-14, 1 page)
            eye_pdf = p_dir / "Eye_Report_2023-10-14.pdf"
            eye_txt = p_dir / "Eye_Report_2023-10-14.txt"
            builder = DocumentBuilder(eye_pdf, eye_txt)
            builder.start_page()
            builder.add_line("CAIRO DIABETIC EYE SPECIALTY CENTER")
            builder.add_line("OPHTHALMOLOGY CONSULTATION REPORT")
            builder.add_line(
                f"Patient: #{pid} - Farouk Adel Mansour   National ID: {p_def['national_id']}"
            )
            builder.add_line("Date of Examination: 14 Oct 2023")
            builder.add_line("Examining Ophthalmologist: Dr. Hany El-Shennawy, MD")
            builder.add_line("Clinical Findings:")
            builder.add_line(
                "Dilated funduscopy: Visual acuity 20/25 OD, 20/20 OS. No diabetic retinopathy."
            )
            builder.add_line(
                "Dilated retinal examination completed on 14 Oct 2023. Next annual retinal screen due in 12 months."
            )
            builder.write_txt()
            builder.render_pdf()
            register_doc(
                "Eye_Report_2023-10-14.pdf", "Eye report · 2023", "2023-10-14", 1, False
            )

            # 2. Lab Report 2025-03-12 (2 pages)
            lab_pdf = p_dir / "Lab_Report_2025-03-12.pdf"
            lab_txt = p_dir / "Lab_Report_2025-03-12.txt"
            builder = DocumentBuilder(lab_pdf, lab_txt)
            builder.start_page()
            builder.add_line("AL-BORG CLINICAL LABORATORIES - ROUTINE DIABETES PANEL")
            builder.add_line(
                f"Patient: #{pid} - Farouk Adel Mansour   Date: 12 Mar 2025"
            )
            builder.add_line("Fasting Blood Glucose: 142 mg/dL (Reference: 70-99)")
            builder.add_line("Serum Creatinine: 1.05 mg/dL (Reference: 0.70-1.20)")
            builder.add_line("Estimated GFR: 78 mL/min/1.73m² (CKD-EPI 2021)")
            builder.start_page()
            builder.add_line("Glycated Hemoglobin (HbA1c): 7.4% (Reference: <5.7%)")
            builder.add_line("Blood Urea Nitrogen: 16 mg/dL")
            builder.write_txt()
            builder.render_pdf()
            register_doc(
                "Lab_Report_2025-03-12.pdf",
                "Lab report · Mar 2025",
                "2025-03-12",
                2,
                False,
            )

            # 3. Visit Note 2025-03-12 (2 pages)
            vn_pdf = p_dir / "Visit_Note_2025-03-12.pdf"
            vn_txt = p_dir / "Visit_Note_2025-03-12.txt"
            builder = DocumentBuilder(vn_pdf, vn_txt)
            builder.start_page()
            builder.add_line("ENDOCRINOLOGY CLINIC - OUTPATIENT VISIT NOTE")
            builder.add_line(
                f"Patient: #{pid} - Farouk Adel Mansour   Date: 12 Mar 2025"
            )
            builder.add_line(
                "Chief Complaint: Routine diabetes follow-up. Diagnosed 12 years ago."
            )
            builder.add_line(
                "Current Medications: Metformin 1000 mg twice daily, Atorvastatin 20 mg at bedtime."
            )
            builder.start_page()
            builder.add_line(
                "Vital signs: BP 130/80 mmHg, Pulse 72 bpm, BMI 28.4 kg/m²."
            )
            builder.add_line(
                "Plan: Continue current therapy. Return in 3 months with repeat labs."
            )
            builder.write_txt()
            builder.render_pdf()
            register_doc(
                "Visit_Note_2025-03-12.pdf",
                "Visit note · Mar 2025",
                "2025-03-12",
                2,
                False,
            )

            # 4. Lab Report 2025-06-18 (2 pages)
            lab_pdf = p_dir / "Lab_Report_2025-06-18.pdf"
            lab_txt = p_dir / "Lab_Report_2025-06-18.txt"
            builder = DocumentBuilder(lab_pdf, lab_txt)
            builder.start_page()
            builder.add_line("AL-BORG CLINICAL LABORATORIES - ROUTINE DIABETES PANEL")
            builder.add_line(
                f"Patient: #{pid} - Farouk Adel Mansour   Date: 18 Jun 2025"
            )
            builder.add_line("Fasting Blood Glucose: 154 mg/dL")
            builder.add_line("Serum Creatinine: 1.10 mg/dL")
            builder.add_line("Estimated GFR: 74 mL/min/1.73m²")
            builder.start_page()
            builder.add_line("Glycated Hemoglobin (HbA1c): 7.8%")
            builder.write_txt()
            builder.render_pdf()
            register_doc(
                "Lab_Report_2025-06-18.pdf",
                "Lab report · Jun 2025",
                "2025-06-18",
                2,
                False,
            )

            # 5. Visit Note 2025-06-18 (Arabic note! 2 pages)
            vn_pdf = p_dir / "Visit_Note_2025-06-18.pdf"
            vn_txt = p_dir / "Visit_Note_2025-06-18.txt"
            builder = DocumentBuilder(vn_pdf, vn_txt)
            builder.start_page()
            builder.add_line("عيادة أمراض السكر والغدد الصماء - مذكرة متابعة دورية")
            builder.add_line(
                f"اسم المريض: فاروق عادل منصور   الرقم القومي: {p_def['national_id']}   التاريخ: 18 يونيو 2025"
            )
            builder.add_line("الشكوى الحالية: متابعة دورية لمرض السكر من النوع الثاني.")
            builder.add_line(
                "الأدوية الحالية: يستمر المريض على Metformin بانتظام و Atorvastatin."
            )
            builder.start_page()
            builder.add_line(
                "الفحص السريري: ضغط الدم 132/82 mmHg. مستوى HbA1c وصل إلى 7.8% و eGFR الحالي 74 mL/min/1.73m²."
            )
            builder.add_line(
                "الخطة العلاجية: التشديد على الحمية الغذائية وممارسة الرياضة والمتابعة بعد ثلاثة أشهر."
            )
            builder.write_txt()
            builder.render_pdf(is_arabic=True)
            register_doc(
                "Visit_Note_2025-06-18.pdf",
                "Visit note · Jun 2025 (Arabic)",
                "2025-06-18",
                2,
                False,
            )
            arabic_notes_count += 1

            # 6. Lab Report 2025-09-15 (2 pages)
            lab_pdf = p_dir / "Lab_Report_2025-09-15.pdf"
            lab_txt = p_dir / "Lab_Report_2025-09-15.txt"
            builder = DocumentBuilder(lab_pdf, lab_txt)
            builder.start_page()
            builder.add_line("AL-BORG CLINICAL LABORATORIES - ROUTINE DIABETES PANEL")
            builder.add_line(
                f"Patient: #{pid} - Farouk Adel Mansour   Date: 15 Sep 2025"
            )
            builder.add_line("Fasting Blood Glucose: 168 mg/dL")
            builder.add_line("Serum Creatinine: 1.18 mg/dL")
            builder.add_line("Estimated GFR: 68 mL/min/1.73m²")
            builder.start_page()
            builder.add_line("Glycated Hemoglobin (HbA1c): 8.1%")
            builder.write_txt()
            builder.render_pdf()
            register_doc(
                "Lab_Report_2025-09-15.pdf",
                "Lab report · Sep 2025",
                "2025-09-15",
                2,
                False,
            )

            # 7. Visit Note 2025-09-15 (2 pages)
            vn_pdf = p_dir / "Visit_Note_2025-09-15.pdf"
            vn_txt = p_dir / "Visit_Note_2025-09-15.txt"
            builder = DocumentBuilder(vn_pdf, vn_txt)
            builder.start_page()
            builder.add_line("ENDOCRINOLOGY CLINIC - OUTPATIENT VISIT NOTE")
            builder.add_line(
                f"Patient: #{pid} - Farouk Adel Mansour   Date: 15 Sep 2025"
            )
            builder.add_line("Assessment: Glycemic control suboptimal with HbA1c 8.1%.")
            builder.start_page()
            builder.add_line(
                "Plan: Counsel on diet. If glycemic trend remains elevated, add secondary agent."
            )
            builder.write_txt()
            builder.render_pdf()
            register_doc(
                "Visit_Note_2025-09-15.pdf",
                "Visit note · Sep 2025",
                "2025-09-15",
                2,
                False,
            )

            # 8. Visit Note 2025-11-12 (Med change! 2 pages, page 2 has quote)
            vn_pdf = p_dir / "Visit_Note_2025-11-12.pdf"
            vn_txt = p_dir / "Visit_Note_2025-11-12.txt"
            builder = DocumentBuilder(vn_pdf, vn_txt)
            builder.start_page()
            builder.add_line("ENDOCRINOLOGY CLINIC - INTERIM MEDICATION REVIEW")
            builder.add_line(
                f"Patient: #{pid} - Farouk Adel Mansour   Date: 12 Nov 2025"
            )
            builder.add_line(
                "Reason for Encounter: Fasting morning sugars elevated at home (170-190 mg/dL)."
            )
            builder.start_page()
            builder.add_line("Plan and Prescriptions:")
            builder.add_line(
                "Gliclazide was added on 12 Nov 2025. No later changes are documented."
            )
            builder.add_line(
                "Prescription: Gliclazide modified release 30 mg orally once daily with breakfast."
            )
            builder.add_line(
                "Continue Metformin 1000 mg twice daily and Atorvastatin 20 mg nightly."
            )
            builder.write_txt()
            builder.render_pdf()
            register_doc(
                "Visit_Note_2025-11-12.pdf",
                "Visit note · Nov 2025",
                "2025-11-12",
                2,
                False,
            )

            # 9. Lab Report 2025-12-10 (2 pages)
            lab_pdf = p_dir / "Lab_Report_2025-12-10.pdf"
            lab_txt = p_dir / "Lab_Report_2025-12-10.txt"
            builder = DocumentBuilder(lab_pdf, lab_txt)
            builder.start_page()
            builder.add_line("AL-BORG CLINICAL LABORATORIES - ROUTINE DIABETES PANEL")
            builder.add_line(
                f"Patient: #{pid} - Farouk Adel Mansour   Date: 10 Dec 2025"
            )
            builder.add_line("Fasting Blood Glucose: 172 mg/dL")
            builder.add_line("Serum Creatinine: 1.24 mg/dL")
            builder.add_line("Estimated GFR: 64 mL/min/1.73m²")
            builder.start_page()
            builder.add_line("Glycated Hemoglobin (HbA1c): 8.4%")
            builder.write_txt()
            builder.render_pdf()
            register_doc(
                "Lab_Report_2025-12-10.pdf",
                "Lab report · Dec 2025",
                "2025-12-10",
                2,
                False,
            )

            # 10. Visit Note 2026-02-15 (3 pages, page 3 has quote!)
            vn_pdf = p_dir / "Visit_Note_2026-02-15.pdf"
            vn_txt = p_dir / "Visit_Note_2026-02-15.txt"
            builder = DocumentBuilder(vn_pdf, vn_txt)
            builder.start_page()
            builder.add_line("ENDOCRINOLOGY CLINIC - OUTPATIENT VISIT NOTE")
            builder.add_line(
                f"Patient: #{pid} - Farouk Adel Mansour   Date: 15 Feb 2026"
            )
            builder.add_line(
                "Interval History: Patient taking Metformin and Gliclazide as prescribed."
            )
            builder.start_page()
            builder.add_line(
                "Physical Examination: Vital signs stable, cardiovascular exam normal."
            )
            builder.start_page()
            builder.add_line("Review of Systems and Symptom Log:")
            builder.add_line(
                "Patient reports occasional episodes of night-time sweating and lightheadedness consistent with mild nocturnal low glucose symptoms."
            )
            builder.add_line(
                "Advised on bedtime glucose check and keeping fast-acting carbohydrates available."
            )
            builder.write_txt()
            builder.render_pdf()
            register_doc(
                "Visit_Note_2026-02-15.pdf",
                "Visit note · Feb 2026",
                "2026-02-15",
                3,
                False,
            )

            # 11. Lab Report 2026-03-18 (4 pages, page 4 has lipid panel!)
            lab_pdf = p_dir / "Lab_Report_2026-03-18.pdf"
            lab_txt = p_dir / "Lab_Report_2026-03-18.txt"
            builder = DocumentBuilder(lab_pdf, lab_txt)
            builder.start_page()
            builder.add_line("AL-BORG CLINICAL LABORATORIES - ROUTINE DIABETES PANEL")
            builder.add_line(
                f"Patient: #{pid} - Farouk Adel Mansour   Date: 18 Mar 2026"
            )
            builder.add_line("Fasting Blood Glucose: 180 mg/dL")
            builder.add_line("Serum Creatinine: 1.30 mg/dL")
            builder.start_page()
            builder.add_line("Estimated GFR: 61 mL/min/1.73m²")
            builder.add_line("Glycated Hemoglobin (HbA1c): 8.7%")
            builder.start_page()
            builder.add_line(
                "Electrolytes: Sodium 139 mmol/L, Potassium 4.5 mmol/L, Chloride 102 mmol/L"
            )
            builder.start_page()
            builder.add_line("LIPID PROFILE COMPREHENSIVE PANEL")
            builder.add_line("Total Cholesterol: 165 mg/dL")
            builder.add_line("Triglycerides: 155 mg/dL")
            builder.add_line("HDL Cholesterol: 46 mg/dL")
            builder.add_line("LDL Cholesterol: 88 mg/dL")
            builder.add_line("Lipid panel completed this year.")
            builder.write_txt()
            builder.render_pdf()
            register_doc(
                "Lab_Report_2026-03-18.pdf",
                "Lab report · Mar 2026",
                "2026-03-18",
                4,
                False,
            )

            # 12. Clinic Note 2026-03-18 (2 pages, page 2 has foot exam!)
            cn_pdf = p_dir / "Clinic_Note_2026-03-18.pdf"
            cn_txt = p_dir / "Clinic_Note_2026-03-18.txt"
            builder = DocumentBuilder(cn_pdf, cn_txt)
            builder.start_page()
            builder.add_line("ENDOCRINOLOGY CLINIC - ANNUAL COMPREHENSIVE ASSESSMENT")
            builder.add_line(
                f"Patient: #{pid} - Farouk Adel Mansour   Date: 18 Mar 2026"
            )
            builder.add_line(
                "Review of microvascular complications and preventive screening."
            )
            builder.start_page()
            builder.add_line("Preventive Foot Screening Assessment:")
            builder.add_line("Foot examination completed this year.")
            builder.add_line(
                "Bilateral 10g Semmes-Weinstein monofilament sensation intact. Dorsalis pedis pulses palpable bilaterally. No ulcerations or calluses."
            )
            builder.write_txt()
            builder.render_pdf()
            register_doc(
                "Clinic_Note_2026-03-18.pdf",
                "Clinic note · Mar 2026",
                "2026-03-18",
                2,
                False,
            )

            # 13. Nephrology Note 2026-06-18 (3 pages, page 1 has exact quote!)
            neph_pdf = p_dir / "Nephrology_Note_2026-06-18.pdf"
            neph_txt = p_dir / "Nephrology_Note_2026-06-18.txt"
            builder = DocumentBuilder(neph_pdf, neph_txt)
            builder.start_page()
            builder.add_line("DEPARTMENT OF NEPHROLOGY - CONSULTATION NOTE")
            builder.add_line(
                f"Patient: #{pid} - Farouk Adel Mansour   National ID: {p_def['national_id']}"
            )
            builder.add_line(
                "Date of Consultation: 18 Jun 2026   Consultant: Dr. Magdy Yacoub Clinic Associate"
            )
            builder.add_line(
                "Reason for visit: routine diabetes follow-up. Blood pressure 134/82. Weight stable."
            )
            builder.add_line(
                "Estimated GFR today is 59 mL/min/1.73m², down from 78 at the first visit in March 2025."
            )
            builder.add_line(
                "Patient continues Metformin and Gliclazide as before. Reports occasional night-time sweating. Foot examination completed. Glucose diary to be brought to the next visit."
            )
            builder.start_page()
            builder.add_line(
                "Renal Ultrasonography: Bilateral kidneys normal size with slightly increased cortical echogenicity."
            )
            builder.add_line("No hydronephrosis or renal calculi detected.")
            builder.start_page()
            builder.add_line("Assessment and Plan:")
            builder.add_line(
                "Stage 3a chronic kidney disease in the setting of long-standing diabetes."
            )
            builder.add_line(
                "Kidney function trend alongside current medication is worth reviewing."
            )
            builder.write_txt()
            builder.render_pdf()
            register_doc(
                "Nephrology_Note_2026-06-18.pdf",
                "Nephrology note · Jun 2026",
                "2026-06-18",
                3,
                False,
            )

            # 14. Lab Report 2026-06-18 (2 pages, page 2 has HbA1c 8.9% quote!)
            lab_pdf = p_dir / "Lab_Report_2026-06-18.pdf"
            lab_txt = p_dir / "Lab_Report_2026-06-18.txt"
            builder = DocumentBuilder(lab_pdf, lab_txt)
            builder.start_page()
            builder.add_line("AL-BORG CLINICAL LABORATORIES - ROUTINE DIABETES PANEL")
            builder.add_line(
                f"Patient: #{pid} - Farouk Adel Mansour   Date: 18 Jun 2026"
            )
            builder.add_line("Fasting Blood Glucose: 192 mg/dL (Reference: 70-99)")
            builder.add_line("Serum Creatinine: 1.34 mg/dL (Reference: 0.70-1.20)")
            builder.add_line("Estimated GFR: 59 mL/min/1.73m² (CKD-EPI 2021)")
            builder.start_page()
            builder.add_line("Glycated Hemoglobin (HbA1c): 8.9%")
            builder.add_line("Blood Urea Nitrogen: 22 mg/dL")
            builder.add_line("Potassium: 4.6 mmol/L")
            builder.write_txt()
            builder.render_pdf()
            register_doc(
                "Lab_Report_2026-06-18.pdf",
                "Lab report · Jun 2026",
                "2026-06-18",
                2,
                False,
            )

            # 15, 16, 17. 3 Unreadable Scans
            scan_names = [
                (
                    "Scanned_Referral_Cover_Sheet.pdf",
                    "Scanned_Referral_Cover_Sheet.txt",
                    "Referral Cover Sheet",
                    "2024-05-10",
                ),
                (
                    "Scanned_Prior_Fax_Header.pdf",
                    "Scanned_Prior_Fax_Header.txt",
                    "Prior Clinic Fax Header",
                    "2024-11-22",
                ),
                (
                    "Scanned_Archived_Intake_Cover.pdf",
                    "Scanned_Archived_Intake_Cover.txt",
                    "Archived Paper Intake Form",
                    "2023-01-15",
                ),
            ]
            for s_pdf, s_txt, s_title, s_date in scan_names:
                render_unreadable_scan(
                    p_dir / s_pdf,
                    p_dir / s_txt,
                    s_title,
                    s_date,
                    p_def["name"],
                    pid,
                    np_rng,
                )
                register_doc(s_pdf, f"Scanned archive · {s_title}", s_date, 1, True)

        else:
            # Patients #1043 to #1051
            visits = p_def["visits"]
            scan_k = p_def["scan_count"]

            # 1. Specialist Eye report
            eye_finding = next(
                (
                    f
                    for f in p_def["planted_findings"]
                    if f["type"] == "overdue_retinal_exam"
                ),
                None,
            )
            eye_date = "2024-02-10"
            eye_file = f"Eye_Report_{eye_date}.pdf"
            if eye_finding and eye_finding["source_file"]:
                eye_file = eye_finding["source_file"]
                eye_date = eye_file.replace("Eye_Report_", "").replace(".pdf", "")

            eye_pdf = p_dir / eye_file
            eye_txt = p_dir / (eye_file.replace(".pdf", ".txt"))
            builder = DocumentBuilder(eye_pdf, eye_txt)
            builder.start_page()
            builder.add_line("OPHTHALMOLOGY CLINICAL REPORT")
            builder.add_line(
                f"Patient: #{pid} - {p_def['name']}   National ID: {p_def['national_id']}"
            )
            builder.add_line(f"Date of Examination: {eye_date}")
            if eye_finding and eye_finding["quote"]:
                builder.add_line(eye_finding["quote"])
            else:
                builder.add_line(
                    "Annual dilated retinal evaluation completed. Visual acuity intact."
                )
            builder.write_txt()
            builder.render_pdf()
            register_doc(eye_file, f"Eye report · {eye_date[:7]}", eye_date, 1, False)

            # 2. Historical Lab Report (if planted finding has an overdue lipid panel from 2024)
            f_hist_lipid = next(
                (
                    f
                    for f in p_def["planted_findings"]
                    if f["source_file"] and "Lab_Report_2024" in f["source_file"]
                ),
                None,
            )
            if f_hist_lipid and f_hist_lipid["source_file"]:
                hl_file = f_hist_lipid["source_file"]
                hl_date = hl_file.replace("Lab_Report_", "").replace(".pdf", "")
                hl_pdf = p_dir / hl_file
                hl_txt = p_dir / (hl_file.replace(".pdf", ".txt"))
                b_hl = DocumentBuilder(hl_pdf, hl_txt)
                b_hl.start_page()
                b_hl.add_line("HISTORICAL LABORATORY ARCHIVE REPORT")
                b_hl.add_line(f"Patient: #{pid} - {p_def['name']}   Date: {hl_date}")
                if f_hist_lipid["quote"]:
                    b_hl.add_line(f_hist_lipid["quote"])
                b_hl.write_txt()
                b_hl.render_pdf()
                register_doc(
                    hl_file,
                    f"Lab report · {hl_date[:7]} (Historical)",
                    hl_date,
                    1,
                    False,
                )

            # 3. Six Routine Lab Reports
            for v_idx, (v_date, v_lbl, v_hba1c, v_egfr) in enumerate(visits, start=1):
                lab_file = f"Lab_Report_{v_date}.pdf"
                lab_pdf = p_dir / lab_file
                lab_txt = p_dir / f"Lab_Report_{v_date}.txt"
                b_lab = DocumentBuilder(lab_pdf, lab_txt)
                b_lab.start_page()
                b_lab.add_line("CLINICAL LABORATORY REPORT")
                b_lab.add_line(f"Patient: #{pid} - {p_def['name']}   Date: {v_date}")
                b_lab.add_line(f"Fasting Blood Glucose: {int(v_hba1c * 20)} mg/dL")
                b_lab.add_line(f"Estimated GFR: {v_egfr} mL/min/1.73m²")
                b_lab.start_page()

                finding_hba1c = next(
                    (
                        f
                        for f in p_def["planted_findings"]
                        if f["source_file"] == lab_file and f["page"] == 2
                    ),
                    None,
                )
                if finding_hba1c and finding_hba1c["quote"]:
                    b_lab.add_line(finding_hba1c["quote"])
                else:
                    b_lab.add_line(f"Glycated Hemoglobin (HbA1c): {v_hba1c}%")

                b_lab.write_txt()
                b_lab.render_pdf()
                register_doc(lab_file, f"Lab report · {v_lbl}", v_date, 2, False)

            # 4. Visit Notes
            has_neph = any(
                f["source_file"] and "Nephrology_Note" in f["source_file"]
                for f in p_def["planted_findings"]
            )
            visit_notes_indices = [1, 2, 3, 4, 5] if has_neph else [1, 2, 3, 4, 5, 6]

            for v_idx in visit_notes_indices:
                v_date, v_lbl, v_hba1c, v_egfr = visits[v_idx - 1]
                is_ar = (v_idx == 2) or (v_idx == 4 and pid in ["1046", "1051"])
                vn_file = f"Visit_Note_{v_date}.pdf"
                vn_pdf = p_dir / vn_file
                vn_txt = p_dir / f"Visit_Note_{v_date}.txt"
                b_vn = DocumentBuilder(vn_pdf, vn_txt)

                if is_ar:
                    arabic_notes_count += 1
                    b_vn.start_page()
                    b_vn.add_line("مذكرة المتابعة السريرية الدورية لمرضى السكري")
                    b_vn.add_line(
                        f"اسم المريض: {p_def['name_ar']}   الرقم القومي: {p_def['national_id']}   التاريخ: {v_date}"
                    )
                    b_vn.add_line(
                        f"النوع: {p_def['type']} - خطة العلاج الدوائي المنتظمة."
                    )
                    b_vn.add_line(f"الأدوية: {' و '.join(p_def['meds'])}.")
                    b_vn.start_page()
                    b_vn.add_line(
                        f"نتائج الفحص: مستوى HbA1c وصل إلى {v_hba1c}% و وظائف الكلى eGFR هي {v_egfr} mL/min/1.73m²."
                    )
                    b_vn.add_line(
                        "تم فحص المريض والتوصية بالمتابعة المنتظمة والالتزام بنمط الحياة الصحي."
                    )
                    b_vn.write_txt()
                    b_vn.render_pdf(is_arabic=True)
                    register_doc(
                        vn_file, f"Visit note · {v_lbl} (Arabic)", v_date, 2, False
                    )
                else:
                    b_vn.start_page()
                    b_vn.add_line("OUTPATIENT CLINICAL ENCOUNTER NOTE")
                    b_vn.add_line(f"Patient: #{pid} - {p_def['name']}   Date: {v_date}")
                    b_vn.add_line(
                        f"Diagnosis: {p_def['type']} diabetes for {p_def['duration']} years."
                    )
                    b_vn.add_line(f"Medications: {', '.join(p_def['meds'])}.")

                    f_p1 = next(
                        (
                            f
                            for f in p_def["planted_findings"]
                            if f["source_file"] == vn_file and f["page"] == 1
                        ),
                        None,
                    )
                    if f_p1 and f_p1["quote"]:
                        b_vn.add_line(f_p1["quote"])

                    b_vn.start_page()
                    b_vn.add_line("Progress Evaluation and System Review:")
                    f_p2 = next(
                        (
                            f
                            for f in p_def["planted_findings"]
                            if f["source_file"] == vn_file and f["page"] == 2
                        ),
                        None,
                    )
                    if f_p2 and f_p2["quote"]:
                        b_vn.add_line(f_p2["quote"])
                    else:
                        b_vn.add_line(
                            "Patient denies acute chest pain, shortness of breath, or focal deficits."
                        )

                    b_vn.write_txt()
                    b_vn.render_pdf()
                    register_doc(vn_file, f"Visit note · {v_lbl}", v_date, 2, False)

            # 5. Interim Visit Note if required by medication change (e.g. #1051)
            f_interim_vn = next(
                (
                    f
                    for f in p_def["planted_findings"]
                    if f["source_file"]
                    and f["source_file"] not in [m["file_name"] for m in manifest]
                    and "Visit_Note" in f["source_file"]
                ),
                None,
            )
            if f_interim_vn and f_interim_vn["source_file"]:
                ivn_file = f_interim_vn["source_file"]
                ivn_date = ivn_file.replace("Visit_Note_", "").replace(".pdf", "")
                ivn_pdf = p_dir / ivn_file
                ivn_txt = p_dir / (ivn_file.replace(".pdf", ".txt"))
                b_ivn = DocumentBuilder(ivn_pdf, ivn_txt)
                b_ivn.start_page()
                b_ivn.add_line("ENDOCRINOLOGY CLINIC - INTERIM MEDICATION REVIEW")
                b_ivn.add_line(f"Patient: #{pid} - {p_def['name']}   Date: {ivn_date}")
                b_ivn.start_page()
                b_ivn.add_line("Clinical Decision & Medication Adjustment:")
                if f_interim_vn["quote"]:
                    b_ivn.add_line(f_interim_vn["quote"])
                b_ivn.write_txt()
                b_ivn.render_pdf()
                register_doc(
                    ivn_file,
                    f"Visit note · {ivn_date[:7]} (Interim)",
                    ivn_date,
                    2,
                    False,
                )

            # 6. Nephrology Note if in planted findings
            f_neph = next(
                (
                    f
                    for f in p_def["planted_findings"]
                    if f["source_file"] and "Nephrology_Note" in f["source_file"]
                ),
                None,
            )
            if f_neph and f_neph["source_file"]:
                n_file = f_neph["source_file"]
                n_date = n_file.replace("Nephrology_Note_", "").replace(".pdf", "")
                n_pdf = p_dir / n_file
                n_txt = p_dir / (n_file.replace(".pdf", ".txt"))
                b_n = DocumentBuilder(n_pdf, n_txt)
                b_n.start_page()
                b_n.add_line("NEPHROLOGY SPECIALTY CONSULTATION")
                b_n.add_line(f"Patient: #{pid} - {p_def['name']}   Date: {n_date}")
                if f_neph["quote"]:
                    b_n.add_line(f_neph["quote"])
                b_n.write_txt()
                b_n.render_pdf()
                register_doc(
                    n_file, f"Nephrology note · {n_date[:7]}", n_date, 1, False
                )

            # 7. Clinic Note if in planted findings
            f_clinic = next(
                (
                    f
                    for f in p_def["planted_findings"]
                    if f["source_file"] and "Clinic_Note" in f["source_file"]
                ),
                None,
            )
            if f_clinic and f_clinic["source_file"]:
                c_file = f_clinic["source_file"]
                c_date = c_file.replace("Clinic_Note_", "").replace(".pdf", "")
                c_pdf = p_dir / c_file
                c_txt = p_dir / (c_file.replace(".pdf", ".txt"))
                b_c = DocumentBuilder(c_pdf, c_txt)
                b_c.start_page()
                b_c.add_line("OUTPATIENT CLINIC EVALUATION")
                b_c.add_line(f"Patient: #{pid} - {p_def['name']}   Date: {c_date}")
                if f_clinic["quote"]:
                    b_c.add_line(f_clinic["quote"])
                b_c.write_txt()
                b_c.render_pdf()
                register_doc(c_file, f"Clinic note · {c_date[:7]}", c_date, 1, False)

            # 8. Scans (2 scans for #1043 - #1051)
            all_scans = [
                (
                    "Scanned_Referral_Cover_Sheet.pdf",
                    "Scanned_Referral_Cover_Sheet.txt",
                    "Referral Cover Sheet",
                    "2024-04-12",
                ),
                (
                    "Scanned_Prior_Fax_Header.pdf",
                    "Scanned_Prior_Fax_Header.txt",
                    "Prior Clinic Fax Transmission",
                    "2024-09-18",
                ),
                (
                    "Scanned_Archived_Intake_Cover.pdf",
                    "Scanned_Archived_Intake_Cover.txt",
                    "Archived Paper Intake",
                    "2023-06-20",
                ),
            ]
            for s_pdf, s_txt, s_title, s_date in all_scans[:scan_k]:
                render_unreadable_scan(
                    p_dir / s_pdf,
                    p_dir / s_txt,
                    s_title,
                    s_date,
                    p_def["name"],
                    pid,
                    np_rng,
                )
                register_doc(s_pdf, f"Scanned archive · {s_title}", s_date, 1, True)

        # -------------------------------------------------------------
        # GROUND TRUTH JSON GENERATION
        # -------------------------------------------------------------
        readable_count = sum(1 for d in manifest if not d["is_scan"])
        scan_total = sum(1 for d in manifest if d["is_scan"])

        trend_hba1c = [
            {"date": v[0], "label": v[1], "value": v[2], "unit": "%"}
            for v in p_def["visits"]
        ]
        trend_egfr = [
            {"date": v[0], "label": v[1], "value": v[3], "unit": "mL/min/1.73m²"}
            for v in p_def["visits"]
        ]

        gt_data = {
            "patient_id": pid,
            "as_of_date": AS_OF_DATE,
            "demographics": {
                "fake_name": p_def["name"],
                "age": p_def["age"],
                "diabetes_type": p_def["type"],
                "duration_years": p_def["duration"],
                "medications": p_def["meds"],
                "fake_national_id": p_def["national_id"],
                "fake_phone": p_def["phone"],
                "fake_address": p_def["address"],
            },
            "planted_findings": p_def["planted_findings"],
            "care_gaps": p_def["care_gaps"],
            "trends": {
                "hba1c": trend_hba1c,
                "egfr": trend_egfr,
            },
            "chat_questions": p_def["chat_questions"],
            "files_summary": {
                "total_files": len(manifest),
                "readable_files": readable_count,
                "unreadable_scans": scan_total,
                "arabic_notes_count": arabic_notes_count,
                "manifest": manifest,
            },
        }

        gt_file = base_gt / f"{pid}.json"
        with open(gt_file, "w", encoding="utf-8") as f:
            json.dump(gt_data, f, indent=2, ensure_ascii=False)

        summary_records.append(
            {
                "patient_id": pid,
                "name": p_def["name"],
                "age": p_def["age"],
                "type": p_def["type"],
                "total_files": len(manifest),
                "readable_files": readable_count,
                "unreadable_scans": scan_total,
                "arabic_notes": arabic_notes_count,
                "planted_findings_count": len(p_def["planted_findings"]),
                "unanswerable_chat_count": sum(
                    1 for q in p_def["chat_questions"] if not q["answerable"]
                ),
            }
        )

    return {"summary": summary_records}


if __name__ == "__main__":
    print(
        f"Generating synthetic diabetes patient dataset (as_of_date: {AS_OF_DATE})..."
    )
    res = generate_all(seed=42)
    print(f"Dataset generated successfully! {len(res['summary'])} patients created.")
    for row in res["summary"]:
        print(
            f"Patient #{row['patient_id']}: {row['total_files']} files ({row['unreadable_scans']} scans), {row['planted_findings_count']} findings, {row['unanswerable_chat_count']} refusal questions."
        )
