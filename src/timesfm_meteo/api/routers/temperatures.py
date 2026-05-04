from __future__ import annotations

from datetime import date as Date

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel

from timesfm_meteo.api.auth import verify_api_key
from timesfm_meteo.api.deps import get_conn
from timesfm_meteo.data_sources.open_meteo import OpenMeteoError
from timesfm_meteo.models import DailyTemperature, Location
from timesfm_meteo.pipeline.historical import get_temperatures

router = APIRouter(prefix="/temperatures", dependencies=[Depends(verify_api_key)])


class TemperaturesResponse(BaseModel):
    cached_count: int
    fetched_count: int
    rows: list[DailyTemperature]


def _validate_historical_date_range(start_date: Date, end_date: Date) -> None:
    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="start_date must be on or before end_date",
        )
    if end_date > Date.today():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="end_date cannot be after today for historical temperatures",
        )


@router.get("", response_model=TemperaturesResponse)
def get_temperatures_endpoint(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    start_date: Date = Query(...),
    end_date: Date = Query(...),
    request: Request = ...,
    conn: psycopg.Connection = Depends(get_conn),
) -> TemperaturesResponse:
    _validate_historical_date_range(start_date, end_date)
    settings = request.app.state.settings
    location = Location(latitude=latitude, longitude=longitude)

    try:
        result = get_temperatures(location, start_date, end_date, conn, settings.open_meteo)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except OpenMeteoError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    return TemperaturesResponse(
        cached_count=result.cached_count,
        fetched_count=result.fetched_count,
        rows=result.rows,
    )
