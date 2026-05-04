## 1. Web project scaffold

- [x] 1.1 Create `web/` Vite React TypeScript project structure (`index.html`, `src/`, `vite.config.ts`, `tsconfig*.json`)
- [x] 1.2 Add `web/package.json` scripts: `dev`, `build`, `test`, `lint`
- [x] 1.3 Add dependencies: React, Vite, TypeScript, ECharts, echarts-for-react, TanStack Query, Vitest, React Testing Library, ESLint
- [x] 1.4 Add `web/.env.example` documenting `VITE_TIMESFM_API_KEY` and optional `VITE_TIMESFM_API_TARGET`
- [x] 1.5 Configure Vite dev proxy so `/api/*` rewrites to the FastAPI server without CORS

## 2. API client and types

- [x] 2.1 Define TypeScript API response types for temperatures, forecasts, evaluation reports, jobs, and job creation responses
- [x] 2.2 Implement `web/src/api/client.ts` with shared fetch wrapper that attaches `Authorization: Bearer <VITE_TIMESFM_API_KEY>`
- [x] 2.3 Implement API functions: `getTemperatures`, `getForecasts`, `getEvaluation`, `postFetchHistory`, `postForecast`, `getJob`
- [x] 2.4 Surface missing `VITE_TIMESFM_API_KEY` as a typed configuration error without sending requests
- [x] 2.5 Add Vitest coverage for auth header injection, `/api/*` paths, and error handling

## 3. Data transformation utilities

- [x] 3.1 Implement horizon-step filtering for `any` and numeric values
- [x] 3.2 Implement temperature + forecast merge by target date while preserving multiple forecast rows for the same target date
- [x] 3.3 Implement aggregate average by target date for max/min p50 values
- [x] 3.4 Implement ECharts option builder with actual lines, forecast raw distribution, p10–p90 interval bands, and aggregate-highlight state
- [x] 3.5 Add Vitest coverage for filtering, merge, aggregation, null/empty data, and option highlighting behavior

## 4. Dashboard layout and filters

- [x] 4.1 Implement app shell with data-dense dashboard style, accessible heading, connection/configuration status, and no emoji icons
- [x] 4.2 Implement filter panel with default Taipei coordinates (`25.05`, `121.57`), editable latitude/longitude, date range, horizon_step selector, and aggregate toggle
- [x] 4.3 Validate coordinate inputs in UI before API calls
- [x] 4.4 Make layout desktop-first with responsive stacking at narrow widths and no horizontal page scroll
- [x] 4.5 Ensure all controls have labels, visible focus states, 44px touch targets, and non-shifting hover states

## 5. Data queries and chart rendering

- [x] 5.1 Configure TanStack Query provider and query keys based on current filters
- [x] 5.2 Fetch temperatures, forecasts, and evaluation report from the API server
- [x] 5.3 Implement loading, empty, and error states for each data section without layout jump
- [x] 5.4 Render main ECharts chart with actual max/min, forecast max/min p50, p10–p90 intervals, raw distribution, and aggregate average toggle
- [x] 5.5 Add tooltips/legend labels that explain actual vs forecast vs aggregate lines clearly

## 6. Evaluation metrics UI

- [x] 6.1 Implement overall summary cards for evaluated_count, pending_count, MAE, interval coverage, and mean interval width
- [x] 6.2 Implement horizon_step breakdown table with max/min metrics per row
- [x] 6.3 Render null metrics as `—` and avoid crashes on empty reports
- [x] 6.4 Ensure cards and table meet contrast and responsive layout requirements

## 7. Manual job controls

- [x] 7.1 Implement Fetch History button that calls `POST /api/fetch-history` with current filters
- [x] 7.2 Implement Run Forecast button that calls `POST /api/forecast` with current location, horizon, and start date
- [x] 7.3 Implement job polling hook that polls `GET /api/jobs/{id}` until `done` or `failed`
- [x] 7.4 Refetch affected queries when fetch-history or forecast jobs complete
- [x] 7.5 Show current job id/status/error in a visible job status panel
- [x] 7.6 Disable the corresponding action button while creation or polling is active
- [x] 7.7 Add Vitest coverage for job polling terminal states and failed job error surfacing

## 8. Documentation

- [x] 8.1 Write `web/README.md` with API server prerequisite, `web/.env.local`, install, dev, test, build, Vite proxy, and local-only API key warning
- [x] 8.2 Update `docs/usage.md` with Web Dashboard setup and workflow
- [x] 8.3 Update `AGENTS.md` with web project layout and Node/Vite test/build commands
- [x] 8.4 Update `docs/roadmap.md` to clarify that Web client is the active implementation of medium-term data visualization

## 9. Validation

- [x] 9.1 Run `npm test` in `web/` and confirm all Vitest tests pass
- [x] 9.2 Run `npm run build` in `web/` and confirm TypeScript + Vite build succeeds
- [x] 9.3 Start FastAPI server and Vite dev server, then manually verify: filters load data, chart renders, aggregate toggle changes highlighting, evaluation table renders
- [x] 9.4 Manually verify Fetch History job button: creates job, polls status, refetches temperatures/evaluation on completion
- [x] 9.5 Manually verify Run Forecast job button when API server has forecast extra available; if not available, verify the 503/error message is visible and actionable
