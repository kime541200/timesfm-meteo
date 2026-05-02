from timesfm_meteo.configs import Settings
from timesfm_meteo.models import Location, QuantileForecast


def forecast_location(location: Location, settings: Settings | None = None) -> list[QuantileForecast]:
    """Forecast temperatures for a location.

    Implementation will connect the Open-Meteo source and forecasting adapter.
    """
    _ = settings or Settings()
    raise NotImplementedError
