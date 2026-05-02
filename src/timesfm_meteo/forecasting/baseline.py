from timesfm_meteo.models import DailyTemperature, QuantileForecast


def forecast_with_baseline(
    history: list[DailyTemperature],
    forecast_days: int,
) -> list[QuantileForecast]:
    """Produce a simple baseline forecast.

    Implementation will be added after the first historical data shape is fixed.
    """
    raise NotImplementedError
