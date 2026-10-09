# Contributing to Clinsight

Thank you for contributing to Clinsight. This project is a clinical decision-support tool for diabetes doctors and adheres to strict safety, privacy, and engineering guidelines.

---

## 1. Branching & Commit Conventions

- **Branch naming**:
  - `backend/*` (e.g., `backend/health-endpoint`, `backend/pdf-parser`)
  - `frontend/*` (e.g., `frontend/patient-brief`, `frontend/token-wiring`)
  - `eval/*` (e.g., `eval/benchmark-suite`, `eval/synthetic-charts`)
  - `docs/*` (e.g., `docs/architecture-adr`, `docs/product-spec`)
- **One contributor per branch**: Exactly one agent or engineer per branch at a time.
- **Never push directly to `main`**: All changes merge via pull requests.
- **Small commits, small tasks**: Keep commits focused and provide clear, imperative commit messages (e.g., `feat(backend): add health endpoint`, `test(frontend): assert brief renders`).

---

## 2. Development Interface & Tooling

On Windows and cross-platform environments, the root `package.json` scripts are the **primary interface**:
- `npm run dev:db` - Launch local PostgreSQL with pgvector container
- `npm run backend` - Start FastAPI backend server locally
- `npm run frontend` - Start Next.js frontend dev server locally
- `npm run test` - Execute both backend and frontend test suites
- `npm run lint` - Execute both backend and frontend linters and format checkers

The `Makefile` (`make dev-db`, `make backend`, `make frontend`, `make test`, `make lint`) is provided as an **optional** convenience for POSIX/Linux/macOS shells.

---

## 3. Pull Request Requirements

Before opening or requesting review on a pull request:
1. Ensure all tests pass (`npm run test` or `pytest` + `vitest`).
2. Ensure linters pass (`npm run lint` or `ruff` + `eslint`).
3. Check that no secrets, API keys, or real patient data are committed.
4. Verify all insights comply with product safety wording rules ("worth reviewing", source citation mandatory).
5. Verify UI strictly matches `/design` tokens and specifications.
