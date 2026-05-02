import pytest

from timesfm_meteo.evaluation.metrics import (
    interval_coverage,
    mean_absolute_error,
    mean_interval_width,
)


def test_mean_absolute_error() -> None:
    assert mean_absolute_error([1.0, 2.0, 3.0], [1.0, 3.0, 1.0]) == 1.0


def test_interval_coverage() -> None:
    assert (
        interval_coverage(
            [10.0, 20.0, 30.0],
            [9.0, 19.0, 31.0],
            [11.0, 21.0, 32.0],
        )
        == 2 / 3
    )


def test_mean_interval_width() -> None:
    assert mean_interval_width([9.0, 19.0], [11.0, 23.0]) == 3.0


def test_metrics_reject_empty_inputs() -> None:
    with pytest.raises(ValueError):
        mean_absolute_error([], [])
