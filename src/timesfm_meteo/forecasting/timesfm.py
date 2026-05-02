from timesfm_meteo.models import DailyTemperature, QuantileForecast


def forecast_with_timesfm(
    history: list[DailyTemperature],
    forecast_days: int,
) -> list[QuantileForecast]:
    """Run TimesFM forecasting for daily temperature data."""
    raise NotImplementedError
