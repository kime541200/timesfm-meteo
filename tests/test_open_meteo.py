from datetime import date

import httpx
import pytest

from timesfm_meteo.data_sources.open_meteo import (
    OpenMeteoError,
    _build_archive_params,
    _parse_daily_temperatures,
    fetch_daily_temperatures,
)
from timesfm_meteo.configs import OpenMeteoSettings
from timesfm_meteo.models import Location


def open_meteo_settings() -> OpenMeteoSettings:
    return OpenMeteoSettings()


def test_build_archive_params() -> None:
    params = _build_archive_params(
        Location(latitude=25.0, longitude=121.5),
        date(2024, 1, 1),
        date(2024, 1, 31),
    )

    assert params == {
        "latitude": 25.0,
        "longitude": 121.5,
        "start_date": "2024-01-01",
        "end_date": "2024-01-31",
        "daily": "temperature_2m_max,temperature_2m_min",
        "temperature_unit": "celsius",
        "timezone": "auto",
    }


def test_parse_daily_temperatures() -> None:
    temperatures = _parse_daily_temperatures(
        {
            "daily": {
                "time": ["2024-01-01", "2024-01-02"],
                "temperature_2m_max": [20.5, 21.0],
                "temperature_2m_min": [12.0, 13.5],
            }
        }
    )

    assert [temperature.date for temperature in temperatures] == [
        date(2024, 1, 1),
        date(2024, 1, 2),
    ]
    assert temperatures[0].temperature_max == 20.5
    assert temperatures[0].temperature_min == 12.0


def test_parse_daily_temperatures_rejects_mismatched_lengths() -> None:
    with pytest.raises(OpenMeteoError, match="same length"):
        _parse_daily_temperatures(
            {
                "daily": {
                    "time": ["2024-01-01", "2024-01-02"],
                    "temperature_2m_max": [20.5],
                    "temperature_2m_min": [12.0, 13.5],
                }
            }
        )


def test_fetch_daily_temperatures_uses_archive_api() -> None:
    settings = open_meteo_settings()

    def handler(request: httpx.Request) -> httpx.Response:
        params = request.url.params

        assert str(request.url).startswith(settings.archive_api_url)
        assert params["latitude"] == "25.0"
        assert params["longitude"] == "121.5"
        assert params["start_date"] == "2022-05-01"
        assert params["end_date"] == "2024-05-01"
        assert params["daily"] == "temperature_2m_max,temperature_2m_min"
        assert params["temperature_unit"] == "celsius"
        assert params["timezone"] == "auto"

        return httpx.Response(
            200,
            json={
                "daily": {
                    "time": ["2024-05-01"],
                    "temperature_2m_max": [29.0],
                    "temperature_2m_min": [21.0],
                }
            },
            request=request,
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))

    temperatures = fetch_daily_temperatures(
        Location(latitude=25.0, longitude=121.5),
        2,
        end_date=date(2024, 5, 1),
        client=client,
        settings=settings,
    )

    assert len(temperatures) == 1
    assert temperatures[0].temperature_max == 29.0
    assert temperatures[0].temperature_min == 21.0


def test_fetch_daily_temperatures_uses_explicit_start_date() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        params = request.url.params

        assert params["start_date"] == "2024-04-25"
        assert params["end_date"] == "2024-05-01"

        return httpx.Response(
            200,
            json={
                "daily": {
                    "time": ["2024-05-01"],
                    "temperature_2m_max": [29.0],
                    "temperature_2m_min": [21.0],
                }
            },
            request=request,
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))

    temperatures = fetch_daily_temperatures(
        Location(latitude=25.0, longitude=121.5),
        start_date=date(2024, 4, 25),
        end_date=date(2024, 5, 1),
        client=client,
        settings=open_meteo_settings(),
    )

    assert len(temperatures) == 1


def test_fetch_daily_temperatures_rejects_missing_start_strategy() -> None:
    with pytest.raises(ValueError, match="start_date or history_years"):
        fetch_daily_temperatures(
            Location(latitude=25.0, longitude=121.5),
            end_date=date(2024, 5, 1),
        )


def test_fetch_daily_temperatures_rejects_start_date_after_end_date() -> None:
    with pytest.raises(ValueError, match="start_date"):
        fetch_daily_temperatures(
            Location(latitude=25.0, longitude=121.5),
            start_date=date(2024, 5, 2),
            end_date=date(2024, 5, 1),
        )


def test_fetch_daily_temperatures_rejects_future_end_date() -> None:
    with pytest.raises(ValueError, match="today"):
        fetch_daily_temperatures(
            Location(latitude=25.0, longitude=121.5),
            start_date=date(2024, 5, 1),
            end_date=date(2999, 1, 1),
        )


def test_fetch_daily_temperatures_wraps_http_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": True}, request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))

    with pytest.raises(OpenMeteoError, match="HTTP 500"):
        fetch_daily_temperatures(
            Location(latitude=25.0, longitude=121.5),
            2,
            end_date=date(2024, 5, 1),
            client=client,
            settings=open_meteo_settings(),
        )


def test_fetch_daily_temperatures_wraps_open_meteo_error_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"error": True, "reason": "Invalid latitude"},
            request=request,
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))

    with pytest.raises(OpenMeteoError, match="Invalid latitude"):
        fetch_daily_temperatures(
            Location(latitude=25.0, longitude=121.5),
            2,
            end_date=date(2024, 5, 1),
            client=client,
            settings=open_meteo_settings(),
        )


def test_fetch_daily_temperatures_uses_open_meteo_settings() -> None:
    settings = OpenMeteoSettings(
        archive_api_url="https://example.test/archive",
        daily_variables=("temperature_2m_max", "temperature_2m_min", "weather_code"),
        default_timeout_seconds=5,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        params = request.url.params

        assert str(request.url).startswith("https://example.test/archive")
        assert params["daily"] == "temperature_2m_max,temperature_2m_min,weather_code"

        return httpx.Response(
            200,
            json={
                "daily": {
                    "time": ["2024-05-01"],
                    "temperature_2m_max": [29.0],
                    "temperature_2m_min": [21.0],
                    "weather_code": [1],
                }
            },
            request=request,
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))

    temperatures = fetch_daily_temperatures(
        Location(latitude=25.0, longitude=121.5),
        start_date=date(2024, 5, 1),
        end_date=date(2024, 5, 1),
        client=client,
        settings=settings,
    )

    assert len(temperatures) == 1
