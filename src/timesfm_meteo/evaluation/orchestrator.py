from datetime import date as Date

import psycopg

from timesfm_meteo.configs import OpenMeteoSettings
from timesfm_meteo.db.forecasts import fetch_forecasts_in_range
from timesfm_meteo.evaluation.metrics import interval_coverage, mean_absolute_error, mean_interval_width
from timesfm_meteo.models import (
    EvaluationReport,
    GroupMetrics,
    HorizonStepReport,
    Location,
    VariableMetrics,
)
from timesfm_meteo.pipeline.historical import get_temperatures


def evaluate_forecasts(
    location: Location,
    start_date_from: Date,
    start_date_to: Date,
    horizon_step_filter: int | None,
    conn: psycopg.Connection,
    open_meteo_settings: OpenMeteoSettings,
) -> EvaluationReport:
    """Fetch stored forecasts, ensure actuals are in DB, JOIN, and compute metrics."""
    forecast_rows = fetch_forecasts_in_range(
        conn, location, start_date_from, start_date_to, horizon_step_filter
    )

    if not forecast_rows:
        empty_overall = GroupMetrics(evaluated_count=0, pending_count=0, max=None, min=None)
        return EvaluationReport(
            location=location,
            start_date_from=start_date_from,
            start_date_to=start_date_to,
            horizon_step_filter=horizon_step_filter,
            by_horizon_step=[],
            overall=empty_overall,
        )

    target_dates = {r.target_date for r in forecast_rows}
    t_min, t_max = min(target_dates), max(target_dates)
    actual_result = get_temperatures(location, t_min, t_max, conn, open_meteo_settings)
    actual_lookup = {row.date: row for row in actual_result.rows}

    by_step: dict[int, list[tuple]] = {}
    for row in forecast_rows:
        step = (row.target_date - row.start_date).days
        by_step.setdefault(step, []).append(row)

    step_reports: list[HorizonStepReport] = []
    all_evaluated: list[tuple] = []
    all_pending: list[tuple] = []

    for step in sorted(by_step):
        rows_for_step = by_step[step]
        evaluated = [(r, actual_lookup[r.target_date]) for r in rows_for_step if r.target_date in actual_lookup]
        pending = [r for r in rows_for_step if r.target_date not in actual_lookup]
        all_evaluated.extend(evaluated)
        all_pending.extend(pending)
        step_reports.append(
            HorizonStepReport(
                horizon_step=step,
                metrics=_build_group_metrics(evaluated, len(pending)),
            )
        )

    overall = _build_group_metrics(all_evaluated, len(all_pending))

    return EvaluationReport(
        location=location,
        start_date_from=start_date_from,
        start_date_to=start_date_to,
        horizon_step_filter=horizon_step_filter,
        by_horizon_step=step_reports,
        overall=overall,
    )


def _build_group_metrics(
    evaluated: list[tuple],
    pending_count: int,
) -> GroupMetrics:
    if not evaluated:
        return GroupMetrics(evaluated_count=0, pending_count=pending_count, max=None, min=None)

    forecast_rows, actual_rows = zip(*evaluated)

    max_actuals = [float(a.temperature_max) for a in actual_rows]
    min_actuals = [float(a.temperature_min) for a in actual_rows]

    max_p10 = [r.max_p10 for r in forecast_rows]
    max_p50 = [r.max_p50 for r in forecast_rows]
    max_p90 = [r.max_p90 for r in forecast_rows]
    min_p10 = [r.min_p10 for r in forecast_rows]
    min_p50 = [r.min_p50 for r in forecast_rows]
    min_p90 = [r.min_p90 for r in forecast_rows]

    return GroupMetrics(
        evaluated_count=len(evaluated),
        pending_count=pending_count,
        max=VariableMetrics(
            mae_p50=mean_absolute_error(max_actuals, max_p50),
            interval_coverage=interval_coverage(max_actuals, max_p10, max_p90),
            mean_interval_width=mean_interval_width(max_p10, max_p90),
        ),
        min=VariableMetrics(
            mae_p50=mean_absolute_error(min_actuals, min_p50),
            interval_coverage=interval_coverage(min_actuals, min_p10, min_p90),
            mean_interval_width=mean_interval_width(min_p10, min_p90),
        ),
    )
