# Backend (fixture mode)

Install (from the repo root, PowerShell):

    .\backend\.venv\Scripts\pip install sqlalchemy alembic "psycopg[binary]" pydantic-settings python-multipart pgvector

Add the same packages to `dependencies` in backend/pyproject.toml.

Run:

    cp .env.example .env            # then check DATABASE_URL uses port 5433
    docker compose up -d
    cd backend
    ..\backend\.venv\Scripts\alembic upgrade head
    ..\backend\.venv\Scripts\python -m scripts.seed_from_ground_truth
    ..\backend\.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000

Open http://localhost:8000/docs

Tests (SQLite in memory, no Docker needed):  .\backend\.venv\Scripts\pytest backend/tests
