from datetime import date as Date
from datetime import timedelta
from typing import Any

import httpx
from pydantic import ValidationError

from timesfm_meteo.models import DailyTemperature, Location

ARCHIVE_API_URL = "https://archive-api.open-meteo.com/v1/archive"
DAILY_VARIABLES = ("temperature_2m_max", "temperature_2m_min")
DEFAULT_TIMEOUT_SECONDS = 30.0


class OpenMeteoError(RuntimeError):
    """Raised when Open-Meteo data cannot be fetched or parsed."""


def fetch_daily_temperatures(
    location: Location,
    history_years: int,
    *,
    end_date: Date | None = None,
    client: httpx.Client | None = None,
) -> list[DailyTemperature]:
    """Fetch historical daily temperatures from Open-Meteo.

    The default end date is yesterday because today's daily aggregate may not be
    complete yet.
    """
    if history_years < 1:
        raise ValueError("history_years must be greater than or equal to 1")

    resolved_end_date = end_date or Date.today() - timedelta(days=1)
    start_date = _subtract_years(resolved_end_date, history_years)
    params = _build_archive_params(location, start_date, resolved_end_date)
    payload = _fetch_archive_payload(params, client=client)
    return _parse_daily_temperatures(payload)


def _build_archive_params(
    location: Location,
    start_date: Date,
    end_date: Date,
) -> dict[str, str | float]:
    if start_date > end_date:
        raise ValueError("start_date must be less than or equal to end_date")

    return {
        "latitude": location.latitude,
        "longitude": location.longitude,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "daily": ",".join(DAILY_VARIABLES),
        "temperature_unit": "celsius",
        "timezone": "auto",
    }


def _fetch_archive_payload(
    params: dict[str, str | float],
    *,
    client: httpx.Client | None,
) -> dict[str, Any]:
    try:
        if client is None:
            with httpx.Client(timeout=DEFAULT_TIMEOUT_SECONDS) as local_client:
                response = local_client.get(ARCHIVE_API_URL, params=params)
        else:
            response = client.get(ARCHIVE_API_URL, params=params)

        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise OpenMeteoError(f"Open-Meteo returned HTTP {exc.response.status_code}") from exc
    except httpx.RequestError as exc:
        raise OpenMeteoError(f"Open-Meteo request failed: {exc}") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise OpenMeteoError("Open-Meteo returned invalid JSON") from exc

    if not isinstance(payload, dict):
        raise OpenMeteoError("Open-Meteo response must be a JSON object")
    if payload.get("error") is True:
        reason = payload.get("reason", "unknown error")
        raise OpenMeteoError(f"Open-Meteo returned an error: {reason}")
    return payload


def _parse_daily_temperatures(payload: dict[str, Any]) -> list[DailyTemperature]:
    daily = payload.get("daily")
    if not isinstance(daily, dict):
        raise OpenMeteoError("Open-Meteo response is missing daily data")

    dates = _daily_values(daily, "time")
    max_values = _daily_values(daily, "temperature_2m_max")
    min_values = _daily_values(daily, "temperature_2m_min")

    if not (len(dates) == len(max_values) == len(min_values)):
        raise OpenMeteoError("Open-Meteo daily arrays must have the same length")

    temperatures: list[DailyTemperature] = []
    for date_text, temperature_max, temperature_min in zip(
        dates,
        max_values,
        min_values,
        strict=True,
    ):
        if temperature_max is None or temperature_min is None:
            raise OpenMeteoError(f"Open-Meteo daily temperature is missing for {date_text}")

        try:
            temperatures.append(
                DailyTemperature(
                    date=Date.fromisoformat(str(date_text)),
                    temperature_max=temperature_max,
                    temperature_min=temperature_min,
                )
            )
        except (TypeError, ValueError, ValidationError) as exc:
            raise OpenMeteoError(f"Open-Meteo daily data is invalid for {date_text}") from exc

    return temperatures


def _daily_values(daily: dict[str, Any], key: str) -> list[Any]:
    values = daily.get(key)
    if not isinstance(values, list):
        raise OpenMeteoError(f"Open-Meteo daily data is missing {key}")
    return values


def _subtract_years(value: Date, years: int) -> Date:
    try:
        return value.replace(year=value.year - years)
    except ValueError:
        return value.replace(year=value.year - years, day=28)
