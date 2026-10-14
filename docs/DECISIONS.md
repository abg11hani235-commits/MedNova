# Clinsight Architectural Decision Records (ADR)

This log documents key architectural, engineering, and design decisions for Clinsight.

## Format
- **Date**: YYYY-MM-DD
- **Status**: Proposed / Accepted / Superseded
- **Context**: Problem statement and alternatives considered
- **Decision**: Chosen solution and rationale
- **Consequences**: Trade-offs and impact

---

## Decisions Log

### ADR-001: Initial Monorepo & Technology Stack Setup
- **Date**: 2026-10-09
- **Status**: Accepted
- **Context**: Repository foundation needed for FastAPI backend, Next.js frontend, and design reference.
- **Decision**: Adopt a monorepo structure with `/backend` (Python 3.11+, FastAPI, pgvector, ruff, pytest) and `/frontend` (Next.js App Router, TypeScript, Tailwind CSS, shadcn/ui, Vitest).
- **Consequences**: Centralized tooling, shared type potential, clean CI/CD validation.

### ADR-002: Rebrand to Rafiq for Egyptian Nutrition Specialists
- **Date**: 2026-10-13
- **Status**: Accepted
- **Context**: Pivot the product layer from generic physician decision support to "Rafiq", tailored specifically for diabetes nutrition specialists in Egypt. The core architecture supports specialist judgment only: deterministic rules compute numbers/trends/gaps while the LLM extracts text with mandatory citations.
- **Decision**:
  1. Rebrand application name to "Rafiq" across UI titles, routes/navigation, packages, and documentation.
  2. Adopt canonical Arabic disclaimer (`أداة مساعدة، القرار النهائي للأخصائي. كل البيانات في الـDemo Synthetic.`) and refusal text (`المعلومة دي مش موجودة في ملف المريض.`) with `dir="auto"`.
  3. **Preserve Database & Infrastructure Names**: Maintain Postgres database name (`clinsight`), container name (`clinsight-db`), and docker volume (`clinsight_pgdata`) intentionally to prevent orphaning or corrupting existing development data.
  4. **Evaluation Baseline Integrity**: Eval baselines stored in `eval/results/` predate the updated `SYSTEM_PROMPT` wording and must not be compared like-for-like without a fresh evaluation run.
  5. **Audit Actor Continuity**: Existing historical `audit_log` rows retain the legacy actor `"DR (Doctor)"`; only new entries default to `"NS (Nutrition Specialist)"`.
- **Consequences**: Seamless transition with zero data loss or migration breaks, preserving all 23 deterministic safety guard tests and patient isolation guarantees.

### ADR-003: Patient Chat Architecture, Evaluation Prompt Lineage, and Demo Role Security
- **Date**: 2026-10-14
- **Status**: Accepted
- **Context**: Introducing the Patient Meal-Logging Chat feature and closing governance gaps identified during rebrand verification.
- **Decision**:
  1. **Evaluation Prompt Lineage**: The user prompt in `eval/run_eval.py` was updated from `"Answer the question following all clinical decision support rules."` to `"Answer the question following all practice guidance rules."`. Because this instruction is directly passed to the LLM as part of the user prompt, evaluation results generated prior to this change in `eval/results/` are historical baselines and not like-for-like with future live runs.
  2. **Citation Verification on Absence Items**: Absences (e.g., missing annual UACR, missing foot exam) are represented with `source=None` and populated `absence_note`. The deterministic citation verifier (`app/rag/verify.py`) and schema enforce that absences are categorized as missing/unrecorded items, never as grounded factual claims from file chunks.
  3. **Docker Environment Status**: Docker is installed on the deployment environment, but the background daemon was inactive during initial pre-flight checks. Fresh evaluation runs will be executed once the engine daemon is running.
  4. **Demo Authentication & Role Enforcement**: In the absence of an enterprise identity provider, role context is communicated via `X-Actor`. Patient routes enforce default-deny: requests without an `X-Actor` header are rejected (403), patient actors (`PT <pid>`) cannot access specialist endpoints or other patients' charts, and specialists (`NS`) retain read access. This is an application-level demo tag and explicitly does NOT provide cryptographic authentication or network-level protection against spoofing.
- **Consequences**: Clean architectural boundary between specialist EHR workflows and patient meal-logging chat, preserving safety and isolation guarantees without inventing security claims.

