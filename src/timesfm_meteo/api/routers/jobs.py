from __future__ import annotations

from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, HTTPException, status

from timesfm_meteo.api.auth import verify_api_key
from timesfm_meteo.api.deps import get_conn
from timesfm_meteo.api.schemas import JobResponse
from timesfm_meteo.db.jobs import fetch_job

router = APIRouter(prefix="/jobs", dependencies=[Depends(verify_api_key)])


@router.get("/{job_id}", response_model=JobResponse)
def get_job(
    job_id: UUID,
    conn: psycopg.Connection = Depends(get_conn),
) -> JobResponse:
    row = fetch_job(conn, job_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {job_id} not found")
    return JobResponse(
        id=row.id,
        type=row.type,
        status=row.status,
        params=row.params,
        result=row.result,
        error=row.error,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
