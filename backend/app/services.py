import re
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import schemas
from .constants import CROSS_PATIENT_TEXT, DECLINE_POLICY_TEXT, REFUSAL_TEXT
from .models import AuditLog, ChatMessage, Chunk, File, Insight, Patient
from .nutrition_rules import (
    evaluate_hba1c_gap,
    evaluate_meal_log_gap,
    evaluate_medication_considerations,
    evaluate_renal_panel_gap,
    evaluate_weight_bmi_gap,
    scan_notes_for_hypoglycemia,
)
from .rag.policy import is_cross_patient, should_decline_policy


def _clean_note(note: str | None) -> str | None:
    if not note:
        return note

    def repl(m: re.Match) -> str:
        d = date(int(m[1]), int(m[2]), int(m[3]))
        return f" in the 12 months before {d.day} {d.strftime('%b %Y')}"

    return re.sub(r"\s*within 12 months of as_of_date \((\d{4})-(\d{2})-(\d{2})\)", repl, note)


_FILE_PREFIX = re.compile(r"^[\w\-]+\.pdf p\.\d+\s*")


def _clean_detail(text: str | None, name: str | None = None, status: str | None = None) -> str:
    raw = text or ""
    t = _clean_note(raw) or ""
    t = _FILE_PREFIX.sub("", t).strip()
    if t.startswith("(") and t.endswith(")"):
        t = t[1:-1].strip()
    if t:
        return t

    # Bare filename fallback: extract date and format a readable sentence
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", raw)
    if m:
        d = date(int(m[1]), int(m[2]), int(m[3]))
        month_yr = d.strftime("%b %Y")
        d_fmt = f"{d.day} {month_yr}"
        if status == "overdue":
            return f"Last recorded on {d_fmt}."
        if status == "missing":
            if name and "foot" in name.lower():
                return f"Diabetic foot examination was missed during evaluation on {d_fmt}."
            return f"Documented as missed during evaluation on {d_fmt}."
        if status == "done":
            return f"Completed on {d_fmt}."
        return f"Last recorded on {d_fmt}."
    return raw


def _resolve_gap_source(
    db: Session,
    patient_id: str,
    evidence: str | None,
    ins_source: schemas.Source | None,
    gap_name: str | None = None,
) -> schemas.Source | None:
    if ins_source is not None:
        return ins_source
    if not evidence:
        return None
    m = re.match(r"^([\w\-]+)\.pdf p\.(\d+)", evidence)
    if not m:
        return None
    stem, page = m.group(1), int(m.group(2))
    cid = f"{patient_id}-{stem}-p{page}"
    chunk = db.get(Chunk, cid)
    if not chunk:
        return None
    f = db.get(File, chunk.file_id)
    lines = [ln.strip() for ln in chunk.text.splitlines() if ln.strip()]
    quote = lines[0] if lines else ""
    if gap_name:
        name_words = [w.lower() for w in gap_name.split() if len(w) > 3]
        for ln in lines:
            if any(w in ln.lower() for w in name_words):
                quote = ln
                break
    else:
        for ln in lines:
            if any(
                k in ln.lower()
                for k in (
                    "completed",
                    "recorded",
                    "screen",
                    "exam",
                    "panel",
                    "due",
                    "missed",
                    "report",
                )
            ):
                quote = ln
                break
    return schemas.Source(
        chunk_id=chunk.id,
        file_name=f.name if f else f"{stem}.pdf",
        page=chunk.page,
        quote=quote,
        date=f.date if f else None,
    )


SEV_RANK = {"urgent_review": 0, "review": 1, "info": 2}
TARGETS = {"hba1c": (6.0, 7.0), "egfr": (60.0, 120.0)}
GAP_TYPES = {
    "retinal": "overdue_retinal_exam",
    "uacr": "missing_uacr",
    "albumin": "missing_uacr",
    "foot": "missed_foot_exam",
    "lipid": "lipid_panel_overdue",
}


def audit(
    db: Session, actor: str, action: str, patient_id: str | None = None, detail: str | None = None
) -> None:
    db.add(AuditLog(actor=actor, action=action, patient_id=patient_id, detail=detail))
    db.commit()


def build_source(db: Session, ins: Insight) -> schemas.Source | None:
    if not ins.source_chunk_id:
        return None
    chunk = db.get(Chunk, ins.source_chunk_id)
    if chunk is None:
        return None
    f = db.get(File, chunk.file_id)
    return schemas.Source(
        chunk_id=chunk.id,
        file_name=f.name if f else chunk.file_id,
        page=chunk.page,
        quote=ins.quote or "",
        date=f.date if f else None,
    )


def _sorted(insights: list[Insight]) -> list[Insight]:
    return sorted(insights, key=lambda i: (SEV_RANK.get(i.severity, 9), i.rank))


def list_patients(db: Session) -> list[schemas.PatientSummary]:
    out = []
    for p in db.scalars(select(Patient).order_by(Patient.id)):
        files = db.scalars(select(File).where(File.patient_id == p.id)).all()
        visits = [f.date for f in files if f.kind in ("visit_note", "clinic_note") and f.date]
        last = max(visits) if visits else p.as_of_date
        open_ins = db.scalars(
            select(Insight).where(Insight.patient_id == p.id, Insight.review_state != "reviewed")
        ).all()
        nxt = (date.fromisoformat(p.as_of_date) + timedelta(days=21)).isoformat()
        out.append(
            schemas.PatientSummary(
                id=p.id,
                display_name=p.display_name,
                age=p.age,
                diabetes_type=p.diabetes_type,
                last_visit=last,
                next_visit=nxt,
                open_items=schemas.OpenItems(
                    urgent=sum(i.severity == "urgent_review" for i in open_ins),
                    review=sum(i.severity == "review" for i in open_ins),
                ),
                files=schemas.FileCounts(
                    total=len(files), readable=sum(not f.is_scan for f in files)
                ),
            )
        )
    return out


def _trend(p: Patient, key: str) -> schemas.Trend:
    lo, hi = TARGETS[key]
    pts = sorted(p.trends.get(key, []), key=lambda x: x["date"])
    return schemas.Trend(
        target=schemas.Target(min=lo, max=hi),
        points=[
            schemas.TrendPoint(date=x["date"], label=x.get("label", x["date"]), value=x["value"])
            for x in pts
        ],
    )


def build_brief(db: Session, p: Patient) -> schemas.Brief:
    insights = _sorted(list(db.scalars(select(Insight).where(Insight.patient_id == p.id))))
    sources = {i.id: build_source(db, i) for i in insights}
    files = db.scalars(select(File).where(File.patient_id == p.id)).all()
    readable = sum(not f.is_scan for f in files)
    snapshot = [
        schemas.Insight(
            id=i.id,
            severity=i.severity,
            statement=i.statement,
            source=sources[i.id],
            absence_note=None if sources[i.id] else _clean_note(i.absence_note),
            review_state=i.review_state,
            feedback=i.feedback,
        )
        for i in insights
    ]
    by_type = {i.type: i for i in insights}
    gaps = []
    existing_gap_names = set()
    for g in p.care_gaps:
        name = g.get("name", "")
        existing_gap_names.add(name.lower())
        ins = next(
            (by_type[t] for k, t in GAP_TYPES.items() if k in name.lower() and t in by_type), None
        )
        st = g.get("status", "missing")
        ev = g.get("evidence")
        detail_str = _clean_detail(ev or g.get("absence_note") or "", name=name, status=st)
        ins_src = sources.get(ins.id) if ins else None
        resolved_src = _resolve_gap_source(
            db, p.id, ev, ins_src, gap_name=name if not ins_src else None
        )
        gaps.append(
            schemas.CareGap(
                name=name,
                status=st,
                detail=detail_str,
                source=resolved_src,
            )
        )

    # Dynamic rule evaluations for care gaps:
    # 1. Meal log gap (evaluated only if meal-log source is present)
    meal_log_source_present = any(f.kind == "meal_log" or "meal" in f.name.lower() for f in files)
    if meal_log_source_present:
        meal_files = [f for f in files if (f.kind == "meal_log" or "meal" in f.name.lower())]
        meal_entries = [{"date": f.date} for f in meal_files if f.date]
        meal_gap = evaluate_meal_log_gap(
            as_of_date=p.as_of_date,
            meal_log_enabled=True,
            meal_logs=meal_entries if meal_entries else None,
        )
        if (
            meal_gap
            and meal_gap["status"] in ("overdue", "missing")
            and not any("meal" in n for n in existing_gap_names)
        ):
            gaps.append(
                schemas.CareGap(
                    name=meal_gap["name"],
                    status=meal_gap["status"],
                    detail=meal_gap["detail"],
                    source=None,
                )
            )

    # 2. HbA1c gap rule (if hba1c tracked in trends and not already in gaps)
    if "hba1c" in (p.trends or {}) and not any("hba1c" in n for n in existing_gap_names):
        hba1c_eval = evaluate_hba1c_gap(
            as_of_date=p.as_of_date,
            hba1c_records=p.trends.get("hba1c", []),
        )
        if hba1c_eval["status"] in ("overdue", "missing"):
            gaps.append(
                schemas.CareGap(
                    name=hba1c_eval["name"],
                    status=hba1c_eval["status"],
                    detail=hba1c_eval["detail"],
                    source=None,
                )
            )

    # 3. Weight/BMI gap rule (if weight tracked in trends and not already in gaps)
    if "weight" in (p.trends or {}) and not any(
        "weight" in n or "bmi" in n for n in existing_gap_names
    ):
        weight_eval = evaluate_weight_bmi_gap(
            as_of_date=p.as_of_date,
            weight_records=p.trends.get("weight", []),
        )
        if weight_eval["status"] in ("overdue", "missing"):
            gaps.append(
                schemas.CareGap(
                    name=weight_eval["name"],
                    status=weight_eval["status"],
                    detail=weight_eval["detail"],
                    source=None,
                )
            )

    # 4. Renal panel gap rule (if renal/egfr tracked and not already in gaps)
    if (
        "renal" in (p.trends or {})
        or (
            "egfr" in (p.trends or {})
            and not any(k in n for n in existing_gap_names for k in ("uacr", "albumin"))
        )
    ) and not any("renal" in n for n in existing_gap_names):
        renal_eval = evaluate_renal_panel_gap(
            as_of_date=p.as_of_date,
            renal_records=p.trends.get("renal") or p.trends.get("egfr", []),
        )
        if renal_eval["status"] in ("overdue", "missing"):
            gaps.append(
                schemas.CareGap(
                    name=renal_eval["name"],
                    status=renal_eval["status"],
                    detail=renal_eval["detail"],
                    source=None,
                )
            )

    # Dynamic rule evaluations for considerations:
    considerations = [
        schemas.Consideration(
            id=i.id,
            severity=i.severity,
            statement=i.statement,
            why=i.why or "",
            source=sources[i.id],
        )
        for i in insights
    ]

    # 5. Medication consideration (Metformin + eGFR)
    if any("metformin" in m.lower() for m in (p.medications or [])) and not any(
        "metformin" in c.statement.lower() or c.id == "cons-metformin-egfr" for c in considerations
    ):
        med_citations = {}
        egfr_chunk = db.scalars(
            select(Chunk)
            .join(File, Chunk.file_id == File.id)
            .where(Chunk.patient_id == p.id, func.lower(Chunk.text).like("%egfr%"))
        ).first()
        if egfr_chunk:
            f = db.get(File, egfr_chunk.file_id)
            q_line = next(
                (ln.strip() for ln in egfr_chunk.text.splitlines() if "egfr" in ln.lower()),
                egfr_chunk.text[:80],
            )
            med_citations["egfr"] = schemas.Source(
                chunk_id=egfr_chunk.id,
                file_name=f.name if f else egfr_chunk.file_id,
                page=egfr_chunk.page,
                quote=q_line,
                date=f.date if f else None,
            )
        med_items = evaluate_medication_considerations(
            medications=p.medications,
            egfr_trends=p.trends.get("egfr", []),
            citations=med_citations,
        )
        for item in med_items:
            considerations.append(
                schemas.Consideration(
                    id=item["id"],
                    severity=item["severity"],
                    statement=item["statement"],
                    why=item["why"],
                    source=item.get("source"),
                )
            )

    # 6. Hypoglycemia scan from notes
    all_chunks = db.scalars(select(Chunk).where(Chunk.patient_id == p.id)).all()
    if all_chunks and not any(
        "hypoglycemia" in c.statement.lower() or "glucose" in c.statement.lower()
        for c in considerations
    ):
        chunk_dicts = []
        for c in all_chunks:
            f = db.get(File, c.file_id)
            chunk_dicts.append(
                {
                    "chunk_id": c.id,
                    "file_name": f.name if f else c.file_id,
                    "page": c.page,
                    "text": c.text,
                    "date": f.date if f else None,
                }
            )
        hypo_findings = scan_notes_for_hypoglycemia(chunk_dicts)
        for idx, hf in enumerate(hypo_findings):
            considerations.append(
                schemas.Consideration(
                    id=f"cons-hypo-{idx + 1}",
                    severity=hf["severity"],
                    statement=hf["statement"],
                    why=hf["why"],
                    source=schemas.Source(**hf["citation"]) if hf.get("citation") else None,
                )
            )

    considerations = sorted(considerations, key=lambda c: SEV_RANK.get(c.severity, 9))

    return schemas.Brief(
        patient=schemas.PatientInfo(
            id=p.id,
            display_name=p.display_name,
            age=p.age,
            diabetes_type=p.diabetes_type,
            duration_years=p.duration_years,
            medications=list(p.medications),
        ),
        coverage=schemas.Coverage(
            total_files=len(files), readable_files=readable, unreadable_files=len(files) - readable
        ),
        snapshot=snapshot,
        trends=schemas.Trends(hba1c=_trend(p, "hba1c"), egfr=_trend(p, "egfr")),
        care_gaps=gaps,
        considerations=considerations[:3],
    )


def _norm(s: str) -> list[str]:
    return re.sub(r"[^\w\s]", "", s.lower()).split()


def _score(a: list[str], b: list[str]) -> float:
    sa, sb = set(a), set(b)
    return len(sa & sb) / len(sa | sb) if sa and sb else 0.0


def answer_question(db: Session, p: Patient, question: str) -> schemas.ChatAnswer:
    """Fixture chat: only answers questions that exist in the ground truth. Never guesses."""
    if is_cross_patient(question, p.id):
        ans = schemas.ChatAnswer(answer=CROSS_PATIENT_TEXT, answerable=False, source=None)
        db.add(ChatMessage(patient_id=p.id, role="user", content=question))
        db.add(
            ChatMessage(
                patient_id=p.id,
                role="assistant",
                content=ans.answer,
                answerable=ans.answerable,
                source_chunk_id=None,
            )
        )
        db.commit()
        return ans

    if should_decline_policy(question):
        ans = schemas.ChatAnswer(answer=DECLINE_POLICY_TEXT, answerable=False, source=None)
        db.add(ChatMessage(patient_id=p.id, role="user", content=question))
        db.add(
            ChatMessage(
                patient_id=p.id,
                role="assistant",
                content=ans.answer,
                answerable=ans.answerable,
                source_chunk_id=None,
            )
        )
        db.commit()
        return ans

    q = _norm(question)
    best, best_score = None, 0.0
    for item in p.chat_questions:
        s = _score(q, _norm(item.get("question", "")))
        if s > best_score:
            best, best_score = item, s
    ans = schemas.ChatAnswer(answer=REFUSAL_TEXT, answerable=False, source=None)
    if (
        best
        and best_score >= 0.8
        and best.get("answerable")
        and best.get("expected_answer_summary")
    ):
        source = None
        if best.get("source_file") and best.get("page"):
            cid = f"{p.id}-{Path(best['source_file']).stem}-p{int(best['page'])}"
            chunk = db.get(Chunk, cid)
            if chunk is not None and chunk.patient_id == p.id:
                f = db.get(File, chunk.file_id)
                source = schemas.Source(
                    chunk_id=cid, file_name=f.name, page=chunk.page, quote="", date=f.date
                )
        ans = schemas.ChatAnswer(
            answer=best["expected_answer_summary"], answerable=True, source=source
        )
    db.add(ChatMessage(patient_id=p.id, role="user", content=question))
    db.add(
        ChatMessage(
            patient_id=p.id,
            role="assistant",
            content=ans.answer,
            answerable=ans.answerable,
            source_chunk_id=ans.source.chunk_id if ans.source else None,
        )
    )
    db.commit()
    return ans


def count_chunks(db: Session, pid: str) -> int:
    return db.scalar(select(func.count()).select_from(Chunk).where(Chunk.patient_id == pid)) or 0


def get_suggested_questions(db: Session, p: Patient) -> list[str]:
    answerable = [
        q["question"] for q in p.chat_questions if q.get("answerable") and q.get("question")
    ]
    unanswerable = [
        q["question"] for q in p.chat_questions if not q.get("answerable") and q.get("question")
    ]
    out = answerable[:2]
    if unanswerable:
        out.append(unanswerable[0])
    return out[:3]
