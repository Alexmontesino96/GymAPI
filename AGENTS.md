# Repository Guidelines

This guide helps contributors work efficiently in GymApi.

## Project Structure & Module Organization
- `app/`: FastAPI code — `api/` (routes), `core/` (settings, scheduler), `db/`, `models/`, `repositories/`, `schemas/`, `services/`, `middleware/`, `webhooks/`.
- Entrypoints: `main.py` (local), `app_wrapper.py` (Docker).
- Tests: `tests/` plus a few `test_*.py` at repo root.
- Migrations: `alembic/`, `alembic.ini`. Utilities: `scripts/`.
- Infra: `Dockerfile`, `docker-compose.yml`, `render.yaml`, `Procfile`.

## Build, Test, and Development Commands
- Create env: `python -m venv env && source env/bin/activate`.
- Install deps: `pip install -r requirements.txt`.
- Run API (dev): `uvicorn main:app --reload` (docs at `/api/v1/docs`).
- Docker: `docker build -t gymapi . && docker run -p 8000:8000 gymapi`.
- Compose stack: `docker-compose up` (DB/Redis, etc.).
- Migrate DB: `alembic upgrade head`; init tables: `python -m app.create_tables`.
- Run tests: `pytest -v` or `bash tests.sh`.

## Coding Style & Naming Conventions
- Python 3.11, PEP 8, 4‑space indents, type hints for public functions.
- Files: `snake_case.py`; Classes: `PascalCase`; funcs/vars: `snake_case`.
- Routers under `app/api/v1/...`; Pydantic in `app/schemas` with `*Schema` suffix.
- Keep business logic in `services/`; DB access in `repositories/`.

## Testing Guidelines
- Framework: Pytest + HTTPX; use fixtures from `tests/conftest.py`.
- Location: tests in `tests/` mirroring modules.
- Naming: files `test_*.py`, functions `test_*`.
- Aim for meaningful coverage on services, repositories, and routes.

## Commit & Pull Request Guidelines
- Commits: imperative, concise (≤72 chars), include scope. Example: `feat(api): add events list`. Reference issues with `#ID` in body.
- PRs: clear description, linked issues, steps to test, and screenshots/logs for API changes. Include migration notes when schema changes (alembic revision ID).

## Security & Configuration Tips
- Copy `.env.example` to `.env`; set Auth0, DB URL, Stream, Redis. Never commit secrets (`.env` is gitignored).
- Configure CORS via `app/core/config.py` (`BACKEND_CORS_ORIGINS`).
