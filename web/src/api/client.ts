import type {
  EvaluationReport,
  ForecastRow,
  JobCreatedResponse,
  JobResponse,
  TemperaturesResponse,
} from './types';

export class ApiConfigError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ApiConfigError';
  }
}

export class ApiHttpError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiHttpError';
    this.status = status;
  }
}

export const getApiKey = (): string => {
  const apiKey = import.meta.env.VITE_TIMESFM_API_KEY;
  if (!apiKey) {
    throw new ApiConfigError('VITE_TIMESFM_API_KEY is not configured. Create web/.env.local before using the dashboard.');
  }
  return apiKey;
};

type RequestOptions = Omit<RequestInit, 'headers'> & {
  headers?: HeadersInit;
};

export const apiFetch = async <T>(path: string, options: RequestOptions = {}): Promise<T> => {
  const apiKey = getApiKey();
  const headers = new Headers(options.headers);
  headers.set('Authorization', `Bearer ${apiKey}`);
  if (options.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(path, { ...options, headers });
  if (!response.ok) {
    let message = response.statusText;
    try {
      const payload = (await response.json()) as { detail?: string };
      message = payload.detail ?? message;
    } catch {
      // Keep statusText when response body is not JSON.
    }
    throw new ApiHttpError(response.status, message);
  }
  return (await response.json()) as T;
};

const buildQuery = (params: Record<string, string | number | undefined>): string => {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) {
      search.set(key, String(value));
    }
  }
  return search.toString();
};

export const getTemperatures = (params: {
  latitude: number;
  longitude: number;
  startDate: string;
  endDate: string;
}): Promise<TemperaturesResponse> => {
  const query = buildQuery({
    latitude: params.latitude,
    longitude: params.longitude,
    start_date: params.startDate,
    end_date: params.endDate,
  });
  return apiFetch<TemperaturesResponse>(`/api/temperatures?${query}`);
};

export const getForecasts = (params: {
  latitude: number;
  longitude: number;
  startDateFrom: string;
  startDateTo: string;
  horizonStep?: number;
}): Promise<ForecastRow[]> => {
  const query = buildQuery({
    latitude: params.latitude,
    longitude: params.longitude,
    start_date_from: params.startDateFrom,
    start_date_to: params.startDateTo,
    horizon_step: params.horizonStep,
  });
  return apiFetch<ForecastRow[]>(`/api/forecasts?${query}`);
};

export const getEvaluation = (params: {
  latitude: number;
  longitude: number;
  startDateFrom: string;
  startDateTo: string;
  horizonStep?: number;
}): Promise<EvaluationReport> => {
  const query = buildQuery({
    latitude: params.latitude,
    longitude: params.longitude,
    start_date_from: params.startDateFrom,
    start_date_to: params.startDateTo,
    horizon_step: params.horizonStep,
  });
  return apiFetch<EvaluationReport>(`/api/evaluate?${query}`);
};

export const postFetchHistory = (body: {
  latitude: number;
  longitude: number;
  start_date: string;
  end_date: string;
}): Promise<JobCreatedResponse> => apiFetch<JobCreatedResponse>('/api/fetch-history', {
  method: 'POST',
  body: JSON.stringify(body),
});

export const postForecast = (body: {
  latitude: number;
  longitude: number;
  horizon: number;
  start_date?: string;
}): Promise<JobCreatedResponse> => apiFetch<JobCreatedResponse>('/api/forecast', {
  method: 'POST',
  body: JSON.stringify(body),
});

export const getJob = (jobId: string): Promise<JobResponse> => apiFetch<JobResponse>(`/api/jobs/${jobId}`);
