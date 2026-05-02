import pytest

from timesfm_meteo.cli import main
from timesfm_meteo.configs import OpenMeteoSettings, PostgresSettings, Settings


def _make_settings(dsn: str) -> Settings:
    return Settings(
        postgres=PostgresSettings(dsn=dsn),
        open_meteo=OpenMeteoSettings(),
    )


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
