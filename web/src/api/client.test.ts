import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiConfigError, ApiHttpError, getForecasts, getTemperatures } from './client';

const setApiKey = (value: string | undefined) => {
  vi.stubEnv('VITE_TIMESFM_API_KEY', value);
};

describe('api client', () => {
  beforeEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it('attaches bearer token and calls /api path', async () => {
    setApiKey('secret');
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ cached_count: 0, fetched_count: 0, rows: [] }), { status: 200 }),
    );
    vi.stubGlobal('fetch', fetchMock);

    await getTemperatures({ latitude: 25.05, longitude: 121.57, startDate: '2024-06-01', endDate: '2024-06-07' });

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toContain('/api/temperatures?');
    expect(String(url)).toContain('start_date=2024-06-01');
    expect((init.headers as Headers).get('Authorization')).toBe('Bearer secret');
  });

  it('passes horizon_step when provided', async () => {
    setApiKey('secret');
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify([]), { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);

    await getForecasts({ latitude: 25.05, longitude: 121.57, startDateFrom: '2024-06-01', startDateTo: '2024-06-30', horizonStep: 1 });

    const [url] = fetchMock.mock.calls[0];
    expect(String(url)).toContain('horizon_step=1');
  });

  it('throws configuration error when api key is missing', async () => {
    setApiKey(undefined);
    await expect(getTemperatures({ latitude: 25.05, longitude: 121.57, startDate: '2024-06-01', endDate: '2024-06-07' })).rejects.toBeInstanceOf(ApiConfigError);
  });

  it('throws HTTP error with detail when response is not ok', async () => {
    setApiKey('secret');
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'Invalid API key' }), { status: 401 })));

    await expect(getTemperatures({ latitude: 25.05, longitude: 121.57, startDate: '2024-06-01', endDate: '2024-06-07' })).rejects.toMatchObject({
      status: 401,
      message: 'Invalid API key',
    } satisfies Partial<ApiHttpError>);
  });
});
