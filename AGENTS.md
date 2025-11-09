# Repository Guidelines

## Project Structure & Modules
- `app/`: FastAPI application code.
  - `api/` (routes), `core/` (settings, scheduler), `db/`, `models/`, `repositories/`, `schemas/`, `services/`, `middleware/`, `webhooks/`.
- `main.py`: Local entrypoint (`main:app`).
- `app_wrapper.py`: Container entrypoint used by Docker.
- `tests/`: Pytest suites (plus a few `test_*.py` at repo root).
- `alembic/` + `alembic.ini`: Database migrations.
- `scripts/`: Maintenance and utilities.
- Infra: `Dockerfile`, `docker-compose.yml`, `render.yaml`, `Procfile`.

## Build, Run, and Test
- Create env: `python -m venv env && source env/bin/activate`.
- Install deps: `pip install -r requirements.txt`.
- Run API (dev): `uvicorn main:app --reload` (docs at `/api/v1/docs`).
- Run with Docker: `docker build -t gymapi . && docker run -p 8000:8000 gymapi`.
- Compose (DB/Redis, etc.): `docker-compose up`.
- DB migrations: `alembic upgrade head` (init tables: `python -m app.create_tables`).
- Tests: `pytest -v` or `bash tests.sh`.

## Coding Style & Naming
- Python 3.11, PEP 8, 4‑space indents, type hints for public functions.
- Files: `snake_case.py`; classes: `PascalCase`; functions/vars: `snake_case`.
- FastAPI routers under `app/api/v1/…`; pydantic models in `app/schemas` suffix `Schema`.
- Keep business logic in `services/`; DB access in `repositories/`.

## Testing Guidelines
- Framework: Pytest + HTTPX; place tests in `tests/` mirroring module paths.
- Names: files `test_*.py`, functions `test_*`.
- Use fixtures from `tests/conftest.py`; add API tests for new endpoints.
- Aim for meaningful coverage on services, repositories, and routes.

## Commit & PR Guidelines
- Commits: imperative mood, concise subject (≤72 chars), include scope, e.g., `feat(api): add events list`.
- Reference issues with `#ID` in body when applicable.
- PRs: clear description, linked issues, steps to test, and screenshots/logs for API changes.
- Include migration notes when schema changes (alembic revision ID).

## Security & Configuration
- Copy `.env.example` to `.env`; set Auth0, DB URL, Stream, Redis.
- Never commit secrets; `.env` is gitignored.
- CORS origins configurable in `app/core/config.py` (`BACKEND_CORS_ORIGINS`).
