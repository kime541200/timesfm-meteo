# temperature-forecasting

## Purpose

用 TimesFM 對指定地點與起始日期，依歷史每日溫度產出未來 N 天的最高溫與最低溫分位數預測。包含 CLI 入口、引擎抽象、領域 adapter，以及讓未來抽出獨立 inference server 的乾淨邊界。

## Requirements

### Requirement: CLI forecast command

The system SHALL provide a `timesfm-meteo forecast` subcommand that produces quantile forecasts of daily maximum and minimum temperatures for a given location, using historical data from the `historical-fetch` pipeline as model input.

#### Scenario: Required arguments accepted

- **WHEN** the user runs `timesfm-meteo forecast --latitude 25.05 --longitude 121.57`
- **THEN** the command SHALL parse the location, default `--horizon` from `Settings.forecast_days`, default `--history-years` from `Settings.history_years`, default `--start-date` to today, and proceed to the forecast flow

#### Scenario: Out-of-range coordinates rejected before any work

- **WHEN** the user runs the command with `--latitude 95.0` or `--longitude 200.0`
- **THEN** the command SHALL exit with a non-zero status and print an error stating the offending coordinate is out of range, without contacting Postgres, Open-Meteo, or loading the model

#### Scenario: Backtest mode via past start date

- **WHEN** the user runs the command with `--start-date` set to a date in the past
- **THEN** the command SHALL use only history strictly before that date (`[start_date - history_years * 365 days, start_date - 1 day]`) as model input
- **AND** the forecast output dates SHALL be `[start_date, start_date + 1, ..., start_date + horizon - 1]`

### Requirement: Inference module independence

The system SHALL keep the inference layer free of project domain types so it can be extracted into a standalone service without refactoring its public API.

#### Scenario: Engine accepts only numeric series

- **WHEN** a caller invokes `TimesFMEngine.forecast(series_list, horizon)`
- **THEN** the engine SHALL accept only `list[numpy.ndarray]` and an integer `horizon`
- **AND** SHALL NOT accept or import any `timesfm_meteo` domain models (`DailyTemperature`, `Location`, etc.)

#### Scenario: Engine returns full quantile output

- **WHEN** the engine completes a forecast call
- **THEN** it SHALL return one `QuantileForecastResult` per input series in the same order as the input
- **AND** each `QuantileForecastResult` SHALL contain a `point` list of length `horizon` and a `quantiles` mapping from `{0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9}` to lists of length `horizon`

#### Scenario: Forecast result is JSON-serializable

- **WHEN** a `QuantileForecastResult` is produced
- **THEN** it SHALL be representable as JSON via `pydantic.BaseModel.model_dump_json()` without requiring custom encoders, by using `list[float]` (not `numpy.ndarray`) for all numeric fields

### Requirement: Engine dependency isolation

The system SHALL isolate the heavy `timesfm` and `torch` dependencies so the base package install remains lean.

#### Scenario: Forecast extra defines heavy dependencies

- **WHEN** a developer inspects `pyproject.toml`
- **THEN** `timesfm[torch]` SHALL appear under `[project.optional-dependencies].forecast`
- **AND** `torch` SHALL NOT appear under `[project].dependencies`

#### Scenario: Importing engine module without forecast extra

- **WHEN** a developer has not installed the `forecast` extra and imports `timesfm_meteo.inference.timesfm_engine`
- **THEN** the import SHALL succeed without raising

#### Scenario: Constructing engine without forecast extra

- **WHEN** a developer has not installed the `forecast` extra and instantiates `TimesFMEngine()`
- **THEN** the constructor SHALL raise an error whose message instructs the user to run `uv sync --extra forecast`

### Requirement: Domain adapter accepts injected engine

The system SHALL provide an adapter that converts domain objects to engine inputs and back, with the engine injected as a dependency.

#### Scenario: Adapter signature accepts a Protocol-typed engine

- **WHEN** a caller invokes the adapter
- **THEN** the adapter SHALL accept any object implementing the `ForecastEngine` Protocol (a `forecast(series_list, horizon)` method returning `list[QuantileForecastResult]`)
- **AND** SHALL NOT instantiate `TimesFMEngine` itself

#### Scenario: Max and min are forecast independently

- **WHEN** the adapter receives a `history` of `DailyTemperature` rows
- **THEN** it SHALL pass `[max_series, min_series]` as the engine batch (in this exact order)
- **AND** SHALL map `quantiles[0.1] / [0.5] / [0.9]` from each result to `QuantileValues.p10 / p50 / p90`

#### Scenario: Output dates match input dates

- **WHEN** the adapter is given a `forecast_dates` list of length N
- **THEN** it SHALL return a `list[DailyTemperatureForecast]` of length N
- **AND** the i-th output's `date` SHALL equal the i-th `forecast_dates` entry

### Requirement: Composite forecast model

The system SHALL represent a single day's forecast as a composite of separate quantile values for maximum and minimum temperature.

#### Scenario: Quantile values enforce ordering

- **WHEN** a `QuantileValues` is constructed
- **THEN** it SHALL reject input violating `p10 <= p50 <= p90` with a validation error

#### Scenario: Daily forecast bundles max and min

- **WHEN** a `DailyTemperatureForecast` is constructed
- **THEN** it SHALL contain a `date`, a `max: QuantileValues`, and a `min: QuantileValues`
- **AND** the median forecast SHALL satisfy `max.p50 >= min.p50`

### Requirement: Configurable model parameters

The system SHALL expose TimesFM model parameters through `Settings` and `configs.yaml` so they can be tuned without code changes.

#### Scenario: Settings exposes TimesFM section

- **WHEN** `Settings` is loaded with no overrides
- **THEN** `Settings.timesfm.model_id` SHALL default to `google/timesfm-2.5-200m-pytorch`
- **AND** `Settings.timesfm.max_context` SHALL default to `1024`
- **AND** `Settings.timesfm.max_horizon` SHALL default to `32`

#### Scenario: YAML overrides take effect

- **WHEN** `configs/configs.yaml` contains a `timesfm:` section with `model-id`, `max-context`, `max-horizon`, or any of the supported `ForecastConfig` flags
- **THEN** `Settings.timesfm` SHALL reflect the overridden values

#### Scenario: HF cache directory respects env var

- **WHEN** the user sets `HF_HOME` in `.env`
- **THEN** TimesFM checkpoint downloads SHALL be stored under that directory
- **AND** when `HF_HOME` is empty or unset the system SHALL fall back to HuggingFace Hub's default cache location

### Requirement: Forecast output format

The system SHALL emit forecast results to stdout as a JSON document parsable by a `ForecastResponse` Pydantic model, and a single human-readable summary line to stderr.

#### Scenario: Stdout is a valid ForecastResponse JSON

- **WHEN** the forecast flow completes successfully
- **THEN** stdout SHALL contain a single JSON document with fields `model` (str), `history_days` (int), `horizon` (int), and `forecasts` (a list of `DailyTemperatureForecast`)
- **AND** the JSON SHALL be parseable via `ForecastResponse.model_validate_json(stdout)` without error

#### Scenario: Stderr summary line

- **WHEN** the forecast flow completes successfully
- **THEN** stderr SHALL contain a single line with `history=<N>`, `horizon=<M>`, and `model=<model_id>`

### Requirement: Forecast flow reuses historical-fetch

The system SHALL retrieve model input history through the existing cache-aware `pipeline.historical.get_temperatures` rather than calling Open-Meteo directly.

#### Scenario: History uses Postgres cache

- **WHEN** the forecast command runs and the requested history range is fully cached in Postgres
- **THEN** the command SHALL NOT issue any HTTP request to Open-Meteo

#### Scenario: Missing history is fetched and cached

- **WHEN** the forecast command runs and some dates in the requested history range are missing from Postgres
- **THEN** the command SHALL fetch them from Open-Meteo and persist them via `upsert_temperatures` before running the model

### Requirement: Database is mandatory for forecast command

The system SHALL require Postgres to be configured and reachable before running the forecast flow, mirroring the `fetch-history` command.

#### Scenario: Missing DATABASE_URL aborts before model load

- **WHEN** `DATABASE_URL` is not configured
- **THEN** the command SHALL exit with a non-zero status and print an error instructing the user to set `DATABASE_URL` in `.env`
- **AND** SHALL NOT load the TimesFM model

#### Scenario: Database connection failure aborts before model load

- **WHEN** `DATABASE_URL` is set but Postgres is unreachable
- **THEN** the command SHALL exit with a non-zero status and print the connection error
- **AND** SHALL NOT load the TimesFM model
