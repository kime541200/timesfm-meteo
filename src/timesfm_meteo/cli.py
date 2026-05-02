import argparse
import sys
from datetime import date as Date
from datetime import datetime, timedelta

import psycopg
from pydantic import ValidationError

from timesfm_meteo.configs import Settings, load_settings
from timesfm_meteo.db.repository import ensure_schema
from timesfm_meteo.forecasting.timesfm import forecast_with_timesfm
from timesfm_meteo.models import ForecastResponse, Location
from timesfm_meteo.pipeline.historical import get_temperatures


def _parse_iso_date(value: str) -> Date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid date '{value}', expected YYYY-MM-DD") from exc


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="timesfm-meteo")
    subparsers = parser.add_subparsers(dest="command", required=True)

    fetch = subparsers.add_parser(
        "fetch-history",
        help="Fetch historical daily temperatures with Postgres caching.",
    )
    fetch.add_argument("--latitude", type=float, required=True)
    fetch.add_argument("--longitude", type=float, required=True)
    fetch.add_argument("--end-date", type=_parse_iso_date, default=None)

    date_group = fetch.add_mutually_exclusive_group(required=True)
    date_group.add_argument("--years", type=int)
    date_group.add_argument("--start-date", type=_parse_iso_date)

    forecast = subparsers.add_parser(
        "forecast",
        help="Forecast future daily max/min temperatures with TimesFM.",
    )
    forecast.add_argument("--latitude", type=float, required=True)
    forecast.add_argument("--longitude", type=float, required=True)
    forecast.add_argument(
        "--horizon",
        type=int,
        default=None,
        help="Forecast horizon in days. Defaults to settings.forecast_days.",
    )
    forecast.add_argument(
        "--history-years",
        type=int,
        default=None,
        help="Years of history to feed the model. Defaults to settings.history_years.",
    )
    forecast.add_argument(
        "--start-date",
        type=_parse_iso_date,
        default=None,
        help="First date to forecast. Defaults to today; setting a past date enables backtest.",
    )

    return parser


def _resolve_dates(args: argparse.Namespace) -> tuple[Date, Date]:
    end_date = args.end_date or Date.today() - timedelta(days=1)
    if args.start_date is not None:
        return args.start_date, end_date
    try:
        start_date = end_date.replace(year=end_date.year - args.years)
    except ValueError:
        start_date = end_date.replace(year=end_date.year - args.years, day=28)
    return start_date, end_date


def _subtract_years(value: Date, years: int) -> Date:
    try:
        return value.replace(year=value.year - years)
    except ValueError:
        return value.replace(year=value.year - years, day=28)


def _run_fetch_history(args: argparse.Namespace, settings: Settings) -> int:
    try:
        location = Location(latitude=args.latitude, longitude=args.longitude)
    except ValidationError as exc:
        print(f"invalid location: {exc}", file=sys.stderr)
        return 2

    try:
        start_date, end_date = _resolve_dates(args)
    except ValueError as exc:
        print(f"invalid date range: {exc}", file=sys.stderr)
        return 2

    if not settings.postgres.dsn:
        print("DATABASE_URL is not configured. Set it in .env.", file=sys.stderr)
        return 2

    try:
        with psycopg.connect(settings.postgres.dsn) as conn:
            ensure_schema(conn)
            result = get_temperatures(
                location,
                start_date,
                end_date,
                conn,
                settings.open_meteo,
            )
    except psycopg.OperationalError as exc:
        print(f"database connection failed: {exc}", file=sys.stderr)
        return 2

    for row in result.rows:
        print(f"{row.date.isoformat()}\t{row.temperature_max}\t{row.temperature_min}")

    print(
        f"cached={result.cached_count} fetched={result.fetched_count} total={len(result.rows)}",
        file=sys.stderr,
    )
    return 0


def _build_engine(settings: Settings):
    """Construct the default TimesFMEngine. Imported lazily to avoid loading torch
    when the forecast command is not used (or when tests mock this function)."""
    from timesfm_meteo.inference.timesfm_engine import TimesFMEngine

    cfg = settings.timesfm
    return TimesFMEngine(
        model_id=cfg.model_id,
        max_context=cfg.max_context,
        max_horizon=cfg.max_horizon,
        normalize_inputs=cfg.normalize_inputs,
        use_continuous_quantile_head=cfg.use_continuous_quantile_head,
        force_flip_invariance=cfg.force_flip_invariance,
        fix_quantile_crossing=cfg.fix_quantile_crossing,
    )


def _run_forecast(args: argparse.Namespace, settings: Settings) -> int:
    try:
        location = Location(latitude=args.latitude, longitude=args.longitude)
    except ValidationError as exc:
        print(f"invalid location: {exc}", file=sys.stderr)
        return 2

    horizon = args.horizon if args.horizon is not None else settings.forecast_days
    history_years = args.history_years if args.history_years is not None else settings.history_years
    start_date = args.start_date or Date.today()

    if horizon < 1:
        print("horizon must be at least 1", file=sys.stderr)
        return 2
    if history_years < 1:
        print("history-years must be at least 1", file=sys.stderr)
        return 2

    history_end = start_date - timedelta(days=1)
    history_start = _subtract_years(history_end, history_years)
    forecast_dates = [start_date + timedelta(days=i) for i in range(horizon)]

    if not settings.postgres.dsn:
        print("DATABASE_URL is not configured. Set it in .env.", file=sys.stderr)
        return 2

    try:
        with psycopg.connect(settings.postgres.dsn) as conn:
            ensure_schema(conn)
            history_result = get_temperatures(
                location,
                history_start,
                history_end,
                conn,
                settings.open_meteo,
            )
    except psycopg.OperationalError as exc:
        print(f"database connection failed: {exc}", file=sys.stderr)
        return 2

    engine = _build_engine(settings)
    forecasts = forecast_with_timesfm(history_result.rows, forecast_dates, engine)

    response = ForecastResponse(
        model=settings.timesfm.model_id,
        history_days=len(history_result.rows),
        horizon=horizon,
        forecasts=forecasts,
    )
    print(response.model_dump_json(indent=2))
    print(
        f"history={len(history_result.rows)} horizon={horizon} model={settings.timesfm.model_id}",
        file=sys.stderr,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run the project command-line entry point."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    settings = load_settings()

    if args.command == "fetch-history":
        return _run_fetch_history(args, settings)
    if args.command == "forecast":
        return _run_forecast(args, settings)
    parser.error(f"unknown command: {args.command}")
    return 2
