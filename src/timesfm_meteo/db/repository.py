from datetime import date as Date
from decimal import Decimal

import psycopg

from timesfm_meteo.models import DailyTemperature, Location

_COORD_PRECISION = Decimal("0.0001")

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS daily_temperatures (
    latitude        NUMERIC(8, 4) NOT NULL,
    longitude       NUMERIC(8, 4) NOT NULL,
    date            DATE          NOT NULL,
    temperature_max REAL          NOT NULL,
    temperature_min REAL          NOT NULL,
    PRIMARY KEY (latitude, longitude, date)
);
"""

_UPSERT = """
INSERT INTO daily_temperatures (latitude, longitude, date, temperature_max, temperature_min)
VALUES (%s, %s, %s, %s, %s)
ON CONFLICT (latitude, longitude, date) DO UPDATE
    SET temperature_max = EXCLUDED.temperature_max,
        temperature_min = EXCLUDED.temperature_min;
"""

_SELECT = """
SELECT date, temperature_max, temperature_min
FROM daily_temperatures
WHERE latitude = %s AND longitude = %s AND date BETWEEN %s AND %s
ORDER BY date;
"""


def _round_coord(value: float) -> Decimal:
    return Decimal(str(value)).quantize(_COORD_PRECISION)


def ensure_schema(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute(_CREATE_TABLE)
    conn.commit()


def upsert_temperatures(
    conn: psycopg.Connection,
    location: Location,
    rows: list[DailyTemperature],
) -> None:
    if not rows:
        return
    lat = _round_coord(location.latitude)
    lon = _round_coord(location.longitude)
    params = [(lat, lon, row.date, row.temperature_max, row.temperature_min) for row in rows]
    with conn.cursor() as cur:
        cur.executemany(_UPSERT, params)
    conn.commit()


def fetch_temperatures(
    conn: psycopg.Connection,
    location: Location,
    start_date: Date,
    end_date: Date,
) -> list[DailyTemperature]:
    lat = _round_coord(location.latitude)
    lon = _round_coord(location.longitude)
    with conn.cursor() as cur:
        cur.execute(_SELECT, (lat, lon, start_date, end_date))
        return [
            DailyTemperature(date=row[0], temperature_max=row[1], temperature_min=row[2])
            for row in cur.fetchall()
        ]
