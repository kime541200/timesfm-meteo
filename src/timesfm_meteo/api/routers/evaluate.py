from __future__ import annotations

from datetime import date as Date

import psycopg
from fastapi import APIRouter, Depends, Query, Request

from timesfm_meteo.api.auth import verify_api_key
from timesfm_meteo.api.deps import get_conn
from timesfm_meteo.evaluation.orchestrator import evaluate_forecasts
from timesfm_meteo.models import EvaluationReport, Location

router = APIRouter(prefix="/evaluate", dependencies=[Depends(verify_api_key)])


@router.get("", response_model=EvaluationReport)
def get_evaluate(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    start_date_from: Date = Query(...),
    start_date_to: Date = Query(...),
    horizon_step: int | None = Query(None),
    request: Request = ...,
    conn: psycopg.Connection = Depends(get_conn),
) -> EvaluationReport:
    settings = request.app.state.settings
    location = Location(latitude=latitude, longitude=longitude)
    return evaluate_forecasts(location, start_date_from, start_date_to, horizon_step, conn, settings.open_meteo)
