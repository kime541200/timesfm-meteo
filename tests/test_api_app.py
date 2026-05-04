"""Tests for the FastAPI app skeleton: import, auth, and startup guards."""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("fastapi", reason="api extra not installed")

from fastapi.testclient import TestClient


def _make_app(api_key: str = "test-key", db_url: str = "postgresql://fake/db"):
    """Build a minimal app with mocked lifespan dependencies."""
    from timesfm_meteo.api.app import create_app

    app = create_app()
    # Simulate what lifespan sets on app.state
    app.state.api_key = api_key
    app.state.settings = MagicMock()
    app.state.settings.postgres.dsn = db_url
    app.state.settings.open_meteo = MagicMock()
    app.state.pool = MagicMock()
    app.state.pool.connection.return_value.__enter__ = lambda s: MagicMock()
    app.state.pool.connection.return_value.__exit__ = MagicMock(return_value=False)
    app.state.engine = MagicMock()
    return app


def test_import_ok():
    from timesfm_meteo.api import app as _  # noqa: F401


def test_missing_api_key_rejected():
    app = _make_app(api_key="secret")
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/temperatures?latitude=25.05&longitude=121.57&start_date=2024-01-01&end_date=2024-01-07")
    assert resp.status_code == 401  # missing bearer → 401


def test_wrong_api_key_rejected():
    app = _make_app(api_key="secret")
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get(
        "/temperatures?latitude=25.05&longitude=121.57&start_date=2024-01-01&end_date=2024-01-07",
        headers={"Authorization": "Bearer wrong"},
    )
    assert resp.status_code == 401


def test_correct_api_key_passes_auth():
    """With the correct key the auth dependency passes (endpoint may still fail due to DB mock)."""
    app = _make_app(api_key="secret")

    conn_mock = MagicMock()
    conn_mock.__enter__ = lambda s: conn_mock
    conn_mock.__exit__ = MagicMock(return_value=False)

    with patch("timesfm_meteo.api.deps.get_conn") as mock_dep:
        mock_dep.return_value = conn_mock
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(
            "/jobs/00000000-0000-0000-0000-000000000000",
            headers={"Authorization": "Bearer secret"},
        )
    # 404 means auth passed and the handler ran (job not found in mock)
    assert resp.status_code in (200, 404, 500)
