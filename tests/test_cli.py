from datetime import date

import numpy as np
import pytest

from timesfm_meteo.cli import main
from timesfm_meteo.configs import (
    OpenMeteoSettings,
    PostgresSettings,
    Settings,
    TimesFMSettings,
)
from timesfm_meteo.models import (
    DailyTemperature,
    EvaluationReport,
    ForecastResponse,
    GroupMetrics,
    QuantileForecastResult,
)
from timesfm_meteo.pipeline.historical import FetchResult


def _make_settings(dsn: str = "") -> Settings:
    return Settings(
        postgres=PostgresSettings(dsn=dsn),
        open_meteo=OpenMeteoSettings(),
        timesfm=TimesFMSettings(),
    )


# ---------- fetch-history tests ----------


def test_parser_rejects_simultaneous_years_and_start_date(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "fetch-history",
                "--latitude", "25.05",
                "--longitude", "121.57",
                "--years", "2",
                "--start-date", "2022-01-01",
            ]
        )
    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "not allowed" in captured.err.lower() or "mutually exclusive" in captured.err.lower()


def test_parser_rejects_missing_date_arguments(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "fetch-history",
                "--latitude", "25.05",
                "--longitude", "121.57",
            ]
        )
    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "--years" in captured.err and "--start-date" in captured.err


def test_invalid_latitude_returns_exit_code_2(monkeypatch, capsys):
    monkeypatch.setattr(
        "timesfm_meteo.cli.load_settings",
        lambda: _make_settings("postgresql://placeholder"),
    )
    rc = main(
        [
            "fetch-history",
            "--latitude", "95.0",
            "--longitude", "121.57",
            "--years", "2",
        ]
    )
    assert rc == 2
    assert "latitude" in capsys.readouterr().err.lower()


def test_missing_database_url_exits_without_external_calls(monkeypatch, capsys):
    monkeypatch.setattr(
        "timesfm_meteo.cli.load_settings",
        lambda: _make_settings(""),
    )

    def fail_psycopg_connect(*args, **kwargs):
        raise AssertionError("psycopg.connect must not be called when DSN is empty")

    def fail_httpx_client(*args, **kwargs):
        raise AssertionError("httpx.Client must not be called when DSN is empty")

    monkeypatch.setattr("timesfm_meteo.cli.psycopg.connect", fail_psycopg_connect)
    monkeypatch.setattr(
        "timesfm_meteo.data_sources.open_meteo.httpx.Client",
        fail_httpx_client,
    )

    rc = main(
        [
            "fetch-history",
            "--latitude", "25.05",
            "--longitude", "121.57",
            "--years", "2",
        ]
    )
    assert rc == 2
    assert "DATABASE_URL is not configured" in capsys.readouterr().err


# ---------- forecast tests ----------


class _FakeEngine:
    def forecast(self, series_list, horizon):
        return [
            QuantileForecastResult(
                horizon=horizon,
                point=[26.0 + i for i in range(horizon)],
                quantiles={
                    q: [26.0 + i + (q - 0.5) * 4 for i in range(horizon)]
                    for q in (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)
                },
            ),
            QuantileForecastResult(
                horizon=horizon,
                point=[18.0 + i for i in range(horizon)],
                quantiles={
                    q: [18.0 + i + (q - 0.5) * 4 for i in range(horizon)]
                    for q in (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)
                },
            ),
        ]


def _fake_history(days: int) -> list[DailyTemperature]:
    return [
        DailyTemperature(
            date=date(2026, 1, 1),
            temperature_max=22.0 + (i % 5),
            temperature_min=15.0 + (i % 4),
        )
        for i in range(days)
    ]


def test_forecast_invalid_latitude_returns_exit_code_2(monkeypatch, capsys):
    monkeypatch.setattr(
        "timesfm_meteo.cli.load_settings",
        lambda: _make_settings("postgresql://placeholder"),
    )
    rc = main(["forecast", "--latitude", "95.0", "--longitude", "121.57"])
    assert rc == 2
    assert "latitude" in capsys.readouterr().err.lower()


def test_forecast_missing_database_url_does_not_load_model(monkeypatch, capsys):
    monkeypatch.setattr("timesfm_meteo.cli.load_settings", lambda: _make_settings(""))

    def fail_engine(_settings):
        raise AssertionError("TimesFMEngine must not be constructed when DSN is empty")

    def fail_psycopg(*args, **kwargs):
        raise AssertionError("psycopg.connect must not be called when DSN is empty")

    monkeypatch.setattr("timesfm_meteo.cli._build_engine", fail_engine)
    monkeypatch.setattr("timesfm_meteo.cli.psycopg.connect", fail_psycopg)

    rc = main(["forecast", "--latitude", "25.05", "--longitude", "121.57"])
    assert rc == 2
    assert "DATABASE_URL is not configured" in capsys.readouterr().err


def test_forecast_happy_path_emits_valid_json(monkeypatch, capsys):
    settings = _make_settings("postgresql://placeholder")
    monkeypatch.setattr("timesfm_meteo.cli.load_settings", lambda: settings)

    history = _fake_history(60)

    class _FakeConnCtx:
        def __enter__(self):
            return object()

        def __exit__(self, *args):
            return False

    monkeypatch.setattr("timesfm_meteo.cli.psycopg.connect", lambda *a, **kw: _FakeConnCtx())
    monkeypatch.setattr("timesfm_meteo.cli.ensure_schema", lambda conn: None)
    monkeypatch.setattr("timesfm_meteo.cli.ensure_schema_forecasts", lambda conn: None)
    monkeypatch.setattr(
        "timesfm_meteo.cli.get_temperatures",
        lambda *args, **kwargs: FetchResult(rows=history, cached_count=60, fetched_count=0),
    )
    monkeypatch.setattr("timesfm_meteo.cli._build_engine", lambda settings: _FakeEngine())
    monkeypatch.setattr("timesfm_meteo.cli.upsert_forecasts", lambda *a, **kw: None)

    rc = main(
        [
            "forecast",
            "--latitude", "25.05",
            "--longitude", "121.57",
            "--horizon", "3",
            "--start-date", "2026-05-03",
        ]
    )
    captured = capsys.readouterr()
    assert rc == 0

    response = ForecastResponse.model_validate_json(captured.out)
    assert response.model == settings.timesfm.model_id
    assert response.horizon == 3
    assert response.history_days == 60
    assert len(response.forecasts) == 3
    assert response.forecasts[0].date == date(2026, 5, 3)
    assert response.forecasts[2].date == date(2026, 5, 5)
    assert "history=60" in captured.err
    assert "horizon=3" in captured.err
    assert settings.timesfm.model_id in captured.err


def test_forecast_uses_settings_defaults(monkeypatch, capsys):
    settings = _make_settings("postgresql://placeholder")
    monkeypatch.setattr("timesfm_meteo.cli.load_settings", lambda: settings)

    captured_args: dict = {}

    class _FakeConnCtx:
        def __enter__(self):
            return object()

        def __exit__(self, *args):
            return False

    monkeypatch.setattr("timesfm_meteo.cli.psycopg.connect", lambda *a, **kw: _FakeConnCtx())
    monkeypatch.setattr("timesfm_meteo.cli.ensure_schema", lambda conn: None)
    monkeypatch.setattr("timesfm_meteo.cli.ensure_schema_forecasts", lambda conn: None)
    monkeypatch.setattr("timesfm_meteo.cli.upsert_forecasts", lambda *a, **kw: None)

    def capture_get_temperatures(location, start, end, conn, om_settings):
        captured_args["history_start"] = start
        captured_args["history_end"] = end
        return FetchResult(rows=_fake_history(60), cached_count=60, fetched_count=0)

    monkeypatch.setattr("timesfm_meteo.cli.get_temperatures", capture_get_temperatures)
    monkeypatch.setattr("timesfm_meteo.cli._build_engine", lambda settings: _FakeEngine())

    rc = main(["forecast", "--latitude", "25.05", "--longitude", "121.57", "--start-date", "2026-05-03"])
    captured = capsys.readouterr()
    assert rc == 0

    response = ForecastResponse.model_validate_json(captured.out)
    # 預設來自 settings.forecast_days=3
    assert response.horizon == 3
    # 預設 history_years=2 → history_end = start_date - 1 = 2026-05-02
    assert captured_args["history_end"] == date(2026, 5, 2)
    # history_start = 2026-05-02 往前 2 年
    assert captured_args["history_start"] == date(2024, 5, 2)


def test_forecast_happy_path_persists_forecasts(monkeypatch, capsys):
    """Dedicated test: verifies upsert_forecasts is called with correct args."""
    settings = _make_settings("postgresql://placeholder")
    monkeypatch.setattr("timesfm_meteo.cli.load_settings", lambda: settings)

    history = _fake_history(60)
    upsert_calls: list[dict] = []

    class _FakeConnCtx:
        def __enter__(self):
            return object()

        def __exit__(self, *args):
            return False

    def capture_upsert(conn, location, start_date, forecasts, model_id, history_days):
        upsert_calls.append(
            {"location": location, "start_date": start_date, "n_forecasts": len(forecasts),
             "model_id": model_id, "history_days": history_days}
        )

    monkeypatch.setattr("timesfm_meteo.cli.psycopg.connect", lambda *a, **kw: _FakeConnCtx())
    monkeypatch.setattr("timesfm_meteo.cli.ensure_schema", lambda conn: None)
    monkeypatch.setattr("timesfm_meteo.cli.ensure_schema_forecasts", lambda conn: None)
    monkeypatch.setattr(
        "timesfm_meteo.cli.get_temperatures",
        lambda *args, **kwargs: FetchResult(rows=history, cached_count=60, fetched_count=0),
    )
    monkeypatch.setattr("timesfm_meteo.cli._build_engine", lambda settings: _FakeEngine())
    monkeypatch.setattr("timesfm_meteo.cli.upsert_forecasts", capture_upsert)

    main([
        "forecast", "--latitude", "25.05", "--longitude", "121.57",
        "--horizon", "3", "--start-date", "2026-05-03",
    ])

    assert len(upsert_calls) == 1
    call = upsert_calls[0]
    assert call["start_date"] == date(2026, 5, 3)
    assert call["n_forecasts"] == 3
    assert call["model_id"] == settings.timesfm.model_id
    assert call["history_days"] == 60


# ---------- evaluate tests ----------


class _FakeConnCtxEval:
    def __enter__(self):
        return object()

    def __exit__(self, *args):
        return False


def _empty_report() -> EvaluationReport:
    from timesfm_meteo.models import Location
    return EvaluationReport(
        location=Location(latitude=25.05, longitude=121.57),
        start_date_from=date(2099, 1, 1),
        start_date_to=date(2099, 1, 31),
        horizon_step_filter=None,
        by_horizon_step=[],
        overall=GroupMetrics(evaluated_count=0, pending_count=0, max=None, min=None),
    )


def _eval_report_with_data() -> EvaluationReport:
    from timesfm_meteo.models import GroupMetrics, HorizonStepReport, Location, VariableMetrics
    vm = VariableMetrics(mae_p50=1.2, interval_coverage=0.85, mean_interval_width=4.0)
    gm = GroupMetrics(evaluated_count=30, pending_count=0, max=vm, min=vm)
    return EvaluationReport(
        location=Location(latitude=25.05, longitude=121.57),
        start_date_from=date(2024, 6, 1),
        start_date_to=date(2024, 6, 30),
        horizon_step_filter=None,
        by_horizon_step=[HorizonStepReport(horizon_step=0, metrics=gm)],
        overall=gm,
    )


def test_evaluate_invalid_latitude_returns_exit_code_2(monkeypatch, capsys):
    monkeypatch.setattr("timesfm_meteo.cli.load_settings",
                        lambda: _make_settings("postgresql://placeholder"))
    rc = main([
        "evaluate", "--latitude", "95.0", "--longitude", "121.57",
        "--start-date-from", "2024-06-01", "--start-date-to", "2024-06-30",
    ])
    assert rc == 2
    assert "latitude" in capsys.readouterr().err.lower()


def test_evaluate_missing_database_url_does_not_call_anything(monkeypatch, capsys):
    monkeypatch.setattr("timesfm_meteo.cli.load_settings", lambda: _make_settings(""))

    def fail_connect(*a, **kw):
        raise AssertionError("psycopg.connect must not be called when DSN is empty")

    monkeypatch.setattr("timesfm_meteo.cli.psycopg.connect", fail_connect)

    rc = main([
        "evaluate", "--latitude", "25.05", "--longitude", "121.57",
        "--start-date-from", "2024-06-01", "--start-date-to", "2024-06-30",
    ])
    assert rc == 2
    assert "DATABASE_URL is not configured" in capsys.readouterr().err


def test_evaluate_rejects_inverted_date_range(monkeypatch, capsys):
    monkeypatch.setattr("timesfm_meteo.cli.load_settings",
                        lambda: _make_settings("postgresql://placeholder"))
    rc = main([
        "evaluate", "--latitude", "25.05", "--longitude", "121.57",
        "--start-date-from", "2024-06-30", "--start-date-to", "2024-06-01",
    ])
    assert rc == 2
    assert "start-date-from" in capsys.readouterr().err.lower() or "before" in capsys.readouterr().err.lower()


def test_evaluate_no_forecasts_exits_zero(monkeypatch, capsys):
    monkeypatch.setattr("timesfm_meteo.cli.load_settings",
                        lambda: _make_settings("postgresql://placeholder"))
    monkeypatch.setattr("timesfm_meteo.cli.psycopg.connect", lambda *a, **kw: _FakeConnCtxEval())
    monkeypatch.setattr("timesfm_meteo.cli.ensure_schema", lambda conn: None)
    monkeypatch.setattr("timesfm_meteo.cli.ensure_schema_forecasts", lambda conn: None)
    monkeypatch.setattr("timesfm_meteo.cli.evaluate_forecasts", lambda *a, **kw: _empty_report())

    rc = main([
        "evaluate", "--latitude", "25.05", "--longitude", "121.57",
        "--start-date-from", "2099-01-01", "--start-date-to", "2099-01-31",
    ])
    captured = capsys.readouterr()
    assert rc == 0
    assert "no forecasts in range" in captured.err.lower()
    report = EvaluationReport.model_validate_json(captured.out)
    assert report.by_horizon_step == []
    assert report.overall.evaluated_count == 0


def test_evaluate_happy_path_emits_valid_json(monkeypatch, capsys):
    monkeypatch.setattr("timesfm_meteo.cli.load_settings",
                        lambda: _make_settings("postgresql://placeholder"))
    monkeypatch.setattr("timesfm_meteo.cli.psycopg.connect", lambda *a, **kw: _FakeConnCtxEval())
    monkeypatch.setattr("timesfm_meteo.cli.ensure_schema", lambda conn: None)
    monkeypatch.setattr("timesfm_meteo.cli.ensure_schema_forecasts", lambda conn: None)
    monkeypatch.setattr("timesfm_meteo.cli.evaluate_forecasts", lambda *a, **kw: _eval_report_with_data())

    rc = main([
        "evaluate", "--latitude", "25.05", "--longitude", "121.57",
        "--start-date-from", "2024-06-01", "--start-date-to", "2024-06-30",
    ])
    captured = capsys.readouterr()
    assert rc == 0

    report = EvaluationReport.model_validate_json(captured.out)
    assert report.overall.evaluated_count == 30
    assert len(report.by_horizon_step) == 1
    assert "evaluated=30" in captured.err
    assert "horizon_step=any" in captured.err
