import type { EChartsOption, SeriesOption } from 'echarts';
import type { DailyTemperature, ForecastRow } from '../api/types';

export type HorizonStepFilter = 'any' | number;

export type ChartDataPoint = {
  date: string;
  actualMax: number | null;
  actualMin: number | null;
  forecasts: ForecastRow[];
  aggregateMaxP50: number | null;
  aggregateMinP50: number | null;
};

const dateDiffDays = (from: string, to: string): number => {
  const start = new Date(`${from}T00:00:00Z`).getTime();
  const end = new Date(`${to}T00:00:00Z`).getTime();
  return Math.round((end - start) / 86_400_000);
};

export const filterForecastsByHorizonStep = (
  forecasts: ForecastRow[],
  horizonStep: HorizonStepFilter,
): ForecastRow[] => {
  if (horizonStep === 'any') {
    return forecasts;
  }
  return forecasts.filter((row) => dateDiffDays(row.start_date, row.target_date) === horizonStep);
};

export const aggregateForecastsByTargetDate = (forecasts: ForecastRow[]): Map<string, { maxP50: number; minP50: number; count: number }> => {
  const grouped = new Map<string, { maxTotal: number; minTotal: number; count: number }>();
  for (const row of forecasts) {
    const current = grouped.get(row.target_date) ?? { maxTotal: 0, minTotal: 0, count: 0 };
    current.maxTotal += row.max_p50;
    current.minTotal += row.min_p50;
    current.count += 1;
    grouped.set(row.target_date, current);
  }

  const aggregated = new Map<string, { maxP50: number; minP50: number; count: number }>();
  for (const [date, value] of grouped) {
    aggregated.set(date, {
      maxP50: value.maxTotal / value.count,
      minP50: value.minTotal / value.count,
      count: value.count,
    });
  }
  return aggregated;
};

export const mergeTemperatureAndForecasts = (
  temperatures: DailyTemperature[],
  forecasts: ForecastRow[],
  evaluationHorizonStep: HorizonStepFilter,
): ChartDataPoint[] => {
  const filteredForecasts = filterForecastsByHorizonStep(forecasts, evaluationHorizonStep);
  const actualByDate = new Map(temperatures.map((row) => [row.date, row]));
  const forecastsByDate = new Map<string, ForecastRow[]>();
  for (const forecast of filteredForecasts) {
    const list = forecastsByDate.get(forecast.target_date) ?? [];
    list.push(forecast);
    forecastsByDate.set(forecast.target_date, list);
  }
  const aggregates = aggregateForecastsByTargetDate(filteredForecasts);
  const dates = Array.from(new Set([...actualByDate.keys(), ...forecastsByDate.keys()])).sort();

  return dates.map((date) => {
    const actual = actualByDate.get(date);
    const aggregate = aggregates.get(date);
    return {
      date,
      actualMax: actual?.temperature_max ?? null,
      actualMin: actual?.temperature_min ?? null,
      forecasts: forecastsByDate.get(date) ?? [],
      aggregateMaxP50: aggregate?.maxP50 ?? null,
      aggregateMinP50: aggregate?.minP50 ?? null,
    };
  });
};

const rawForecastScatter = (points: ChartDataPoint[], key: 'max_p50' | 'min_p50'): [string, number][] =>
  points.flatMap((point) => point.forecasts.map((forecast) => [point.date, forecast[key]] as [string, number]));

const intervalAreaSeries = (
  name: string,
  points: ChartDataPoint[],
  lowerKey: 'max_p10' | 'min_p10',
  upperKey: 'max_p90' | 'min_p90',
  color: string,
  opacity: number,
): SeriesOption[] => {
  const lower = points.map((point): [string, number | null] => {
    const values = point.forecasts.map((forecast) => forecast[lowerKey]);
    return [point.date, values.length ? Math.min(...values) : null];
  });
  const width = points.map((point): [string, number | null] => {
    const lowers = point.forecasts.map((forecast) => forecast[lowerKey]);
    const uppers = point.forecasts.map((forecast) => forecast[upperKey]);
    if (!lowers.length || !uppers.length) {
      return [point.date, null];
    }
    return [point.date, Math.max(...uppers) - Math.min(...lowers)];
  });

  return [
    {
      name: `${name} lower bound`,
      type: 'line',
      data: lower,
      stack: `${name}-interval`,
      symbol: 'none',
      lineStyle: { opacity: 0 },
      itemStyle: { opacity: 0 },
      tooltip: { show: false },
    },
    {
      name: `${name} p10–p90 interval`,
      type: 'line',
      data: width,
      stack: `${name}-interval`,
      symbol: 'none',
      lineStyle: { opacity: 0 },
      areaStyle: { color, opacity },
      tooltip: { show: false },
    },
  ];
};

export const buildChartOption = (points: ChartDataPoint[], showAggregate: boolean): EChartsOption => {
  const rawOpacity = showAggregate ? 0.22 : 0.72;
  const rawSymbolSize = showAggregate ? 4 : 6;

  const series: SeriesOption[] = [
    {
      name: 'Actual max',
      type: 'line',
      data: points.map((point) => [point.date, point.actualMax]),
      connectNulls: false,
      symbolSize: 7,
      lineStyle: { color: '#DC2626', width: 2.4 },
      itemStyle: { color: '#DC2626' },
    },
    {
      name: 'Actual min',
      type: 'line',
      data: points.map((point) => [point.date, point.actualMin]),
      connectNulls: false,
      symbolSize: 7,
      lineStyle: { color: '#2563EB', width: 2.4 },
      itemStyle: { color: '#2563EB' },
    },
    ...intervalAreaSeries('Max forecast', points, 'max_p10', 'max_p90', '#FCA5A5', showAggregate ? 0.08 : 0.16),
    ...intervalAreaSeries('Min forecast', points, 'min_p10', 'min_p90', '#93C5FD', showAggregate ? 0.08 : 0.16),
    {
      name: 'Forecast max p50',
      type: 'scatter',
      data: rawForecastScatter(points, 'max_p50'),
      symbolSize: rawSymbolSize,
      itemStyle: { color: '#EF4444', opacity: rawOpacity },
    },
    {
      name: 'Forecast min p50',
      type: 'scatter',
      data: rawForecastScatter(points, 'min_p50'),
      symbolSize: rawSymbolSize,
      itemStyle: { color: '#3B82F6', opacity: rawOpacity },
    },
  ];

  if (showAggregate) {
    series.push(
      {
        name: 'Aggregate max p50',
        type: 'line',
        data: points.map((point) => [point.date, point.aggregateMaxP50]),
        connectNulls: false,
        symbolSize: 8,
        lineStyle: { color: '#F59E0B', width: 3.2 },
        itemStyle: { color: '#F59E0B' },
      },
      {
        name: 'Aggregate min p50',
        type: 'line',
        data: points.map((point) => [point.date, point.aggregateMinP50]),
        connectNulls: false,
        symbolSize: 8,
        lineStyle: { color: '#D97706', width: 3.2, type: 'dashed' },
        itemStyle: { color: '#D97706' },
      },
    );
  }

  return {
    backgroundColor: 'transparent',
    color: ['#DC2626', '#2563EB', '#EF4444', '#3B82F6', '#F59E0B'],
    tooltip: { trigger: 'axis' },
    legend: { top: 0, type: 'scroll' },
    grid: { top: 72, right: 24, bottom: 64, left: 56 },
    dataZoom: [{ type: 'inside' }, { type: 'slider', height: 24 }],
    xAxis: { type: 'time', name: 'Target date' },
    yAxis: { type: 'value', name: '°C', scale: true },
    series,
  };
};
