"""The heart of flakeguard: turning many runs into a flakiness score.

Take every test, look at how it behaved across the runs we were given, and
ask: *how often does it disagree with itself?*

The crucial subtlety is that a test can only be flaky **on the same code**. A
test that passed for twenty builds and then failed for twenty more is not
flaky - a real regression landed. So when we know which commit each run came
from, we only count disagreement *within* a commit.

Without commit information we fall back to pooling every run, which is a
weaker signal - it cannot tell a flake from a regression - so callers should
pass commits whenever they can.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Sequence

from .models import Outcome, TestCase


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
    # How many distinct commits this test was seen on (1 when unknown).
    commit_groups: int = 0

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
        parts = [p for p in (self.classname, self.name) if p]
        return "::".join(parts) if parts else self.name or self.key

    def is_flaky(self, min_score: float = 0.0) -> bool:
        """A test is flaky if it both passed and failed, and clears the bar."""
        return self.passed > 0 and self.failures > 0 and self.score > min_score


def _score(passed: int, failures: int) -> float:
    """Flakiness score in [0, 1] for a single commit.

    ``2 * min(passes, failures) / (passes + failures)``:

    * all passes, or all failures -> 0.0 (consistent, not flaky)
    * perfectly alternating 50/50 -> 1.0 (maximally flaky)
    """
    total = passed + failures
    if total == 0:
        return 0.0
    return min(1.0, 2.0 * min(passed, failures) / total)


def analyze(
    runs: Iterable[Iterable[TestCase]],
    commits: Optional[Sequence[Optional[str]]] = None,
) -> List[FlakeStats]:
    """Aggregate runs into per-test flake statistics, most-flaky first.

    ``runs`` is an iterable of runs; each run is an iterable of
    :class:`TestCase`. ``commits`` is an optional parallel sequence of commit
    labels (git SHAs, build numbers - anything stable). When supplied,
    flakiness is judged *within* each commit, so a regression (consistent
    failure after a change) is not mistaken for a flake.
    """
    runs = list(runs)
    if commits is None:
        commits = [None] * len(runs)
    else:
        commits = list(commits)
        if len(commits) != len(runs):
            raise ValueError("commits and runs must have the same length")

    agg: dict[str, FlakeStats] = {}
    # key -> commit -> [passes, failures] within that commit
    per_commit: dict[str, dict[Optional[str], List[int]]] = {}

    for commit, run in zip(commits, runs):
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

            bucket = per_commit.setdefault(key, {}).setdefault(commit, [0, 0])
            if case.outcome is Outcome.PASSED:
                bucket[0] += 1
            elif case.outcome in (Outcome.FAILED, Outcome.ERROR):
                bucket[1] += 1

    for key, stats in agg.items():
        groups = per_commit.get(key, {})
        stats.commit_groups = len(groups)
        # Disagreement *within* a commit is the only real flakiness signal.
        flips = sum(min(passes, fails) for passes, fails in groups.values())
        decided = sum(passes + fails for passes, fails in groups.values())
        stats.score = min(1.0, 2.0 * flips / decided) if decided else 0.0

    return sorted(
        agg.values(),
        key=lambda s: (s.score, s.failures, s.runs),
        reverse=True,
    )
