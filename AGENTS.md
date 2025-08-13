# Repository Guidelines

## Overview
Welcome! This guide explains how to work effectively in this repository. It covers structure, common commands, coding style, testing, and pull request expectations. Please keep changes focused, documented, and small whenever possible.

## Repository Structure
- `app/`: FastAPI app modules (API, services, repositories, models, schemas).
- `app/api/v1/`: Versioned routes and request/response schemas.
- `app/core/`: Config, scheduling, and utilities (logging, timezones).
- `app/repositories/`: Data access layer; keep DB logic isolated.
- `alembic/`: Database migrations.
- `tests/`: Unit and integration tests.

## Common Commands
- Run app: `uvicorn app.main:app --reload`
- Lint: `ruff check .`  | Format: `ruff format .` (or `black .` if configured)
- Type check: `mypy .`
- Tests: `pytest -q`  | Single test: `pytest tests/test_x.py::TestCase::test_y`
- Migrations: `alembic revision --autogenerate -m "msg" && alembic upgrade head`

## Style Conventions
- Python 3.10+; prefer type hints everywhere.
- Time handling: store UTC in DB, convert at edges; always use timezone-aware `datetime`.
- Naming: modules/symbols are snake_case; classes are PascalCase; constants UPPER_CASE.
- Errors: raise domain-specific exceptions in services; return safe messages from API.
- Keep functions small; avoid side effects in repositories.

## Testing
- Add tests with every behavior change; cover success, edge, and failure paths.
- For time-sensitive code, freeze time with `freezegun` or helper fixtures.
- Avoid network and real DB in unit tests; use factories and fakes.

## Pull Requests
- Include a clear summary, rationale, and screenshots/logs when relevant.
- Checklist: updated tests, docs, and migrations; no linter/type errors.
- Keep PRs under ~300 lines of diff when possible; split larger changes.
- Reference related issues and add migration notes for deploys.

## Security Tips (Optional)
- Never log secrets; redact tokens and PII.
- Validate and normalize all inputs at API boundaries.
- Use least-privilege DB roles; prefer parameterized queries.
- Review third-party dependencies regularly; pin versions and scan reports.

