# Repository Guidelines

This guide covers how to navigate, run, test, and contribute to GymApi.

## Project Structure & Module Organization
- `app/`: FastAPI code — `api/` (routes), `core/` (settings, scheduler), `db/`, `models/`, `repositories/`, `schemas/`, `services/`, `middleware/`, `webhooks/`.
- Entrypoints: `main.py` (local dev), `app_wrapper.py` (Docker).
- Tests: `tests/` plus a few `test_*.py` at repo root.
- Migrations: `alembic/`, `alembic.ini`; Utilities: `scripts/`.
- Infra: `Dockerfile`, `docker-compose.yml`, `render.yaml`, `Procfile`.

## Build, Test, and Development Commands
- Create env: `python -m venv env && source env/bin/activate` — setup virtualenv.
- Install deps: `pip install -r requirements.txt` — install Python packages.
- Run API (dev): `uvicorn main:app --reload` — serve at `http://localhost:8000` (docs at `/api/v1/docs`).
- DB migrate: `alembic upgrade head` — apply latest migrations.
- Init tables: `python -m app.create_tables` — bootstrap required tables.
- Tests: `pytest -v` or `bash tests.sh` — run test suite.
- Docker: `docker build -t gymapi . && docker run -p 8000:8000 gymapi`; stack: `docker-compose up`.

## Coding Style & Naming Conventions
- Python 3.11, PEP 8, 4-space indents; use type hints for public functions.
- Files: `snake_case.py`; Classes: `PascalCase`; funcs/vars: `snake_case`.
- Routers under `app/api/v1/...`; Pydantic models in `app/schemas` with `*Schema` suffix.
- Keep business logic in `services/`; DB access in `repositories/`.

## Testing Guidelines
- Frameworks: Pytest + HTTPX; shared fixtures in `tests/conftest.py`.
- Location mirrors modules; file names `test_*.py`, test functions `test_*`.
- Run: `pytest -v`; aim for meaningful coverage across services, repositories, and routes.

## Commit & Pull Request Guidelines
- Commits: imperative, concise (≤72 chars) with scope. Example: `feat(api): add events list`. Reference issues with `#ID` in the body.
- PRs: clear description, linked issues, steps to test, and screenshots/logs for API changes. Include migration notes (alembic revision ID) when schema changes.

## Security & Configuration Tips
- Copy `.env.example` to `.env`; set Auth0, DB URL, Stream, and Redis. `.env` is gitignored.
- Configure CORS via `app/core/config.py` (`BACKEND_CORS_ORIGINS`).

