from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import psycopg

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS jobs (
    id          UUID        PRIMARY KEY,
    type        TEXT        NOT NULL CHECK (type IN ('forecast', 'fetch-history')),
    status      TEXT        NOT NULL CHECK (status IN ('pending', 'running', 'done', 'failed')),
    params      JSONB       NOT NULL,
    result      JSONB,
    error       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS jobs_status_idx     ON jobs (status);
CREATE INDEX IF NOT EXISTS jobs_created_at_idx ON jobs (created_at DESC);
"""

_INSERT = """
INSERT INTO jobs (id, type, status, params, created_at, updated_at)
VALUES (%s, %s, 'pending', %s, %s, %s);
"""

_UPDATE = """
UPDATE jobs
SET status = %s, result = %s, error = %s, updated_at = %s
WHERE id = %s;
"""

_SELECT = """
SELECT id, type, status, params, result, error, created_at, updated_at
FROM jobs WHERE id = %s;
"""


class JobRow:
    __slots__ = ("id", "type", "status", "params", "result", "error", "created_at", "updated_at")

    def __init__(
        self,
        id: UUID,
        type: str,
        status: str,
        params: dict[str, Any],
        result: dict[str, Any] | None,
        error: str | None,
        created_at: datetime,
        updated_at: datetime,
    ) -> None:
        self.id = id
        self.type = type
        self.status = status
        self.params = params
        self.result = result
        self.error = error
        self.created_at = created_at
        self.updated_at = updated_at


def ensure_schema_jobs(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute(_CREATE_TABLE)
    conn.commit()


def create_job(conn: psycopg.Connection, job_type: str, params: dict[str, Any]) -> JobRow:
    job_id = uuid4()
    now = datetime.now(tz=timezone.utc)
    with conn.cursor() as cur:
        cur.execute(_INSERT, (str(job_id), job_type, json.dumps(params), now, now))
    conn.commit()
    return JobRow(id=job_id, type=job_type, status="pending", params=params, result=None, error=None, created_at=now, updated_at=now)


def update_job_status(
    conn: psycopg.Connection,
    job_id: UUID,
    status: str,
    result: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    now = datetime.now(tz=timezone.utc)
    result_json = json.dumps(result) if result is not None else None
    with conn.cursor() as cur:
        cur.execute(_UPDATE, (status, result_json, error, now, str(job_id)))
    conn.commit()


def fetch_job(conn: psycopg.Connection, job_id: UUID) -> JobRow | None:
    with conn.cursor() as cur:
        cur.execute(_SELECT, (str(job_id),))
        row = cur.fetchone()
    if row is None:
        return None
    return JobRow(
        id=UUID(str(row[0])),
        type=row[1],
        status=row[2],
        params=row[3] if isinstance(row[3], dict) else json.loads(row[3]),
        result=row[4] if row[4] is None or isinstance(row[4], dict) else json.loads(row[4]),
        error=row[5],
        created_at=row[6],
        updated_at=row[7],
    )
