"""The heart of flakewatch: turning many runs into a flakiness score.

The idea is simple and explainable. Take every test, look at how it
behaved across all the runs we were given, and ask: *how often does it
disagree with itself?*

We ignore skips (a skipped test tells us nothing about flakiness) and
count only passes vs. non-passes. A test that always passes, or always
fails, is **not flaky** - it is consistent. Flakiness is disagreement.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable, List, Optional

from .models import Outcome, TestCase, join_unique


@dataclass
class FlakeStats:
    """Aggregated behaviour of one test across all observed runs."""

    key: str
    name: str
    suite: str
    classname: str
    runs: int = 0
    passed: int = 0
    failed: int = 0
    errored: int = 0
    skipped: int = 0
    score: float = 0.0
    last_message: Optional[str] = None
    messages: List[str] = field(default_factory=list)

    @property
    def considered(self) -> int:
        """Runs that actually inform flakiness (passes + failures + errors)."""
        return self.passed + self.failed + self.errored

    @property
    def failures(self) -> int:
        """Non-passes that were not skips (failures + errors)."""
        return self.failed + self.errored

    @property
    def display_name(self) -> str:
        return join_unique([self.classname, self.name]) or self.name or self.key

    def is_flaky(self, min_score: float = 0.0) -> bool:
        """A test is flaky if it both passed and failed, and clears the bar."""
        return self.passed > 0 and self.failures > 0 and self.score > min_score


def _score(passed: int, failures: int) -> float:
    """Flakiness score in [0, 1].

    Defined as ``2 * min(passes, failures) / (passes + failures)``.

    * all passes, or all failures  -> 0.0  (consistent, not flaky)
    * perfectly alternating 50/50  -> 1.0  (maximally flaky)

    Doubling means the score reads the way people expect: a coin-flip test
    is "100% flaky", not "50% flaky".
    """
    total = passed + failures
    if total == 0:
        return 0.0
    return min(1.0, 2.0 * min(passed, failures) / total)


def analyze(runs: Iterable[Iterable[TestCase]]) -> List[FlakeStats]:
    """Aggregate several runs of test cases into per-test flake statistics.

    ``runs`` is an iterable of runs; each run is an iterable of
    :class:`TestCase`. Returns stats for every distinct test seen, sorted
    most-flaky first.
    """
    agg: dict[str, FlakeStats] = {}

    for run in runs:
        seen_in_run: set[str] = set()
        for case in run:
            key = case.key
            # If a framework reports the same key twice in one run (e.g.
            # parametrised tests without unique names) count it once.
            if key in seen_in_run:
                continue
            seen_in_run.add(key)

            stats = agg.get(key)
            if stats is None:
                stats = FlakeStats(
                    key=key, name=case.name, suite=case.suite, classname=case.classname
                )
                agg[key] = stats

            stats.runs += 1
            if case.outcome is Outcome.PASSED:
                stats.passed += 1
            elif case.outcome is Outcome.FAILED:
                stats.failed += 1
            elif case.outcome is Outcome.ERROR:
                stats.errored += 1
            else:
                stats.skipped += 1

            if case.message:
                stats.last_message = case.message
                if case.message not in stats.messages:
                    stats.messages.append(case.message)

    for stats in agg.values():
        stats.score = _score(stats.passed, stats.failures)

    return sorted(
        agg.values(),
        key=lambda s: (s.score, s.failures, s.runs),
        reverse=True,
    )
