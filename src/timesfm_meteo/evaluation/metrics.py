def mean_absolute_error(actual: list[float], predicted: list[float]) -> float:
    """Calculate mean absolute error for equal-length numeric sequences."""
    if len(actual) != len(predicted):
        raise ValueError("actual and predicted must have the same length")
    if not actual:
        raise ValueError("actual and predicted must not be empty")

    return sum(abs(a - p) for a, p in zip(actual, predicted, strict=True)) / len(actual)


def interval_coverage(actual: list[float], lower: list[float], upper: list[float]) -> float:
    """Calculate the share of actual values inside prediction intervals."""
    if not (len(actual) == len(lower) == len(upper)):
        raise ValueError("actual, lower, and upper must have the same length")
    if not actual:
        raise ValueError("actual, lower, and upper must not be empty")

    covered = sum(lo <= value <= hi for value, lo, hi in zip(actual, lower, upper, strict=True))
    return covered / len(actual)


def mean_interval_width(lower: list[float], upper: list[float]) -> float:
    """Calculate mean prediction interval width."""
    if len(lower) != len(upper):
        raise ValueError("lower and upper must have the same length")
    if not lower:
        raise ValueError("lower and upper must not be empty")

    return sum(hi - lo for lo, hi in zip(lower, upper, strict=True)) / len(lower)
