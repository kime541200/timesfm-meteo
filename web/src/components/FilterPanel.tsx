import type { DashboardFilters } from '../api/types';

type FilterPanelProps = {
  draft: DashboardFilters;
  onDraftChange: (value: DashboardFilters) => void;
  onApply: () => void;
  validationError: string | null;
};

export default function FilterPanel({ draft, onDraftChange, onApply, validationError }: FilterPanelProps) {
  return (
    <section className="panel filter-panel" aria-labelledby="filters-title">
      <div className="section-heading">
        <h2 id="filters-title">Filters</h2>
        <p>History start/end control the actual range. Forecast horizon controls future days; Evaluation horizon step only filters historical forecast analysis.</p>
      </div>

      <div className="filter-grid">
        <label>
          Latitude
          <input
            type="number"
            step="0.0001"
            value={draft.latitude}
            onChange={(event) => onDraftChange({ ...draft, latitude: Number(event.target.value) })}
          />
        </label>
        <label>
          Longitude
          <input
            type="number"
            step="0.0001"
            value={draft.longitude}
            onChange={(event) => onDraftChange({ ...draft, longitude: Number(event.target.value) })}
          />
        </label>
        <label>
          History start
          <input
            type="date"
            value={draft.historyStart}
            onChange={(event) => onDraftChange({ ...draft, historyStart: event.target.value })}
          />
        </label>
        <label>
          History end
          <input
            type="date"
            value={draft.historyEnd}
            onChange={(event) => onDraftChange({ ...draft, historyEnd: event.target.value })}
          />
        </label>
        <label>
          Forecast horizon
          <input
            type="number"
            min="1"
            step="1"
            value={draft.forecastHorizon}
            onChange={(event) => onDraftChange({ ...draft, forecastHorizon: Number(event.target.value) })}
          />
        </label>
        <label>
          Evaluation horizon step
          <select
            value={draft.evaluationHorizonStep}
            onChange={(event) => onDraftChange({
              ...draft,
              evaluationHorizonStep: event.target.value === 'any' ? 'any' : Number(event.target.value),
            })}
          >
            <option value="any">Any (all forecast origins)</option>
            <option value={0}>0</option>
            <option value={1}>1</option>
            <option value={2}>2</option>
          </select>
        </label>
        <label className="toggle-label">
          <input
            type="checkbox"
            checked={draft.showAggregate}
            onChange={(event) => onDraftChange({ ...draft, showAggregate: event.target.checked })}
          />
          Show aggregate average
        </label>
      </div>

      {validationError ? <p className="error-text" role="alert">{validationError}</p> : null}

      <button type="button" className="primary-button" onClick={onApply}>
        Apply filters
      </button>
    </section>
  );
}
