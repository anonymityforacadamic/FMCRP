from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

from .assignment import hungarian
from .config import DEFAULT_FIWI_THRESHOLD, DEFAULT_MATCHING_WINDOW_SIZE
from .models import FunctionSpec, Replica


@dataclass
class Decision:
    function: str
    replica: str
    branch: str
    fiwi: float
    cost: float
    missing_dependencies: list[str]
    cold_start: bool


class FMCRPScheduler:
    """Fine-grained matching and replica-retention policy."""

    def __init__(
        self,
        functions: Iterable[FunctionSpec],
        replicas: Iterable[Replica] = (),
        theta: float = DEFAULT_FIWI_THRESHOLD,
        matching_window_size: int = DEFAULT_MATCHING_WINDOW_SIZE,
    ):
        if matching_window_size < 1:
            raise ValueError("matching_window_size must be positive")
        self.functions = {function.name: function for function in functions}
        self.replicas = list(replicas)
        self.theta = theta
        self.matching_window_size = matching_window_size

    def fiwi(self, function_name: str, rates: dict[str, float]) -> float:
        target = self.functions[function_name]
        others = [name for name in self.functions if name != function_name]
        if not others:
            return 0.0
        denominator = 0.0
        for name in others:
            other = self.functions[name]
            overlap = len(target.dependencies & other.dependencies) / max(1, len(target.dependencies))
            denominator += overlap * rates.get(name, 0.0)
        if denominator == 0:
            return 0.0
        return (len(self.functions) - 1) * rates.get(function_name, 0.0) / denominator

    def _cost(self, replica: Replica, function: FunctionSpec) -> float:
        return function.cold_start_cost() if replica.is_virtual else function.completion_cost(replica)

    def _virtuals(self, count: int) -> list[Replica]:
        return [Replica(f"virtual-{index}", "*", "*", is_virtual=True) for index in range(count)]

    def _apply(self, assignments: list[tuple[FunctionSpec, Replica]], branch: str, impact: float) -> list[Decision]:
        decisions = []
        for function, replica in assignments:
            cost = self._cost(replica, function)
            cold_start = replica.is_virtual
            if cold_start:
                replica.base, replica.runtime = function.base, function.runtime
                replica.is_virtual = False
                self.replicas.append(replica)
                missing = set(function.dependencies)
            else:
                missing = replica.complete_for(function)
            decisions.append(Decision(function.name, replica.name, branch, impact, cost, sorted(missing), cold_start))
        return decisions

    def schedule(
        self,
        current: str,
        rates: dict[str, float],
        predicted_counts: dict[str, int] | None = None,
        window_limit: int | None = None,
    ) -> list[Decision]:
        function = self.functions[current]
        impact = self.fiwi(current, rates)
        window_limit = self.matching_window_size if window_limit is None else window_limit
        if impact <= self.theta:
            candidates = [replica for replica in self.replicas if replica.compatible_with(function)]
            replica = min(candidates, key=lambda item: function.completion_cost(item), default=self._virtuals(1)[0])
            return self._apply([(function, replica)], "greedy", impact)

        group = [function]
        for name, count in (predicted_counts or {}).items():
            if name == current:
                count = max(0, count - 1)
            group.extend([self.functions[name]] * min(count, window_limit - len(group)))
            if len(group) >= window_limit:
                break
        candidates = self.replicas[:] + self._virtuals(max(0, len(group) - len(self.replicas)))
        large = 1e12
        matrix = [[min(self._cost(replica, request), large) for request in group] for replica in candidates]
        rows = hungarian(matrix)
        return self._apply([(group[column], candidates[row]) for column, row in enumerate(rows)], "hungarian", impact)

    def retention_actions(
        self,
        demand: dict[tuple[str, str, frozenset[str]], int],
        requested_last_period: dict[str, int],
        hits_last_period: dict[str, int],
        previous_accuracy: float,
    ) -> dict[str, list[str]]:
        """Algorithm 2; returns keep/close/open decisions without deleting state."""
        remaining = dict(demand)
        kept: list[Replica] = []
        surplus: list[Replica] = []
        for replica in self.replicas:
            exact = (replica.base, replica.runtime, frozenset(replica.dependencies))
            if remaining.get(exact, 0) > 0:
                kept.append(replica); remaining[exact] -= 1
            else:
                surplus.append(replica)
        still_surplus = []
        for replica in surplus:
            matches = [key for key, count in remaining.items() if count > 0 and key[0] == replica.base and key[1] == replica.runtime and key[2] <= replica.dependencies]
            if matches:
                chosen = max(matches, key=lambda key: len(key[2])); kept.append(replica); remaining[chosen] -= 1
            else:
                still_surplus.append(replica)
        q = min(len(still_surplus), max(1, math.ceil((1 - previous_accuracy) * len(still_surplus)))) if still_surplus else 0
        def score(replica: Replica) -> float:
            avoided = sum(requested_last_period.get(dep, 0) * (hits_last_period.get(dep, 0) / max(1, requested_last_period.get(dep, 0))) for dep in replica.dependencies)
            return avoided / max(1.0, replica.memory_mb)
        retained = sorted(still_surplus, key=lambda replica: (-score(replica), replica.memory_mb))[:q]
        kept.extend(retained)
        closes = [replica for replica in still_surplus if replica not in retained]
        opens = []
        for (base, runtime, dependencies), count in remaining.items():
            opens.extend([f"open:{base}/{runtime}:{','.join(sorted(dependencies))}"] * max(0, count))
        return {"keep": [replica.name for replica in kept], "close": [replica.name for replica in closes], "open_or_complete": opens}
