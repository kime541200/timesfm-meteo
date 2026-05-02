from timesfm_meteo.models import DailyTemperature, Location


def fetch_daily_temperatures(location: Location, history_years: int) -> list[DailyTemperature]:
    """Fetch historical daily temperatures from Open-Meteo.

    Implementation will be added with the Open-Meteo data pipeline.
    """
    raise NotImplementedError
