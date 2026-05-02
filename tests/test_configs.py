from pathlib import Path
import os

import pytest

from timesfm_meteo.configs import (
    OpenMeteoSettings,
    Settings,
    TimesFMSettings,
    load_settings,
)


def test_load_settings_from_yaml(tmp_path: Path) -> None:
    config_path = tmp_path / "configs.yaml"
    env_path = tmp_path / ".env"
    config_path.write_text(
        """
history_years: 3
forecast_days: 5
open-meteo:
  archive-api-url: https://example.test/archive
  daily-variables:
    - temperature_2m_max
    - temperature_2m_min
  default-timeout-seconds: 12.5
timesfm:
  model-id: google/timesfm-1.0-200m-pytorch
  max-context: 2048
  max-horizon: 64
  normalize-inputs: false
""".strip(),
        encoding="utf-8",
    )

    settings = load_settings(config_path, env_path)

    assert settings.history_years == 3
    assert settings.forecast_days == 5
    assert settings.open_meteo.archive_api_url == "https://example.test/archive"
    assert settings.open_meteo.daily_variables == (
        "temperature_2m_max",
        "temperature_2m_min",
    )
    assert settings.open_meteo.default_timeout_seconds == 12.5
    assert settings.timesfm.model_id == "google/timesfm-1.0-200m-pytorch"
    assert settings.timesfm.max_context == 2048
    assert settings.timesfm.max_horizon == 64
    assert settings.timesfm.normalize_inputs is False


def test_timesfm_settings_defaults() -> None:
    settings = TimesFMSettings()

    assert settings.model_id == "google/timesfm-2.5-200m-pytorch"
    assert settings.max_context == 1024
    assert settings.max_horizon == 32
    assert settings.normalize_inputs is True
    assert settings.use_continuous_quantile_head is True
    assert settings.force_flip_invariance is True
    assert settings.fix_quantile_crossing is True


def test_timesfm_settings_accepts_aliases() -> None:
    settings = TimesFMSettings.model_validate(
        {
            "model-id": "custom/model",
            "max-context": 512,
            "max-horizon": 16,
            "normalize-inputs": False,
            "use-continuous-quantile-head": False,
            "force-flip-invariance": False,
            "fix-quantile-crossing": False,
        }
    )

    assert settings.model_id == "custom/model"
    assert settings.max_context == 512
    assert settings.normalize_inputs is False


def test_load_settings_uses_defaults_when_yaml_is_missing(tmp_path: Path) -> None:
    settings = load_settings(tmp_path / "missing.yaml", tmp_path / ".env")

    assert settings == Settings()


def test_load_settings_loads_dotenv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TIMESFM_METEO_TEST_VALUE", raising=False)
    env_path = tmp_path / ".env"
    env_path.write_text("TIMESFM_METEO_TEST_VALUE=loaded\n", encoding="utf-8")

    load_settings(tmp_path / "missing.yaml", env_path)

    assert os.environ["TIMESFM_METEO_TEST_VALUE"] == "loaded"


def test_load_settings_rejects_non_mapping_yaml(tmp_path: Path) -> None:
    config_path = tmp_path / "configs.yaml"
    config_path.write_text("- invalid\n", encoding="utf-8")

    with pytest.raises(ValueError, match="YAML object"):
        load_settings(config_path, tmp_path / ".env")


def test_open_meteo_settings_accepts_aliases() -> None:
    settings = OpenMeteoSettings.model_validate(
        {
            "archive-api-url": "https://example.test/archive",
            "daily-variables": ["a", "b"],
            "default-timeout-seconds": 10,
        }
    )

    assert settings.archive_api_url == "https://example.test/archive"
    assert settings.daily_variables == ("a", "b")
    assert settings.default_timeout_seconds == 10
