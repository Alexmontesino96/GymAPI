# Repository Guidelines

## Project Structure & Module Organization
- `app/api/v1/`: FastAPI routers (versioned endpoints)
- `app/models/`: SQLAlchemy models; `app/schemas/`: Pydantic DTOs
- `app/repositories/`: DB access; `app/services/`: business logic
- `app/core/`: config, logging, scheduler; `app/middleware/`: cross‑cutting concerns
- `app/db/`: DB helpers; `app/webhooks/` and `app/utils/`: integrations/utilities
- Root: `main.py` (dev entry), `tests/` (pytest suite), `migrations/` + `alembic.ini`, `Dockerfile`, `docker-compose.yml`, `scripts/`

## Build, Run, and Dev Commands
- Install deps (Python 3.11):
  - `python -m venv env && source env/bin/activate`
  - `pip install -r requirements.txt`
- Initialize DB:
  - `python -m app.create_tables` (quick start) or `alembic upgrade head`
- Run locally (auto-reload):
  - `uvicorn main:app --reload` (serves at `http://localhost:8000/api/v1/docs`)
- Docker (app + Postgres + Redis):
  - `docker compose up --build`

## Coding Style & Naming Conventions
- Follow PEP 8; 4‑space indentation; keep functions small and typed.
- Naming: modules/files `snake_case`, classes `PascalCase`, functions/vars `snake_case`.
- API: one router per domain under `app/api/v1/<domain>.py`; request/response models in `app/schemas/*`.
- Place DB queries in `repositories/` and orchestrate logic in `services/`.
- Prefer dependency injection via function params; avoid global state.

## Testing Guidelines
- Framework: pytest. Structure mirrors app modules under `tests/`.
- Run all tests: `pytest -v tests/` or `./tests.sh`
- Example single test: `pytest tests/schedule/test_fixed_session.py -q`
- Functional smoke with real token: `python tests/functional_test.py --token "<JWT>"`
- Add tests for new endpoints/services; cover success + error paths.

## Commit & Pull Request Guidelines
- Conventional commits (Spanish), e.g.: `feat: …`, `fix: …`, `refactor: …` as seen in history.
- PRs must include: clear description, linked issue, testing notes (pytest output or curl examples), and any DB migration steps (`alembic revision --autogenerate && alembic upgrade head`).
- Ensure no secrets are committed and CI/tests pass locally.

## Security & Configuration Tips
- Copy `.env.example` to `.env`; set `DATABASE_URL`, `REDIS_URL`, Auth0, Stream, Stripe keys. Never commit secrets.
- Use `DEBUG_MODE=True` only locally. Validate CORS and rate limiting in `app/main.py`.
- Rotate tokens/keys when sharing logs; avoid printing full Bearer tokens.

