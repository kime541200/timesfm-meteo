from datetime import date

import pytest
from pydantic import ValidationError

from timesfm_meteo.configs import Settings
from timesfm_meteo.models import DailyTemperature, Location, QuantileForecast


def test_location_accepts_valid_coordinates() -> None:
    location = Location(latitude="25.0", longitude="121.5")

    assert location.latitude == 25.0
    assert location.longitude == 121.5


def test_location_rejects_out_of_range_coordinates() -> None:
    with pytest.raises(ValidationError):
        Location(latitude=91, longitude=0)


def test_daily_temperature_rejects_min_above_max() -> None:
    with pytest.raises(ValidationError):
        DailyTemperature(
            date=date(2026, 5, 2),
            temperature_max=20,
            temperature_min=30,
        )


def test_quantile_forecast_rejects_unordered_quantiles() -> None:
    with pytest.raises(ValidationError):
        QuantileForecast(
            date=date(2026, 5, 2),
            p10=30,
            p50=20,
            p90=10,
        )


def test_settings_has_pipeline_defaults() -> None:
    settings = Settings()

    assert settings.history_years == 2
    assert settings.forecast_days == 3
    assert settings.forecast_quantiles == (0.1, 0.5, 0.9)
