import ReactECharts from 'echarts-for-react';
import type { ChartDataPoint } from '../lib/chartData';
import { buildChartOption } from '../lib/chartData';

type ForecastChartProps = {
  points: ChartDataPoint[];
  showAggregate: boolean;
  isLoading: boolean;
  error: unknown;
};

export default function ForecastChart({ points, showAggregate, isLoading, error }: ForecastChartProps) {
  if (error) {
    return <div className="state-box error-text" role="alert">Chart data failed to load: {String((error as Error).message ?? error)}</div>;
  }

  if (isLoading) {
    return <div className="state-box">Loading chart data…</div>;
  }

  if (points.length === 0) {
    return <div className="state-box">No data for the selected range. Try Fetch History or Run Forecast.</div>;
  }

  return (
    <ReactECharts
      option={buildChartOption(points, showAggregate)}
      notMerge
      lazyUpdate
      style={{ height: 520, width: '100%' }}
    />
  );
}
