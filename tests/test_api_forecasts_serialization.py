from datetime import date
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("fastapi", reason="api extra not installed")

from fastapi.testclient import TestClient

from timesfm_meteo.db.forecasts import ForecastRow


def test_get_forecasts_serializes_dates_as_iso_strings():
    from timesfm_meteo.api.app import create_app
    from timesfm_meteo.api import deps

    app = create_app()
    app.state.api_key = "test-key"
    app.state.settings = MagicMock()
    app.state.engine = None

    def fake_conn():
        yield MagicMock()

    app.dependency_overrides[deps.get_conn] = fake_conn
    row = ForecastRow(
        start_date=date(2024, 4, 4),
        target_date=date(2024, 4, 6),
        max_p10=22.0,
        max_p50=27.5,
        max_p90=32.0,
        min_p10=15.0,
        min_p50=18.7,
        min_p90=21.4,
        model_id="model",
        history_days=732,
    )

    with patch("timesfm_meteo.api.routers.forecasts.fetch_forecasts_in_range", return_value=[row]):
        resp = TestClient(app).get(
            "/forecasts?latitude=25.05&longitude=121.57&start_date_from=2024-04-01&start_date_to=2024-04-30",
            headers={"Authorization": "Bearer test-key"},
        )

    assert resp.status_code == 200
    assert resp.json()[0]["start_date"] == "2024-04-04"
    assert resp.json()[0]["target_date"] == "2024-04-06"
