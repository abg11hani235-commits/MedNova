# Rafiq (رفيق) — EHR Review Assistant for Nutrition Specialists

> **"Every finding, traced to its source."**  
> *(أداة مساعدة، القرار النهائي للأخصائي. كل البيانات في الـDemo Synthetic)*

Rafiq is an assistive workspace designed for diabetes nutrition specialists reviewing patient records in Egypt. It synthesizes longitudinal patient electronic health records (lab results, specialist notes, dilated eye exams, foot screenings) into an actionable, source-grounded brief.

Rafiq supports specialist judgment only: it highlights patterns, screening gaps, and clinical considerations while preserving specialist autonomy. Every clinical claim is bound to a verified source citation, and all numerical computations and clinical screening rules are executed deterministically in code.

---

## The 7 Core Patient Brief Sections

The patient workspace aggregates EHR records into seven structured sections:

1. **Patient Header & Demographics**: Patient identifier, age, duration of diabetes, diabetes type, and active prescribed medications.
2. **File Coverage & Audit Summary**: Explicit accounting of all patient files, distinguishing readable documents from scanned or unreadable attachments.
3. **Clinical Snapshot**: High-priority findings categorized by severity (`urgent_review`, `review`, `info`), prioritized and anchored to specific documents.
4. **Deterministic Trends**: Longitudinal trajectories for Glycated Hemoglobin (HbA1c) and Estimated Glomerular Filtration Rate (eGFR) against clinical targets.
5. **Care Gaps & Screening Tracker**: ADA/KDIGO-aligned screening status (completed, overdue, or missing) for retinal exams, foot exams, urine albumin-creatinine ratio (UACR), lipid panels, and nutrition logs.
6. **Clinical & Nutrition Considerations**: Code-evaluated medication safety alerts (such as Metformin continuation amidst declining eGFR) and scanned hypoglycemia history.
7. **Source Viewer & Patient Chat**: Interactive dialogue grounded strictly in the patient's retrieved chunks, featuring character-offset quote highlighting and deterministic refusal guarantees.

---

## Architectural Principles & Safety Guards

Rafiq follows strict product safety and engineering constraints defined in [AGENTS.md](AGENTS.md):

- **Support Specialist Judgment Only**: Rafiq supports specialist judgment only. It never outputs a diagnosis, a drug dose, or a directive instruction. All advisories are framed neutrally (e.g., *"worth reviewing with the specialist"*).
- **Mandatory Source Grounding**: Every insight, care gap, and consideration must carry a complete source citation (document name, page number, quotation, and date). Uncited claims are rejected.
- **Strict Refusal Guarantee**: If a requested fact or finding is absent from the patient's records, Rafiq replies with the canonical refusal:
  > `"المعلومة دي مش موجودة في ملف المريض."`  
  *(Never guesses, extrapolates, or hallucinates).*
- **Clinical Policy Guard**: Prescribing or dosage modification queries are declined with the canonical policy notice:
  > `"صرف أدوية أو تعديل جرعات مش من اختصاص رفيق. دي مسؤولية الطبيب المعالج فقط."`
- **Deterministic Rules Engine**: Numbers, trends, ranges, and screening gaps are evaluated exclusively by deterministic Python code rules in `backend/app/nutrition_rules.py`, never by the LLM. The LLM is restricted to summarizing and answering from retrieved text.
- **Patient Isolation**: Every database query and search retrieval is strictly isolated by `patient_id`. Cross-patient retrieval is prohibited and tested.
- **De-Identification**: Personal identifiers (such as Egyptian National IDs and phone numbers) are stripped prior to submitting any text to an external LLM.

---

## Privacy, Security & Egyptian PDPL Compliance

- **Synthetic Data**: The demonstration environment operates exclusively on synthetic patient profiles (`data/synthetic/` and `data/ground_truth/`). No real patient data is ever committed or stored.
- **Audit Logging**: Comprehensive audit logging records all patient file accesses, brief views, upload events, and chat queries with actor timestamps.
- **Secret Hygiene**: API keys and credentials reside strictly in git-ignored `.env` files; `.env.example` provides safe placeholders.
- **Regulatory Roadmap**: Architecture adheres to principles of Egyptian Personal Data Protection Law (Law No. 151 of 2020), including explicit data minimization, purpose limitation, and storage segregation.

---

## System Requirements & Technology Stack

- **Backend**: Python 3.11+, FastAPI, SQLAlchemy, PostgreSQL with `pgvector`, Pydantic, Ruff, Pytest.
- **Frontend**: Next.js, TypeScript, Tailwind CSS, shadcn/ui, CSS Logical Properties (RTL native).
- **Database**: PostgreSQL 16 with `pgvector` extension.

---

## Getting Started

### 1. Database Setup

Start the PostgreSQL service with pgvector enabled:

```bash
docker compose up -d db
```

Run database migrations to initialize tables and vector indices:

```bash
cd backend
alembic upgrade head
cd ..
```

### 2. Backend API Service

Activate the Python virtual environment and run the FastAPI server:

```powershell
# Set backend import path
$env:PYTHONPATH = "backend"

# Start the server
backend\.venv\Scripts\uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

The API documentation is available at `http://localhost:8000/docs`.

### 3. Frontend Web Interface

Install dependencies and start the Next.js development server:

```bash
cd frontend
npm install
npm run dev
```

Access the user interface at `http://localhost:3000`.

---

## Testing & Verification Suites

### 1. Unit & Wiring Tests (Pytest)

Rafiq ships with a comprehensive test suite verifying the API, patient isolation, deterministic rules, negation parsing, and services:

```powershell
backend\.venv\Scripts\pytest backend/tests data/tests -q
```
*Current test suite: 123 passed tests.*

### 2. Deterministic Rules Engine Evaluation

Evaluates the deterministic rules engine against synthetic fixtures covering real patient data and edge cases (boundary conditions, missing data, negated symptoms, and bilingual phrases):

```powershell
backend\.venv\Scripts\python eval/run_rules_eval.py
```

*Author-written regression cases (`eval/rules_eval_report.md`):*
| Rule Name | Regression Cases (n) | Passed / Total | Severity Matches | Status |
| :--- | :---: | :---: | :---: | :---: |
| `hba1c_gap` | 5 | 5/5 | 2/2 | Passed |
| `hypoglycemia_scan` | 5 | 5/5 | 3/3 | Passed |
| `meal_log_gap` | 3 | 3/3 | 1/1 | Passed |
| `medication_consideration` | 7 | 7/7 | 4/4 | Passed |
| `renal_panel_gap` | 5 | 5/5 | 3/3 | Passed |
| `weight_bmi_gap` | 3 | 3/3 | 2/2 | Passed |
| **Overall Total** | **28** | **28/28** | **All Evaluated** | **All Passed** |

### 3. RAG Baseline Evaluation Harness

The retrieval and generation evaluation harness evaluates question-answering pipelines (Vector, BM25, Hybrid, Hybrid Terms, Facts Table Router, Fullchart) over synthetic questions:

```powershell
# Dry-run retrieval evaluation (0 LLM tokens consumed)
backend\.venv\Scripts\python eval/run_eval.py --pipeline hybrid_terms --dry-run

# Generate comparative evaluation report
backend\.venv\Scripts\python eval/report.py
```

---

## License & Disclaimer

*أداة مساعدة، القرار النهائي للأخصائي. كل البيانات في الـDemo Synthetic.*  
Rafiq is an assistive tool that supports specialist judgment only. Final decisions remain solely with the specialist. All demo data is synthetic.
