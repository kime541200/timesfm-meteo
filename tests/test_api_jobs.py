"""Tests for async job endpoints (POST /forecast, POST /fetch-history, GET /jobs/{id})."""
from __future__ import annotations

import asyncio
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

pytest.importorskip("fastapi", reason="api extra not installed")

from fastapi.testclient import TestClient

from timesfm_meteo.db.jobs import JobRow

_API_KEY = "test-key"
_AUTH = {"Authorization": f"Bearer {_API_KEY}"}


def _make_client() -> TestClient:
    from timesfm_meteo.api.app import create_app

    app = create_app()
    app.state.api_key = _API_KEY
    app.state.settings = MagicMock()
    app.state.settings.postgres.dsn = "postgresql://fake/db"
    app.state.settings.forecast_days = 3
    app.state.settings.history_years = 2
    app.state.settings.timesfm.model_id = "google/timesfm-2.5-200m-pytorch"
    app.state.settings.open_meteo = MagicMock()
    app.state.engine = MagicMock()

    conn_mock = MagicMock()
    conn_ctx = MagicMock()
    conn_ctx.__enter__ = MagicMock(return_value=conn_mock)
    conn_ctx.__exit__ = MagicMock(return_value=False)
    pool_mock = MagicMock()
    pool_mock.connection.return_value = conn_ctx
    app.state.pool = pool_mock

    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# POST /forecast
# ---------------------------------------------------------------------------

def test_post_forecast_returns_job_id():
    from datetime import datetime, timezone

    client = _make_client()

    _job = JobRow(
        id=uuid4(), type="forecast", status="pending",
        params={"latitude": 25.05, "longitude": 121.57, "start_date": "2024-06-01"},
        result=None, error=None,
        created_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
    )

    with patch("timesfm_meteo.api.routers.forecasts.create_job", return_value=_job), \
         patch("timesfm_meteo.api.routers.forecasts.run_forecast_job", new=AsyncMock(return_value=None)):
        resp = client.post(
            "/forecast",
            json={"latitude": 25.05, "longitude": 121.57, "start_date": "2024-06-01"},
            headers=_AUTH,
        )
    assert resp.status_code == 202
    body = resp.json()
    assert "job_id" in body
    assert body["status"] == "pending"


def test_post_forecast_invalid_coords():
    client = _make_client()
    resp = client.post(
        "/forecast",
        json={"latitude": 95.0, "longitude": 121.57},
        headers=_AUTH,
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /fetch-history
# ---------------------------------------------------------------------------

def test_post_fetch_history_returns_job_id():
    from datetime import datetime, timezone

    client = _make_client()

    _job = JobRow(
        id=uuid4(), type="fetch-history", status="pending",
        params={"latitude": 25.05, "longitude": 121.57, "years": 2},
        result=None, error=None,
        created_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
    )

    with patch("timesfm_meteo.api.routers.fetch_history.create_job", return_value=_job), \
         patch("timesfm_meteo.api.routers.fetch_history.run_fetch_history_job", new=AsyncMock(return_value=None)):
        resp = client.post(
            "/fetch-history",
            json={"latitude": 25.05, "longitude": 121.57, "years": 2},
            headers=_AUTH,
        )
    assert resp.status_code == 202
    assert "job_id" in resp.json()


def test_post_fetch_history_missing_date_spec():
    client = _make_client()
    resp = client.post(
        "/fetch-history",
        json={"latitude": 25.05, "longitude": 121.57},
        headers=_AUTH,
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /jobs/{job_id}
# ---------------------------------------------------------------------------

def test_get_job_returns_state():
    from datetime import datetime, timezone

    client = _make_client()
    job_id = uuid4()
    _job = JobRow(
        id=job_id, type="forecast", status="done",
        params={"latitude": 25.05, "longitude": 121.57},
        result={"horizon": 3}, error=None,
        created_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
    )
    with patch("timesfm_meteo.api.routers.jobs.fetch_job", return_value=_job):
        resp = client.get(f"/jobs/{job_id}", headers=_AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "done"
    assert data["result"] == {"horizon": 3}
    assert data["error"] is None


def test_get_job_unknown_returns_404():
    client = _make_client()
    with patch("timesfm_meteo.api.routers.jobs.fetch_job", return_value=None):
        resp = client.get(f"/jobs/{uuid4()}", headers=_AUTH)
    assert resp.status_code == 404


def test_get_job_failed_has_error():
    from datetime import datetime, timezone

    client = _make_client()
    job_id = uuid4()
    _job = JobRow(
        id=job_id, type="forecast", status="failed",
        params={}, result=None, error="model load failed",
        created_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
    )
    with patch("timesfm_meteo.api.routers.jobs.fetch_job", return_value=_job):
        resp = client.get(f"/jobs/{job_id}", headers=_AUTH)
    assert resp.status_code == 200
    assert resp.json()["status"] == "failed"
    assert resp.json()["error"] == "model load failed"
