## 1. Rename and separate frontend filter state

- [x] 1.1 Replace `DashboardFilters.startDate/endDate` with `historyStart/historyEnd`
- [x] 1.2 Add `forecastHorizon` to `DashboardFilters` with default `3`
- [x] 1.3 Rename `horizonStep` to `evaluationHorizonStep` in frontend types/hooks/components
- [x] 1.4 Update FilterPanel labels and help text: History start, History end, Forecast horizon, Evaluation horizon step
- [x] 1.5 Keep coordinate validation behavior unchanged

## 2. Correct forecast date calculation and API query ranges

- [x] 2.1 Add date utility `nextDate(historyEnd) -> forecastStart`
- [x] 2.2 Change Run Forecast request body to send `start_date = nextDate(historyEnd)` and `horizon = forecastHorizon`
- [x] 2.3 Change temperatures query to use `historyStart/historyEnd`
- [x] 2.4 Split or extend forecasts query so the chart can include future forecasts whose `start_date = nextDate(historyEnd)`
- [x] 2.5 Ensure evaluation query uses `historyStart/historyEnd` plus optional `evaluationHorizonStep`, not `forecastHorizon`

## 3. Update chart data and UI copy

- [x] 3.1 Ensure chart merge includes actual historical dates plus future forecast target dates
- [x] 3.2 Update chart heading/help copy to explain actual history followed by future forecast
- [x] 3.3 Ensure aggregate average still works for historical forecast analysis and future forecasts
- [x] 3.4 Ensure job status panel explains forecast start date and forecast horizon after Run Forecast

## 4. Tests

- [x] 4.1 Add Vitest coverage for `nextDate(historyEnd)` including month/year rollover
- [x] 4.2 Add Vitest coverage that Run Forecast posts `historyEnd + 1` and `forecastHorizon`
- [x] 4.3 Add Vitest coverage that evaluation horizon step remains separate from forecast horizon
- [x] 4.4 Add Vitest coverage for actual history ending at History end while future forecasts remain in chart data

## 5. Documentation

- [x] 5.1 Update `web/README.md` with corrected vocabulary and examples
- [x] 5.2 Update `docs/usage.md` Web Dashboard section with corrected forecast semantics
- [x] 5.3 Update `docs/roadmap.md` if needed to clarify Web Dashboard uses history range + future forecast horizon

## 6. Validation

- [x] 6.1 Run `npm --prefix web test`
- [x] 6.2 Run `npm --prefix web run build`
- [x] 6.3 Manually verify with local Web Dashboard: Run Forecast after History end creates forecast points after the actual line
