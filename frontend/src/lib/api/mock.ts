import { REFUSAL_TEXT } from "../constants";
import type {
  Api,
  AuditEntry,
  Brief,
  ChatAnswer,
  Feedback,
  PatientSummary,
  ReviewState,
  Source,
  SourcePage,
} from "./types";

const wait = (ms = 60) => new Promise((r) => setTimeout(r, ms));

const NEPHRO_QUOTE =
  "Estimated GFR today is 59 mL/min/1.73m², down from 78 at the first visit in March 2025.";
const SWEAT_QUOTE =
  "Patient reports occasional episodes of night-time sweating and lightheadedness consistent with mild nocturnal low glucose symptoms.";
const EYE_QUOTE =
  "Dilated retinal examination completed on 14 Oct 2023. Next annual retinal screen due in 12 months.";

const src = (stem: string, page: number, quote: string, date: string): Source => ({
  chunk_id: `1042-${stem}-p${page}`,
  file_name: `${stem}.pdf`,
  page,
  quote,
  date,
});

const S = {
  nephro: src("Nephrology_Note_2026-06-18", 1, NEPHRO_QUOTE, "2026-06-18"),
  lab: src("Lab_Report_2026-06-18", 2, "HbA1c: 8.9%", "2026-06-18"),
  sweat: src("Visit_Note_2026-02-15", 3, SWEAT_QUOTE, "2026-02-15"),
  eye: src("Eye_Report_2023-10-14", 1, EYE_QUOTE, "2023-10-14"),
  visitNov: src("Visit_Note_2025-11-12", 2, "", "2025-11-12"),
};

const PAGE_TEXT: Record<string, string> = {
  [S.nephro.chunk_id]: `Nephrology clinic note, 18 Jun 2026\n\nReason for visit: routine diabetes follow-up. Blood pressure 134/82. Weight stable. ${NEPHRO_QUOTE} Patient continues Metformin and Gliclazide as before. Reports occasional night-time sweating. Foot examination completed. Glucose diary to be brought to the next visit.`,
  [S.lab.chunk_id]: `Laboratory report, 18 Jun 2026 (page 2)\n\nHbA1c: 8.9%\neGFR: 59 mL/min/1.73m²\nFasting glucose: 168 mg/dL`,
  [S.sweat.chunk_id]: `Visit note, 15 Feb 2026 (page 3)\n\n${SWEAT_QUOTE} Diary requested.`,
  [S.eye.chunk_id]: `Eye report, 14 Oct 2023\n\n${EYE_QUOTE}`,
  [S.visitNov.chunk_id]: `Visit note, 12 Nov 2025 (page 2)\n\nGliclazide added to the current regimen. No other medication changes today.`,
};

const dates = ["2025-03-12", "2025-06-18", "2025-09-15", "2025-12-10", "2026-03-18", "2026-06-18"];
const labels = ["Mar 25", "Jun 25", "Sep 25", "Dec 25", "Mar 26", "Jun 26"];
const series = (vals: number[]) => vals.map((value, i) => ({ date: dates[i], label: labels[i], value }));

const BRIEF_1042: Brief = {
  patient: {
    id: "1042",
    display_name: "Synthetic Patient #1042",
    age: 58,
    diabetes_type: "Type 2",
    duration_years: 12,
    medications: ["Metformin", "Gliclazide", "Atorvastatin"],
  },
  coverage: { total_files: 17, readable_files: 14, unreadable_files: 3 },
  snapshot: [
    { id: "1042-F1", severity: "urgent_review", statement: "eGFR fell from 78 to 59 over 6 visits while Metformin continues. Worth reviewing.", source: S.nephro, absence_note: null, review_state: "none", feedback: "none" },
    { id: "1042-F2", severity: "review", statement: "HbA1c has risen across 6 visits (7.4 to 8.9). Worth reviewing.", source: S.lab, absence_note: null, review_state: "none", feedback: "none" },
    { id: "1042-F3", severity: "review", statement: "No urine albumin-creatinine ratio found in the last 12 months.", source: null, absence_note: "No record in 14 readable files", review_state: "none", feedback: "none" },
    { id: "1042-F4", severity: "review", statement: "Night-time low glucose symptoms mentioned in a visit note. Worth reviewing.", source: S.sweat, absence_note: null, review_state: "none", feedback: "none" },
    { id: "1042-F5", severity: "review", statement: "Retinal exam overdue. Last recorded 2023. Worth reviewing.", source: S.eye, absence_note: null, review_state: "none", feedback: "none" },
  ],
  trends: {
    hba1c: { target: { min: 6, max: 7 }, points: series([7.4, 7.8, 8.1, 8.4, 8.7, 8.9]) },
    egfr: { target: { min: 60, max: 120 }, points: series([78, 74, 68, 64, 61, 59]) },
  },
  care_gaps: [
    { name: "Retinal exam", status: "overdue", detail: "Last recorded 2023", source: S.eye },
    { name: "Foot exam", status: "done", detail: "Completed this year", source: null },
    { name: "Urine albumin-creatinine ratio", status: "missing", detail: "None in the last 12 months", source: null },
    { name: "Lipid panel", status: "done", detail: "Completed this year", source: null },
  ],
  considerations: [
    { id: "1042-F1", severity: "urgent_review", statement: "Kidney function trend alongside current medication is worth reviewing.", why: "eGFR fell from 78 to 59, and Metformin is listed as ongoing.", source: S.nephro },
    { id: "1042-F2", severity: "review", statement: "HbA1c rising across 3 consecutive visits. Worth reviewing the current treatment plan.", why: "Last three results were 8.4, 8.7 and 8.9.", source: S.lab },
  ],
};

const PATIENTS: PatientSummary[] = [
  ["1042", 58, "Type 2", "2026-06-18", { urgent: 1, review: 4 }, 17, 14],
  ["1043", 46, "Type 1", "2026-06-02", { urgent: 0, review: 5 }, 16, 14],
  ["1044", 67, "Type 2", "2026-05-11", { urgent: 1, review: 4 }, 16, 14],
  ["1045", 39, "Type 2", "2026-05-29", { urgent: 0, review: 5 }, 16, 14],
  ["1046", 72, "Type 2", "2026-04-20", { urgent: 1, review: 4 }, 17, 15],
].map(([id, age, diabetes_type, last, open_items, total, readable]) => ({
  id: id as string,
  display_name: `Synthetic Patient #${id}`,
  age: age as number,
  diabetes_type: diabetes_type as string,
  last_visit: last as string,
  next_visit: "2026-07-09",
  open_items: open_items as PatientSummary["open_items"],
  files: { total: total as number, readable: readable as number },
}));

const QA: { q: string; a: string; source: Source | null }[] = [
  { q: "when was the medication last changed", a: "Gliclazide was added on 12 Nov 2025. No later changes are documented.", source: S.visitNov },
  { q: "what was the last hba1c", a: "8.9% on 18 Jun 2026.", source: S.lab },
];
const norm = (s: string) => s.toLowerCase().replace(/[^\w\s]/g, "").replace(/\s+/g, " ").trim();

const reviewState = new Map<string, { review_state: ReviewState; feedback: Feedback }>();
const audit: AuditEntry[] = [
  { time: "2026-06-18T09:12:00Z", actor: "DR (Doctor)", action: "view_brief", patient_id: "1042" },
  { time: "2026-06-18T09:14:00Z", actor: "DR (Doctor)", action: "view_source", patient_id: "1042" },
  { time: "2026-06-18T09:31:00Z", actor: "Clinic admin", action: "upload", patient_id: "1046" },
];
const log = (action: string, patient_id: string | null) =>
  audit.unshift({ time: new Date().toISOString(), actor: "DR (Doctor)", action, patient_id });

export const mockApi: Api = {
  async listPatients() {
    await wait();
    return PATIENTS;
  },
  async getBrief(id) {
    await wait();
    const p = PATIENTS.find((x) => x.id === id);
    if (!p) throw new Error("Patient not found");
    log("view_brief", id);
    return {
      ...BRIEF_1042,
      patient: { ...BRIEF_1042.patient, id, display_name: p.display_name, age: p.age, diabetes_type: p.diabetes_type },
      snapshot: BRIEF_1042.snapshot.map((i) => ({ ...i, ...(reviewState.get(i.id) ?? {}) })),
    };
  },
  async getSource(id, chunkId): Promise<SourcePage> {
    await wait();
    const text = PAGE_TEXT[chunkId];
    if (!text) throw new Error("Source not found");
    const all = [...BRIEF_1042.snapshot.map((i) => i.source), ...Object.values(S)].filter(Boolean) as Source[];
    const s = all.find((x) => x.chunk_id === chunkId)!;
    const start = s.quote ? text.indexOf(s.quote) : -1;
    log("view_source", id);
    return {
      chunk_id: chunkId,
      file_name: s.file_name,
      page: s.page,
      date: s.date,
      page_text: text,
      quote: s.quote,
      highlight: start >= 0 ? { start, end: start + s.quote.length } : null,
    };
  },
  async chat(id, question): Promise<ChatAnswer> {
    await wait();
    log("chat_question", id);
    const hit = QA.find((x) => norm(question) === x.q);
    return hit
      ? { answer: hit.a, answerable: true, source: hit.source }
      : { answer: REFUSAL_TEXT, answerable: false, source: null };
  },
  async review(insightId, action) {
    await wait();
    const cur = reviewState.get(insightId) ?? { review_state: "none" as ReviewState, feedback: "none" as Feedback };
    const next = action === "reviewed" ? { ...cur, review_state: "reviewed" as ReviewState } : { ...cur, feedback: action as Feedback };
    reviewState.set(insightId, next);
    log(`review_${action}`, insightId.split("-")[0]);
    return { id: insightId, ...next };
  },
  async upload(id) {
    await wait(200);
    log("upload", id);
    return { file_id: `mock-${Date.now()}`, status: "queued" };
  },
  async audit() {
    await wait();
    return [...audit];
  },
};
