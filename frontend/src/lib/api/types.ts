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

export interface Api {
  listPatients(): Promise<PatientSummary[]>;
  getBrief(id: string): Promise<Brief>;
  getSource(id: string, chunkId: string): Promise<SourcePage>;
  chat(id: string, question: string): Promise<ChatAnswer>;
  review(insightId: string, action: ReviewAction): Promise<ReviewResult>;
  upload(id: string, file: File): Promise<UploadResult>;
  audit(): Promise<AuditEntry[]>;
}
