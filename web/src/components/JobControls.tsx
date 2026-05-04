import type { JobResponse } from '../api/types';

type JobControlsProps = {
  fetchHistory: () => void;
  runForecast: () => void;
  fetchPending: boolean;
  forecastPending: boolean;
  currentJob: JobResponse | undefined;
  jobError: unknown;
};

export default function JobControls({
  fetchHistory,
  runForecast,
  fetchPending,
  forecastPending,
  currentJob,
  jobError,
}: JobControlsProps) {
  const forecastStart = typeof currentJob?.params.start_date === 'string' ? currentJob.params.start_date : null;
  const forecastHorizon = typeof currentJob?.params.horizon === 'number' ? currentJob.params.horizon : null;

  return (
    <section className="panel" aria-labelledby="jobs-title">
      <div className="section-heading">
        <h2 id="jobs-title">Manual actions</h2>
        <p>Fetch History reloads the selected history range. Run Forecast starts on the day after History end and uses the current Forecast horizon.</p>
      </div>

      <div className="action-row">
        <button type="button" onClick={fetchHistory} disabled={fetchPending}>
          {fetchPending ? 'Fetching…' : 'Fetch History'}
        </button>
        <button type="button" onClick={runForecast} disabled={forecastPending}>
          {forecastPending ? 'Forecasting…' : 'Run Forecast'}
        </button>
      </div>

      <div className="job-status" aria-live="polite">
        {currentJob ? (
          <>
            <span className={`status-pill status-${currentJob.status}`}>{currentJob.status}</span>
            <code>{currentJob.id}</code>
            {currentJob.type === 'forecast' && forecastStart ? (
              <p>
                Forecast start {forecastStart}
                {forecastHorizon !== null ? ` · horizon ${forecastHorizon}` : ''}
              </p>
            ) : null}
            {currentJob.error ? <p className="error-text">{currentJob.error}</p> : null}
          </>
        ) : (
          <p>No active job.</p>
        )}
        {jobError ? <p className="error-text" role="alert">{String((jobError as Error).message ?? jobError)}</p> : null}
      </div>
    </section>
  );
}
