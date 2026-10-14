# Rafiq API contract v0

Shared by the backend and frontend. Change it only through a pull request that both sides review.


## Types

~~~
Source  = { chunk_id, file_name, page, quote, date }

Insight = { id,
            severity: "info" | "review" | "urgent_review",
            statement,
            source: Source | null,
            absence_note: string | null,
            review_state: "none" | "reviewed",
            feedback: "none" | "helpful" | "not_helpful" }

MealItem = { id, food_id, food_name_ar, food_name_en, quantity, unit,
             grams, kcal, protein_g, carbs_g, fat_g, fiber_g,
             match_method, match_score, confirmed, source_food_row? }

MealLog  = { id, patient_id, local_date, logged_at, meal_type, raw_text,
             status: "parsed" | "needs_clarification" | "unknown_food" | "rejected" | "emergency",
             clarification_question: string | null, clarification_options: object[] | null,
             safety_flag: string | null, items: MealItem[], total_kcal, total_carbs_g,
             total_protein_g, total_fat_g, total_fiber_g, is_estimated }

DailyMealSummary = { date, meal_count, total_kcal, total_carbs_g, total_protein_g,
                     total_fat_g, total_fiber_g, is_estimated, meals: MealLog[] }

MealSection = { has_logs: boolean, recent_days: DailyMealSummary[], note: string | null }
~~~

Rules that apply to every endpoint:

- An insight with no `source` must carry an `absence_note` (for example "No record in 14 files").
- Wording is "worth reviewing". Never a diagnosis, dose or instruction.
- Every patient-scoped query is filtered by `patient_id`. A chunk of patient A requested through patient B returns 404.
- `X-Actor` Header: This is a demo context tag, NOT real authentication.
  - On patient meal routes (`/patients/{id}/meals/*`), default-deny is enforced: requests without `X-Actor` are rejected with 403.
  - Patient actors (`PT <pid>`) receive 403 on specialist routes (brief, audit, other patients).
  - Specialist actors (`NS`) can view meal history and daily summaries.

## Endpoints

### GET /patients
~~~
-> [{ id, display_name, age, diabetes_type, last_visit, next_visit,
      open_items: { urgent, review },
      files: { total, readable } }]
~~~

### GET /patients/{id}/brief
~~~
-> { patient: { id, display_name, age, diabetes_type, duration_years, medications[] },
     coverage: { total_files, readable_files, unreadable_files },
     snapshot: Insight[]                       // sorted by severity, urgent first
     trends: { hba1c: { target: { min, max }, points: [{ date, label, value }] },
               egfr:  { target: { min, max }, points: [{ date, label, value }] } },
     care_gaps: [{ name, status: "done" | "overdue" | "missing", detail, source: Source | null }],
     considerations: [{ id, severity, statement, why, source: Source | null }],
     meals: MealSection | null }               // present when meal logs exist
~~~

### GET /patients/{id}/sources/{chunk_id}
~~~
-> { chunk_id, file_name, page, date, page_text, quote,
     highlight: { start, end } }               // character offsets of the quote in page_text
~~~

### GET /patients/{id}/suggested-questions
~~~
-> string[]                                    // max 3 suggested questions
~~~
Fixture mode: up to 2 answerable questions from the patient's ground-truth chat_questions plus 1 unanswerable one, so the demo shows both an answer and the refusal. Unknown patient returns 404.

### POST /patients/{id}/chat
~~~
body: { question }
-> { answer, answerable: boolean, source: Source | null }
~~~
When the answer is not in the patient's files:
`answer = "I couldn't find this in the patient's files."`, `answerable = false`, `source = null`.
The refusal text is a single shared constant (straight apostrophe), identical to `data/constants.py`.

### POST /insights/{id}/review
~~~
body: { action: "reviewed" | "helpful" | "not_helpful" }
-> { id, review_state, feedback }
~~~

### POST /patients/{id}/files
~~~
multipart/form-data
-> { file_id, status: "queued" }
~~~

### POST /patients/{id}/meals/chat
~~~
header: X-Actor: "PT <id>"
body: { message: string, meal_type?: string }
-> { status: "parsed" | "needs_clarification" | "unknown_food" | "rejected" | "emergency" | "record_lookup",
     reply: string,
     meal_log: MealLog | null,
     clarification_options?: object[] | null,
     safety_flag?: string | null,
     is_estimated: boolean,
     disclaimer: string }
~~~

### POST /patients/{id}/meals/{meal_log_id}/clarify
~~~
header: X-Actor: "PT <id>"
body: { selected_option?: object, free_text?: string }
-> MealLog
~~~

### GET /patients/{id}/meals/history
~~~
header: X-Actor: "PT <id>" or "NS"
-> MealLog[]
~~~

### GET /patients/{id}/meals/daily-summary
~~~
header: X-Actor: "PT <id>" or "NS"
query: ?date=YYYY-MM-DD (optional, defaults to Cairo today)
-> DailyMealSummary
~~~

### GET /audit
~~~
-> [{ time, actor, action, patient_id }]
~~~

### GET /health
~~~
-> { status: "ok" }
~~~