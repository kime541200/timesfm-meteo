import argparse
import sys
from datetime import date as Date
from datetime import datetime, timedelta

import psycopg
from pydantic import ValidationError

from timesfm_meteo.configs import Settings, load_settings
from timesfm_meteo.db.repository import ensure_schema
from timesfm_meteo.models import Location
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


def main(argv: list[str] | None = None) -> int:
    """Run the project command-line entry point."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    settings = load_settings()

    if args.command == "fetch-history":
        return _run_fetch_history(args, settings)
    parser.error(f"unknown command: {args.command}")
    return 2
