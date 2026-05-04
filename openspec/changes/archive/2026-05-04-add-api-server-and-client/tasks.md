## 1. Dependencies and configuration

- [x] 1.1 Add `[project.optional-dependencies].api` with `fastapi` and `uvicorn[standard]` to `pyproject.toml`
- [x] 1.2 Register `timesfm-meteo-client = "timesfm_meteo.client.cli:main"` under `[project.scripts]` in `pyproject.toml`
- [x] 1.3 Run `uv sync --extra api --extra forecast --extra dev` and confirm lockfile updates
- [x] 1.4 Add `API_KEY=`, `TIMESFM_API_URL=`, `TIMESFM_API_KEY=` placeholders to `.env.example`

## 2. Database layer for jobs

- [x] 2.1 Create `src/timesfm_meteo/db/jobs.py` with `JobRow` NamedTuple/Pydantic model and `ensure_schema_jobs(conn)`
- [x] 2.2 Implement `create_job(conn, job_type, params) -> JobRow`, `update_job_status(conn, job_id, status, result=None, error=None)`, `fetch_job(conn, job_id) -> JobRow | None`
- [x] 2.3 Add unit/integration tests in `tests/test_db_jobs.py` (skip cleanly when `DATABASE_URL` absent)

## 3. API server skeleton

- [x] 3.1 Create `src/timesfm_meteo/api/__init__.py`, `app.py`, `deps.py`, `auth.py`, `schemas.py`, `jobs.py`, and `routers/` package
- [x] 3.2 Implement `lifespan(app)` that loads `Settings`, opens a connection pool (psycopg `ConnectionPool` or per-request connections), calls `ensure_schema` / `ensure_schema_forecasts` / `ensure_schema_jobs`, and instantiates `TimesFMEngine` into `app.state.engine`
- [x] 3.3 Implement `verify_api_key` dependency reading `Settings.api.api_key` (or env), raising 401 on mismatch; verify startup fails when `API_KEY` empty
- [x] 3.4 Wire `app = FastAPI(lifespan=...)`, register routers, add global `Depends(verify_api_key)` to all routers
- [x] 3.5 Add `tests/test_api_app.py` covering import succeeds with `[api]` extra, lifespan startup invokes schema bootstrappers, and missing `API_KEY` aborts

## 4. Read endpoints

- [x] 4.1 Implement `routers/temperatures.py` with `GET /temperatures` calling `pipeline.historical.get_temperatures`
- [x] 4.2 Implement `routers/forecasts.py` with `GET /forecasts` calling `db.forecasts.fetch_forecasts_in_range`, supporting optional `horizon_step`
- [x] 4.3 Implement `routers/evaluate.py` with `GET /evaluate` calling `evaluation.orchestrator.evaluate_forecasts`
- [x] 4.4 Add request validation: latitude in [-90, 90], longitude in [-180, 180]; reject with HTTP 422 before any work
- [x] 4.5 Add `tests/test_api_read_endpoints.py` using `httpx.ASGITransport` with mocked engine and DB connection

## 5. Async trigger endpoints and background runner

- [x] 5.1 Implement `api/jobs.py` runner with `run_forecast_job(job_id, params, engine, settings)` and `run_fetch_history_job(job_id, params, settings)` that update job status and persist results
- [x] 5.2 Add `asyncio.Lock` (or equivalent) ensuring only one engine.forecast call executes at a time on the resident engine
- [x] 5.3 Implement `routers/forecasts.py::POST /forecast`: validate body, create job row, schedule background task, return HTTP 202 with `{job_id, status}`
- [x] 5.4 Implement `routers/fetch_history.py::POST /fetch-history`: validate body, create job row, schedule background task, return HTTP 202
- [x] 5.5 Implement `routers/jobs.py::GET /jobs/{job_id}` returning full job state, 404 on unknown
- [x] 5.6 Add `tests/test_api_jobs.py` covering: job created with `pending` status, background task transitions through `running` → `done`, exception path leaves `failed` with error message, unknown job returns 404
- [x] 5.7 Document forecast serialization (single in-flight) in `docs/api-server.md`

## 6. CLI client

- [x] 6.1 Create `src/timesfm_meteo/client/__init__.py`, `cli.py`, `http.py`, and `commands/` package
- [x] 6.2 Implement `client/http.py` reading `TIMESFM_API_URL` / `TIMESFM_API_KEY`, returning a configured `httpx.Client` with auth header; raise actionable errors when env vars missing
- [x] 6.3 Implement `commands/temperatures.py`, `commands/forecasts.py`, `commands/evaluate.py`, `commands/jobs.py` covering all read subcommands
- [x] 6.4 Implement `commands/forecasts.py::run` and `commands/fetch_history.py::run` with default wait-mode (poll `GET /jobs/{id}`), `--no-wait`, `--timeout` flags
- [x] 6.5 Implement error handling: 401 → "API key invalid", 404 from jobs get → "job not found", network error → URL + reason; all exit non-zero
- [x] 6.6 Wire `client/cli.py:main` argparse dispatcher to subcommands
- [x] 6.7 Add `tests/test_client_cli.py` using `respx` (or simple `httpx` mock transport) to assert request shape, header injection, wait/no-wait behavior

## 7. Documentation

- [x] 7.1 Write `docs/api-server.md`: endpoint table, auth setup, lifespan/model loading explanation, jobs schema, deployment commands (uvicorn), known limitations (single in-flight forecast)
- [x] 7.2 Write `docs/cli-client.md`: install (base extras only), env var setup, subcommand reference with example commands and outputs, AI-Agent usage tips
- [x] 7.3 Update `docs/usage.md` with new "API server" and "CLI client" sections referencing the dedicated docs
- [x] 7.4 Update `AGENTS.md` Setup / Development sections to mention `[api]` extra, `timesfm-meteo-client` entry point, and new file layout
- [x] 7.5 Update `README.md` to mention the API server / CLI client and link to their docs

## 8. End-to-end validation

- [x] 8.1 Manual smoke test: start uvicorn, hit `GET /temperatures` and `GET /forecasts` with curl using the API key
- [x] 8.2 Manual smoke test: trigger `POST /forecast` for a known location, poll `GET /jobs/{id}` until done, confirm row appears in `forecasts` table
- [x] 8.3 Manual smoke test: run `timesfm-meteo-client temperatures get` and confirm CLI client returns valid JSON
- [x] 8.4 Run full test suite `uv run --extra dev --extra api --extra forecast pytest`; all green
