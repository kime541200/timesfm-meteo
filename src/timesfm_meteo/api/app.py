from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator

try:
    from fastapi import FastAPI
    from psycopg_pool import ConnectionPool
except ImportError as exc:
    raise ImportError(
        "API server dependencies are not installed. Run: uv sync --extra api"
    ) from exc

from timesfm_meteo.configs import load_settings
from timesfm_meteo.db.forecasts import ensure_schema_forecasts
from timesfm_meteo.db.jobs import ensure_schema_jobs
from timesfm_meteo.db.repository import ensure_schema


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = load_settings()

    if not settings.postgres.dsn:
        print("ERROR: DATABASE_URL is not set. Add it to .env.", file=sys.stderr)
        raise RuntimeError("DATABASE_URL is required")

    if not settings.api.api_key:
        print("ERROR: API_KEY is not set. Add it to .env.", file=sys.stderr)
        raise RuntimeError("API_KEY is required")

    pool = ConnectionPool(settings.postgres.dsn, open=True)
    with pool.connection() as conn:
        ensure_schema(conn)
        ensure_schema_forecasts(conn)
        ensure_schema_jobs(conn)

    from timesfm_meteo.inference.timesfm_engine import TimesFMEngine

    try:
        engine = TimesFMEngine(
            model_id=settings.timesfm.model_id,
            max_context=settings.timesfm.max_context,
            max_horizon=settings.timesfm.max_horizon,
            normalize_inputs=settings.timesfm.normalize_inputs,
            use_continuous_quantile_head=settings.timesfm.use_continuous_quantile_head,
            force_flip_invariance=settings.timesfm.force_flip_invariance,
            fix_quantile_crossing=settings.timesfm.fix_quantile_crossing,
        )
    except RuntimeError as exc:
        # Missing [forecast] extra: start in read-only mode; POST /forecast will return 503.
        print(f"WARNING: TimesFM not loaded ({exc}). POST /forecast will be unavailable.", file=sys.stderr)
        engine = None

    app.state.settings = settings
    app.state.pool = pool
    app.state.engine = engine
    app.state.api_key = settings.api.api_key

    yield

    pool.close()


def create_app() -> FastAPI:
    app = FastAPI(
        title="timesfm-meteo API",
        description="HTTP API for the timesfm-meteo weather forecasting pipeline.",
        version="0.1.0",
        lifespan=lifespan,
    )

    from timesfm_meteo.api.routers import evaluate, fetch_history, forecasts, jobs, temperatures

    app.include_router(temperatures.router)
    app.include_router(forecasts.router)
    app.include_router(evaluate.router)
    app.include_router(fetch_history.router)
    app.include_router(jobs.router)

    return app


app = create_app()
