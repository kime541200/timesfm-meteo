import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field

DEFAULT_CONFIG_PATH = Path("configs/configs.yaml")
DEFAULT_ENV_PATH = Path(".env")


class OpenMeteoSettings(BaseModel):
    """Open-Meteo API settings.

    Reference: https://open-meteo.com/en/docs/historical-weather-api
    """

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    archive_api_url: str = Field(
        "https://archive-api.open-meteo.com/v1/archive",
        alias="archive-api-url",
        description="Open-Meteo historical archive API URL",
    )
    daily_variables: tuple[str, ...] = Field(
        ("temperature_2m_max", "temperature_2m_min"),
        alias="daily-variables",
        min_length=1,
        description="Daily weather variables to request",
    )
    default_timeout_seconds: float = Field(
        30.0,
        alias="default-timeout-seconds",
        gt=0,
        description="HTTP request timeout in seconds",
    )


class TimesFMSettings(BaseModel):
    """TimesFM model settings.

    The model architecture allows up to context=16384 and horizon=1000;
    project defaults are tighter — see docs/timesfm-engine.md for rationale.
    """

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    model_id: str = Field(
        "google/timesfm-2.5-200m-pytorch",
        alias="model-id",
        description="HuggingFace model identifier",
    )
    max_context: int = Field(
        1024,
        alias="max-context",
        ge=1,
        le=16384,
        description="Maximum input series length the compiled graph supports",
    )
    max_horizon: int = Field(
        32,
        alias="max-horizon",
        ge=1,
        le=1000,
        description="Maximum forecast horizon the compiled graph supports",
    )
    normalize_inputs: bool = Field(True, alias="normalize-inputs")
    use_continuous_quantile_head: bool = Field(True, alias="use-continuous-quantile-head")
    force_flip_invariance: bool = Field(True, alias="force-flip-invariance")
    fix_quantile_crossing: bool = Field(True, alias="fix-quantile-crossing")


class PostgresSettings(BaseModel):
    """PostgreSQL connection settings. DSN is read from DATABASE_URL env var."""

    model_config = ConfigDict(frozen=True)

    dsn: str = Field(
        default_factory=lambda: os.environ.get("DATABASE_URL", ""),
        description="PostgreSQL connection string (set DATABASE_URL in .env)",
    )


class ApiSettings(BaseModel):
    """HTTP API server settings."""

    model_config = ConfigDict(frozen=True)

    api_key: str = Field(
        default_factory=lambda: os.environ.get("API_KEY", ""),
        description="Bearer token for API authentication (set API_KEY in .env)",
    )


class Settings(BaseModel):
    """Runtime settings for the local forecasting pipeline."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    history_years: int = Field(2, ge=1, le=100, description="Number of years of historical data to load")
    forecast_days: int = Field(3, ge=1, le=365, description="Number of days to forecast")
    open_meteo: OpenMeteoSettings = Field(
        default_factory=OpenMeteoSettings,
        alias="open-meteo",
    )
    postgres: PostgresSettings = Field(default_factory=PostgresSettings)
    timesfm: TimesFMSettings = Field(default_factory=TimesFMSettings)
    api: ApiSettings = Field(default_factory=ApiSettings)


def load_settings(
    config_path: Path | str = DEFAULT_CONFIG_PATH,
    env_path: Path | str = DEFAULT_ENV_PATH,
) -> Settings:
    """Load runtime settings from .env and YAML config."""
    load_dotenv(env_path)
    payload = _load_yaml_config(Path(config_path))
    return Settings.model_validate(payload)


def _load_yaml_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        return {}

    with config_path.open("r", encoding="utf-8") as config_file:
        payload = yaml.safe_load(config_file)

    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise ValueError(f"Config file must contain a YAML object: {config_path}")
    return payload
