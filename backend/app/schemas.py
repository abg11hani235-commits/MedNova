from typing import Any, Literal

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


class MealItemSchema(BaseModel):
    id: str
    food_id: str
    food_name_ar: str
    food_name_en: str
    quantity: float
    unit: str
    grams: float
    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float
    match_method: str
    match_score: float
    confirmed: bool
    source_food_row: dict[str, Any] | None = None


class MealLogSchema(BaseModel):
    id: str
    patient_id: str
    local_date: str
    logged_at: str
    meal_type: str
    raw_text: str
    status: str
    clarification_question: str | None = None
    clarification_options: list[dict[str, Any]] | None = None
    safety_flag: str | None = None
    items: list[MealItemSchema] = []
    total_kcal: float = 0.0
    total_carbs_g: float = 0.0
    total_protein_g: float = 0.0
    total_fat_g: float = 0.0
    total_fiber_g: float = 0.0
    is_estimated: bool = True


class DailyMealSummary(BaseModel):
    date: str
    meal_count: int
    total_kcal: float
    total_carbs_g: float
    total_protein_g: float
    total_fat_g: float
    total_fiber_g: float
    is_estimated: bool = True
    meals: list[MealLogSchema] = []


class MealSection(BaseModel):
    has_logs: bool
    recent_days: list[DailyMealSummary] = []
    note: str | None = None


class Brief(BaseModel):
    patient: PatientInfo
    coverage: Coverage
    snapshot: list[Insight]
    trends: Trends
    care_gaps: list[CareGap]
    considerations: list[Consideration]
    meals: MealSection | None = None


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


class PatientChatRequest(BaseModel):
    message: str
    meal_type: str = "snack"


class PatientClarifyRequest(BaseModel):
    selected_option: dict[str, Any] | None = None
    free_text: str | None = None


class PatientChatResponse(BaseModel):
    status: str
    reply: str
    meal_log: MealLogSchema | None = None
    clarification_options: list[dict[str, Any]] | None = None
    safety_flag: str | None = None
    is_estimated: bool = True
    disclaimer: str = "أداة مساعدة، القرار النهائي للأخصائي. كل البيانات في الـDemo Synthetic."
