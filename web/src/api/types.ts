export type DailyTemperature = {
  date: string;
  temperature_max: number;
  temperature_min: number;
};

export type TemperaturesResponse = {
  cached_count: number;
  fetched_count: number;
  rows: DailyTemperature[];
};

export type ForecastRow = {
  start_date: string;
  target_date: string;
  max_p10: number;
  max_p50: number;
  max_p90: number;
  min_p10: number;
  min_p50: number;
  min_p90: number;
  model_id: string;
  history_days: number;
};

export type VariableMetrics = {
  mae_p50: number;
  interval_coverage: number;
  mean_interval_width: number;
};

export type GroupMetrics = {
  evaluated_count: number;
  pending_count: number;
  max: VariableMetrics | null;
  min: VariableMetrics | null;
};

export type HorizonStepReport = {
  horizon_step: number;
  metrics: GroupMetrics;
};

export type EvaluationReport = {
  location: {
    latitude: number;
    longitude: number;
  };
  start_date_from: string;
  start_date_to: string;
  horizon_step_filter: number | null;
  by_horizon_step: HorizonStepReport[];
  overall: GroupMetrics;
};

export type JobStatus = 'pending' | 'running' | 'done' | 'failed';
export type JobType = 'forecast' | 'fetch-history';

export type JobCreatedResponse = {
  job_id: string;
  status: JobStatus;
};

export type JobResponse = {
  id: string;
  type: JobType;
  status: JobStatus;
  params: Record<string, unknown>;
  result: Record<string, unknown> | null;
  error: string | null;
  created_at: string;
  updated_at: string;
};

export type DashboardFilters = {
  latitude: number;
  longitude: number;
  historyStart: string;
  historyEnd: string;
  forecastHorizon: number;
  evaluationHorizonStep: 'any' | number;
  showAggregate: boolean;
};
