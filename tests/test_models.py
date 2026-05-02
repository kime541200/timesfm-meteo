from datetime import date

import pytest
from pydantic import ValidationError

from timesfm_meteo.configs import Settings
from timesfm_meteo.models import (
    DailyTemperature,
    DailyTemperatureForecast,
    Location,
    QuantileForecastResult,
    QuantileValues,
)


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


def test_quantile_values_rejects_unordered_quantiles() -> None:
    with pytest.raises(ValidationError):
        QuantileValues(p10=30, p50=20, p90=10)


def test_quantile_values_accepts_equal_quantiles() -> None:
    values = QuantileValues(p10=20, p50=20, p90=20)
    assert values.p10 == values.p50 == values.p90


def test_daily_temperature_forecast_rejects_max_below_min() -> None:
    with pytest.raises(ValidationError):
        DailyTemperatureForecast(
            date=date(2026, 5, 3),
            max=QuantileValues(p10=10, p50=12, p90=14),
            min=QuantileValues(p10=18, p50=20, p90=22),
        )


def test_daily_temperature_forecast_accepts_valid_combination() -> None:
    forecast = DailyTemperatureForecast(
        date=date(2026, 5, 3),
        max=QuantileValues(p10=24, p50=26, p90=28),
        min=QuantileValues(p10=18, p50=20, p90=22),
    )
    assert forecast.date == date(2026, 5, 3)
    assert forecast.max.p50 == 26
    assert forecast.min.p50 == 20


def test_quantile_forecast_result_validates_lengths() -> None:
    with pytest.raises(ValidationError):
        QuantileForecastResult(
            horizon=3,
            point=[1.0, 2.0],  # length mismatch
            quantiles={0.5: [1.0, 2.0, 3.0]},
        )


def test_quantile_forecast_result_validates_quantile_lengths() -> None:
    with pytest.raises(ValidationError):
        QuantileForecastResult(
            horizon=3,
            point=[1.0, 2.0, 3.0],
            quantiles={0.5: [1.0, 2.0]},  # length mismatch
        )


def test_quantile_forecast_result_round_trip_json() -> None:
    result = QuantileForecastResult(
        horizon=2,
        point=[10.0, 11.0],
        quantiles={0.1: [9.0, 9.5], 0.5: [10.0, 11.0], 0.9: [11.0, 12.5]},
    )
    rebuilt = QuantileForecastResult.model_validate_json(result.model_dump_json())
    assert rebuilt == result


def test_settings_has_pipeline_defaults() -> None:
    settings = Settings()

    assert settings.history_years == 2
    assert settings.forecast_days == 3
