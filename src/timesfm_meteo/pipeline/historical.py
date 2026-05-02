from timesfm_meteo.configs import Settings
from timesfm_meteo.data_sources.open_meteo import fetch_daily_temperatures
from timesfm_meteo.models import DailyTemperature, Location


def load_historical_temperatures(
    location: Location,
    settings: Settings | None = None,
) -> list[DailyTemperature]:
    """Load historical temperatures for a location."""
    resolved_settings = settings or Settings()
    return fetch_daily_temperatures(
        location,
        resolved_settings.history_years,
        settings=resolved_settings.open_meteo,
    )
