from __future__ import annotations

from dataclasses import dataclass, field
from typing import FrozenSet


@dataclass(frozen=True)
class FunctionSpec:
    name: str
    base: str
    runtime: str
    dependencies: FrozenSet[str]
    load_costs: dict[str, float]
    base_cost: float = 1.0
    runtime_cost: float = 1.0

    def completion_cost(self, replica: "Replica") -> float:
        """Return infinity for incompatible base or runtime layers."""
        if replica.base != self.base or replica.runtime != self.runtime:
            return float("inf")
        return sum(self.load_costs[dep] for dep in self.dependencies - replica.dependencies)

    def cold_start_cost(self) -> float:
        return self.base_cost + self.runtime_cost + sum(self.load_costs.values())


@dataclass
class Replica:
    name: str
    base: str
    runtime: str
    dependencies: set[str] = field(default_factory=set)
    memory_mb: float = 0.0
    is_virtual: bool = False

    def compatible_with(self, function: FunctionSpec) -> bool:
        return self.base == function.base and self.runtime == function.runtime

    def complete_for(self, function: FunctionSpec) -> set[str]:
        missing = set(function.dependencies) - self.dependencies
        self.dependencies.update(function.dependencies)
        return missing
