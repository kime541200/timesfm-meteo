# api-server

## Purpose

Expose the existing historical-fetch / forecast / evaluate pipeline as a secured HTTP API via FastAPI, with background job execution and Postgres-backed job tracking.

## Requirements

### Requirement: FastAPI app exposes pipeline as HTTP endpoints

The system SHALL provide a FastAPI application at `timesfm_meteo.api.app:app` that exposes the existing historical-fetch / forecast / evaluate pipeline through HTTP endpoints.

#### Scenario: Importing the app module succeeds with [api] extra installed

- **WHEN** a developer with the `api` extra installed imports `timesfm_meteo.api.app`
- **THEN** the import SHALL succeed without raising
- **AND** the imported `app` SHALL be a `fastapi.FastAPI` instance

#### Scenario: Importing without [api] extra fails with actionable message

- **WHEN** a developer without the `api` extra imports `timesfm_meteo.api.app`
- **THEN** the import SHALL raise an error whose message instructs running `uv sync --extra api`

### Requirement: API key authentication on all endpoints

All API endpoints SHALL require a valid API key supplied via the `Authorization: Bearer <key>` header. The expected key SHALL be loaded from the `API_KEY` environment variable (or `.env`) at startup.

#### Scenario: Missing API_KEY aborts startup

- **WHEN** the server starts and `API_KEY` is unset or empty
- **THEN** server startup SHALL fail with an error message instructing the user to set `API_KEY` in `.env`

#### Scenario: Request without Authorization header is rejected

- **WHEN** a client sends any request to a non-public endpoint without `Authorization` header
- **THEN** the response SHALL be HTTP 401 with a JSON error body

#### Scenario: Request with wrong API key is rejected

- **WHEN** a client sends a request with `Authorization: Bearer <wrong>`
- **THEN** the response SHALL be HTTP 401

#### Scenario: Request with correct API key is accepted

- **WHEN** a client sends a request with `Authorization: Bearer <correct>`
- **THEN** authentication SHALL succeed and the request SHALL proceed to the endpoint handler

### Requirement: Read endpoints return structured pipeline output

The system SHALL provide read-only endpoints that return data already in Postgres without triggering background work, except `GET /evaluate` which may transparently fetch missing actuals via the existing pipeline.

#### Scenario: GET /temperatures returns historical rows

- **WHEN** a client calls `GET /temperatures?latitude=25.05&longitude=121.57&start_date=2024-06-01&end_date=2024-06-07`
- **THEN** the response SHALL be HTTP 200 with a JSON body parseable as `FetchResult` (rows, cached_count, fetched_count)
- **AND** missing dates SHALL be auto-fetched and persisted via `pipeline.historical.get_temperatures`

#### Scenario: GET /forecasts returns stored forecast rows

- **WHEN** a client calls `GET /forecasts?latitude=25.05&longitude=121.57&start_date_from=2024-06-01&start_date_to=2024-06-30`
- **THEN** the response SHALL be HTTP 200 with a JSON list of forecast rows including `start_date`, `target_date`, max p10/p50/p90, min p10/p50/p90, `model_id`, `history_days`, `run_at`
- **AND** the optional `horizon_step` query parameter SHALL further filter by `target_date - start_date`

#### Scenario: GET /evaluate returns EvaluationReport JSON

- **WHEN** a client calls `GET /evaluate?latitude=25.05&longitude=121.57&start_date_from=2024-06-01&start_date_to=2024-06-30`
- **THEN** the response SHALL be HTTP 200 with a JSON body parseable by `EvaluationReport.model_validate_json`

#### Scenario: Out-of-range coordinates rejected

- **WHEN** a client sends any read endpoint with `latitude=95.0` or `longitude=200.0`
- **THEN** the response SHALL be HTTP 422 (validation error) without contacting Postgres or Open-Meteo

### Requirement: Asynchronous forecast and fetch-history endpoints

The system SHALL provide trigger endpoints (`POST /forecast`, `POST /fetch-history`) that immediately return a job identifier and run the pipeline in the background.

#### Scenario: POST /forecast returns job_id immediately

- **WHEN** a client calls `POST /forecast` with body `{latitude, longitude, horizon, history_years, start_date}`
- **THEN** the server SHALL immediately persist a row in `jobs` with `type='forecast'`, `status='pending'`, `params=<request body>`
- **AND** the response SHALL be HTTP 202 with body `{job_id: <uuid>, status: "pending"}`
- **AND** the actual forecast SHALL run in a background task that updates job status to `running`, then `done` or `failed`

#### Scenario: POST /fetch-history returns job_id immediately

- **WHEN** a client calls `POST /fetch-history` with body containing `latitude`, `longitude`, and either `years` or `start_date` / `end_date`
- **THEN** the server SHALL immediately create a job row and return `job_id` in HTTP 202
- **AND** background execution SHALL invoke `pipeline.historical.get_temperatures` and update job status accordingly

#### Scenario: Forecast job persists results to forecasts table

- **WHEN** a `forecast` job runs successfully in the background
- **THEN** results SHALL be upserted into the `forecasts` table via the existing `db.forecasts.upsert_forecasts`
- **AND** the job's `result` JSONB column SHALL contain a summary `{horizon, model_id, history_days, target_dates}`

#### Scenario: Failed background job records error

- **WHEN** the background execution of a job raises an exception
- **THEN** the job row SHALL be updated to `status='failed'` with the exception message stored in the `error` column
- **AND** subsequent calls to `GET /jobs/{id}` SHALL return that error message

### Requirement: Job status endpoint

The system SHALL provide `GET /jobs/{job_id}` returning the current status of a previously created job.

#### Scenario: Existing job returns full state

- **WHEN** a client calls `GET /jobs/<existing-uuid>`
- **THEN** the response SHALL be HTTP 200 with body containing `id`, `type`, `status`, `params`, `result`, `error`, `created_at`, `updated_at`

#### Scenario: Unknown job returns 404

- **WHEN** a client calls `GET /jobs/<unknown-uuid>`
- **THEN** the response SHALL be HTTP 404

### Requirement: Jobs schema bootstrap is idempotent

The system SHALL provide `ensure_schema_jobs` that creates the `jobs` table if absent and is safe to call repeatedly.

#### Scenario: Schema bootstrap is idempotent

- **WHEN** any API startup or database-touching flow calls `ensure_schema_jobs`
- **THEN** the `jobs` table SHALL be created if absent
- **AND** SHALL NOT alter or remove existing rows when already present

#### Scenario: Jobs table primary key and indexes

- **WHEN** the `jobs` table exists
- **THEN** it SHALL have `id UUID PRIMARY KEY`, `type TEXT NOT NULL`, `status TEXT NOT NULL`, `params JSONB NOT NULL`, `result JSONB`, `error TEXT`, `created_at TIMESTAMPTZ DEFAULT NOW()`, `updated_at TIMESTAMPTZ DEFAULT NOW()`
- **AND** SHALL have indexes on `status` and `created_at DESC`

### Requirement: TimesFM model loaded at startup via lifespan

The system SHALL load the `TimesFMEngine` once during FastAPI startup and keep it resident in memory for the entire server lifetime.

#### Scenario: Engine initialized in lifespan startup

- **WHEN** the FastAPI app starts
- **THEN** lifespan startup SHALL construct a `TimesFMEngine` using `Settings.timesfm` parameters
- **AND** the engine SHALL be exposed via `app.state.engine` for dependency injection
- **AND** subsequent forecast jobs SHALL reuse the same engine without reloading

#### Scenario: Engine load failure aborts startup

- **WHEN** lifespan startup fails to load TimesFM (e.g., missing forecast extra, checkpoint download failure)
- **THEN** the server SHALL fail to start and log the underlying error

#### Scenario: Engine accessed via Protocol in handlers

- **WHEN** a forecast handler needs the engine
- **THEN** it SHALL receive an object satisfying the `ForecastEngine` Protocol via FastAPI dependency injection
- **AND** SHALL NOT instantiate `TimesFMEngine` directly

### Requirement: Database mandatory for all endpoints

The system SHALL require Postgres to be configured and reachable, mirroring the existing CLI commands.

#### Scenario: Missing DATABASE_URL aborts startup

- **WHEN** the server starts and `DATABASE_URL` is unset
- **THEN** startup SHALL fail with an error message instructing the user to set `DATABASE_URL`

#### Scenario: Database connection failure aborts startup

- **WHEN** `DATABASE_URL` is set but Postgres is unreachable
- **THEN** startup SHALL fail with the underlying connection error

#### Scenario: Schema bootstrap covers all tables at startup

- **WHEN** the FastAPI app starts
- **THEN** lifespan startup SHALL call `ensure_schema`, `ensure_schema_forecasts`, and `ensure_schema_jobs` before serving any request

### Requirement: API extra defines server dependencies

The system SHALL isolate FastAPI / uvicorn dependencies under a `[api]` optional dependency group.

#### Scenario: api extra contains server dependencies

- **WHEN** a developer inspects `pyproject.toml`
- **THEN** `fastapi` and `uvicorn[standard]` SHALL appear under `[project.optional-dependencies].api`
- **AND** SHALL NOT appear under `[project].dependencies`

### Requirement: Existing CLI behavior unchanged

The introduction of the API server SHALL NOT change the behavior of the existing `timesfm-meteo` CLI commands (`fetch-history`, `forecast`, `evaluate`).

#### Scenario: CLI runs without API extra

- **WHEN** a developer runs any existing CLI command without installing the `[api]` extra
- **THEN** the command SHALL execute as before, with no requirement on FastAPI or uvicorn
