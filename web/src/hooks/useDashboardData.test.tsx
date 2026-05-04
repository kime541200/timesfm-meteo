import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import * as api from '../api/client';
import type { DashboardFilters } from '../api/types';
import { nextDate } from '../lib/date';
import { numericHorizonStep, useDashboardData, useJobActions } from './useDashboardData';

const filters: DashboardFilters = {
  latitude: 25.05,
  longitude: 121.57,
  historyStart: '2024-06-01',
  historyEnd: '2024-06-03',
  forecastHorizon: 5,
  evaluationHorizonStep: 1,
  showAggregate: true,
};

const createWrapper = () => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
};

describe('useDashboardData', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('keeps evaluation horizon step separate from forecast horizon', async () => {
    const getTemperatures = vi.spyOn(api, 'getTemperatures').mockResolvedValue({ cached_count: 0, fetched_count: 0, rows: [] });
    const getForecasts = vi.spyOn(api, 'getForecasts')
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([]);
    const getEvaluation = vi.spyOn(api, 'getEvaluation').mockResolvedValue({
      location: { latitude: filters.latitude, longitude: filters.longitude },
      start_date_from: filters.historyStart,
      start_date_to: filters.historyEnd,
      horizon_step_filter: 1,
      by_horizon_step: [],
      overall: { evaluated_count: 0, pending_count: 0, max: null, min: null },
    });

    renderHook(() => useDashboardData(filters, true), { wrapper: createWrapper() });

    await waitFor(() => expect(getTemperatures).toHaveBeenCalled());
    expect(getTemperatures).toHaveBeenCalledWith({
      latitude: filters.latitude,
      longitude: filters.longitude,
      startDate: filters.historyStart,
      endDate: filters.historyEnd,
    });
    expect(getForecasts).toHaveBeenNthCalledWith(1, {
      latitude: filters.latitude,
      longitude: filters.longitude,
      startDateFrom: filters.historyStart,
      startDateTo: filters.historyEnd,
      horizonStep: 1,
    });
    expect(getForecasts).toHaveBeenNthCalledWith(2, {
      latitude: filters.latitude,
      longitude: filters.longitude,
      startDateFrom: nextDate(filters.historyEnd),
      startDateTo: nextDate(filters.historyEnd),
    });
    expect(getEvaluation).toHaveBeenCalledWith({
      latitude: filters.latitude,
      longitude: filters.longitude,
      startDateFrom: filters.historyStart,
      startDateTo: filters.historyEnd,
      horizonStep: 1,
    });
  });

  it('posts forecast with historyEnd plus one day and forecastHorizon', async () => {
    vi.spyOn(api, 'postFetchHistory').mockResolvedValue({ job_id: 'fetch-job', status: 'pending' });
    const postForecast = vi.spyOn(api, 'postForecast').mockResolvedValue({ job_id: 'forecast-job', status: 'pending' });

    const { result } = renderHook(() => useJobActions(filters), { wrapper: createWrapper() });
    await result.current.forecast.mutateAsync();

    expect(postForecast).toHaveBeenCalledWith({
      latitude: filters.latitude,
      longitude: filters.longitude,
      start_date: '2024-06-04',
      horizon: 5,
    });
  });

  it('maps any evaluation horizon step to undefined', () => {
    expect(numericHorizonStep('any')).toBeUndefined();
  });
});
