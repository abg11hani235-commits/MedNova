# ClinSight RAG Baseline Evaluation Harness

Evaluation dataset, retrieval pipelines, verification metrics, and reporting harness for clinical retrieval-based chat on synthetic diabetes EHR records.

Follows all rules in [AGENTS.md](../AGENTS.md):
- **Decision support only**: Responses phrase findings as "worth reviewing".
- **Strict citation grounding**: Every clinical claim carries document name, page, and quoted snippet.
- **Strict refusal**: If the finding is absent from patient files, replies exactly: `"I couldn't find this in the patient's files."`
- **Patient isolation**: Every query is filtered by `patient_id`.
- **De-identification**: Egyptian National IDs and phone numbers are stripped prior to LLM submission.
- **Deterministic facts**: Trends and numerical comparisons computed by deterministic code rules.
- **Secret security**: API keys live in `.env` only (git-ignored) and are NEVER logged or included in cache keys.

---

## 1. Environment & Setup

Ensure the virtual environment is ready and dependencies are installed. All commands should be executed from the **repository root** (`ClinSight`):

```powershell
# Set backend import path for Python commands run from repository root
$env:PYTHONPATH = "backend"

# Ensure PostgreSQL container with pgvector is running (port 5433)
docker compose up -d db

# Run Alembic migrations (with embedding dimension 1024 and Postgres HNSW index)
cd backend
.\.venv\Scripts\alembic upgrade head
cd ..
```

---

## 2. Generate and Validate Questions Dataset

Builds `eval/questions.jsonl` deterministically (seed 42) from ground-truth clinical data:

```powershell
# Generate 220 evaluation questions across 10 patients
.\backend\.venv\Scripts\python eval/build_questions.py

# Validate all gold chunks exist and expected values appear in raw text
.\backend\.venv\Scripts\python eval/validate_questions.py
```

### Dataset Structure
- **Total questions**: 220 (22 questions per patient across 10 synthetic patients).
- **Categories**:
  - `last_value`: Most recent lab/vital (e.g. HbA1c, eGFR).
  - `value_at_date`: Lab value on a specific historical date.
  - `first_vs_last`: Comparison of earliest to latest readings.
  - `trend`: Directional change over time (rising, falling, stable).
  - `medication`: Documented medications in the record.
  - `exam_date`: Date of dilated eye or foot examinations.
  - `symptom`: Documented hypoglycemia or low blood sugar episodes.
  - `absence`: Specific missing tests (e.g. UACR) with audit summary.
  - `unanswerable`: Clinical questions outside the patient's record.
  - `policy`: Prescribing instructions / medication dosage queries.
  - `injection`: Adversarial prompt-injection attempts.
  - `cross_patient`: Queries attempting to access another patient's data.
  - `arabic`: Questions written in Arabic (medical terms in English) about facts living in English documents, sharing identical gold chunks and expected values with English twins.
  - `synonym`: Medical abbreviation and dialect variations.

---

## 3. Populate Chunk Embeddings

Embed patient chunks into PostgreSQL (`chunks.embedding` using `BAAI/bge-m3` 1024-dimensional vectors):

```powershell
# Downloads BAAI/bge-m3 (~2.2GB) if not already cached and embeds all readable chunks
.\backend\.venv\Scripts\python backend/scripts/embed_chunks.py
```

---

## 4. Evaluation Runs

### A. Dry-Run (Retrieval Only - 0 LLM Tokens Spent)
Runs retrieval without making LLM calls, evaluating Hit@1, Hit@3, MRR, latency, and token cost estimation:

```powershell
# Dense vector retrieval
.\backend\.venv\Scripts\python eval/run_eval.py --pipeline vector --dry-run

# BM25 lexical retrieval
.\backend\.venv\Scripts\python eval/run_eval.py --pipeline bm25 --dry-run

# Hybrid (Dense + BM25 with Reciprocal Rank Fusion k=60)
.\backend\.venv\Scripts\python eval/run_eval.py --pipeline hybrid --dry-run

# Hybrid + Clinical Term Expansion
.\backend\.venv\Scripts\python eval/run_eval.py --pipeline hybrid_terms --dry-run

# Deterministic Facts Table Router
.\backend\.venv\Scripts\python eval/run_eval.py --pipeline facts --dry-run

# Fullchart (Token budget: 20,000 tokens ~ 80,000 characters)
.\backend\.venv\Scripts\python eval/run_eval.py --pipeline fullchart --dry-run
```

### B. Smoke Run (20 Questions with Live LLM)
Runs a controlled sample of 20 questions with one pipeline to measure live token usage and extrapolate full-run cost:

```powershell
.\backend\.venv\Scripts\python eval/run_eval.py --pipeline hybrid_terms --limit 20
```

---

## 5. Generate Evaluation Report

Combines all pipeline run artifacts in `eval/results/` into a concise comparison report:

```powershell
.\backend\.venv\Scripts\python eval/report.py
```

---

## 6. Secret Redaction & Security

- `GROQ_API_KEY` must only reside in `.env`.
- LLM cache keys (`eval/cache/llm/`) are hashed with SHA-256 and never contain raw API credentials.
- All log outputs and exception traces redact secrets as `[REDACTED]`.
