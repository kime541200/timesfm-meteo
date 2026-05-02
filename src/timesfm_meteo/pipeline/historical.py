from datetime import date as Date, timedelta
from typing import NamedTuple

import psycopg

from timesfm_meteo.configs import OpenMeteoSettings, Settings
from timesfm_meteo.data_sources.open_meteo import fetch_daily_temperatures
from timesfm_meteo.db.repository import fetch_temperatures, upsert_temperatures
from timesfm_meteo.models import DailyTemperature, Location


class FetchResult(NamedTuple):
    rows: list[DailyTemperature]
    cached_count: int
    fetched_count: int


def load_historical_temperatures(
    location: Location,
    settings: Settings | None = None,
) -> list[DailyTemperature]:
    """Load historical temperatures directly from Open-Meteo (no DB)."""
    resolved_settings = settings or Settings()
    return fetch_daily_temperatures(
        location,
        resolved_settings.history_years,
        settings=resolved_settings.open_meteo,
    )


def get_temperatures(
    location: Location,
    start_date: Date,
    end_date: Date,
    conn: psycopg.Connection,
    settings: OpenMeteoSettings | None = None,
) -> FetchResult:
    """Return temperatures for the date range, fetching missing days from Open-Meteo and caching them."""
    existing = fetch_temperatures(conn, location, start_date, end_date)
    existing_dates = {r.date for r in existing}
    cached_count = len(existing)

    all_dates = {start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1)}
    missing_dates = all_dates - existing_dates

    if not missing_dates:
        return FetchResult(rows=existing, cached_count=cached_count, fetched_count=0)

    fetched = fetch_daily_temperatures(
        location,
        start_date=min(missing_dates),
        end_date=max(missing_dates),
        settings=settings,
    )
    upsert_temperatures(conn, location, fetched)

    merged = {r.date: r for r in existing}
    merged.update({r.date: r for r in fetched})
    rows = sorted(merged.values(), key=lambda r: r.date)
    fetched_count = len(rows) - cached_count
    return FetchResult(rows=rows, cached_count=cached_count, fetched_count=fetched_count)
