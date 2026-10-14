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

