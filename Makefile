.PHONY: dev-db backend frontend test test-backend test-frontend lint lint-backend lint-frontend

dev-db:
	docker compose up -d

backend:
	cd backend && uvicorn app.main:app --reload --port 8000

frontend:
	npm --prefix frontend run dev

test: test-backend test-frontend

test-backend:
	pytest backend/tests

test-frontend:
	npm --prefix frontend run test

lint: lint-backend lint-frontend

lint-backend:
	ruff check backend && ruff format --check backend

lint-frontend:
	npm --prefix frontend run lint
