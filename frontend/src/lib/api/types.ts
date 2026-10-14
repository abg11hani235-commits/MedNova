// Mirrors docs/API.md (contract v0). Change both together, through a pull request.

export type Severity = "info" | "review" | "urgent_review";
export type ReviewState = "none" | "reviewed";
export type Feedback = "none" | "helpful" | "not_helpful";
export type ReviewAction = "reviewed" | "helpful" | "not_helpful";

export interface Source {
  chunk_id: string;
  file_name: string;
  page: number;
  quote: string;
  date: string | null;
}

export interface Insight {
  id: string;
  severity: Severity;
  statement: string;
  source: Source | null;
  absence_note: string | null;
  review_state: ReviewState;
  feedback: Feedback;
}

export interface PatientSummary {
  id: string;
  display_name: string;
  age: number;
  diabetes_type: string;
  last_visit: string;
  next_visit: string;
  open_items: { urgent: number; review: number };
  files: { total: number; readable: number };
}

export interface TrendPoint {
  date: string;
  label: string;
  value: number;
}

export interface Trend {
  target: { min: number; max: number };
  points: TrendPoint[];
}

export interface CareGap {
  name: string;
  status: "done" | "overdue" | "missing";
  detail: string;
  source: Source | null;
}

export interface Consideration {
  id: string;
  severity: Severity;
  statement: string;
  why: string;
  source: Source | null;
}

export interface MealItem {
  id: string;
  food_id: string;
  food_name_ar: string;
  food_name_en: string;
  quantity: number;
  unit: string;
  grams: number;
  kcal: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  fiber_g: number;
  match_method: string;
  match_score: number;
  confirmed: boolean;
  source_food_row?: Record<string, unknown> | null;
}

export interface MealLog {
  id: string;
  patient_id: string;
  local_date: string;
  logged_at: string;
  meal_type: string;
  raw_text: string;
  status: string;
  clarification_question: string | null;
  clarification_options: Array<Record<string, unknown>> | null;
  safety_flag: string | null;
  items: MealItem[];
  total_kcal: number;
  total_carbs_g: number;
  total_protein_g: number;
  total_fat_g: number;
  total_fiber_g: number;
  is_estimated: boolean;
}

export interface DailyMealSummary {
  date: string;
  meal_count: number;
  total_kcal: number;
  total_carbs_g: number;
  total_protein_g: number;
  total_fat_g: number;
  total_fiber_g: number;
  is_estimated: boolean;
  meals: MealLog[];
}

export interface MealSection {
  has_logs: boolean;
  recent_days: DailyMealSummary[];
  note: string | null;
}

export interface Brief {
  patient: {
    id: string;
    display_name: string;
    age: number;
    diabetes_type: string;
    duration_years: number | null;
    medications: string[];
  };
  coverage: { total_files: number; readable_files: number; unreadable_files: number };
  snapshot: Insight[];
  trends: { hba1c: Trend; egfr: Trend };
  care_gaps: CareGap[];
  considerations: Consideration[];
  meals?: MealSection | null;
}

export interface SourcePage {
  chunk_id: string;
  file_name: string;
  page: number;
  date: string | null;
  page_text: string;
  quote: string;
  highlight: { start: number; end: number } | null;
}

export interface ChatAnswer {
  answer: string;
  answerable: boolean;
  source: Source | null;
}

export interface ReviewResult {
  id: string;
  review_state: ReviewState;
  feedback: Feedback;
}

export interface UploadResult {
  file_id: string;
  status: "queued";
}

export interface AuditEntry {
  time: string;
  actor: string;
  action: string;
  patient_id: string | null;
}

export interface PatientChatResponse {
  status: string;
  reply: string;
  meal_log: MealLog | null;
  clarification_options?: Array<Record<string, unknown>> | null;
  safety_flag?: string | null;
  is_estimated: boolean;
  disclaimer: string;
}

export interface Api {
  listPatients(): Promise<PatientSummary[]>;
  getBrief(id: string): Promise<Brief>;
  getSource(id: string, chunkId: string): Promise<SourcePage>;
  chat(id: string, question: string): Promise<ChatAnswer>;
  suggestedQuestions(id: string): Promise<string[]>;
  review(insightId: string, action: ReviewAction): Promise<ReviewResult>;
  upload(id: string, file: File): Promise<UploadResult>;
  audit(): Promise<AuditEntry[]>;
  postPatientMealChat(
    id: string,
    message: string,
    mealType?: string,
    actorHeader?: string
  ): Promise<PatientChatResponse>;
  clarifyMeal(
    id: string,
    mealLogId: string,
    selectedOption?: Record<string, unknown>,
    actorHeader?: string
  ): Promise<MealLog>;
  getMealHistory(id: string, actorHeader?: string): Promise<MealLog[]>;
  getDailyMealSummary(id: string, date?: string, actorHeader?: string): Promise<DailyMealSummary>;
}
