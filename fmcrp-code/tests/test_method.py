import math
import unittest

from fmcrp.models import FunctionSpec, Replica
from fmcrp.prediction import keep_alive_interval, poisson_quantile, predicted_demands
from fmcrp.scheduler import FMCRPScheduler
from fmcrp.config import (
    DEFAULT_FIWI_THRESHOLD,
    DEFAULT_HISTORY_WINDOW_SIZE,
    DEFAULT_MATCHING_WINDOW_SIZE,
    DEFAULT_PREDICTION_CONFIDENCE,
    DEFAULT_SMOOTHING_ALPHA,
)


def function(name, dependencies, base="debian", runtime="python"):
    return FunctionSpec(name, base, runtime, frozenset(dependencies), {package: 1.0 for package in dependencies}, 3.0, 2.0)


class FMCRPMethodTests(unittest.TestCase):
    def test_completion_cost_and_incompatible_layers(self):
        resize = function("resize", {"pillow", "numpy"})
        partial = Replica("partial", "debian", "python", {"pillow"})
        foreign = Replica("foreign", "alpine", "python", {"pillow", "numpy"})
        self.assertEqual(resize.completion_cost(partial), 1.0)
        self.assertTrue(math.isinf(resize.completion_cost(foreign)))

    def test_low_fiwi_uses_greedy_and_completes_partial_replica(self):
        target = function("target", {"a", "b"})
        unrelated = function("unrelated", {"z"})
        scheduler = FMCRPScheduler([target, unrelated], [Replica("partial", "debian", "python", {"a"})], theta=0.1)
        decision = scheduler.schedule("target", {"target": 4.0, "unrelated": 10.0})[0]
        self.assertEqual(decision.branch, "greedy")
        self.assertEqual(decision.replica, "partial")
        self.assertEqual(decision.missing_dependencies, ["b"])

    def test_high_fiwi_uses_hungarian_and_adds_virtual_candidate(self):
        a = function("a", {"shared", "a"})
        b = function("b", {"shared", "b"})
        scheduler = FMCRPScheduler([a, b], [Replica("r", "debian", "python", {"shared"})], theta=0.5)
        decisions = scheduler.schedule("a", {"a": 3.0, "b": 1.0}, {"a": 1, "b": 1})
        self.assertEqual(decisions[0].branch, "hungarian")
        self.assertEqual(len(decisions), 2)
        self.assertTrue(any(item.cold_start for item in decisions))

    def test_prediction_and_retention(self):
        config = ("debian", "python", frozenset({"a"}))
        rates, demands = predicted_demands({"f": [0, 1, 2, 3]}, {"f": config}, 1, 0.9, 1.0)
        self.assertEqual(rates["f"], 4 / 3)
        self.assertGreaterEqual(demands[config], 1)
        self.assertEqual(poisson_quantile(0, 0.9), 0)
        self.assertGreater(keep_alive_interval(1, 0.9), 2)
        scheduler = FMCRPScheduler([function("f", {"a"})], [Replica("exact", "debian", "python", {"a"}, 100), Replica("surplus", "debian", "python", {"x"}, 50)])
        actions = scheduler.retention_actions({config: 1}, {"x": 1}, {"x": 1}, previous_accuracy=1.0)
        self.assertEqual(actions["keep"], ["exact", "surplus"])

    def test_default_parameters(self):
        scheduler = FMCRPScheduler([function("f", {"a"})])
        self.assertEqual(scheduler.theta, DEFAULT_FIWI_THRESHOLD)
        self.assertEqual(scheduler.matching_window_size, DEFAULT_MATCHING_WINDOW_SIZE)
        self.assertEqual(DEFAULT_HISTORY_WINDOW_SIZE, 8)
        self.assertEqual(DEFAULT_PREDICTION_CONFIDENCE, 0.75)
        self.assertEqual(DEFAULT_SMOOTHING_ALPHA, 0.5)
        config = ("debian", "python", frozenset({"a"}))
        rates, _ = predicted_demands({"f": list(range(10))}, {"f": config}, 1)
        self.assertEqual(rates["f"], 8 / 7)


if __name__ == "__main__":
    unittest.main()
