"""TimesFM inference engine — domain-agnostic wrapper around upstream `timesfm`.

This module is intentionally decoupled from `timesfm_meteo` domain types so it
can be packaged into a standalone inference server later. See
`docs/timesfm-engine.md` for engine usage and parameter rationale (defaults
trade compile speed against future flexibility; the underlying TimesFM 2.5
architecture supports up to context=16384 and horizon=1000).

Heavy dependencies (`timesfm`, `torch`, `numpy`) are loaded lazily inside the
constructor so importing this module without the `forecast` extra installed
does not fail.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from timesfm_meteo.models import QuantileForecastResult

if TYPE_CHECKING:
    import numpy as np


_QUANTILE_LEVELS: tuple[float, ...] = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)


class ForecastEngine(Protocol):
    """Inference contract: numeric series in, quantile forecasts out."""

    def forecast(
        self, series_list: list[np.ndarray], horizon: int
    ) -> list[QuantileForecastResult]: ...


class TimesFMEngine:
    """Wraps a compiled TimesFM 2.5 model behind the `ForecastEngine` Protocol."""

    def __init__(
        self,
        model_id: str = "google/timesfm-2.5-200m-pytorch",
        max_context: int = 1024,
        max_horizon: int = 32,
        normalize_inputs: bool = True,
        use_continuous_quantile_head: bool = True,
        force_flip_invariance: bool = True,
        fix_quantile_crossing: bool = True,
    ) -> None:
        try:
            import numpy as np  # noqa: F401  (kept available for forecast())
            import timesfm
        except ImportError as exc:
            raise RuntimeError(
                "TimesFM dependencies not installed. Run: uv sync --extra forecast"
            ) from exc

        self._timesfm = timesfm
        self._np = np
        self._model_id = model_id

        model_cls = getattr(timesfm, "TimesFM_2p5_200M_torch", None)
        if model_cls is None:
            raise RuntimeError(
                "timesfm package does not expose TimesFM_2p5_200M_torch — torch backend "
                "may not be installed. Run: uv sync --extra forecast"
            )

        self._model = model_cls.from_pretrained(model_id)
        self._model.compile(
            timesfm.ForecastConfig(
                max_context=max_context,
                max_horizon=max_horizon,
                normalize_inputs=normalize_inputs,
                use_continuous_quantile_head=use_continuous_quantile_head,
                force_flip_invariance=force_flip_invariance,
                fix_quantile_crossing=fix_quantile_crossing,
            )
        )

    def forecast(
        self, series_list: list[np.ndarray], horizon: int
    ) -> list[QuantileForecastResult]:
        if not series_list:
            return []

        point_array, quantile_array = self._model.forecast(
            horizon=horizon, inputs=series_list
        )
        # point_array.shape    == (batch, horizon)
        # quantile_array.shape == (batch, horizon, 10): index 0 = mean, 1..9 = p10..p90.
        results: list[QuantileForecastResult] = []
        for i in range(len(series_list)):
            point_values = [float(v) for v in point_array[i, :horizon]]
            quantiles = {
                level: [float(v) for v in quantile_array[i, :horizon, idx + 1]]
                for idx, level in enumerate(_QUANTILE_LEVELS)
            }
            results.append(
                QuantileForecastResult(
                    horizon=horizon,
                    point=point_values,
                    quantiles=quantiles,
                )
            )
        return results
