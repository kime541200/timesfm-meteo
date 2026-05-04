from __future__ import annotations

from datetime import date as Date
from typing import Any
from uuid import UUID

import psycopg
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from timesfm_meteo.api.auth import verify_api_key
from timesfm_meteo.api.deps import get_conn
from timesfm_meteo.api.jobs import run_forecast_job
from timesfm_meteo.api.schemas import JobCreatedResponse
from timesfm_meteo.db.forecasts import ForecastRow, fetch_forecasts_in_range
from timesfm_meteo.db.jobs import create_job
from timesfm_meteo.models import Location

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/forecasts", response_model=list[dict[str, Any]])
def list_forecasts(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    start_date_from: Date = Query(...),
    start_date_to: Date = Query(...),
    horizon_step: int | None = Query(None),
    conn: psycopg.Connection = Depends(get_conn),
) -> list[dict[str, Any]]:
    location = Location(latitude=latitude, longitude=longitude)
    rows: list[ForecastRow] = fetch_forecasts_in_range(
        conn, location, start_date_from, start_date_to, horizon_step
    )
    return [
        {
            **row._asdict(),
            "start_date": row.start_date.isoformat(),
            "target_date": row.target_date.isoformat(),
        }
        for row in rows
    ]


class ForecastRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    horizon: int | None = None
    history_years: int | None = None
    start_date: Date = Field(default_factory=Date.today)


@router.post("/forecast", response_model=JobCreatedResponse, status_code=202)
async def trigger_forecast(
    body: ForecastRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    conn: psycopg.Connection = Depends(get_conn),
) -> JobCreatedResponse:
    from timesfm_meteo.api.jobs import run_forecast_job

    settings = request.app.state.settings
    engine = request.app.state.engine
    if engine is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TimesFM model not loaded. Start the server with uv sync --extra forecast.",
        )
    dsn = settings.postgres.dsn

    params: dict[str, Any] = {
        "latitude": body.latitude,
        "longitude": body.longitude,
        "start_date": body.start_date.isoformat(),
    }
    if body.horizon is not None:
        params["horizon"] = body.horizon
    if body.history_years is not None:
        params["history_years"] = body.history_years

    job = create_job(conn, "forecast", params)
    background_tasks.add_task(run_forecast_job, job.id, params, engine, settings, dsn)
    return JobCreatedResponse(job_id=job.id)
