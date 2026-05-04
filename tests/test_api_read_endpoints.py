"""Tests for read-only API endpoints using mocked pipeline functions."""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("fastapi", reason="api extra not installed")

from fastapi.testclient import TestClient

from timesfm_meteo.data_sources.open_meteo import OpenMeteoError
from timesfm_meteo.db.forecasts import ForecastRow
from timesfm_meteo.models import DailyTemperature, EvaluationReport, GroupMetrics, Location
from timesfm_meteo.pipeline.historical import FetchResult

_API_KEY = "test-key"
_AUTH = {"Authorization": f"Bearer {_API_KEY}"}


def _make_client() -> tuple[TestClient, MagicMock]:
    from timesfm_meteo.api.app import create_app

    app = create_app()
    app.state.api_key = _API_KEY
    app.state.settings = MagicMock()
    app.state.settings.postgres.dsn = "postgresql://fake/db"
    app.state.settings.open_meteo = MagicMock()
    app.state.engine = MagicMock()

    conn_mock = MagicMock()
    conn_ctx = MagicMock()
    conn_ctx.__enter__ = MagicMock(return_value=conn_mock)
    conn_ctx.__exit__ = MagicMock(return_value=False)
    pool_mock = MagicMock()
    pool_mock.connection.return_value = conn_ctx
    app.state.pool = pool_mock

    return TestClient(app, raise_server_exceptions=True), conn_mock


# ---------------------------------------------------------------------------
# GET /temperatures
# ---------------------------------------------------------------------------

def test_get_temperatures_returns_rows():
    client, conn = _make_client()
    rows = [DailyTemperature(date=date(2024, 6, 1), temperature_max=30.0, temperature_min=22.0)]
    fetch_result = FetchResult(rows=rows, cached_count=1, fetched_count=0)

    with patch("timesfm_meteo.api.routers.temperatures.get_temperatures", return_value=fetch_result):
        resp = client.get(
            "/temperatures?latitude=25.05&longitude=121.57&start_date=2024-06-01&end_date=2024-06-01",
            headers=_AUTH,
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["cached_count"] == 1
    assert data["fetched_count"] == 0
    assert len(data["rows"]) == 1
    assert data["rows"][0]["temperature_max"] == 30.0


def test_get_temperatures_invalid_latitude():
    client, _ = _make_client()
    resp = client.get(
        "/temperatures?latitude=95.0&longitude=121.57&start_date=2024-06-01&end_date=2024-06-01",
        headers=_AUTH,
    )
    assert resp.status_code == 422


def test_get_temperatures_invalid_longitude():
    client, _ = _make_client()
    resp = client.get(
        "/temperatures?latitude=25.05&longitude=200.0&start_date=2024-06-01&end_date=2024-06-01",
        headers=_AUTH,
    )
    assert resp.status_code == 422


def test_get_temperatures_rejects_future_end_date():
    client, _ = _make_client()
    resp = client.get(
        "/temperatures?latitude=25.05&longitude=121.57&start_date=2024-06-01&end_date=2999-01-01",
        headers=_AUTH,
    )
    assert resp.status_code == 422
    assert resp.json()["detail"] == "end_date cannot be after today for historical temperatures"


def test_get_temperatures_rejects_start_date_after_end_date():
    client, _ = _make_client()
    resp = client.get(
        "/temperatures?latitude=25.05&longitude=121.57&start_date=2024-06-02&end_date=2024-06-01",
        headers=_AUTH,
    )
    assert resp.status_code == 422
    assert resp.json()["detail"] == "start_date must be on or before end_date"


def test_get_temperatures_wraps_open_meteo_error_as_bad_gateway():
    client, _ = _make_client()

    with patch(
        "timesfm_meteo.api.routers.temperatures.get_temperatures",
        side_effect=OpenMeteoError("Open-Meteo returned HTTP 400"),
    ):
        resp = client.get(
            "/temperatures?latitude=25.05&longitude=121.57&start_date=2024-06-01&end_date=2024-06-01",
            headers=_AUTH,
        )

    assert resp.status_code == 502
    assert resp.json()["detail"] == "Open-Meteo returned HTTP 400"


# ---------------------------------------------------------------------------
# GET /forecasts
# ---------------------------------------------------------------------------

def test_get_forecasts_returns_list():
    client, _ = _make_client()
    row = ForecastRow(
        start_date=date(2024, 6, 1), target_date=date(2024, 6, 2),
        max_p10=28.0, max_p50=30.0, max_p90=32.0,
        min_p10=20.0, min_p50=22.0, min_p90=24.0,
        model_id="google/timesfm-2.5-200m-pytorch", history_days=730,
    )
    with patch("timesfm_meteo.api.routers.forecasts.fetch_forecasts_in_range", return_value=[row]):
        resp = client.get(
            "/forecasts?latitude=25.05&longitude=121.57&start_date_from=2024-06-01&start_date_to=2024-06-30",
            headers=_AUTH,
        )
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_get_forecasts_invalid_latitude():
    client, _ = _make_client()
    resp = client.get(
        "/forecasts?latitude=-91&longitude=121.57&start_date_from=2024-06-01&start_date_to=2024-06-30",
        headers=_AUTH,
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /evaluate
# ---------------------------------------------------------------------------

def test_get_evaluate_returns_report():
    client, _ = _make_client()
    report = EvaluationReport(
        location=Location(latitude=25.05, longitude=121.57),
        start_date_from=date(2024, 6, 1),
        start_date_to=date(2024, 6, 30),
        horizon_step_filter=None,
        by_horizon_step=[],
        overall=GroupMetrics(evaluated_count=0, pending_count=0, max=None, min=None),
    )
    with patch("timesfm_meteo.api.routers.evaluate.evaluate_forecasts", return_value=report):
        resp = client.get(
            "/evaluate?latitude=25.05&longitude=121.57&start_date_from=2024-06-01&start_date_to=2024-06-30",
            headers=_AUTH,
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["overall"]["evaluated_count"] == 0
