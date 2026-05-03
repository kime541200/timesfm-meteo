from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest

from timesfm_meteo.db.forecasts import ForecastRow
from timesfm_meteo.evaluation.orchestrator import evaluate_forecasts
from timesfm_meteo.models import DailyTemperature, Location
from timesfm_meteo.pipeline.historical import FetchResult

_LOC = Location(latitude=25.05, longitude=121.57)
_START = date(2024, 6, 1)


def _row(start: date, target: date, max_p50: float = 28.0, min_p50: float = 20.0) -> ForecastRow:
    offset = 2.0
    return ForecastRow(
        start_date=start,
        target_date=target,
        max_p10=max_p50 - offset,
        max_p50=max_p50,
        max_p90=max_p50 + offset,
        min_p10=min_p50 - offset,
        min_p50=min_p50,
        min_p90=min_p50 + offset,
        model_id="test-model",
        history_days=730,
    )


def _actual(d: date, t_max: float, t_min: float) -> DailyTemperature:
    return DailyTemperature(date=d, temperature_max=t_max, temperature_min=t_min)


def _make_fetch_result(actuals: list[DailyTemperature]) -> FetchResult:
    return FetchResult(rows=actuals, cached_count=len(actuals), fetched_count=0)


@pytest.fixture
def mock_conn():
    return MagicMock()


def _run(
    monkeypatch,
    mock_conn,
    forecast_rows: list[ForecastRow],
    actuals: list[DailyTemperature],
    horizon_step_filter: int | None = None,
):
    monkeypatch.setattr(
        "timesfm_meteo.evaluation.orchestrator.fetch_forecasts_in_range",
        lambda *a, **kw: forecast_rows,
    )
    monkeypatch.setattr(
        "timesfm_meteo.evaluation.orchestrator.get_temperatures",
        lambda *a, **kw: _make_fetch_result(actuals),
    )
    return evaluate_forecasts(
        _LOC, _START, _START, horizon_step_filter, mock_conn, MagicMock()
    )


def test_happy_path_three_steps(monkeypatch, mock_conn):
    rows = [_row(_START, _START + timedelta(days=i), max_p50=28.0 + i, min_p50=20.0 + i) for i in range(3)]
    actuals = [_actual(_START + timedelta(days=i), 28.0 + i, 20.0 + i) for i in range(3)]
    report = _run(monkeypatch, mock_conn, rows, actuals)

    assert report.overall.evaluated_count == 3
    assert report.overall.pending_count == 0
    assert len(report.by_horizon_step) == 3
    assert [s.horizon_step for s in report.by_horizon_step] == [0, 1, 2]
    assert report.overall.max is not None
    assert report.overall.min is not None


def test_partial_pending(monkeypatch, mock_conn):
    rows = [_row(_START, _START + timedelta(days=i)) for i in range(3)]
    actuals = [_actual(_START, 28.0, 20.0), _actual(_START + timedelta(days=1), 29.0, 21.0)]
    report = _run(monkeypatch, mock_conn, rows, actuals)

    assert report.overall.evaluated_count == 2
    assert report.overall.pending_count == 1
    # step 2 should be pending-only → still in by_horizon_step but metrics=None
    step2 = next(s for s in report.by_horizon_step if s.horizon_step == 2)
    assert step2.metrics.max is None
    assert step2.metrics.pending_count == 1


def test_all_pending(monkeypatch, mock_conn):
    rows = [_row(_START, _START + timedelta(days=i)) for i in range(3)]
    report = _run(monkeypatch, mock_conn, rows, [])

    assert report.overall.evaluated_count == 0
    assert report.overall.pending_count == 3
    assert report.overall.max is None
    assert report.overall.min is None


def test_empty_forecasts(monkeypatch, mock_conn):
    report = _run(monkeypatch, mock_conn, [], [])

    assert report.by_horizon_step == []
    assert report.overall.evaluated_count == 0
    assert report.overall.pending_count == 0
    assert report.overall.max is None


def test_horizon_step_grouping_is_independent(monkeypatch, mock_conn):
    # 6 forecasts: steps 0,1,2 × 2 start_dates
    rows = [
        _row(_START, _START + timedelta(days=i), max_p50=28.0, min_p50=20.0)
        for i in range(3)
    ] + [
        _row(_START + timedelta(days=1), _START + timedelta(days=1 + i), max_p50=29.0, min_p50=21.0)
        for i in range(3)
    ]
    actuals = [
        _actual(_START + timedelta(days=i), 28.0, 20.0) for i in range(4)
    ]
    report = _run(monkeypatch, mock_conn, rows, actuals)
    # Steps 0,1,2,3 are present (step 3 comes from second batch)
    steps = {s.horizon_step for s in report.by_horizon_step}
    assert 0 in steps and 1 in steps and 2 in steps
    # Metrics for step 0 should use only the step-0 forecasts
    step0 = next(s for s in report.by_horizon_step if s.horizon_step == 0)
    assert step0.metrics.evaluated_count >= 1


def test_horizon_step_filter(monkeypatch, mock_conn):
    rows = [_row(_START, _START + timedelta(days=i)) for i in range(3)]
    actuals = [_actual(_START + timedelta(days=i), 28.0 + i, 20.0 + i) for i in range(3)]

    monkeypatch.setattr(
        "timesfm_meteo.evaluation.orchestrator.fetch_forecasts_in_range",
        lambda *a, **kw: [rows[1]],  # simulate filter already applied in DB layer
    )
    monkeypatch.setattr(
        "timesfm_meteo.evaluation.orchestrator.get_temperatures",
        lambda *a, **kw: _make_fetch_result([actuals[1]]),
    )
    report = evaluate_forecasts(_LOC, _START, _START, 1, mock_conn, MagicMock())

    assert report.horizon_step_filter == 1
    assert len(report.by_horizon_step) == 1
    assert report.by_horizon_step[0].horizon_step == 1


def test_mae_uses_p50_not_mean(monkeypatch, mock_conn):
    row = _row(_START, _START, max_p50=30.0, min_p50=20.0)
    row = row._replace(max_p10=25.0, max_p90=35.0, min_p10=15.0, min_p90=25.0)
    actual = _actual(_START, 28.0, 19.0)
    report = _run(monkeypatch, mock_conn, [row], [actual])

    # MAE on max: |28.0 - 30.0| = 2.0
    assert report.overall.max.mae_p50 == pytest.approx(2.0)
    # MAE on min: |19.0 - 20.0| = 1.0
    assert report.overall.min.mae_p50 == pytest.approx(1.0)


def test_coverage_and_width_correct(monkeypatch, mock_conn):
    row = _row(_START, _START, max_p50=28.0, min_p50=20.0)
    # max interval [26.0, 30.0], actual=27.0 (inside) → coverage=1.0, width=4.0
    actual = _actual(_START, 27.0, 20.0)
    report = _run(monkeypatch, mock_conn, [row], [actual])

    assert report.overall.max.interval_coverage == pytest.approx(1.0)
    assert report.overall.max.mean_interval_width == pytest.approx(4.0)
