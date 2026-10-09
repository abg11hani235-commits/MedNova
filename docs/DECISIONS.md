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
