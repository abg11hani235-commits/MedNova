import re
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import schemas
from .constants import REFUSAL_TEXT
from .models import AuditLog, ChatMessage, Chunk, File, Insight, Patient


def _clean_note(note: str | None) -> str | None:
    if not note:
        return note

    def repl(m: re.Match) -> str:
        d = date(int(m[1]), int(m[2]), int(m[3]))
        return f" in the 12 months before {d.day} {d.strftime('%b %Y')}"

    return re.sub(r"\s*within 12 months of as_of_date \((\d{4})-(\d{2})-(\d{2})\)", repl, note)


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
    for g in p.care_gaps:
        name = g.get("name", "")
        ins = next(
            (by_type[t] for k, t in GAP_TYPES.items() if k in name.lower() and t in by_type), None
        )
        gaps.append(
            schemas.CareGap(
                name=name,
                status=g.get("status", "missing"),
                detail=_clean_note(g.get("evidence") or g.get("absence_note") or ""),
                source=sources.get(ins.id) if ins else None,
            )
        )
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
        considerations=[
            schemas.Consideration(
                id=i.id,
                severity=i.severity,
                statement=i.statement,
                why=i.why or "",
                source=sources[i.id],
            )
            for i in insights[:3]
        ],
    )


def _norm(s: str) -> list[str]:
    return re.sub(r"[^\w\s]", "", s.lower()).split()


def _score(a: list[str], b: list[str]) -> float:
    sa, sb = set(a), set(b)
    return len(sa & sb) / len(sa | sb) if sa and sb else 0.0


def answer_question(db: Session, p: Patient, question: str) -> schemas.ChatAnswer:
    """Fixture chat: only answers questions that exist in the ground truth. Never guesses."""
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
