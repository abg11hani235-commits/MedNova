import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File as UploadFileField, Header, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import schemas, services
from .config import get_settings
from .db import get_db
from .models import AuditLog, Chunk, File, Insight, Patient

router = APIRouter()
DEFAULT_ACTOR = "DR (Doctor)"


def actor_header(x_actor: str | None = Header(default=None)) -> str:
    return (x_actor or DEFAULT_ACTOR)[:64]


def patient_or_404(db: Session, pid: str) -> Patient:
    p = db.get(Patient, pid)
    if p is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    return p


@router.get("/patients", response_model=list[schemas.PatientSummary])
def list_patients(db: Session = Depends(get_db)):
    return services.list_patients(db)


@router.get("/patients/{pid}/brief", response_model=schemas.Brief)
def get_brief(pid: str, db: Session = Depends(get_db), actor: str = Depends(actor_header)):
    p = patient_or_404(db, pid)
    brief = services.build_brief(db, p)
    services.audit(db, actor, "view_brief", pid)
    return brief


@router.get("/patients/{pid}/sources/{chunk_id}", response_model=schemas.SourcePage)
def get_source(pid: str, chunk_id: str, db: Session = Depends(get_db), actor: str = Depends(actor_header)):
    patient_or_404(db, pid)
    chunk = db.get(Chunk, chunk_id)
    if chunk is None or chunk.patient_id != pid:
        raise HTTPException(status_code=404, detail="Source not found")
    f = db.get(File, chunk.file_id)
    ins = db.scalars(
        select(Insight).where(Insight.patient_id == pid, Insight.source_chunk_id == chunk_id).order_by(Insight.rank)
    ).first()
    quote = (ins.quote or "") if ins else ""
    start = chunk.text.find(quote) if quote else -1
    services.audit(db, actor, "view_source", pid, chunk_id)
    return schemas.SourcePage(
        chunk_id=chunk.id,
        file_name=f.name if f else chunk.file_id,
        page=chunk.page,
        date=f.date if f else None,
        page_text=chunk.text,
        quote=quote,
        highlight=schemas.Highlight(start=start, end=start + len(quote)) if start >= 0 else None,
    )


@router.post("/patients/{pid}/chat", response_model=schemas.ChatAnswer)
def chat(pid: str, body: schemas.ChatRequest, db: Session = Depends(get_db), actor: str = Depends(actor_header)):
    p = patient_or_404(db, pid)
    answer = services.answer_question(db, p, body.question)
    services.audit(db, actor, "chat_question", pid, body.question[:200])
    return answer


@router.post("/insights/{insight_id}/review", response_model=schemas.ReviewResult)
def review(insight_id: str, body: schemas.ReviewRequest, db: Session = Depends(get_db), actor: str = Depends(actor_header)):
    ins = db.get(Insight, insight_id)
    if ins is None:
        raise HTTPException(status_code=404, detail="Insight not found")
    if body.action == "reviewed":
        ins.review_state = "reviewed"
    else:
        ins.feedback = body.action
    db.commit()
    services.audit(db, actor, f"review_{body.action}", ins.patient_id, insight_id)
    return schemas.ReviewResult(id=ins.id, review_state=ins.review_state, feedback=ins.feedback)


@router.post("/patients/{pid}/files", response_model=schemas.UploadResult)
async def upload(pid: str, file: UploadFile = UploadFileField(...), db: Session = Depends(get_db), actor: str = Depends(actor_header)):
    patient_or_404(db, pid)
    settings = get_settings()
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", Path(file.filename or "upload").name)[:120] or "upload"
    file_id = uuid.uuid4().hex
    dest_dir = settings.storage_dir / "uploads" / pid
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{file_id}_{safe}"
    limit = settings.max_upload_mb * 1024 * 1024
    size = 0
    with dest.open("wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > limit:
                out.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="File too large")
            out.write(chunk)
    db.add(
        File(id=file_id, patient_id=pid, name=safe, kind="upload", is_scan=False, status="queued", storage_path=str(dest))
    )
    db.commit()
    services.audit(db, actor, "upload", pid, safe)
    return schemas.UploadResult(file_id=file_id, status="queued")


@router.get("/audit", response_model=list[schemas.AuditEntry])
def get_audit(db: Session = Depends(get_db)):
    rows = db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(200)).all()
    return [
        schemas.AuditEntry(time=r.ts.isoformat(), actor=r.actor, action=r.action, patient_id=r.patient_id)
        for r in rows
    ]
