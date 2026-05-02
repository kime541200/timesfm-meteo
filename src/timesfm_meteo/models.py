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


class QuantileForecast(ProjectModel):
    date: Date = Field(..., ge=Date(1900, 1, 1), description="Date in YYYY-MM-DD format")
    p10: float = Field(..., ge=-100, le=100, description="10th percentile temperature in degrees Celsius")
    p50: float = Field(..., ge=-100, le=100, description="50th percentile temperature in degrees Celsius")
    p90: float = Field(..., ge=-100, le=100, description="90th percentile temperature in degrees Celsius")

    @model_validator(mode="after")
    def validate_quantile_order(self) -> "QuantileForecast":
        if not self.p10 <= self.p50 <= self.p90:
            raise ValueError("quantiles must satisfy p10 <= p50 <= p90")
        return self
