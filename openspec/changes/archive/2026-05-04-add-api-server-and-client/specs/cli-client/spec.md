## ADDED Requirements

### Requirement: Lightweight CLI client entry point

The system SHALL provide a `timesfm-meteo-client` console script that invokes the API server over HTTP without requiring server-side dependencies.

#### Scenario: Entry point declared in pyproject.toml

- **WHEN** a developer inspects `pyproject.toml`
- **THEN** `timesfm-meteo-client = "timesfm_meteo.client.cli:main"` SHALL appear under `[project.scripts]`

#### Scenario: Client module avoids heavy imports

- **WHEN** a developer imports `timesfm_meteo.client.cli`
- **THEN** the import SHALL succeed without `psycopg`, `timesfm`, or `torch` installed
- **AND** SHALL NOT import any module from `timesfm_meteo.api`, `timesfm_meteo.db`, `timesfm_meteo.inference`, `timesfm_meteo.forecasting`, `timesfm_meteo.pipeline`, or `timesfm_meteo.evaluation`

### Requirement: Configuration from environment variables

The CLI client SHALL read its base URL and API key from `TIMESFM_API_URL` and `TIMESFM_API_KEY` environment variables (or `.env`).

#### Scenario: Missing TIMESFM_API_URL exits with error

- **WHEN** the user runs any client subcommand and `TIMESFM_API_URL` is not configured
- **THEN** the client SHALL exit with non-zero status and print an error instructing the user to set `TIMESFM_API_URL`

#### Scenario: Missing TIMESFM_API_KEY exits with error

- **WHEN** the user runs any client subcommand and `TIMESFM_API_KEY` is not configured
- **THEN** the client SHALL exit with non-zero status and print an error instructing the user to set `TIMESFM_API_KEY`

#### Scenario: Authorization header attached to every request

- **WHEN** the client sends any HTTP request
- **THEN** the request SHALL include `Authorization: Bearer <TIMESFM_API_KEY>`

### Requirement: Subcommands cover all API endpoints

The CLI client SHALL provide subcommands corresponding to each API endpoint group.

#### Scenario: temperatures get subcommand

- **WHEN** the user runs `timesfm-meteo-client temperatures get --latitude 25.05 --longitude 121.57 --start-date 2024-06-01 --end-date 2024-06-07`
- **THEN** the client SHALL call `GET /temperatures` with those parameters
- **AND** SHALL print the JSON response to stdout

#### Scenario: forecasts list subcommand

- **WHEN** the user runs `timesfm-meteo-client forecasts list --latitude 25.05 --longitude 121.57 --start-date-from 2024-06-01 --start-date-to 2024-06-30`
- **THEN** the client SHALL call `GET /forecasts`
- **AND** the optional `--horizon-step N` flag SHALL forward to the query string

#### Scenario: evaluate get subcommand

- **WHEN** the user runs `timesfm-meteo-client evaluate get --latitude 25.05 --longitude 121.57 --start-date-from 2024-06-01 --start-date-to 2024-06-30`
- **THEN** the client SHALL call `GET /evaluate`

#### Scenario: jobs get subcommand

- **WHEN** the user runs `timesfm-meteo-client jobs get <job_id>`
- **THEN** the client SHALL call `GET /jobs/<job_id>` and print the JSON response

### Requirement: Synchronous wait mode for async actions

The `forecast run` and `fetch-history run` subcommands SHALL by default wait until the job reaches a terminal status before exiting.

#### Scenario: forecast run waits for completion by default

- **WHEN** the user runs `timesfm-meteo-client forecast run --latitude 25.05 --longitude 121.57 --horizon 3`
- **THEN** the client SHALL call `POST /forecast`, capture the returned job_id, and poll `GET /jobs/<id>` until status is `done` or `failed`
- **AND** on `done` SHALL exit with status 0 and print the final job record (including `result`) to stdout
- **AND** on `failed` SHALL exit with non-zero status and print the error message

#### Scenario: --no-wait returns job_id immediately

- **WHEN** the user adds `--no-wait` to `forecast run` or `fetch-history run`
- **THEN** the client SHALL print the initial `{job_id, status}` response and exit immediately with status 0

#### Scenario: --timeout flag bounds wait duration

- **WHEN** the user passes `--timeout 30` to `forecast run`
- **THEN** the client SHALL stop polling after approximately 30 seconds and exit non-zero with a timeout message
- **AND** the underlying server-side job SHALL continue running

### Requirement: Error responses surfaced to user

The CLI client SHALL communicate HTTP error responses to the user clearly without crashing on stack traces.

#### Scenario: 401 Unauthorized prints concise message

- **WHEN** any subcommand receives HTTP 401
- **THEN** the client SHALL exit with non-zero status and print a message indicating that the API key is invalid or missing

#### Scenario: 404 from jobs get prints concise message

- **WHEN** `jobs get <unknown-id>` receives HTTP 404
- **THEN** the client SHALL exit with non-zero status and print a message stating that the job was not found

#### Scenario: Network error prints concise message

- **WHEN** the client cannot reach `TIMESFM_API_URL` (connection refused, DNS, timeout)
- **THEN** the client SHALL exit with non-zero status and print a message describing the network error and the URL attempted

### Requirement: Client dependencies remain in base install

The CLI client SHALL NOT introduce any new heavy runtime dependencies; it MUST work with the base install only.

#### Scenario: pyproject does not add new core deps for client

- **WHEN** a developer inspects `pyproject.toml`
- **THEN** `[project].dependencies` SHALL NOT add new packages beyond those already required for the base install (specifically, `httpx` and `pydantic` are reused)
