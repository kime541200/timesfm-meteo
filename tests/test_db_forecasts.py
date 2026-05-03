import os
from datetime import date

import pytest

from timesfm_meteo.db.forecasts import ensure_schema_forecasts, fetch_forecasts_in_range, upsert_forecasts
from timesfm_meteo.models import DailyTemperatureForecast, Location, QuantileValues

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set",
)

_LOC = Location(latitude=25.05, longitude=121.57)
_START = date(2024, 6, 1)
_FORECASTS = [
    DailyTemperatureForecast(
        date=date(2024, 6, 1),
        max=QuantileValues(p10=26.0, p50=28.0, p90=30.0),
        min=QuantileValues(p10=18.0, p50=20.0, p90=22.0),
    ),
    DailyTemperatureForecast(
        date=date(2024, 6, 2),
        max=QuantileValues(p10=27.0, p50=29.0, p90=31.0),
        min=QuantileValues(p10=19.0, p50=21.0, p90=23.0),
    ),
    DailyTemperatureForecast(
        date=date(2024, 6, 3),
        max=QuantileValues(p10=28.0, p50=30.0, p90=32.0),
        min=QuantileValues(p10=20.0, p50=22.0, p90=24.0),
    ),
]


@pytest.fixture
def conn():
    import psycopg

    dsn = os.environ["DATABASE_URL"]
    with psycopg.connect(dsn) as connection:
        ensure_schema_forecasts(connection)
        yield connection
        connection.execute(
            "DELETE FROM forecasts WHERE latitude = 25.0500 AND longitude = 121.5700 AND start_date = %s",
            (_START,),
        )
        connection.commit()


def test_ensure_schema_is_idempotent(conn):
    ensure_schema_forecasts(conn)  # second call should not raise


def test_upsert_and_fetch(conn):
    upsert_forecasts(conn, _LOC, _START, _FORECASTS, "test-model", 730)
    rows = fetch_forecasts_in_range(conn, _LOC, _START, date(2024, 6, 3))
    assert len(rows) == 3
    assert rows[0].target_date == date(2024, 6, 1)
    assert rows[0].max_p50 == pytest.approx(28.0)
    assert rows[0].min_p10 == pytest.approx(18.0)
    assert rows[0].model_id == "test-model"
    assert rows[0].history_days == 730


def test_upsert_overwrites_existing(conn):
    upsert_forecasts(conn, _LOC, _START, _FORECASTS, "model-v1", 730)
    updated = [
        DailyTemperatureForecast(
            date=date(2024, 6, 1),
            max=QuantileValues(p10=30.0, p50=32.0, p90=34.0),
            min=QuantileValues(p10=22.0, p50=24.0, p90=26.0),
        )
    ]
    upsert_forecasts(conn, _LOC, _START, updated, "model-v2", 365)
    # horizon_step=0 selects only target_date==start_date (2024-06-01)
    rows = fetch_forecasts_in_range(conn, _LOC, _START, date(2024, 6, 1), horizon_step_filter=0)
    assert len(rows) == 1
    assert rows[0].max_p50 == pytest.approx(32.0)
    assert rows[0].model_id == "model-v2"
    assert rows[0].history_days == 365


def test_start_date_range_filter(conn):
    upsert_forecasts(conn, _LOC, _START, _FORECASTS, "test-model", 730)
    rows = fetch_forecasts_in_range(conn, _LOC, date(2024, 6, 2), date(2024, 6, 2))
    # start_date filter is on the forecast's start_date, not target_date
    assert len(rows) == 0  # all 3 rows have start_date=2024-06-01, not 2024-06-02


def test_horizon_step_filter(conn):
    upsert_forecasts(conn, _LOC, _START, _FORECASTS, "test-model", 730)
    # horizon_step=0: target_date == start_date (2024-06-01 - 2024-06-01 = 0)
    rows_step0 = fetch_forecasts_in_range(conn, _LOC, _START, date(2024, 6, 1), horizon_step_filter=0)
    assert len(rows_step0) == 1
    assert rows_step0[0].target_date == date(2024, 6, 1)

    # horizon_step=2: target_date = 2024-06-03 (offset 2)
    rows_step2 = fetch_forecasts_in_range(conn, _LOC, _START, date(2024, 6, 1), horizon_step_filter=2)
    assert len(rows_step2) == 1
    assert rows_step2[0].target_date == date(2024, 6, 3)


def test_fetch_empty_when_no_rows(conn):
    rows = fetch_forecasts_in_range(conn, _LOC, date(2099, 1, 1), date(2099, 1, 31))
    assert rows == []


def test_upsert_empty_list_is_noop(conn):
    upsert_forecasts(conn, _LOC, _START, [], "test-model", 730)
    rows = fetch_forecasts_in_range(conn, _LOC, _START, date(2024, 6, 3))
    assert rows == []
