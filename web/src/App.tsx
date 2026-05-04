import { useMemo, useState } from 'react';
import type { DashboardFilters, JobResponse } from './api/types';
import { getApiKey, ApiConfigError } from './api/client';
import EvaluationPanel from './components/EvaluationPanel';
import FilterPanel from './components/FilterPanel';
import ForecastChart from './components/ForecastChart';
import JobControls from './components/JobControls';
import { useDashboardData, useJobActions, useJobPolling } from './hooks/useDashboardData';
import { mergeTemperatureAndForecasts } from './lib/chartData';
import { toDateInput, validateCoordinates, validateHistoryRange } from './lib/validation';

const today = new Date();
const daysAgo = (days: number) => {
  const copy = new Date(today);
  copy.setDate(copy.getDate() - days);
  return copy;
};

const initialFilters: DashboardFilters = {
  latitude: 25.05,
  longitude: 121.57,
  historyStart: toDateInput(daysAgo(30)),
  historyEnd: toDateInput(today),
  forecastHorizon: 3,
  evaluationHorizonStep: 'any',
  showAggregate: true,
};

export default function App() {
  const [filters, setFilters] = useState<DashboardFilters>(initialFilters);
  const [draft, setDraft] = useState<DashboardFilters>(initialFilters);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);
  const [lastJob, setLastJob] = useState<JobResponse | undefined>();

  const apiConfigError = useMemo(() => {
    try {
      getApiKey();
      return null;
    } catch (error) {
      return error instanceof ApiConfigError ? error.message : String(error);
    }
  }, []);

  const dataEnabled = apiConfigError === null;
  const dashboard = useDashboardData(filters, dataEnabled);
  const jobActions = useJobActions(filters);

  const activeJob = useJobPolling(
    currentJobId,
    (job) => {
      setLastJob(job);
      setCurrentJobId(null);
      if (job.type === 'fetch-history') {
        void jobActions.invalidateTemperatures();
      }
      if (job.type === 'forecast') {
        void jobActions.invalidateForecasts();
      }
    },
    dataEnabled,
  );

  const activeJobData = activeJob.data ?? lastJob;
  const isFetchPending = jobActions.fetchHistory.isPending || (activeJobData?.type === 'fetch-history' && (activeJobData.status === 'pending' || activeJobData.status === 'running'));
  const isForecastPending = jobActions.forecast.isPending || (activeJobData?.type === 'forecast' && (activeJobData.status === 'pending' || activeJobData.status === 'running'));

  const chartForecasts = useMemo(
    () => [
      ...(dashboard.analysisForecasts.data ?? []),
      ...(dashboard.futureForecasts.data ?? []),
    ],
    [dashboard.analysisForecasts.data, dashboard.futureForecasts.data],
  );

  const chartPoints = useMemo(
    () => mergeTemperatureAndForecasts(dashboard.temperatures.data?.rows ?? [], chartForecasts, 'any'),
    [dashboard.temperatures.data, chartForecasts],
  );

  const onApplyFilters = () => {
    const coordinateError = validateCoordinates(draft.latitude, draft.longitude);
    if (coordinateError) {
      setValidationError(coordinateError);
      return;
    }

    const dateRangeError = validateHistoryRange(draft.historyStart, draft.historyEnd);
    if (dateRangeError) {
      setValidationError(dateRangeError);
      return;
    }

    setValidationError(null);
    setFilters(draft);
  };

  const triggerFetchHistory = async () => {
    const created = await jobActions.fetchHistory.mutateAsync();
    setCurrentJobId(created.job_id);
  };

  const triggerForecast = async () => {
    const created = await jobActions.forecast.mutateAsync();
    setCurrentJobId(created.job_id);
  };

  const dataError = dashboard.temperatures.error ?? dashboard.analysisForecasts.error ?? dashboard.futureForecasts.error;
  const isChartLoading = dashboard.temperatures.isLoading || dashboard.analysisForecasts.isLoading || dashboard.futureForecasts.isLoading;

  return (
    <main className="app-shell">
      <header className="hero panel">
        <div>
          <p className="eyebrow">timesfm-meteo</p>
          <h1>Weather Forecast Intelligence Dashboard</h1>
          <p>
            Compare actual history through History end with historical forecast analysis,
            future forecast output, uncertainty intervals, and evaluation metrics.
          </p>
        </div>
        <div className="connection-card" aria-live="polite">
          <span className={apiConfigError ? 'status-pill status-failed' : 'status-pill status-done'}>
            {apiConfigError ? 'Configuration needed' : 'API configured'}
          </span>
          {apiConfigError ? <p className="error-text">{apiConfigError}</p> : <p>Using `/api/*` through Vite proxy.</p>}
        </div>
      </header>

      <div className="dashboard-grid">
        <aside className="side-column">
          <FilterPanel
            draft={draft}
            onDraftChange={setDraft}
            onApply={onApplyFilters}
            validationError={validationError}
          />
          <JobControls
            fetchHistory={triggerFetchHistory}
            runForecast={triggerForecast}
            fetchPending={Boolean(isFetchPending)}
            forecastPending={Boolean(isForecastPending)}
            currentJob={activeJobData}
            jobError={activeJob.error ?? jobActions.fetchHistory.error ?? jobActions.forecast.error}
          />
        </aside>

        <section className="main-column">
          <section className="panel" aria-labelledby="chart-title">
            <div className="section-heading chart-heading">
              <div>
                <h2 id="chart-title">Actual history + forecast output</h2>
                <p>
                  Actual lines use History start → History end. Historical forecast analysis follows the evaluation horizon step,
                  while future forecast points start on the day after History end.
                </p>
              </div>
              <span className="status-pill">{chartPoints.length} dates</span>
            </div>
            <ForecastChart
              points={chartPoints}
              showAggregate={filters.showAggregate}
              isLoading={isChartLoading}
              error={dataError}
            />
          </section>

          <EvaluationPanel
            report={dashboard.evaluation.data}
            isLoading={dashboard.evaluation.isLoading}
            error={dashboard.evaluation.error}
          />
        </section>
      </div>
    </main>
  );
}
