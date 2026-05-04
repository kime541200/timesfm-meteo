from __future__ import annotations

import argparse
import sys


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="timesfm-meteo-client")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- temperatures ---
    temps = subparsers.add_parser("temperatures", help="Query historical temperatures.")
    temps_sub = temps.add_subparsers(dest="subcommand", required=True)
    t_get = temps_sub.add_parser("get")
    t_get.add_argument("--latitude", type=float, required=True)
    t_get.add_argument("--longitude", type=float, required=True)
    t_get.add_argument("--start-date", dest="start_date", required=True)
    t_get.add_argument("--end-date", dest="end_date", required=True)

    # --- forecasts ---
    fcs = subparsers.add_parser("forecasts", help="List stored forecasts.")
    fcs_sub = fcs.add_subparsers(dest="subcommand", required=True)
    f_list = fcs_sub.add_parser("list")
    f_list.add_argument("--latitude", type=float, required=True)
    f_list.add_argument("--longitude", type=float, required=True)
    f_list.add_argument("--start-date-from", dest="start_date_from", required=True)
    f_list.add_argument("--start-date-to", dest="start_date_to", required=True)
    f_list.add_argument("--horizon-step", dest="horizon_step", type=int, default=None)

    # --- forecast run ---
    fc = subparsers.add_parser("forecast", help="Trigger a forecast job.")
    fc_sub = fc.add_subparsers(dest="subcommand", required=True)
    fc_run = fc_sub.add_parser("run")
    fc_run.add_argument("--latitude", type=float, required=True)
    fc_run.add_argument("--longitude", type=float, required=True)
    fc_run.add_argument("--horizon", type=int, default=None)
    fc_run.add_argument("--history-years", dest="history_years", type=int, default=None)
    fc_run.add_argument("--start-date", dest="start_date", default=None)
    fc_run.add_argument("--no-wait", dest="no_wait", action="store_true")
    fc_run.add_argument("--timeout", type=float, default=120)

    # --- fetch-history run ---
    fh = subparsers.add_parser("fetch-history", help="Trigger a fetch-history job.")
    fh_sub = fh.add_subparsers(dest="subcommand", required=True)
    fh_run = fh_sub.add_parser("run")
    fh_run.add_argument("--latitude", type=float, required=True)
    fh_run.add_argument("--longitude", type=float, required=True)
    fh_run.add_argument("--years", type=int, default=None)
    fh_run.add_argument("--start-date", dest="start_date", default=None)
    fh_run.add_argument("--end-date", dest="end_date", default=None)
    fh_run.add_argument("--no-wait", dest="no_wait", action="store_true")
    fh_run.add_argument("--timeout", type=float, default=120)

    # --- evaluate ---
    ev = subparsers.add_parser("evaluate", help="Get evaluation report.")
    ev_sub = ev.add_subparsers(dest="subcommand", required=True)
    ev_get = ev_sub.add_parser("get")
    ev_get.add_argument("--latitude", type=float, required=True)
    ev_get.add_argument("--longitude", type=float, required=True)
    ev_get.add_argument("--start-date-from", dest="start_date_from", required=True)
    ev_get.add_argument("--start-date-to", dest="start_date_to", required=True)
    ev_get.add_argument("--horizon-step", dest="horizon_step", type=int, default=None)

    # --- jobs ---
    jobs = subparsers.add_parser("jobs", help="Query job status.")
    jobs_sub = jobs.add_subparsers(dest="subcommand", required=True)
    j_get = jobs_sub.add_parser("get")
    j_get.add_argument("job_id")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    from timesfm_meteo.client.commands import (
        evaluate,
        fetch_history,
        forecasts,
        jobs,
        temperatures,
    )

    if args.command == "temperatures":
        return temperatures.cmd_temperatures_get(args)
    if args.command == "forecasts":
        return forecasts.cmd_forecasts_list(args)
    if args.command == "forecast":
        return forecasts.cmd_forecast_run(args)
    if args.command == "fetch-history":
        return fetch_history.cmd_fetch_history_run(args)
    if args.command == "evaluate":
        return evaluate.cmd_evaluate_get(args)
    if args.command == "jobs":
        return jobs.cmd_jobs_get(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
