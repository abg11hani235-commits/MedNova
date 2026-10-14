import json
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from .config import get_settings


class Base(DeclarativeBase):
    pass


class EmbeddingType(TypeDecorator):
    """pgvector on Postgres, JSON text elsewhere (tests). Unused in fixture mode."""

    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from pgvector.sqlalchemy import Vector

            return dialect.type_descriptor(Vector(get_settings().embedding_dim))
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        if value is None or dialect.name == "postgresql":
            return value
        return json.dumps(value)

    def process_result_value(self, value, dialect):
        if value is None or dialect.name == "postgresql":
            return value
        return json.loads(value)


CAIRO_TZ = ZoneInfo("Africa/Cairo")


def _now() -> datetime:
    return datetime.now(UTC)


def get_cairo_date(dt: datetime | None = None) -> str:
    """Return YYYY-MM-DD date string computed in Africa/Cairo timezone."""
    if dt is None:
        dt = datetime.now(UTC)
    elif dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(CAIRO_TZ).strftime("%Y-%m-%d")


def get_cairo_datetime(dt: datetime | None = None) -> datetime:
    """Return datetime localized to Africa/Cairo timezone."""
    if dt is None:
        dt = datetime.now(UTC)
    elif dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(CAIRO_TZ)


class Patient(Base):
    __tablename__ = "patients"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(128))
    age: Mapped[int] = mapped_column(Integer)
    diabetes_type: Mapped[str] = mapped_column(String(32))
    duration_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    medications: Mapped[list] = mapped_column(JSON, default=list)
    as_of_date: Mapped[str] = mapped_column(String(10))
    trends: Mapped[dict] = mapped_column(JSON, default=dict)
    care_gaps: Mapped[list] = mapped_column(JSON, default=list)
    chat_questions: Mapped[list] = mapped_column(JSON, default=list)


class File(Base):
    __tablename__ = "files"
    id: Mapped[str] = mapped_column(String(200), primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    kind: Mapped[str] = mapped_column(String(32))
    date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    is_scan: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(32), default="ready")
    storage_path: Mapped[str | None] = mapped_column(String(500), nullable=True)


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (
        Index(
            "ix_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
    id: Mapped[str] = mapped_column(String(240), primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    file_id: Mapped[str] = mapped_column(ForeignKey("files.id"), index=True)
    page: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list | None] = mapped_column(EmbeddingType(), nullable=True)


class Insight(Base):
    __tablename__ = "insights"
    id: Mapped[str] = mapped_column(String(200), primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    type: Mapped[str] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(String(16))
    statement: Mapped[str] = mapped_column(Text)
    why: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_chunk_id: Mapped[str | None] = mapped_column(ForeignKey("chunks.id"), nullable=True)
    quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    absence_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_state: Mapped[str] = mapped_column(String(16), default="none")
    feedback: Mapped[str] = mapped_column(String(16), default="none")
    rank: Mapped[int] = mapped_column(Integer, default=0)


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    answerable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    source_chunk_id: Mapped[str | None] = mapped_column(String(240), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    actor: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64))
    patient_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)


class MealLog(Base):
    __tablename__ = "meal_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    local_date: Mapped[str] = mapped_column(String(10), index=True)  # YYYY-MM-DD in Africa/Cairo
    logged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    meal_type: Mapped[str] = mapped_column(String(32), default="unspecified")
    raw_text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(32)
    )  # parsed, needs_clarification, unknown_food, rejected, emergency
    clarification_question: Mapped[str | None] = mapped_column(Text, nullable=True)
    clarification_options: Mapped[list | None] = mapped_column(JSON, nullable=True)
    safety_flag: Mapped[str | None] = mapped_column(String(64), nullable=True)

    items: Mapped[list["MealItem"]] = relationship(
        "MealItem", back_populates="meal_log", cascade="all, delete-orphan"
    )


class MealItem(Base):
    __tablename__ = "meal_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    meal_log_id: Mapped[str] = mapped_column(
        ForeignKey("meal_logs.id", ondelete="CASCADE"), index=True
    )
    food_id: Mapped[str] = mapped_column(String(64), index=True)
    food_name_ar: Mapped[str] = mapped_column(String(128))
    food_name_en: Mapped[str] = mapped_column(String(128))
    quantity: Mapped[float] = mapped_column(Float, default=1.0)
    unit: Mapped[str] = mapped_column(String(64))
    grams: Mapped[float] = mapped_column(Float)
    kcal: Mapped[float] = mapped_column(Float)
    protein_g: Mapped[float] = mapped_column(Float)
    carbs_g: Mapped[float] = mapped_column(Float)
    fat_g: Mapped[float] = mapped_column(Float)
    fiber_g: Mapped[float] = mapped_column(Float)
    match_method: Mapped[str] = mapped_column(
        String(32)
    )  # exact_alias, fuzzy, llm_extracted, deterministic_fallback
    match_score: Mapped[float] = mapped_column(Float, default=1.0)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=True)

    meal_log: Mapped["MealLog"] = relationship("MealLog", back_populates="items")


class PatientChatMessage(Base):
    __tablename__ = "patient_chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    role: Mapped[str] = mapped_column(String(16))  # patient, assistant, system
    content: Mapped[str] = mapped_column(Text)
    meal_log_id: Mapped[str | None] = mapped_column(
        ForeignKey("meal_logs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
