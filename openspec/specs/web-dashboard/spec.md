# web-dashboard Specification

## Purpose

TBD - created by syncing change `add-web-client`.

## Requirements

### Requirement: React Vite web dashboard project

The system SHALL provide a React + Vite + TypeScript web application under `web/` for human-facing visualization and manual operation of the existing API server.

#### Scenario: Web project has expected scripts

- **WHEN** a developer inspects `web/package.json`
- **THEN** it SHALL define `dev`, `build`, `test`, and `lint` scripts
- **AND** `build` SHALL run TypeScript checking and Vite production build
- **AND** `test` SHALL run Vitest

#### Scenario: Web project documents startup flow

- **WHEN** a developer reads `web/README.md`
- **THEN** it SHALL explain how to start Postgres, start the FastAPI server, configure `web/.env.local`, install dependencies, run the Vite dev server, run tests, and build production assets

### Requirement: Local-only API configuration

The web dashboard SHALL call the API server through Vite dev proxy using `/api/*` paths and attach the configured API key as a Bearer token.

#### Scenario: API key is read from Vite env

- **WHEN** the dashboard starts in development
- **THEN** it SHALL read `VITE_TIMESFM_API_KEY` from `web/.env.local` or environment
- **AND** every API request SHALL include `Authorization: Bearer <VITE_TIMESFM_API_KEY>`

#### Scenario: Missing API key is visible in UI

- **WHEN** `VITE_TIMESFM_API_KEY` is absent or empty
- **THEN** the dashboard SHALL display a clear configuration error near the top of the page
- **AND** SHALL NOT attempt API requests that require auth

#### Scenario: Vite proxy rewrites /api prefix

- **WHEN** the dashboard calls `/api/temperatures`
- **THEN** Vite dev server SHALL proxy the request to the FastAPI server at `/temperatures`
- **AND** this behavior SHALL be documented in `web/README.md`

#### Scenario: Local-only warning documented

- **WHEN** a developer reads `web/README.md`
- **THEN** it SHALL warn that `VITE_TIMESFM_API_KEY` is visible to browser runtime and MUST NOT be used for public deployment

### Requirement: Dashboard filter controls

The dashboard SHALL provide controls for location, date range, horizon step, and aggregate-average visibility.

#### Scenario: Taipei default location

- **WHEN** the dashboard first loads
- **THEN** latitude SHALL default to `25.05`
- **AND** longitude SHALL default to `121.57`

#### Scenario: User can edit coordinates

- **WHEN** the user edits latitude or longitude and applies the filter
- **THEN** subsequent API requests SHALL use the edited coordinates
- **AND** invalid coordinate values SHALL be rejected in the UI before sending requests

#### Scenario: User can edit date range

- **WHEN** the user edits start and end dates and applies the filter
- **THEN** `GET /api/temperatures`, `GET /api/forecasts`, and `GET /api/evaluate` SHALL use the selected range

#### Scenario: User can select horizon step

- **WHEN** the user selects `any`, `0`, `1`, or `2` in the horizon step control
- **THEN** chart forecast data SHALL update according to that selection
- **AND** `GET /api/evaluate` SHALL include `horizon_step` only when a numeric step is selected

#### Scenario: User can toggle aggregate average

- **WHEN** the user toggles aggregate average on
- **THEN** the main chart SHALL display aggregate forecast lines by target date
- **AND** raw forecast series SHALL remain visible but visually de-emphasized

### Requirement: Actual vs forecast chart

The dashboard SHALL render a main ECharts visualization comparing actual daily temperatures with past forecast data on a calendar target-date axis.

#### Scenario: Actual temperature lines rendered

- **WHEN** `GET /api/temperatures` returns rows
- **THEN** the chart SHALL render actual maximum and actual minimum temperature lines by `date`

#### Scenario: Forecast p50 rendered by target_date

- **WHEN** `GET /api/forecasts` returns forecast rows
- **THEN** the chart SHALL render forecast max p50 and forecast min p50 by `target_date`
- **AND** raw forecast points or lines SHALL support multiple forecast rows for the same `target_date`

#### Scenario: Forecast interval bands rendered

- **WHEN** forecast rows contain p10 and p90 values
- **THEN** the chart SHALL represent p10–p90 uncertainty intervals for max and min forecasts

#### Scenario: horizon_step any shows raw forecast distribution

- **WHEN** horizon step filter is `any`
- **THEN** the chart SHALL include all forecast rows in the selected date range
- **AND** multiple forecasts for the same target date SHALL remain distinct rather than being silently collapsed

#### Scenario: numeric horizon_step filters forecast rows

- **WHEN** horizon step filter is `1`
- **THEN** the chart SHALL include only forecasts where `target_date - start_date == 1`

#### Scenario: aggregate average line computed by target_date

- **WHEN** aggregate average is enabled
- **THEN** the chart SHALL compute mean max p50 and mean min p50 for each `target_date` over the currently visible forecast rows
- **AND** aggregate average lines SHALL be visually highest priority

#### Scenario: chart supports responsive layout

- **WHEN** viewport width becomes narrow
- **THEN** the chart SHALL remain within viewport width without horizontal page scroll
- **AND** surrounding panels SHALL stack vertically

### Requirement: Evaluation metrics UI

The dashboard SHALL display forecast evaluation metrics returned by `GET /api/evaluate`.

#### Scenario: Overall summary cards

- **WHEN** an `EvaluationReport` is loaded
- **THEN** the dashboard SHALL display overall `evaluated_count`, `pending_count`, max/min `mae_p50`, max/min `interval_coverage`, and max/min `mean_interval_width`

#### Scenario: Horizon-step breakdown table

- **WHEN** an `EvaluationReport` contains `by_horizon_step`
- **THEN** the dashboard SHALL display one table row per horizon step
- **AND** each row SHALL show evaluated count, pending count, and max/min metrics when available

#### Scenario: Null metrics handled gracefully

- **WHEN** a group has `max` or `min` metrics equal to `null`
- **THEN** the UI SHALL display a non-crashing placeholder such as `—`

### Requirement: Manual job actions

The dashboard SHALL let users trigger fetch-history and forecast jobs, poll job status, and refresh affected data when the job completes.

#### Scenario: Fetch History button creates job

- **WHEN** the user clicks `Fetch History`
- **THEN** the dashboard SHALL call `POST /api/fetch-history` with the current location and date range
- **AND** SHALL display the returned job id and pending/running status

#### Scenario: Forecast button creates job

- **WHEN** the user clicks `Run Forecast`
- **THEN** the dashboard SHALL call `POST /api/forecast` with the current location, horizon, and optional start date
- **AND** SHALL display the returned job id and pending/running status

#### Scenario: Running job is polled until terminal status

- **WHEN** a job is pending or running
- **THEN** the dashboard SHALL poll `GET /api/jobs/{id}` until the job status becomes `done` or `failed`

#### Scenario: Completed fetch-history refreshes affected queries

- **WHEN** a fetch-history job reaches `done`
- **THEN** the dashboard SHALL refetch temperatures and evaluation data for the current filters

#### Scenario: Completed forecast refreshes affected queries

- **WHEN** a forecast job reaches `done`
- **THEN** the dashboard SHALL refetch forecasts and evaluation data for the current filters

#### Scenario: Failed job shows error feedback

- **WHEN** a job reaches `failed`
- **THEN** the dashboard SHALL display the job error message in a visible error state

#### Scenario: Action buttons disabled while request pending

- **WHEN** the dashboard is creating a job or polling an active job of the same type
- **THEN** the corresponding action button SHALL be disabled and show loading feedback

### Requirement: UI/UX accessibility and quality

The dashboard SHALL follow the project UI/UX quality baseline for accessibility, responsive layout, and professional dashboard presentation.

#### Scenario: Controls have accessible labels

- **WHEN** the dashboard renders input fields, selects, toggles, or buttons
- **THEN** each interactive control SHALL have a visible label or accessible name

#### Scenario: Keyboard focus visible

- **WHEN** the user navigates controls with keyboard
- **THEN** focused controls SHALL show visible focus state

#### Scenario: Clickable elements use clear interaction feedback

- **WHEN** a user hovers or focuses buttons and clickable controls
- **THEN** the UI SHALL provide visual feedback without layout shift

#### Scenario: Chart data has table alternative

- **WHEN** the chart is rendered
- **THEN** the evaluation breakdown table and metrics cards SHALL provide a non-chart summary of the key data

#### Scenario: No emoji icons used as interface icons

- **WHEN** the dashboard uses icons
- **THEN** icons SHALL come from SVG/icon libraries rather than emoji characters

### Requirement: Frontend test coverage

The web dashboard SHALL include targeted tests for data transformations and API behavior.

#### Scenario: Forecast filtering tested

- **WHEN** `npm test` runs
- **THEN** tests SHALL cover filtering forecasts by numeric horizon step and by `any`

#### Scenario: Forecast aggregation tested

- **WHEN** multiple forecast rows share a `target_date`
- **THEN** tests SHALL verify aggregate average p50 values are computed correctly

#### Scenario: Temperature and forecast merge tested

- **WHEN** temperatures and forecasts contain overlapping target dates
- **THEN** tests SHALL verify chart data aligns by date without dropping distinct forecast rows

#### Scenario: API client auth tested

- **WHEN** API client functions are tested
- **THEN** tests SHALL verify `Authorization: Bearer <key>` is attached to requests

#### Scenario: Job polling tested

- **WHEN** job polling is tested
- **THEN** tests SHALL verify polling stops on `done`, stops on `failed`, and surfaces failed job errors

#### Scenario: Production build succeeds

- **WHEN** a developer runs `npm run build` under `web/`
- **THEN** TypeScript checking and Vite production build SHALL complete successfully
