"""Tests for the timesfm-meteo-client CLI using respx to mock HTTP."""
from __future__ import annotations

import json
import os
from unittest.mock import patch
from uuid import uuid4

import pytest
import respx
import httpx

from timesfm_meteo.client.cli import main


@pytest.fixture(autouse=True)
def _set_env(monkeypatch):
    monkeypatch.setenv("TIMESFM_API_URL", "http://testserver")
    monkeypatch.setenv("TIMESFM_API_KEY", "test-key")


# ---------------------------------------------------------------------------
# Auth header injection
# ---------------------------------------------------------------------------

@respx.mock
def test_auth_header_attached(capsys):
    route = respx.get("http://testserver/temperatures").mock(
        return_value=httpx.Response(200, json={"cached_count": 0, "fetched_count": 0, "rows": []})
    )
    rc = main(["temperatures", "get", "--latitude", "25.05", "--longitude", "121.57",
               "--start-date", "2024-06-01", "--end-date", "2024-06-07"])
    assert rc == 0
    assert route.called
    assert route.calls[0].request.headers["authorization"] == "Bearer test-key"


# ---------------------------------------------------------------------------
# temperatures get
# ---------------------------------------------------------------------------

@respx.mock
def test_temperatures_get_prints_json(capsys):
    payload = {"cached_count": 1, "fetched_count": 0, "rows": [{"date": "2024-06-01", "temperature_max": 30.0, "temperature_min": 22.0}]}
    respx.get("http://testserver/temperatures").mock(return_value=httpx.Response(200, json=payload))
    rc = main(["temperatures", "get", "--latitude", "25.05", "--longitude", "121.57",
               "--start-date", "2024-06-01", "--end-date", "2024-06-07"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["cached_count"] == 1


# ---------------------------------------------------------------------------
# forecast run with --no-wait
# ---------------------------------------------------------------------------

@respx.mock
def test_forecast_run_no_wait(capsys):
    job_id = str(uuid4())
    respx.post("http://testserver/forecast").mock(
        return_value=httpx.Response(202, json={"job_id": job_id, "status": "pending"})
    )
    rc = main(["forecast", "run", "--latitude", "25.05", "--longitude", "121.57",
               "--horizon", "3", "--no-wait"])
    assert rc == 0
    out = capsys.readouterr().out
    assert job_id in out


# ---------------------------------------------------------------------------
# forecast run wait-mode (done)
# ---------------------------------------------------------------------------

@respx.mock
def test_forecast_run_wait_done(capsys):
    job_id = str(uuid4())
    respx.post("http://testserver/forecast").mock(
        return_value=httpx.Response(202, json={"job_id": job_id, "status": "pending"})
    )
    respx.get(f"http://testserver/jobs/{job_id}").mock(
        return_value=httpx.Response(200, json={"job_id": job_id, "status": "done", "result": {"horizon": 3}})
    )
    rc = main(["forecast", "run", "--latitude", "25.05", "--longitude", "121.57", "--no-wait"])
    assert rc == 0


# ---------------------------------------------------------------------------
# 401 handling
# ---------------------------------------------------------------------------

@respx.mock
def test_401_exits_nonzero(capsys):
    respx.get("http://testserver/temperatures").mock(return_value=httpx.Response(401))
    with pytest.raises(SystemExit) as exc_info:
        main(["temperatures", "get", "--latitude", "25.05", "--longitude", "121.57",
              "--start-date", "2024-06-01", "--end-date", "2024-06-07"])
    assert exc_info.value.code == 1
    assert "invalid" in capsys.readouterr().err.lower()


# ---------------------------------------------------------------------------
# jobs get 404
# ---------------------------------------------------------------------------

@respx.mock
def test_jobs_get_404(capsys):
    job_id = str(uuid4())
    respx.get(f"http://testserver/jobs/{job_id}").mock(return_value=httpx.Response(404))
    with pytest.raises(SystemExit) as exc_info:
        main(["jobs", "get", job_id])
    assert exc_info.value.code == 1
    assert "not found" in capsys.readouterr().err.lower()


# ---------------------------------------------------------------------------
# Missing env var exits immediately
# ---------------------------------------------------------------------------

def test_missing_api_url_exits(monkeypatch, capsys):
    monkeypatch.delenv("TIMESFM_API_URL", raising=False)
    with pytest.raises(SystemExit) as exc_info:
        main(["temperatures", "get", "--latitude", "25.05", "--longitude", "121.57",
              "--start-date", "2024-06-01", "--end-date", "2024-06-07"])
    assert exc_info.value.code == 1


def test_missing_api_key_exits(monkeypatch, capsys):
    monkeypatch.delenv("TIMESFM_API_KEY", raising=False)
    with pytest.raises(SystemExit) as exc_info:
        main(["temperatures", "get", "--latitude", "25.05", "--longitude", "121.57",
              "--start-date", "2024-06-01", "--end-date", "2024-06-07"])
    assert exc_info.value.code == 1
