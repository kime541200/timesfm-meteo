from pydantic import BaseModel, ConfigDict, Field


class Settings(BaseModel):
    """Runtime settings for the local forecasting pipeline."""

    model_config = ConfigDict(frozen=True)

    history_years: int = Field(2, ge=1, le=100, description="Number of years of historical data to load")
    forecast_days: int = Field(3, ge=1, le=365, description="Number of days to forecast")
    forecast_quantiles: tuple[float, ...] = Field(
        (0.1, 0.5, 0.9),
        description="Quantiles to forecast",
    )
