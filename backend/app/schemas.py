from typing import Literal

from pydantic import BaseModel

Severity = Literal["info", "review", "urgent_review"]


class Source(BaseModel):
    chunk_id: str
    file_name: str
    page: int
    quote: str
    date: str | None = None


class Insight(BaseModel):
    id: str
    severity: Severity
    statement: str
    source: Source | None = None
    absence_note: str | None = None
    review_state: Literal["none", "reviewed"] = "none"
    feedback: Literal["none", "helpful", "not_helpful"] = "none"


class OpenItems(BaseModel):
    urgent: int
    review: int


class FileCounts(BaseModel):
    total: int
    readable: int


class PatientSummary(BaseModel):
    id: str
    display_name: str
    age: int
    diabetes_type: str
    last_visit: str
    next_visit: str
    open_items: OpenItems
    files: FileCounts


class PatientInfo(BaseModel):
    id: str
    display_name: str
    age: int
    diabetes_type: str
    duration_years: int | None = None
    medications: list[str]


class Coverage(BaseModel):
    total_files: int
    readable_files: int
    unreadable_files: int


class TrendPoint(BaseModel):
    date: str
    label: str
    value: float


class Target(BaseModel):
    min: float
    max: float


class Trend(BaseModel):
    target: Target
    points: list[TrendPoint]


class Trends(BaseModel):
    hba1c: Trend
    egfr: Trend


class CareGap(BaseModel):
    name: str
    status: Literal["done", "overdue", "missing"]
    detail: str
    source: Source | None = None


class Consideration(BaseModel):
    id: str
    severity: Severity
    statement: str
    why: str
    source: Source | None = None


class Brief(BaseModel):
    patient: PatientInfo
    coverage: Coverage
    snapshot: list[Insight]
    trends: Trends
    care_gaps: list[CareGap]
    considerations: list[Consideration]


class Highlight(BaseModel):
    start: int
    end: int


class SourcePage(BaseModel):
    chunk_id: str
    file_name: str
    page: int
    date: str | None = None
    page_text: str
    quote: str
    highlight: Highlight | None = None


class ChatRequest(BaseModel):
    question: str


class ChatAnswer(BaseModel):
    answer: str
    answerable: bool
    source: Source | None = None


class ReviewRequest(BaseModel):
    action: Literal["reviewed", "helpful", "not_helpful"]


class ReviewResult(BaseModel):
    id: str
    review_state: Literal["none", "reviewed"]
    feedback: Literal["none", "helpful", "not_helpful"]


class UploadResult(BaseModel):
    file_id: str
    status: Literal["queued"]


class AuditEntry(BaseModel):
    time: str
    actor: str
    action: str
    patient_id: str | None = None
