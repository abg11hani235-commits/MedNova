"""Load the synthetic dataset (ground truth + page-delimited text) into the database.

Idempotent: re-seeding a patient replaces that patient's rows.
"""

import json
import re
from datetime import datetime
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .models import (
    ChatMessage,
    Chunk,
    File,
    Insight,
    MealItem,
    MealLog,
    Patient,
    PatientChatMessage,
)

PAGE_RE = re.compile(r"^=== PAGE (\d+) ===[ \t]*$", re.M)
DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
SEVERITIES = {"info", "review", "urgent_review"}
GAP_KEYS = {
    "missing_uacr": ("uacr", "albumin"),
    "overdue_retinal_exam": ("retinal",),
    "missed_foot_exam": ("foot",),
    "lipid_panel_overdue": ("lipid",),
}
KIND_PREFIX = [
    ("Scanned_", "scan"),
    ("Lab_Report", "lab"),
    ("Visit_Note", "visit_note"),
    ("Clinic_Note", "clinic_note"),
    ("Nephrology_Note", "specialist"),
    ("Eye_Report", "specialist"),
]


def split_pages(text: str) -> list[tuple[int, str]]:
    parts = PAGE_RE.split(text)
    pages = [(int(parts[i]), parts[i + 1].strip("\n")) for i in range(1, len(parts) - 1, 2)]
    if not pages and text.strip():
        pages = [(1, text.strip("\n"))]
    return pages


def file_kind(stem: str) -> str:
    for prefix, kind in KIND_PREFIX:
        if stem.startswith(prefix):
            return kind
    return "other"


def chunk_id(pid: str, stem: str, page: int) -> str:
    return f"{pid}-{stem}-p{page}"


def why_for(ftype: str, trends: dict, meds: list[str]) -> str:
    hba1c = [p["value"] for p in sorted(trends.get("hba1c", []), key=lambda p: p["date"])]
    egfr = [p["value"] for p in sorted(trends.get("egfr", []), key=lambda p: p["date"])]
    if ftype == "rising_hba1c" and len(hba1c) >= 3:
        last = ", ".join(f"{v:g}" for v in hba1c[-3:])
        return f"Last three HbA1c results: {last}."
    if ftype == "falling_egfr" and len(egfr) >= 2:
        extra = (
            " Metformin is listed as ongoing (worth reviewing with treating physician)."
            if "Metformin" in meds
            else ""
        )
        return f"eGFR went from {egfr[0]:g} to {egfr[-1]:g} across the visits.{extra}"
    return {
        "missing_uacr": (
            "No urine albumin-creatinine ratio appears in the files from the last 12 months."
        ),
        "overdue_retinal_exam": "The last retinal exam on file is more than 12 months old.",
        "hypoglycemia_symptoms": "A visit note describes symptoms that may relate to low glucose.",
        "medication_changed_no_followup": (
            "A medication change is documented without a later follow-up note."
        ),
        "missed_foot_exam": "No foot examination appears in the files from the last 12 months.",
        "lipid_panel_overdue": "No lipid panel appears in the files from the last 12 months.",
    }.get(ftype, "This is documented in the source file.")


def seed_patient(db: Session, pid: str, gt: dict, text_dir: Path) -> None:
    for model in (Insight, Chunk, File, ChatMessage):
        db.execute(delete(model).where(model.patient_id == pid))
    db.execute(delete(Patient).where(Patient.id == pid))

    demo = gt.get("demographics", {})
    meds = list(demo.get("medications", []))
    trends = gt.get("trends", {})
    db.add(
        Patient(
            id=pid,
            display_name=f"Synthetic Patient #{pid}",
            age=int(demo.get("age", 0)),
            diabetes_type=demo.get("diabetes_type", "Type 2"),
            duration_years=demo.get("duration_years"),
            medications=meds,
            as_of_date=gt.get("as_of_date", "2026-06-18"),
            trends=trends,
            care_gaps=gt.get("care_gaps", []),
            chat_questions=gt.get("chat_questions", []),
        )
    )
    db.flush()

    chunk_ids: set[str] = set()
    for txt in sorted(text_dir.glob("*.txt")):
        stem = txt.stem
        text = txt.read_text(encoding="utf-8")
        is_scan = stem.startswith("Scanned_") or "[UNREADABLE SCANNED DOCUMENT" in text
        m = DATE_RE.search(stem)
        db.add(
            File(
                id=f"{pid}-{stem}",
                patient_id=pid,
                name=f"{stem}.pdf",
                kind=file_kind(stem),
                date=m.group(1) if m else None,
                is_scan=is_scan,
                status="unreadable" if is_scan else "ready",
            )
        )
        db.flush()
        if is_scan:
            continue
        for page, body in split_pages(text):
            if not body.strip():
                continue
            cid = chunk_id(pid, stem, page)
            chunk_ids.add(cid)
            db.add(Chunk(id=cid, patient_id=pid, file_id=f"{pid}-{stem}", page=page, text=body))
    db.flush()

    gaps = gt.get("care_gaps", [])
    for rank, f in enumerate(gt.get("planted_findings", [])):
        sev = f.get("severity") if f.get("severity") in SEVERITIES else "review"
        src_file, page = f.get("source_file"), f.get("page")
        cid = chunk_id(pid, Path(src_file).stem, int(page)) if src_file and page else None
        if cid not in chunk_ids:
            cid = None
        absence = None
        if cid is None:
            absence = f.get("absence_note")
            keys = GAP_KEYS.get(f.get("type", ""), ())
            for g in gaps:
                if not absence and any(k in g.get("name", "").lower() for k in keys):
                    absence = g.get("absence_note") or g.get("evidence")
            absence = absence or "No record found in the patient's readable files."
        db.add(
            Insight(
                id=f"{pid}-{f['id']}",
                patient_id=pid,
                type=f.get("type", "other"),
                severity=sev,
                statement=f["statement"],
                why=why_for(f.get("type", ""), trends, meds),
                source_chunk_id=cid,
                quote=f.get("quote") if cid else None,
                absence_note=absence,
                rank=rank,
            )
        )
    db.commit()


def seed_meals(db: Session, seed_file: Path) -> int:
    """Seed synthetic meal logs and patient chat messages from separate file."""
    if not seed_file.exists():
        return 0
    data = json.loads(seed_file.read_text(encoding="utf-8"))
    count = 0
    for pid, logs in data.get("patients", {}).items():
        existing_log_ids = db.scalars(select(MealLog.id).where(MealLog.patient_id == pid)).all()
        if existing_log_ids:
            db.execute(delete(MealItem).where(MealItem.meal_log_id.in_(existing_log_ids)))
            db.execute(delete(PatientChatMessage).where(PatientChatMessage.patient_id == pid))
            db.execute(delete(MealLog).where(MealLog.patient_id == pid))

        for ml_data in logs:
            dt_str = ml_data.get("logged_at")
            logged_at = datetime.fromisoformat(dt_str) if dt_str else datetime.now()
            ml = MealLog(
                id=ml_data.get("id"),
                patient_id=pid,
                local_date=ml_data.get("local_date"),
                logged_at=logged_at,
                meal_type=ml_data.get("meal_type", "unspecified"),
                raw_text=ml_data.get("raw_text", ""),
                status=ml_data.get("status", "parsed"),
                clarification_question=ml_data.get("clarification_question"),
                clarification_options=ml_data.get("clarification_options"),
                safety_flag=ml_data.get("safety_flag"),
            )
            db.add(ml)
            db.flush()

            db.add(
                PatientChatMessage(
                    patient_id=pid,
                    meal_log_id=ml.id,
                    role="patient",
                    content=ml.raw_text,
                    created_at=logged_at,
                )
            )

            for item_data in ml_data.get("items", []):
                mi = MealItem(
                    meal_log_id=ml.id,
                    food_id=item_data["food_id"],
                    food_name_ar=item_data.get("food_name_ar", ""),
                    food_name_en=item_data.get("food_name_en", ""),
                    quantity=float(item_data.get("quantity", 1.0)),
                    unit=item_data.get("unit", "حصة"),
                    grams=float(item_data.get("grams", 100.0)),
                    kcal=float(item_data.get("kcal", 0.0)),
                    protein_g=float(item_data.get("protein_g", 0.0)),
                    carbs_g=float(item_data.get("carbs_g", 0.0)),
                    fat_g=float(item_data.get("fat_g", 0.0)),
                    fiber_g=float(item_data.get("fiber_g", 0.0)),
                    match_method=item_data.get("match_method", "seed_exact"),
                    match_score=float(item_data.get("match_score", 1.0)),
                    confirmed=bool(item_data.get("confirmed", True)),
                )
                db.add(mi)
            count += 1
    db.commit()
    return count


def seed_all(db: Session, data_dir: Path) -> list[str]:
    ids = []
    for gt_path in sorted((data_dir / "ground_truth").glob("*.json")):
        pid = gt_path.stem
        gt = json.loads(gt_path.read_text(encoding="utf-8"))
        seed_patient(db, pid, gt, data_dir / "synthetic" / pid)
        ids.append(pid)

    seed_meals(db, data_dir / "seed_meals.json")
    return ids
