import { describe, expect, it } from 'vitest';
import type { SeriesOption } from 'echarts';
import type { DailyTemperature, ForecastRow } from '../api/types';
import {
  aggregateForecastsByTargetDate,
  buildChartOption,
  filterForecastsByHorizonStep,
  mergeTemperatureAndForecasts,
} from './chartData';

const historicalForecasts: ForecastRow[] = [
  {
    start_date: '2024-06-01',
    target_date: '2024-06-02',
    max_p10: 28,
    max_p50: 30,
    max_p90: 32,
    min_p10: 20,
    min_p50: 22,
    min_p90: 24,
    model_id: 'model',
    history_days: 730,
  },
  {
    start_date: '2024-05-31',
    target_date: '2024-06-02',
    max_p10: 27,
    max_p50: 29,
    max_p90: 33,
    min_p10: 19,
    min_p50: 21,
    min_p90: 25,
    model_id: 'model',
    history_days: 730,
  },
  {
    start_date: '2024-06-02',
    target_date: '2024-06-02',
    max_p10: 29,
    max_p50: 31,
    max_p90: 34,
    min_p10: 21,
    min_p50: 23,
    min_p90: 26,
    model_id: 'model',
    history_days: 730,
  },
];

const futureForecast: ForecastRow = {
  start_date: '2024-06-03',
  target_date: '2024-06-04',
  max_p10: 30,
  max_p50: 32,
  max_p90: 34,
  min_p10: 22,
  min_p50: 24,
  min_p90: 26,
  model_id: 'model',
  history_days: 730,
};

const temperatures: DailyTemperature[] = [
  { date: '2024-06-01', temperature_max: 29.5, temperature_min: 21.5 },
  { date: '2024-06-02', temperature_max: 30.5, temperature_min: 22.5 },
  { date: '2024-06-03', temperature_max: 31.5, temperature_min: 23.5 },
];

describe('chart data transforms', () => {
  it('keeps all forecasts for any horizon step', () => {
    expect(filterForecastsByHorizonStep(historicalForecasts, 'any')).toHaveLength(3);
  });

  it('filters forecasts by numeric horizon step', () => {
    expect(filterForecastsByHorizonStep(historicalForecasts, 1)).toHaveLength(1);
    expect(filterForecastsByHorizonStep(historicalForecasts, 0)).toHaveLength(1);
  });

  it('aggregates average p50 by target date', () => {
    const aggregate = aggregateForecastsByTargetDate(historicalForecasts).get('2024-06-02');
    expect(aggregate).toEqual({ maxP50: 30, minP50: 22, count: 3 });
  });

  it('merges actuals with distinct historical forecast rows by target date', () => {
    const points = mergeTemperatureAndForecasts([{ date: '2024-06-02', temperature_max: 30.5, temperature_min: 22.5 }], historicalForecasts, 'any');
    expect(points).toHaveLength(1);
    expect(points[0].actualMax).toBe(30.5);
    expect(points[0].forecasts).toHaveLength(3);
    expect(points[0].aggregateMaxP50).toBe(30);
  });

  it('keeps future forecast dates after the actual history range', () => {
    const points = mergeTemperatureAndForecasts(temperatures, [futureForecast], 'any');
    expect(points.map((point) => point.date)).toEqual(['2024-06-01', '2024-06-02', '2024-06-03', '2024-06-04']);
    expect(points[2].actualMax).toBe(31.5);
    expect(points[3].actualMax).toBeNull();
    expect(points[3].forecasts).toEqual([futureForecast]);
  });

  it('handles empty inputs', () => {
    expect(mergeTemperatureAndForecasts([], [], 'any')).toEqual([]);
  });

  it('adds aggregate series only when enabled and de-emphasizes raw points', () => {
    const points = mergeTemperatureAndForecasts([{ date: '2024-06-02', temperature_max: 30.5, temperature_min: 22.5 }], historicalForecasts, 'any');
    const withAggregate = buildChartOption(points, true);
    const withoutAggregate = buildChartOption(points, false);

    const withSeries = withAggregate.series as SeriesOption[];
    const withoutSeries = withoutAggregate.series as SeriesOption[];

    expect(withSeries.some((series) => series.name === 'Aggregate max p50')).toBe(true);
    expect(withoutSeries.some((series) => series.name === 'Aggregate max p50')).toBe(false);

    const rawWithAggregate = withSeries.find((series) => series.name === 'Forecast max p50') as { itemStyle: { opacity: number } };
    const rawWithoutAggregate = withoutSeries.find((series) => series.name === 'Forecast max p50') as { itemStyle: { opacity: number } };
    expect(rawWithAggregate.itemStyle.opacity).toBeLessThan(rawWithoutAggregate.itemStyle.opacity);
  });
});
