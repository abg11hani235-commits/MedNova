import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException, UploadFile
from fastapi import File as UploadFileField
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import schemas, services
from .config import get_settings
from .db import get_db
from .meal_parser import calculate_item_macros, get_foods_table, parse_meal_text
from .meal_policy import (
    EMERGENCY_SYMPTOM_TEXT,
    PATIENT_CHAT_DECLINE_TEXT,
    is_emergency_symptom,
    is_plain_record_lookup,
    should_decline_patient_chat,
    validate_and_build_daily_summary,
)
from .models import (
    AuditLog,
    Chunk,
    File,
    Insight,
    MealItem,
    MealLog,
    Patient,
    PatientChatMessage,
    get_cairo_date,
    get_cairo_datetime,
)

router = APIRouter()
DEFAULT_ACTOR = "NS (Nutrition Specialist)"


def require_specialist_actor(x_actor: str | None = Header(default=None)) -> str:
    """Specialist auth dependency.

    Denies patient actors ('PT <pid>') from accessing specialist EHR routes.
    """
    if x_actor and x_actor.strip().startswith("PT"):
        raise HTTPException(
            status_code=403,
            detail="Patient actors cannot access specialist EHR routes or other patients",
        )
    return (x_actor or DEFAULT_ACTOR)[:64]


def require_patient_or_specialist(
    pid: str,
    x_actor: str | None = Header(default=None),
) -> str:
    """Patient meal routes auth dependency (AGENTS rule 5).

    Enforces default-deny:
    - Missing X-Actor -> 403 Forbidden.
    - 'PT <wrong_pid>' -> 403 Forbidden.
    - 'PT <pid>' -> Allowed.
    - 'NS' (Specialist) -> Allowed to read/view.
    """
    if not x_actor or not x_actor.strip():
        raise HTTPException(
            status_code=403,
            detail="X-Actor header required for patient routes (default-deny)",
        )
    actor = x_actor.strip()
    if actor.startswith("PT"):
        parts = actor.split()
        actor_pid = parts[1] if len(parts) > 1 else actor[2:].strip(" :_-")
        if actor_pid != str(pid).strip():
            raise HTTPException(
                status_code=403,
                detail="Patient cannot access another patient's data",
            )
        return actor[:64]
    elif actor.startswith("NS"):
        return actor[:64]
    else:
        raise HTTPException(status_code=403, detail="Unauthorized actor role")


def patient_or_404(db: Session, pid: str) -> Patient:
    p = db.get(Patient, pid)
    if p is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    return p


# ---------------------------------------------------------------------------
# Specialist EHR Routes (Protected from PT actors)
# ---------------------------------------------------------------------------


@router.get("/patients", response_model=list[schemas.PatientSummary])
def list_patients(
    db: Session = Depends(get_db),
    actor: str = Depends(require_specialist_actor),
):
    return services.list_patients(db)


@router.get("/patients/{pid}/brief", response_model=schemas.Brief)
def get_brief(
    pid: str,
    db: Session = Depends(get_db),
    actor: str = Depends(require_specialist_actor),
):
    p = patient_or_404(db, pid)
    brief = services.build_brief(db, p)
    services.audit(db, actor, "view_brief", pid)
    return brief


@router.get("/patients/{pid}/sources/{chunk_id}", response_model=schemas.SourcePage)
def get_source(
    pid: str,
    chunk_id: str,
    db: Session = Depends(get_db),
    actor: str = Depends(require_specialist_actor),
):
    patient_or_404(db, pid)
    chunk = db.get(Chunk, chunk_id)
    if chunk is None or chunk.patient_id != pid:
        raise HTTPException(status_code=404, detail="Source not found")
    f = db.get(File, chunk.file_id)
    ins = db.scalars(
        select(Insight)
        .where(Insight.patient_id == pid, Insight.source_chunk_id == chunk_id)
        .order_by(Insight.rank)
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


@router.get("/patients/{pid}/suggested-questions", response_model=list[str])
def get_suggested_questions(
    pid: str,
    db: Session = Depends(get_db),
    actor: str = Depends(require_specialist_actor),
):
    p = patient_or_404(db, pid)
    return services.get_suggested_questions(db, p)


@router.post("/patients/{pid}/chat", response_model=schemas.ChatAnswer)
def chat(
    pid: str,
    body: schemas.ChatRequest,
    db: Session = Depends(get_db),
    actor: str = Depends(require_specialist_actor),
):
    p = patient_or_404(db, pid)
    answer = services.answer_question(db, p, body.question)
    services.audit(db, actor, "chat_question", pid, body.question[:200])
    return answer


@router.post("/insights/{insight_id}/review", response_model=schemas.ReviewResult)
def review(
    insight_id: str,
    body: schemas.ReviewRequest,
    db: Session = Depends(get_db),
    actor: str = Depends(require_specialist_actor),
):
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
async def upload(
    pid: str,
    file: UploadFile = UploadFileField(...),
    db: Session = Depends(get_db),
    actor: str = Depends(require_specialist_actor),
):
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
        File(
            id=file_id,
            patient_id=pid,
            name=safe,
            kind="upload",
            is_scan=False,
            status="queued",
            storage_path=str(dest),
        )
    )
    db.commit()
    services.audit(db, actor, "upload", pid, safe)
    return schemas.UploadResult(file_id=file_id, status="queued")


@router.get("/audit", response_model=list[schemas.AuditEntry])
def get_audit(
    db: Session = Depends(get_db),
    actor: str = Depends(require_specialist_actor),
):
    rows = db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(200)).all()
    return [
        schemas.AuditEntry(
            time=r.ts.isoformat(), actor=r.actor, action=r.action, patient_id=r.patient_id
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Patient Meal Logging & Chat Routes (Isolated by patient_id)
# ---------------------------------------------------------------------------


@router.post("/patients/{pid}/meals/chat", response_model=schemas.PatientChatResponse)
def patient_meal_chat(
    pid: str,
    body: schemas.PatientChatRequest,
    db: Session = Depends(get_db),
    actor: str = Depends(require_patient_or_specialist),
):
    """Patient meal logging chat endpoint."""
    patient_or_404(db, pid)
    services.audit(db, actor, "patient_chat_message", pid, body.message[:200])

    # Record inbound patient message
    msg_in = PatientChatMessage(
        patient_id=pid,
        role="patient",
        content=body.message,
        created_at=get_cairo_datetime(),
    )
    db.add(msg_in)
    db.commit()

    # 1. Emergency symptom triage
    if is_emergency_symptom(body.message):
        meal_log = MealLog(
            patient_id=pid,
            local_date=get_cairo_date(),
            logged_at=get_cairo_datetime(),
            meal_type=body.meal_type,
            raw_text=body.message,
            status="emergency",
            safety_flag="emergency_symptom",
        )
        db.add(meal_log)
        db.commit()

        msg_out = PatientChatMessage(
            patient_id=pid,
            meal_log_id=meal_log.id,
            role="assistant",
            content=EMERGENCY_SYMPTOM_TEXT,
            created_at=get_cairo_datetime(),
        )
        db.add(msg_out)
        db.commit()

        return schemas.PatientChatResponse(
            status="emergency",
            reply=EMERGENCY_SYMPTOM_TEXT,
            meal_log=services.build_meal_log_schema(db, meal_log),
            safety_flag="emergency_symptom",
        )

    # 2. Policy decline (diet plans, calorie prescriptions, meds, diagnosis)
    if should_decline_patient_chat(body.message):
        meal_log = MealLog(
            patient_id=pid,
            local_date=get_cairo_date(),
            logged_at=get_cairo_datetime(),
            meal_type=body.meal_type,
            raw_text=body.message,
            status="rejected",
            safety_flag="policy_decline",
        )
        db.add(meal_log)
        db.commit()

        msg_out = PatientChatMessage(
            patient_id=pid,
            meal_log_id=meal_log.id,
            role="assistant",
            content=PATIENT_CHAT_DECLINE_TEXT,
            created_at=get_cairo_datetime(),
        )
        db.add(msg_out)
        db.commit()

        return schemas.PatientChatResponse(
            status="rejected",
            reply=PATIENT_CHAT_DECLINE_TEXT,
            meal_log=services.build_meal_log_schema(db, meal_log),
            safety_flag="policy_decline",
        )

    # 3. Plain record lookup ("أكلت إيه امبارح؟")
    if is_plain_record_lookup(body.message):
        today_str = get_cairo_date()
        sec = services.build_meals_section(db, pid)
        today_summary = next((d for d in sec.recent_days if d.date == today_str), None)
        if not today_summary and sec.recent_days:
            today_summary = sec.recent_days[0]

        if today_summary and today_summary.meal_count > 0:
            reply_text = validate_and_build_daily_summary(today_summary.dict())
        else:
            reply_text = "لسه مفيش وجبات مسجلة في سجل النهاردة. تحب تسجل وجبة دلوقتي؟"

        msg_out = PatientChatMessage(
            patient_id=pid,
            role="assistant",
            content=reply_text,
            created_at=get_cairo_datetime(),
        )
        db.add(msg_out)
        db.commit()

        return schemas.PatientChatResponse(
            status="record_lookup",
            reply=reply_text,
        )

    # 4. Standard meal parsing
    parse_res = parse_meal_text(body.message)

    if parse_res.status == "needs_clarification":
        meal_log = MealLog(
            patient_id=pid,
            local_date=get_cairo_date(),
            logged_at=get_cairo_datetime(),
            meal_type=body.meal_type,
            raw_text=body.message,
            status="needs_clarification",
            clarification_question=parse_res.clarification_question,
            clarification_options=parse_res.clarification_options,
        )
        db.add(meal_log)
        db.commit()

        msg_out = PatientChatMessage(
            patient_id=pid,
            meal_log_id=meal_log.id,
            role="assistant",
            content=parse_res.clarification_question or "",
            created_at=get_cairo_datetime(),
        )
        db.add(msg_out)
        db.commit()

        return schemas.PatientChatResponse(
            status="needs_clarification",
            reply=parse_res.clarification_question or "",
            meal_log=services.build_meal_log_schema(db, meal_log),
            clarification_options=parse_res.clarification_options,
        )

    if parse_res.status == "unknown_food":
        meal_log = MealLog(
            patient_id=pid,
            local_date=get_cairo_date(),
            logged_at=get_cairo_datetime(),
            meal_type=body.meal_type,
            raw_text=body.message,
            status="unknown_food",
            clarification_question=parse_res.clarification_question,
            clarification_options=[],
        )
        db.add(meal_log)
        db.commit()

        msg_out = PatientChatMessage(
            patient_id=pid,
            meal_log_id=meal_log.id,
            role="assistant",
            content=parse_res.clarification_question or "",
            created_at=get_cairo_datetime(),
        )
        db.add(msg_out)
        db.commit()

        return schemas.PatientChatResponse(
            status="unknown_food",
            reply=parse_res.clarification_question or "",
            meal_log=services.build_meal_log_schema(db, meal_log),
            clarification_options=[],
        )

    # Parsed successfully
    meal_log = MealLog(
        patient_id=pid,
        local_date=get_cairo_date(),
        logged_at=get_cairo_datetime(),
        meal_type=body.meal_type,
        raw_text=body.message,
        status="parsed",
    )
    db.add(meal_log)
    db.flush()

    for it in parse_res.items:
        m_item = MealItem(
            meal_log_id=meal_log.id,
            food_id=it.food_id,
            food_name_ar=it.food_name_ar,
            food_name_en=it.food_name_en,
            quantity=it.quantity,
            unit=it.unit,
            grams=it.grams,
            kcal=it.kcal,
            protein_g=it.protein_g,
            carbs_g=it.carbs_g,
            fat_g=it.fat_g,
            fiber_g=it.fiber_g,
            match_method=it.match_method,
            match_score=it.match_score,
            confirmed=True,
        )
        db.add(m_item)
    db.commit()

    items_summary = "، ".join(
        f"{it.food_name_ar} ({it.quantity} {it.unit})" for it in parse_res.items
    )
    reply_text = (
        f"سجلتلك: {items_summary}. "
        f"إجمالي السعرات: {int(parse_res.total_kcal)} سعر حراري (تقديري). ألف صحة وهنا!"
    )
    msg_out = PatientChatMessage(
        patient_id=pid,
        meal_log_id=meal_log.id,
        role="assistant",
        content=reply_text,
        created_at=get_cairo_datetime(),
    )
    db.add(msg_out)
    db.commit()

    return schemas.PatientChatResponse(
        status="parsed",
        reply=reply_text,
        meal_log=services.build_meal_log_schema(db, meal_log),
    )


@router.post("/patients/{pid}/meals/{meal_log_id}/clarify", response_model=schemas.MealLogSchema)
def clarify_meal(
    pid: str,
    meal_log_id: str,
    body: schemas.PatientClarifyRequest,
    db: Session = Depends(get_db),
    actor: str = Depends(require_patient_or_specialist),
):
    """Confirm or clarify an ambiguous food portion."""
    patient_or_404(db, pid)
    log = db.get(MealLog, meal_log_id)
    if not log or log.patient_id != pid:
        raise HTTPException(status_code=404, detail="Meal log not found")

    if body.selected_option:
        opt = body.selected_option
        food_id = opt.get("food_id")
        foods = get_foods_table()
        food_entry = next((f for f in foods if f["id"] == food_id), None)
        if food_entry:
            extracted = calculate_item_macros(
                food=food_entry,
                quantity=float(opt.get("quantity", 1.0)),
                unit_str=opt.get("unit"),
                match_method="clarification_selected",
                match_score=1.0,
            )
            m_item = MealItem(
                meal_log_id=log.id,
                food_id=extracted.food_id,
                food_name_ar=extracted.food_name_ar,
                food_name_en=extracted.food_name_en,
                quantity=extracted.quantity,
                unit=extracted.unit,
                grams=extracted.grams,
                kcal=extracted.kcal,
                protein_g=extracted.protein_g,
                carbs_g=extracted.carbs_g,
                fat_g=extracted.fat_g,
                fiber_g=extracted.fiber_g,
                match_method=extracted.match_method,
                match_score=extracted.match_score,
                confirmed=True,
            )
            db.add(m_item)
            log.status = "parsed"
            log.clarification_question = None
            db.commit()

    services.audit(db, actor, "clarify_meal", pid, str(meal_log_id))
    return services.build_meal_log_schema(db, log)


@router.get("/patients/{pid}/meals/history", response_model=list[schemas.MealLogSchema])
def get_meal_history(
    pid: str,
    db: Session = Depends(get_db),
    actor: str = Depends(require_patient_or_specialist),
):
    """Retrieve meal logging history for a patient."""
    patient_or_404(db, pid)
    logs = list(
        db.scalars(
            select(MealLog).where(MealLog.patient_id == pid).order_by(MealLog.logged_at.desc())
        )
    )
    services.audit(db, actor, "view_meal_history", pid)
    return [services.build_meal_log_schema(db, item) for item in logs]


@router.get("/patients/{pid}/meals/daily-summary", response_model=schemas.DailyMealSummary)
def get_daily_summary(
    pid: str,
    date: str | None = None,
    db: Session = Depends(get_db),
    actor: str = Depends(require_patient_or_specialist),
):
    """Retrieve daily nutrition totals computed strictly deterministically."""
    patient_or_404(db, pid)
    target_date = date or get_cairo_date()
    sec = services.build_meals_section(db, pid)
    day_summary = next((d for d in sec.recent_days if d.date == target_date), None)
    if not day_summary:
        day_summary = schemas.DailyMealSummary(
            date=target_date,
            meal_count=0,
            total_kcal=0.0,
            total_carbs_g=0.0,
            total_protein_g=0.0,
            total_fat_g=0.0,
            total_fiber_g=0.0,
            is_estimated=True,
            meals=[],
        )
    services.audit(db, actor, "view_meal_daily_summary", pid, target_date)
    return day_summary
