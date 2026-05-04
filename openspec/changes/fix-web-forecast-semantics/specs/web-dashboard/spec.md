## MODIFIED Requirements

### Requirement: Dashboard filter controls

The dashboard SHALL provide controls for location, history date range, forecast horizon, evaluation horizon step, and aggregate-average visibility.

#### Scenario: Taipei default location

- **WHEN** the dashboard first loads
- **THEN** latitude SHALL default to `25.05`
- **AND** longitude SHALL default to `121.57`

#### Scenario: User can edit coordinates

- **WHEN** the user edits latitude or longitude and applies the filter
- **THEN** subsequent API requests SHALL use the edited coordinates
- **AND** invalid coordinate values SHALL be rejected in the UI before sending requests

#### Scenario: User can edit history date range

- **WHEN** the user edits History start and History end and applies the filter
- **THEN** `GET /api/temperatures` SHALL use History start as `start_date` and History end as `end_date`
- **AND** the actual temperature line SHALL represent only that historical range

#### Scenario: History end defines future forecast start

- **WHEN** the user clicks `Run Forecast`
- **THEN** the dashboard SHALL compute Forecast start as History end plus one calendar day
- **AND** SHALL send Forecast start as `start_date` in `POST /api/forecast`

#### Scenario: User can edit forecast horizon

- **WHEN** the user edits Forecast horizon and clicks `Run Forecast`
- **THEN** the dashboard SHALL send that value as `horizon` in `POST /api/forecast`
- **AND** Forecast horizon SHALL NOT be confused with evaluation horizon step

#### Scenario: User can select evaluation horizon step

- **WHEN** the user selects `any`, `0`, `1`, or `2` in the Evaluation horizon step control
- **THEN** chart historical forecast analysis and `GET /api/evaluate` SHALL update according to that selection
- **AND** this control SHALL NOT change the number of future days forecast by `Run Forecast`

#### Scenario: User can toggle aggregate average

- **WHEN** the user toggles aggregate average on
- **THEN** the main chart SHALL display aggregate forecast lines by target date
- **AND** raw forecast series SHALL remain visible but visually de-emphasized

### Requirement: Actual vs forecast chart

The dashboard SHALL render a main ECharts visualization comparing actual daily temperatures with past forecast data and future forecast output on a calendar target-date axis.

#### Scenario: Actual temperature lines rendered through history end

- **WHEN** `GET /api/temperatures` returns rows for History start through History end
- **THEN** the chart SHALL render actual maximum and actual minimum temperature lines by `date`
- **AND** those actual lines SHALL end at History end unless actual future rows exist

#### Scenario: Future forecast appears after history end

- **WHEN** a forecast job completes for Forecast start = History end + 1 day with Forecast horizon N
- **THEN** the chart SHALL display forecast p50 and p10–p90 values for dates `[Forecast start, Forecast start + N - 1]`
- **AND** these forecast values SHALL visually appear after the historical actual line

#### Scenario: Forecast p50 rendered by target_date

- **WHEN** `GET /api/forecasts` returns forecast rows
- **THEN** the chart SHALL render forecast max p50 and forecast min p50 by `target_date`
- **AND** raw forecast points or lines SHALL support multiple forecast rows for the same `target_date`

#### Scenario: Forecast interval bands rendered

- **WHEN** forecast rows contain p10 and p90 values
- **THEN** the chart SHALL represent p10–p90 uncertainty intervals for max and min forecasts

#### Scenario: evaluation horizon step any shows raw forecast distribution

- **WHEN** Evaluation horizon step filter is `any`
- **THEN** the chart SHALL include all forecast rows in the selected analysis range
- **AND** multiple forecasts for the same target date SHALL remain distinct rather than being silently collapsed

#### Scenario: numeric evaluation horizon step filters forecast rows

- **WHEN** Evaluation horizon step filter is `1`
- **THEN** historical forecast analysis SHALL include only forecasts where `target_date - start_date == 1`

#### Scenario: aggregate average line computed by target_date

- **WHEN** aggregate average is enabled
- **THEN** the chart SHALL compute mean max p50 and mean min p50 for each `target_date` over the currently visible forecast rows
- **AND** aggregate average lines SHALL be visually highest priority

#### Scenario: chart supports responsive layout

- **WHEN** viewport width becomes narrow
- **THEN** the chart SHALL remain within viewport width without horizontal page scroll
- **AND** surrounding panels SHALL stack vertically

### Requirement: Manual job actions

The dashboard SHALL let users trigger fetch-history and forecast jobs, poll job status, and refresh affected data when the job completes.

#### Scenario: Fetch History button creates job for history range

- **WHEN** the user clicks `Fetch History`
- **THEN** the dashboard SHALL call `POST /api/fetch-history` with current location, History start, and History end
- **AND** SHALL display the returned job id and pending/running status

#### Scenario: Forecast button creates future forecast job

- **WHEN** the user clicks `Run Forecast`
- **THEN** the dashboard SHALL call `POST /api/forecast` with current location, `start_date = History end + 1 day`, and `horizon = Forecast horizon`
- **AND** SHALL display the returned job id and pending/running status

#### Scenario: Running job is polled until terminal status

- **WHEN** a job is pending or running
- **THEN** the dashboard SHALL poll `GET /api/jobs/{id}` until the job status becomes `done` or `failed`

#### Scenario: Completed fetch-history refreshes affected queries

- **WHEN** a fetch-history job reaches `done`
- **THEN** the dashboard SHALL refetch temperatures and evaluation data for the current filters

#### Scenario: Completed forecast refreshes future forecast query

- **WHEN** a forecast job reaches `done`
- **THEN** the dashboard SHALL refetch forecasts for the newly created Forecast start date
- **AND** SHALL refetch evaluation data for the current filters

#### Scenario: Failed job shows error feedback

- **WHEN** a job reaches `failed`
- **THEN** the dashboard SHALL display the job error message in a visible error state

#### Scenario: Action buttons disabled while request pending

- **WHEN** the dashboard is creating a job or polling an active job of the same type
- **THEN** the corresponding action button SHALL be disabled and show loading feedback

### Requirement: Web dashboard documentation

The system SHALL document the corrected Web Dashboard date and forecast semantics.

#### Scenario: Documentation defines history and forecast vocabulary

- **WHEN** a developer reads `web/README.md` or `docs/usage.md`
- **THEN** the docs SHALL define History start, History end, Forecast start, Forecast horizon, and Evaluation horizon step

#### Scenario: Documentation explains future forecast placement

- **WHEN** a developer reads the Web Dashboard instructions
- **THEN** the docs SHALL state that Run Forecast predicts from History end plus one day
- **AND** forecast values should appear after the historical actual line in the chart

### Requirement: Frontend test coverage

The web dashboard SHALL include targeted tests for corrected forecast semantics.

#### Scenario: Forecast start utility tested

- **WHEN** `npm test` runs
- **THEN** tests SHALL verify Forecast start equals History end plus one calendar day

#### Scenario: Forecast request body tested

- **WHEN** the Run Forecast action is tested
- **THEN** tests SHALL verify `POST /api/forecast` receives `start_date = historyEnd + 1 day` and `horizon = forecastHorizon`

#### Scenario: Future forecast merge tested

- **WHEN** actual temperatures end at History end and forecast rows target dates after History end
- **THEN** tests SHALL verify merged chart data includes future forecast dates after the actual range

#### Scenario: Evaluation horizon step remains separate from forecast horizon

- **WHEN** evaluation horizon step and forecast horizon have different values
- **THEN** tests SHALL verify the evaluation query uses evaluation horizon step while Run Forecast uses forecast horizon
