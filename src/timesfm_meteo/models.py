from datetime import date as Date

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProjectModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class Location(ProjectModel):
    latitude: float = Field(..., ge=-90, le=90, description="Latitude in degrees")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude in degrees")


class DailyTemperature(ProjectModel):
    date: Date = Field(..., ge=Date(1900, 1, 1), description="Date in YYYY-MM-DD format")
    temperature_max: float = Field(..., ge=-100, le=100, description="Maximum temperature in degrees Celsius")
    temperature_min: float = Field(..., ge=-100, le=100, description="Minimum temperature in degrees Celsius")

    @model_validator(mode="after")
    def validate_temperature_range(self) -> "DailyTemperature":
        if self.temperature_min > self.temperature_max:
            raise ValueError("temperature_min must be less than or equal to temperature_max")
        return self


class QuantileValues(ProjectModel):
    p10: float = Field(..., ge=-100, le=100, description="10th percentile in degrees Celsius")
    p50: float = Field(..., ge=-100, le=100, description="50th percentile (median) in degrees Celsius")
    p90: float = Field(..., ge=-100, le=100, description="90th percentile in degrees Celsius")

    @model_validator(mode="after")
    def validate_quantile_order(self) -> "QuantileValues":
        if not self.p10 <= self.p50 <= self.p90:
            raise ValueError("quantiles must satisfy p10 <= p50 <= p90")
        return self


class DailyTemperatureForecast(ProjectModel):
    date: Date = Field(..., ge=Date(1900, 1, 1), description="Forecast target date")
    max: QuantileValues = Field(..., description="Quantile forecast for daily maximum temperature")
    min: QuantileValues = Field(..., description="Quantile forecast for daily minimum temperature")

    @model_validator(mode="after")
    def validate_max_above_min(self) -> "DailyTemperatureForecast":
        if self.max.p50 < self.min.p50:
            raise ValueError("max.p50 must be greater than or equal to min.p50")
        return self


class QuantileForecastResult(ProjectModel):
    """Engine-level forecast result for a single input series.

    JSON-serializable by design: lists (not numpy arrays) so the type can
    cross a future inference-server boundary without custom encoders.
    """

    horizon: int = Field(..., gt=0, description="Number of forecast steps")
    point: list[float] = Field(..., description="Mean forecast, length = horizon")
    quantiles: dict[float, list[float]] = Field(
        ...,
        description="Quantile forecasts keyed by quantile (e.g. 0.1, 0.5, 0.9); each list length = horizon",
    )

    @model_validator(mode="after")
    def validate_lengths(self) -> "QuantileForecastResult":
        if len(self.point) != self.horizon:
            raise ValueError("point length must equal horizon")
        for q, values in self.quantiles.items():
            if len(values) != self.horizon:
                raise ValueError(f"quantile {q} length must equal horizon")
        return self


class ForecastResponse(ProjectModel):
    """CLI-level response wrapping a list of daily forecasts plus run metadata."""

    model: str = Field(..., description="Model identifier used for forecasting")
    history_days: int = Field(..., ge=0, description="Number of historical days fed to the model")
    horizon: int = Field(..., gt=0, description="Number of forecast days produced")
    forecasts: list[DailyTemperatureForecast] = Field(..., description="Per-day forecasts ordered by date")
