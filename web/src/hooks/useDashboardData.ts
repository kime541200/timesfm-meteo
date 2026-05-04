import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getEvaluation, getForecasts, getJob, getTemperatures, postFetchHistory, postForecast } from '../api/client';
import type { DashboardFilters, JobResponse } from '../api/types';
import { nextDate } from '../lib/date';

export const numericHorizonStep = (value: DashboardFilters['evaluationHorizonStep']): number | undefined =>
  value === 'any' ? undefined : value;

export const useDashboardData = (filters: DashboardFilters, enabled: boolean) => {
  const evaluationHorizonStep = numericHorizonStep(filters.evaluationHorizonStep);
  const forecastStartDate = nextDate(filters.historyEnd);
  const baseParams = {
    latitude: filters.latitude,
    longitude: filters.longitude,
  };

  const temperatures = useQuery({
    queryKey: ['temperatures', filters.latitude, filters.longitude, filters.historyStart, filters.historyEnd],
    queryFn: () => getTemperatures({ ...baseParams, startDate: filters.historyStart, endDate: filters.historyEnd }),
    enabled,
  });

  const analysisForecasts = useQuery({
    queryKey: ['forecasts', 'analysis', filters.latitude, filters.longitude, filters.historyStart, filters.historyEnd, evaluationHorizonStep ?? 'any'],
    queryFn: () => getForecasts({
      ...baseParams,
      startDateFrom: filters.historyStart,
      startDateTo: filters.historyEnd,
      horizonStep: evaluationHorizonStep,
    }),
    enabled,
  });

  const futureForecasts = useQuery({
    queryKey: ['forecasts', 'future', filters.latitude, filters.longitude, forecastStartDate],
    queryFn: () => getForecasts({
      ...baseParams,
      startDateFrom: forecastStartDate,
      startDateTo: forecastStartDate,
    }),
    enabled,
  });

  const evaluation = useQuery({
    queryKey: ['evaluation', filters.latitude, filters.longitude, filters.historyStart, filters.historyEnd, evaluationHorizonStep ?? 'any'],
    queryFn: () => getEvaluation({
      ...baseParams,
      startDateFrom: filters.historyStart,
      startDateTo: filters.historyEnd,
      horizonStep: evaluationHorizonStep,
    }),
    enabled,
  });

  return { temperatures, analysisForecasts, futureForecasts, evaluation };
};

export const useJobActions = (filters: DashboardFilters) => {
  const queryClient = useQueryClient();
  const forecastStartDate = nextDate(filters.historyEnd);

  const invalidateTemperatures = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['temperatures'] }),
      queryClient.invalidateQueries({ queryKey: ['evaluation'] }),
    ]);
  };

  const invalidateForecasts = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['forecasts'] }),
      queryClient.invalidateQueries({ queryKey: ['evaluation'] }),
    ]);
  };

  const fetchHistory = useMutation({
    mutationFn: () => postFetchHistory({
      latitude: filters.latitude,
      longitude: filters.longitude,
      start_date: filters.historyStart,
      end_date: filters.historyEnd,
    }),
  });

  const forecast = useMutation({
    mutationFn: () => postForecast({
      latitude: filters.latitude,
      longitude: filters.longitude,
      horizon: filters.forecastHorizon,
      start_date: forecastStartDate,
    }),
  });

  return { fetchHistory, forecast, invalidateTemperatures, invalidateForecasts };
};

export const useJobPolling = (
  jobId: string | null,
  onDone: (job: JobResponse) => void,
  enabled: boolean,
) => useQuery({
  queryKey: ['job', jobId],
  queryFn: async () => {
    if (!jobId) throw new Error('jobId is required');
    return getJob(jobId);
  },
  enabled: enabled && Boolean(jobId),
  refetchInterval: (query) => {
    const status = query.state.data?.status;
    return status === 'done' || status === 'failed' ? false : 1_500;
  },
  refetchIntervalInBackground: true,
  select: (job) => {
    if (job.status === 'done') {
      onDone(job);
    }
    return job;
  },
});
