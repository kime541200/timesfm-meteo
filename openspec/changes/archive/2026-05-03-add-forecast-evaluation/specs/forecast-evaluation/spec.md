## ADDED Requirements

### Requirement: Forecast persistence schema

The system SHALL store TimesFM forecast outputs in a Postgres table named `forecasts` keyed by `(latitude, longitude, start_date, target_date)`, allowing different forecast vantage points for the same target date to coexist.

#### Scenario: Schema bootstrap is idempotent

- **WHEN** any CLI flow that touches forecasts (`forecast` or `evaluate`) calls `ensure_schema_forecasts`
- **THEN** the `forecasts` table SHALL be created if absent
- **AND** SHALL NOT alter or remove existing rows when already present

#### Scenario: Forecast row stores p10/p50/p90 for max and min

- **WHEN** a forecast for one target date is upserted
- **THEN** the row SHALL contain `max_p10`, `max_p50`, `max_p90`, `min_p10`, `min_p50`, `min_p90` as REAL columns
- **AND** SHALL contain `model_id` (TEXT), `history_days` (INT), and `run_at` (TIMESTAMPTZ) metadata

#### Scenario: Re-running same start_date and target_date overwrites prior row

- **WHEN** `upsert_forecasts` is called with the same `(latitude, longitude, start_date, target_date)` as an existing row
- **THEN** the existing row SHALL be updated in place with the new quantile values, `model_id`, `history_days`, and `run_at`

### Requirement: Forecast command persists outputs automatically

The `timesfm-meteo forecast` command SHALL upsert each per-day forecast into the `forecasts` table after generating the JSON output, with no flag required to enable persistence.

#### Scenario: Successful forecast writes one row per target date

- **WHEN** the `forecast` command runs successfully with `--horizon N`
- **THEN** N rows SHALL be inserted or updated in `forecasts`, one per target date in `[start_date, start_date + N - 1]`
- **AND** each row SHALL store the `model_id` from `Settings.timesfm.model_id` and the `history_days` actually used as model input

#### Scenario: Forecast persistence does not change stdout/stderr contract

- **WHEN** the `forecast` command writes forecasts to the database
- **THEN** stdout SHALL still contain the `ForecastResponse` JSON document
- **AND** stderr SHALL still contain the existing summary line

### Requirement: Evaluate command computes metrics over forecast range

The system SHALL provide a `timesfm-meteo evaluate` subcommand that compares stored forecasts against observed temperatures and emits a structured report.

#### Scenario: Required arguments accepted

- **WHEN** the user runs `timesfm-meteo evaluate --latitude 25.05 --longitude 121.57 --start-date-from 2024-06-01 --start-date-to 2024-06-30`
- **THEN** the command SHALL filter forecasts by the location and the inclusive `start_date` range and proceed to the evaluation flow

#### Scenario: Optional horizon_step filter restricts to one step

- **WHEN** the user adds `--horizon-step 1`
- **THEN** only forecasts where `target_date - start_date == 1` SHALL be considered

#### Scenario: Out-of-range coordinates rejected before any work

- **WHEN** the user runs the command with `--latitude 95.0` or `--longitude 200.0`
- **THEN** the command SHALL exit with a non-zero status without contacting Postgres or Open-Meteo

### Requirement: Evaluate auto-fetches missing actuals via cache-aware pipeline

The evaluate flow SHALL ensure observed temperatures are present in `daily_temperatures` for the target-date range covered by selected forecasts, by calling the existing `pipeline.historical.get_temperatures`.

#### Scenario: Actuals already cached do not trigger HTTP

- **WHEN** every target_date in the selected forecasts already has a row in `daily_temperatures`
- **THEN** the evaluate flow SHALL NOT issue any HTTP request to Open-Meteo

#### Scenario: Missing actuals are fetched and persisted

- **WHEN** one or more target_dates lack a row in `daily_temperatures`
- **THEN** the evaluate flow SHALL request the missing range from Open-Meteo via `get_temperatures` and upsert the returned rows
- **AND** target_dates that Open-Meteo cannot supply (e.g., future dates) SHALL be left absent and counted as `pending` in the report

### Requirement: Metrics grouped by horizon_step with overall aggregate

The evaluation report SHALL include a per-horizon-step breakdown plus an overall aggregate, with separate metrics for daily maximum and minimum temperatures.

#### Scenario: Three metrics computed per group

- **WHEN** a group has at least one forecast with a matching actual
- **THEN** the group SHALL produce a `VariableMetrics` for `max` and one for `min`, each containing `mae_p50`, `interval_coverage`, and `mean_interval_width`
- **AND** `mae_p50` SHALL use `p50` as the point prediction
- **AND** `interval_coverage` SHALL use `[p10, p90]` as the interval bounds
- **AND** `mean_interval_width` SHALL be the mean of `p90 - p10`

#### Scenario: Empty group emits null metrics

- **WHEN** a group has zero forecasts with matching actuals (all pending or no rows)
- **THEN** `max` and `min` in that group's `GroupMetrics` SHALL be `None`
- **AND** `evaluated_count` SHALL be `0`

#### Scenario: Horizon step grouping omits empty steps from list

- **WHEN** the report is built and a particular `horizon_step` has no rows at all (neither evaluated nor pending)
- **THEN** that step SHALL be omitted from `by_horizon_step` rather than included with zero counts

### Requirement: Evaluate exits successfully when no data is available

The system SHALL treat "no forecasts in range" and "all rows pending" as successful outcomes (exit code `0`) and inform the user via stderr, distinguishing them from configuration or input errors.

#### Scenario: No forecasts in range

- **WHEN** the evaluate flow finds zero forecast rows matching the location and date filters
- **THEN** the command SHALL exit with status `0`
- **AND** stdout SHALL contain a valid `EvaluationReport` JSON with `by_horizon_step: []` and `overall` having all-zero counts and `null` metrics
- **AND** stderr SHALL contain a message indicating that no forecasts were found in the range

#### Scenario: All forecasts are pending

- **WHEN** every selected forecast lacks a matching actual
- **THEN** the command SHALL exit with status `0`
- **AND** the report's `pending_count` SHALL reflect the number of pending rows
- **AND** all `max` and `min` fields in the metrics SHALL be `null`

### Requirement: Evaluation report is JSON-serializable Pydantic

The evaluate command SHALL emit a JSON document parsable by `EvaluationReport.model_validate_json()` to stdout, plus a single human-readable summary line to stderr.

#### Scenario: Stdout is a valid EvaluationReport

- **WHEN** the evaluate flow completes
- **THEN** stdout SHALL contain a single JSON document with the fields `location`, `start_date_from`, `start_date_to`, `horizon_step_filter`, `by_horizon_step`, and `overall`
- **AND** the JSON SHALL be parseable via `EvaluationReport.model_validate_json(stdout)` without error

#### Scenario: Stderr summary line

- **WHEN** the evaluate flow completes
- **THEN** stderr SHALL contain a single line with `evaluated=<N>` and `pending=<M>` and `horizon_step=<value-or-any>`

### Requirement: Database is mandatory for evaluate

The evaluate command SHALL require Postgres to be configured and reachable, mirroring `forecast` and `fetch-history`.

#### Scenario: Missing DATABASE_URL aborts before any work

- **WHEN** `DATABASE_URL` is not configured
- **THEN** the command SHALL exit with a non-zero status and print an error instructing the user to set `DATABASE_URL` in `.env`
- **AND** SHALL NOT issue any HTTP request

#### Scenario: Database connection failure aborts before any work

- **WHEN** `DATABASE_URL` is set but Postgres is unreachable
- **THEN** the command SHALL exit with a non-zero status and print the connection error
