from __future__ import annotations

from datetime import date as Date
from typing import Any

import psycopg
from fastapi import APIRouter, BackgroundTasks, Depends, Request
from pydantic import BaseModel, Field, model_validator

from timesfm_meteo.api.auth import verify_api_key
from timesfm_meteo.api.deps import get_conn
from timesfm_meteo.api.jobs import run_fetch_history_job
from timesfm_meteo.api.schemas import JobCreatedResponse
from timesfm_meteo.db.jobs import create_job

router = APIRouter(prefix="/fetch-history", dependencies=[Depends(verify_api_key)])


class FetchHistoryRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    years: int | None = Field(None, ge=1, le=100)
    start_date: Date | None = None
    end_date: Date | None = None

    @model_validator(mode="after")
    def validate_date_spec(self) -> "FetchHistoryRequest":
        if self.years is None and self.start_date is None:
            raise ValueError("Provide either 'years' or 'start_date'")
        return self


@router.post("", response_model=JobCreatedResponse, status_code=202)
async def trigger_fetch_history(
    body: FetchHistoryRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    conn: psycopg.Connection = Depends(get_conn),
) -> JobCreatedResponse:
    settings = request.app.state.settings
    dsn = settings.postgres.dsn

    params: dict[str, Any] = {"latitude": body.latitude, "longitude": body.longitude}
    if body.years is not None:
        params["years"] = body.years
    if body.start_date is not None:
        params["start_date"] = body.start_date.isoformat()
    if body.end_date is not None:
        params["end_date"] = body.end_date.isoformat()

    job = create_job(conn, "fetch-history", params)
    background_tasks.add_task(run_fetch_history_job, job.id, params, settings, dsn)
    return JobCreatedResponse(job_id=job.id)
