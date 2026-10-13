# Rafiq Backend

FastAPI decision-support service for Rafiq.

## Local Setup
```bash
python -m venv .venv
source .venv/bin/activate  # Or on Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Running the API
```bash
uvicorn app.main:app --reload --port 8000
```

## Running Tests & Linters
```bash
pytest tests
ruff check .
ruff format --check .
```
