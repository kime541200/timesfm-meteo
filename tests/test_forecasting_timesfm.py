from datetime import date

import numpy as np
import pytest

from timesfm_meteo.forecasting.timesfm import forecast_with_timesfm
from timesfm_meteo.models import DailyTemperature, QuantileForecastResult


class _FakeEngine:
    """Fake `ForecastEngine` implementation used in adapter tests."""

    def __init__(
        self,
        max_result: QuantileForecastResult,
        min_result: QuantileForecastResult,
    ) -> None:
        self._max_result = max_result
        self._min_result = min_result
        self.calls: list[tuple[list[np.ndarray], int]] = []

    def forecast(
        self, series_list: list[np.ndarray], horizon: int
    ) -> list[QuantileForecastResult]:
        self.calls.append((series_list, horizon))
        return [self._max_result, self._min_result]


def _result(point: list[float], offset: float = 0.0) -> QuantileForecastResult:
    horizon = len(point)
    return QuantileForecastResult(
        horizon=horizon,
        point=point,
        quantiles={
            0.1: [v - 2 + offset for v in point],
            0.2: [v - 1.5 + offset for v in point],
            0.3: [v - 1 + offset for v in point],
            0.4: [v - 0.5 + offset for v in point],
            0.5: [v + offset for v in point],
            0.6: [v + 0.5 + offset for v in point],
            0.7: [v + 1 + offset for v in point],
            0.8: [v + 1.5 + offset for v in point],
            0.9: [v + 2 + offset for v in point],
        },
    )


_HISTORY = [
    DailyTemperature(date=date(2026, 4, 30), temperature_max=22.0, temperature_min=15.0),
    DailyTemperature(date=date(2026, 5, 1), temperature_max=23.0, temperature_min=16.0),
    DailyTemperature(date=date(2026, 5, 2), temperature_max=24.0, temperature_min=17.0),
]


def test_adapter_passes_max_then_min_to_engine() -> None:
    engine = _FakeEngine(
        max_result=_result([26.0, 27.0]),
        min_result=_result([18.0, 19.0]),
    )
    forecast_dates = [date(2026, 5, 3), date(2026, 5, 4)]

    forecast_with_timesfm(_HISTORY, forecast_dates, engine)

    assert len(engine.calls) == 1
    series_list, horizon = engine.calls[0]
    assert horizon == 2
    assert len(series_list) == 2
    np.testing.assert_array_equal(series_list[0], np.array([22.0, 23.0, 24.0], dtype=np.float32))
    np.testing.assert_array_equal(series_list[1], np.array([15.0, 16.0, 17.0], dtype=np.float32))


def test_adapter_maps_quantile_dict_to_p10_p50_p90() -> None:
    engine = _FakeEngine(
        max_result=_result([30.0]),
        min_result=_result([20.0]),
    )
    forecast_dates = [date(2026, 5, 3)]

    forecasts = forecast_with_timesfm(_HISTORY, forecast_dates, engine)

    assert len(forecasts) == 1
    assert forecasts[0].max.p10 == pytest.approx(28.0)  # 30 - 2
    assert forecasts[0].max.p50 == pytest.approx(30.0)
    assert forecasts[0].max.p90 == pytest.approx(32.0)  # 30 + 2
    assert forecasts[0].min.p10 == pytest.approx(18.0)
    assert forecasts[0].min.p50 == pytest.approx(20.0)
    assert forecasts[0].min.p90 == pytest.approx(22.0)


def test_adapter_output_dates_match_forecast_dates() -> None:
    engine = _FakeEngine(
        max_result=_result([26.0, 27.0, 28.0]),
        min_result=_result([18.0, 19.0, 20.0]),
    )
    forecast_dates = [date(2026, 5, 3), date(2026, 5, 4), date(2026, 5, 5)]

    forecasts = forecast_with_timesfm(_HISTORY, forecast_dates, engine)

    assert [f.date for f in forecasts] == forecast_dates


def test_adapter_rejects_empty_history() -> None:
    engine = _FakeEngine(_result([26.0]), _result([18.0]))
    with pytest.raises(ValueError, match="history"):
        forecast_with_timesfm([], [date(2026, 5, 3)], engine)


def test_adapter_rejects_empty_forecast_dates() -> None:
    engine = _FakeEngine(_result([26.0]), _result([18.0]))
    with pytest.raises(ValueError, match="forecast_dates"):
        forecast_with_timesfm(_HISTORY, [], engine)
