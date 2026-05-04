from __future__ import annotations

import asyncio
import datetime as dt
from datetime import date as Date
from typing import TYPE_CHECKING, Any
from uuid import UUID

import psycopg

from timesfm_meteo.configs import Settings
from timesfm_meteo.db.forecasts import ensure_schema_forecasts, upsert_forecasts
from timesfm_meteo.db.jobs import update_job_status
from timesfm_meteo.db.repository import ensure_schema
from timesfm_meteo.forecasting.timesfm import forecast_with_timesfm
from timesfm_meteo.models import Location
from timesfm_meteo.pipeline.historical import get_temperatures

if TYPE_CHECKING:
    from timesfm_meteo.inference.timesfm_engine import ForecastEngine

# Serialise model inference: only one engine.forecast() at a time.
_forecast_lock = asyncio.Lock()


def _run_forecast_sync(
    location: Location,
    start_date: Date,
    horizon: int,
    history_years: int,
    engine: ForecastEngine,
    settings: Settings,
    dsn: str,
    job_id: UUID,
) -> dict[str, Any]:
    with psycopg.connect(dsn) as conn:
        ensure_schema(conn)
        ensure_schema_forecasts(conn)

        history_end = start_date - dt.timedelta(days=1)
        history_start = history_end.replace(year=history_end.year - history_years)
        fetch_result = get_temperatures(location, history_start, history_end, conn, settings.open_meteo)
        history = fetch_result.rows

        forecast_dates = [start_date + dt.timedelta(days=i) for i in range(horizon)]
        daily = forecast_with_timesfm(history, forecast_dates, engine)
        upsert_forecasts(conn, location, start_date, daily, settings.timesfm.model_id, len(history))

    return {
        "horizon": horizon,
        "model_id": settings.timesfm.model_id,
        "history_days": len(history),
        "target_dates": [d.isoformat() for d in forecast_dates],
    }


async def run_forecast_job(
    job_id: UUID,
    params: dict[str, Any],
    engine: ForecastEngine,
    settings: Settings,
    dsn: str,
) -> None:
    with psycopg.connect(dsn) as conn:
        update_job_status(conn, job_id, "running")
    try:
        location = Location(latitude=params["latitude"], longitude=params["longitude"])
        start_date = Date.fromisoformat(params["start_date"])
        horizon = int(params.get("horizon", settings.forecast_days))
        history_years = int(params.get("history_years", settings.history_years))

        async with _forecast_lock:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                _run_forecast_sync,
                location, start_date, horizon, history_years, engine, settings, dsn, job_id,
            )

        with psycopg.connect(dsn) as conn:
            update_job_status(conn, job_id, "done", result=result)
    except Exception as exc:
        with psycopg.connect(dsn) as conn:
            update_job_status(conn, job_id, "failed", error=str(exc))
        raise


def _run_fetch_history_sync(
    location: Location,
    start_date: Date,
    end_date: Date,
    settings: Settings,
    dsn: str,
) -> dict[str, Any]:
    with psycopg.connect(dsn) as conn:
        ensure_schema(conn)
        fetch_result = get_temperatures(location, start_date, end_date, conn, settings.open_meteo)
    return {
        "cached_count": fetch_result.cached_count,
        "fetched_count": fetch_result.fetched_count,
        "total": len(fetch_result.rows),
    }


async def run_fetch_history_job(
    job_id: UUID,
    params: dict[str, Any],
    settings: Settings,
    dsn: str,
) -> None:
    with psycopg.connect(dsn) as conn:
        update_job_status(conn, job_id, "running")
    try:
        location = Location(latitude=params["latitude"], longitude=params["longitude"])
        today = Date.today()
        if "years" in params:
            end_date = Date.fromisoformat(params["end_date"]) if "end_date" in params else today
            start_date = end_date.replace(year=end_date.year - int(params["years"]))
        else:
            start_date = Date.fromisoformat(params["start_date"])
            end_date = Date.fromisoformat(params.get("end_date", today.isoformat()))

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, _run_fetch_history_sync, location, start_date, end_date, settings, dsn
        )

        with psycopg.connect(dsn) as conn:
            update_job_status(conn, job_id, "done", result=result)
    except Exception as exc:
        with psycopg.connect(dsn) as conn:
            update_job_status(conn, job_id, "failed", error=str(exc))
        raise
