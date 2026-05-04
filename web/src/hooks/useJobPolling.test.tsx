import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';
import * as api from '../api/client';
import type { JobResponse } from '../api/types';
import { useJobPolling } from './useDashboardData';

const makeJob = (status: JobResponse['status'], overrides: Partial<JobResponse> = {}): JobResponse => ({
  id: 'job-1',
  type: 'forecast',
  status,
  params: {},
  result: status === 'done' ? { ok: true } : null,
  error: status === 'failed' ? 'boom' : null,
  created_at: '2024-06-01T00:00:00Z',
  updated_at: '2024-06-01T00:00:00Z',
  ...overrides,
});

const wrapper = ({ children }: { children: ReactNode }) => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
};

describe('useJobPolling', () => {
  it('calls onDone when job reaches done', async () => {
    const onDone = vi.fn();
    vi.spyOn(api, 'getJob').mockResolvedValue(makeJob('done'));

    const { result } = renderHook(() => useJobPolling('job-1', onDone, true), { wrapper });

    await waitFor(() => expect(result.current.data?.status).toBe('done'));
    expect(onDone).toHaveBeenCalledWith(expect.objectContaining({ status: 'done' }));
  });

  it('surfaces failed job without calling onDone', async () => {
    const onDone = vi.fn();
    vi.spyOn(api, 'getJob').mockResolvedValue(makeJob('failed'));

    const { result } = renderHook(() => useJobPolling('job-1', onDone, true), { wrapper });

    await waitFor(() => expect(result.current.data?.status).toBe('failed'));
    expect(result.current.data?.error).toBe('boom');
    expect(onDone).not.toHaveBeenCalled();
  });
});
