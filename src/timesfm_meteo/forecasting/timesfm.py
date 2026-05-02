"""Domain adapter: maps `DailyTemperature` history to engine inputs and back."""

from __future__ import annotations

from datetime import date as Date
from typing import TYPE_CHECKING

from timesfm_meteo.models import DailyTemperature, DailyTemperatureForecast, QuantileValues

if TYPE_CHECKING:
    from timesfm_meteo.inference.timesfm_engine import ForecastEngine


def forecast_with_timesfm(
    history: list[DailyTemperature],
    forecast_dates: list[Date],
    engine: ForecastEngine,
) -> list[DailyTemperatureForecast]:
    """Run TimesFM forecasting for daily max / min temperature.

    The engine is injected so callers (CLI, tests) can supply a mock or a
    remote client without changing this module.
    """
    if not history:
        raise ValueError("history must contain at least one DailyTemperature")
    if not forecast_dates:
        raise ValueError("forecast_dates must contain at least one date")

    import numpy as np

    max_series = np.array([row.temperature_max for row in history], dtype=np.float32)
    min_series = np.array([row.temperature_min for row in history], dtype=np.float32)

    horizon = len(forecast_dates)
    max_result, min_result = engine.forecast([max_series, min_series], horizon=horizon)

    forecasts: list[DailyTemperatureForecast] = []
    for i, target_date in enumerate(forecast_dates):
        forecasts.append(
            DailyTemperatureForecast(
                date=target_date,
                max=QuantileValues(
                    p10=max_result.quantiles[0.1][i],
                    p50=max_result.quantiles[0.5][i],
                    p90=max_result.quantiles[0.9][i],
                ),
                min=QuantileValues(
                    p10=min_result.quantiles[0.1][i],
                    p50=min_result.quantiles[0.5][i],
                    p90=min_result.quantiles[0.9][i],
                ),
            )
        )
    return forecasts
