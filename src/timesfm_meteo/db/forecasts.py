from datetime import date as Date, datetime, timezone
from decimal import Decimal
from typing import NamedTuple

import psycopg

from timesfm_meteo.models import DailyTemperatureForecast, Location

_COORD_PRECISION = Decimal("0.0001")

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS forecasts (
    latitude     NUMERIC(8, 4) NOT NULL,
    longitude    NUMERIC(8, 4) NOT NULL,
    start_date   DATE          NOT NULL,
    target_date  DATE          NOT NULL,
    max_p10      REAL          NOT NULL,
    max_p50      REAL          NOT NULL,
    max_p90      REAL          NOT NULL,
    min_p10      REAL          NOT NULL,
    min_p50      REAL          NOT NULL,
    min_p90      REAL          NOT NULL,
    model_id     TEXT          NOT NULL,
    history_days INT           NOT NULL,
    run_at       TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    PRIMARY KEY (latitude, longitude, start_date, target_date)
);
"""

_UPSERT = """
INSERT INTO forecasts (
    latitude, longitude, start_date, target_date,
    max_p10, max_p50, max_p90,
    min_p10, min_p50, min_p90,
    model_id, history_days, run_at
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (latitude, longitude, start_date, target_date) DO UPDATE
    SET max_p10      = EXCLUDED.max_p10,
        max_p50      = EXCLUDED.max_p50,
        max_p90      = EXCLUDED.max_p90,
        min_p10      = EXCLUDED.min_p10,
        min_p50      = EXCLUDED.min_p50,
        min_p90      = EXCLUDED.min_p90,
        model_id     = EXCLUDED.model_id,
        history_days = EXCLUDED.history_days,
        run_at       = EXCLUDED.run_at;
"""

_SELECT = """
SELECT start_date, target_date,
       max_p10, max_p50, max_p90,
       min_p10, min_p50, min_p90,
       model_id, history_days
FROM forecasts
WHERE latitude = %s AND longitude = %s
  AND start_date BETWEEN %s AND %s
  {horizon_filter}
ORDER BY start_date, target_date;
"""


class ForecastRow(NamedTuple):
    start_date: Date
    target_date: Date
    max_p10: float
    max_p50: float
    max_p90: float
    min_p10: float
    min_p50: float
    min_p90: float
    model_id: str
    history_days: int


def _round_coord(value: float) -> Decimal:
    return Decimal(str(value)).quantize(_COORD_PRECISION)


def ensure_schema_forecasts(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute(_CREATE_TABLE)
    conn.commit()


def upsert_forecasts(
    conn: psycopg.Connection,
    location: Location,
    start_date: Date,
    forecasts: list[DailyTemperatureForecast],
    model_id: str,
    history_days: int,
) -> None:
    if not forecasts:
        return
    lat = _round_coord(location.latitude)
    lon = _round_coord(location.longitude)
    run_at = datetime.now(tz=timezone.utc)
    params = [
        (
            lat, lon, start_date, row.date,
            row.max.p10, row.max.p50, row.max.p90,
            row.min.p10, row.min.p50, row.min.p90,
            model_id, history_days, run_at,
        )
        for row in forecasts
    ]
    with conn.cursor() as cur:
        cur.executemany(_UPSERT, params)
    conn.commit()


def fetch_forecasts_in_range(
    conn: psycopg.Connection,
    location: Location,
    start_date_from: Date,
    start_date_to: Date,
    horizon_step_filter: int | None = None,
) -> list[ForecastRow]:
    lat = _round_coord(location.latitude)
    lon = _round_coord(location.longitude)
    if horizon_step_filter is not None:
        horizon_clause = "AND (target_date - start_date) = %s"
        extra_params: tuple = (horizon_step_filter,)
    else:
        horizon_clause = ""
        extra_params = ()
    sql = _SELECT.format(horizon_filter=horizon_clause)
    with conn.cursor() as cur:
        cur.execute(sql, (lat, lon, start_date_from, start_date_to) + extra_params)
        return [ForecastRow(*row) for row in cur.fetchall()]
