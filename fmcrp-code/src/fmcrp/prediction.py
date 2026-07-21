from __future__ import annotations

import math
from collections import defaultdict
from typing import Iterable

from .config import (
    DEFAULT_HISTORY_WINDOW_SIZE,
    DEFAULT_PREDICTION_CONFIDENCE,
    DEFAULT_SMOOTHING_ALPHA,
)


def arrival_rate(timestamps: Iterable[float]) -> float:
    values = list(timestamps)
    if len(values) < 2 or values[-1] <= values[0]:
        return 0.0
    return len(values) / (values[-1] - values[0])


def poisson_quantile(mean: float, confidence: float) -> int:
    """Return the smallest x whose Poisson CDF is at least confidence."""
    if mean <= 0:
        return 0
    if not 0 < confidence < 1:
        raise ValueError("confidence must be in (0, 1)")
    probability = math.exp(-mean)
    cdf = probability
    x = 0
    while cdf < confidence:
        x += 1
        probability *= mean / x
        cdf += probability
    return x


def predicted_demands(
    histories: dict[str, list[float]],
    configuration_by_function: dict[str, tuple[str, str, frozenset[str]]],
    horizon_seconds: float,
    confidence: float = DEFAULT_PREDICTION_CONFIDENCE,
    alpha: float = DEFAULT_SMOOTHING_ALPHA,
    observed: dict[tuple[str, str, frozenset[str]], float] | None = None,
    history_window_size: int = DEFAULT_HISTORY_WINDOW_SIZE,
) -> tuple[dict[str, float], dict[tuple[str, str, frozenset[str]], float]]:
    """Estimate aggregate Poisson demand and smooth each configuration."""
    if history_window_size < 2:
        raise ValueError("history_window_size must be at least 2")
    if not 0 <= alpha <= 1:
        raise ValueError("alpha must be in [0, 1]")
    rates = {name: arrival_rate(history[-history_window_size:]) for name, history in histories.items()}
    grouped: dict[tuple[str, str, frozenset[str]], float] = defaultdict(float)
    for name, rate in rates.items():
        grouped[configuration_by_function[name]] += rate
    observed = observed or {}
    demands = {}
    for config, rate in grouped.items():
        estimate = poisson_quantile(rate * horizon_seconds, confidence)
        demands[config] = alpha * estimate + (1 - alpha) * observed.get(config, estimate)
    return rates, demands


def keep_alive_interval(rate: float, confidence: float) -> float:
    return float("inf") if rate <= 0 else -math.log(1 - confidence) / rate
