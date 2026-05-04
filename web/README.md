# timesfm-meteo Web Dashboard

React + Vite dashboard for visualizing actual history, historical TimesFM forecast analysis, future forecast output, uncertainty intervals, and evaluation metrics.

## Prerequisites

1. Start Postgres.
2. Start the FastAPI API server:

```bash
uv sync --extra api --extra forecast
uv run uvicorn timesfm_meteo.api.app:app --port 8000
```

If `[forecast]` is not installed, read endpoints still work but `Run Forecast` returns an actionable 503 error.

## Configure

Create `web/.env.local`:

```env
VITE_TIMESFM_API_KEY=<same value as API_KEY in project .env>
VITE_TIMESFM_API_TARGET=http://localhost:8000
```

`VITE_TIMESFM_API_KEY` is visible in browser runtime. Use this only on localhost or a private network; do not use it for public deployment.

## Install and run

```bash
cd web
npm install
npm run dev
```

Open the Vite URL, usually `http://localhost:5173`.

## Vite proxy

The browser calls `/api/*`. Vite rewrites the path and proxies to the FastAPI server:

- `/api/temperatures` → `http://localhost:8000/temperatures`
- `/api/forecasts` → `http://localhost:8000/forecasts`
- `/api/evaluate` → `http://localhost:8000/evaluate`
- `/api/fetch-history` → `http://localhost:8000/fetch-history`
- `/api/forecast` → `http://localhost:8000/forecast`
- `/api/jobs/{id}` → `http://localhost:8000/jobs/{id}`

## Dashboard vocabulary

- **History start**: first day of the historical actual range and fetch-history range.
- **History end**: last day of the historical actual range and forecast cutoff.
- **Forecast start**: `History end + 1 day`.
- **Forecast horizon**: how many future days `Run Forecast` requests from Forecast start.
- **Evaluation horizon step**: optional lead-time filter for historical forecast analysis and evaluation only.

## Dashboard workflow

1. Adjust filters: latitude, longitude, History start, History end, Forecast horizon, Evaluation horizon step, and aggregate average.
2. Apply filters to load actual history, historical forecasts, future forecasts, and evaluation metrics.
3. The chart shows actual lines through History end.
4. `Run Forecast` posts `start_date = History end + 1 day` and `horizon = Forecast horizon`.
5. Future forecast points should appear after the actual history line, while Evaluation horizon step only changes historical forecast analysis.
6. Enable aggregate average to highlight the same-target-date average forecast while de-emphasizing raw points.
7. Click `Fetch History` or `Run Forecast` to create an API job. The dashboard polls job status and refetches affected data when complete.

## Tests and build

```bash
npm test
npm run lint
npm run build
```

Vitest focuses on date utilities, data transforms, forecast aggregation, API client behavior, and job polling terminal states.

## Troubleshooting

- **Configuration needed**: Check `web/.env.local` has `VITE_TIMESFM_API_KEY`.
- **401**: `VITE_TIMESFM_API_KEY` must match the API server's `API_KEY`.
- **Network errors**: Ensure FastAPI is running on `VITE_TIMESFM_API_TARGET`.
- **Run Forecast returns 503**: Start API server after installing `[forecast]` extra.
- **Forecast points do not appear after the actual line**: Confirm History end is the last actual day you want to display, then rerun `Run Forecast`; the job should start on the next calendar day.
