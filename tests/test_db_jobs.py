import os
from uuid import UUID

import pytest

_DSN = os.environ.get("DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not _DSN, reason="DATABASE_URL not set")


@pytest.fixture()
def conn():
    import psycopg
    from timesfm_meteo.db.jobs import ensure_schema_jobs

    with psycopg.connect(_DSN) as c:
        ensure_schema_jobs(c)
        yield c
        c.execute("DELETE FROM jobs WHERE type IN ('forecast', 'fetch-history') AND params->>'_test' = 'true'")
        c.commit()


def test_create_job(conn):
    from timesfm_meteo.db.jobs import create_job

    job = create_job(conn, "forecast", {"_test": "true", "latitude": 25.05})
    assert isinstance(job.id, UUID)
    assert job.status == "pending"
    assert job.type == "forecast"
    assert job.params["latitude"] == 25.05
    assert job.result is None
    assert job.error is None


def test_update_job_to_done(conn):
    from timesfm_meteo.db.jobs import create_job, fetch_job, update_job_status

    job = create_job(conn, "forecast", {"_test": "true"})
    update_job_status(conn, job.id, "running")
    mid = fetch_job(conn, job.id)
    assert mid is not None
    assert mid.status == "running"

    update_job_status(conn, job.id, "done", result={"horizon": 3})
    done = fetch_job(conn, job.id)
    assert done is not None
    assert done.status == "done"
    assert done.result == {"horizon": 3}
    assert done.error is None


def test_update_job_to_failed(conn):
    from timesfm_meteo.db.jobs import create_job, fetch_job, update_job_status

    job = create_job(conn, "fetch-history", {"_test": "true"})
    update_job_status(conn, job.id, "failed", error="something went wrong")
    row = fetch_job(conn, job.id)
    assert row is not None
    assert row.status == "failed"
    assert row.error == "something went wrong"


def test_fetch_unknown_job(conn):
    from uuid import uuid4

    from timesfm_meteo.db.jobs import fetch_job

    assert fetch_job(conn, uuid4()) is None


def test_ensure_schema_idempotent(conn):
    from timesfm_meteo.db.jobs import ensure_schema_jobs

    ensure_schema_jobs(conn)  # second call must not raise
