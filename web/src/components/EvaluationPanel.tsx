import type { EvaluationReport, GroupMetrics, VariableMetrics } from '../api/types';

type EvaluationPanelProps = {
  report: EvaluationReport | undefined;
  isLoading: boolean;
  error: unknown;
};

const fmt = (value: number | null | undefined, digits = 2): string => (
  value === null || value === undefined || Number.isNaN(value) ? '—' : value.toFixed(digits)
);

const percent = (value: number | null | undefined): string => (
  value === null || value === undefined || Number.isNaN(value) ? '—' : `${(value * 100).toFixed(1)}%`
);

const metricCards = (label: string, metrics: VariableMetrics | null) => [
  { label: `${label} MAE p50`, value: fmt(metrics?.mae_p50) },
  { label: `${label} Coverage`, value: percent(metrics?.interval_coverage) },
  { label: `${label} Width`, value: fmt(metrics?.mean_interval_width) },
];

export default function EvaluationPanel({ report, isLoading, error }: EvaluationPanelProps) {
  if (error) {
    return <section className="panel error-text" role="alert">Evaluation failed to load: {String((error as Error).message ?? error)}</section>;
  }

  if (isLoading) {
    return <section className="panel state-box">Loading evaluation metrics…</section>;
  }

  if (!report) {
    return <section className="panel state-box">No evaluation report loaded.</section>;
  }

  const overall: GroupMetrics = report.overall;
  const cards = [
    { label: 'Evaluated', value: String(overall.evaluated_count) },
    { label: 'Pending', value: String(overall.pending_count) },
    ...metricCards('Max', overall.max),
    ...metricCards('Min', overall.min),
  ];

  return (
    <section className="panel" aria-labelledby="evaluation-title">
      <div className="section-heading">
        <h2 id="evaluation-title">Evaluation</h2>
        <p>Overall and horizon-step metrics from the selected date range.</p>
      </div>

      <div className="metric-grid">
        {cards.map((card) => (
          <div className="metric-card" key={card.label}>
            <span>{card.label}</span>
            <strong>{card.value}</strong>
          </div>
        ))}
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Step</th>
              <th>Evaluated</th>
              <th>Pending</th>
              <th>Max MAE</th>
              <th>Max Coverage</th>
              <th>Min MAE</th>
              <th>Min Coverage</th>
            </tr>
          </thead>
          <tbody>
            {report.by_horizon_step.length ? report.by_horizon_step.map((row) => (
              <tr key={row.horizon_step}>
                <td>{row.horizon_step}</td>
                <td>{row.metrics.evaluated_count}</td>
                <td>{row.metrics.pending_count}</td>
                <td>{fmt(row.metrics.max?.mae_p50)}</td>
                <td>{percent(row.metrics.max?.interval_coverage)}</td>
                <td>{fmt(row.metrics.min?.mae_p50)}</td>
                <td>{percent(row.metrics.min?.interval_coverage)}</td>
              </tr>
            )) : (
              <tr>
                <td colSpan={7}>No horizon-step metrics available.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
