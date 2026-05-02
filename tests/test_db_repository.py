import os
from datetime import date

import pytest

from timesfm_meteo.db.repository import ensure_schema, fetch_temperatures, upsert_temperatures
from timesfm_meteo.models import DailyTemperature, Location

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set",
)


@pytest.fixture
def conn():
    import psycopg

    dsn = os.environ["DATABASE_URL"]
    with psycopg.connect(dsn) as connection:
        ensure_schema(connection)
        yield connection
        connection.execute("DELETE FROM daily_temperatures WHERE latitude = 25.0500 AND longitude = 121.5700")
        connection.commit()


_LOCATION = Location(latitude=25.05, longitude=121.57)
_ROWS = [
    DailyTemperature(date=date(2024, 1, 1), temperature_max=18.0, temperature_min=12.0),
    DailyTemperature(date=date(2024, 1, 2), temperature_max=19.5, temperature_min=13.5),
]


def test_upsert_and_fetch(conn):
    upsert_temperatures(conn, _LOCATION, _ROWS)
    result = fetch_temperatures(conn, _LOCATION, date(2024, 1, 1), date(2024, 1, 2))
    assert len(result) == 2
    assert result[0].date == date(2024, 1, 1)
    assert result[0].temperature_max == pytest.approx(18.0)
    assert result[1].date == date(2024, 1, 2)


def test_upsert_overwrites(conn):
    upsert_temperatures(conn, _LOCATION, _ROWS)
    updated = [DailyTemperature(date=date(2024, 1, 1), temperature_max=20.0, temperature_min=14.0)]
    upsert_temperatures(conn, _LOCATION, updated)
    result = fetch_temperatures(conn, _LOCATION, date(2024, 1, 1), date(2024, 1, 1))
    assert result[0].temperature_max == pytest.approx(20.0)


def test_fetch_empty_range(conn):
    result = fetch_temperatures(conn, _LOCATION, date(2000, 1, 1), date(2000, 1, 31))
    assert result == []


def test_upsert_empty_rows(conn):
    upsert_temperatures(conn, _LOCATION, [])
    result = fetch_temperatures(conn, _LOCATION, date(2024, 1, 1), date(2024, 1, 2))
    assert result == []
