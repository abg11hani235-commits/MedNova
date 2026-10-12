# Clinsight API contract v0

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
~~~

Rules that apply to every endpoint:

- An insight with no `source` must carry an `absence_note` (for example "No record in 14 files").
- Wording is "worth reviewing". Never a diagnosis, dose or instruction.
- Every patient-scoped query is filtered by `patient_id`. A chunk of patient A requested through patient B returns 404.

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
     considerations: [{ id, severity, statement, why, source: Source | null }] }
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

### GET /audit
~~~
-> [{ time, actor, action, patient_id }]
~~~

### GET /health
~~~
-> { status: "ok" }
~~~