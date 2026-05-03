## ADDED Requirements

### Requirement: Forecast command persists results

The `timesfm-meteo forecast` command SHALL upsert its outputs into the `forecasts` table after generating the JSON output, with no flag required to enable persistence.

#### Scenario: Successful forecast writes one row per target date

- **WHEN** the `forecast` command runs successfully with `--horizon N`
- **THEN** N rows SHALL be inserted or updated in the `forecasts` table, one per target date in `[start_date, start_date + N - 1]`
- **AND** each row SHALL store `model_id` from `Settings.timesfm.model_id` and the `history_days` actually used

#### Scenario: Persistence does not change stdout/stderr contract

- **WHEN** persistence succeeds
- **THEN** stdout SHALL still contain the existing `ForecastResponse` JSON document
- **AND** stderr SHALL still contain the existing summary line
- **AND** the command's exit code SHALL still be `0`

#### Scenario: Schema bootstrap covers forecasts table

- **WHEN** the `forecast` command opens its database connection
- **THEN** it SHALL call both `ensure_schema` (for `daily_temperatures`) and `ensure_schema_forecasts` (for `forecasts`) before any read or write
