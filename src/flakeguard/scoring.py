"""The heart of flakeguard: turning many runs into a flakiness score.

Take every test, look at how it behaved across the runs we were given, and
ask: *how often does it disagree with itself?*

Three subtleties matter, and getting any wrong makes the number useless.

**A test can only be flaky on the same code.** A test that passed for twenty
builds and then failed for twenty more is not flaky - a regression landed.
So when we know which commit each run came from, we only count disagreement
*within* a commit.

**A commit needs more than one run to say anything.** A commit where the
test ran once can never show a flip, so including it would only dilute the
score - and one-run-per-commit is the most common CI shape of all. Only
commits with at least two decided runs count.

**"How sure" and "how often" are different questions.** ``score`` answers
the first (disagreement within a commit); ``rate`` answers the second (how
often the test misbehaves across every run). A test that flaked once in a
hundred runs is certainly flaky - but it is not as urgent as one that fails
a third of the time. Reporting one number for both would lie about one of
them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Sequence

from .models import Outcome, TestCase, collapse_run


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
    # Runs where the test failed and then passed on a retry.
    flaky_retries: int = 0
    # How *sure* we are it is flaky: disagreement within a commit.
    score: float = 0.0
    # How *often* it misbehaves: the minority outcome over every decided run.
    rate: float = 0.0
    last_message: Optional[str] = None
    messages: List[str] = field(default_factory=list)
    # Distinct commits this test was seen on.
    commit_groups: int = 0
    # Commits where it decided more than once - the only ones that can show
    # flakiness.
    informative_commits: int = 0

    @property
    def considered(self) -> int:
        """Runs that actually inform flakiness (everything but skips).

        Derived from ``runs`` rather than summing the outcome counters: a
        retry flake is recorded as both a pass and a failure, so summing them
        would report 101 runs for 100 real ones.
        """
        return max(0, self.runs - self.skipped)

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

    def is_unconfirmed(self) -> bool:
        """Changed across commits, but no commit ran it twice.

        We can see it behaved differently, but we cannot tell a flake from a
        regression - so we say so rather than guess.
        """
        return (
            self.passed > 0
            and self.failures > 0
            and self.informative_commits == 0
            and self.flaky_retries == 0
        )


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
    """Aggregate runs into per-test flake statistics, most frequent first.

    ``runs`` is an iterable of runs; each run is an iterable of
    :class:`TestCase`. ``commits`` is an optional parallel sequence of commit
    labels. When supplied, flakiness is judged *within* each commit, so a
    regression is not mistaken for a flake.
    """
    runs = list(runs)
    if commits is None:
        commits = [None] * len(runs)
    else:
        commits = list(commits)
        if len(commits) != len(runs):
            raise ValueError("commits and runs must have the same length")

    agg: dict[str, FlakeStats] = {}
    # key -> commit -> [passes, failures] decided within that commit
    per_commit: dict[str, dict[Optional[str], List[int]]] = {}

    for commit, run in zip(commits, runs):
        for case in collapse_run(run):
            key = case.key
            stats = agg.get(key)
            if stats is None:
                stats = FlakeStats(
                    key=key, name=case.name, suite=case.suite, classname=case.classname
                )
                agg[key] = stats

            stats.runs += 1
            bucket = per_commit.setdefault(key, {}).setdefault(commit, [0, 0])

            if case.outcome is Outcome.PASSED:
                stats.passed += 1
                bucket[0] += 1
            elif case.outcome is Outcome.FAILED:
                stats.failed += 1
                bucket[1] += 1
            elif case.outcome is Outcome.ERROR:
                stats.errored += 1
                bucket[1] += 1
            elif case.outcome is Outcome.FLAKY:
                # Failed then passed within one run: a flip we can see directly.
                stats.flaky_retries += 1
                stats.passed += 1
                stats.failed += 1
                bucket[0] += 1
                bucket[1] += 1
            else:
                stats.skipped += 1

            if case.message:
                stats.last_message = case.message
                if case.message not in stats.messages:
                    stats.messages.append(case.message)

    for key, stats in agg.items():
        groups = per_commit.get(key, {})
        stats.commit_groups = len(groups)
        # Only commits with at least two decided runs can show a flip. A
        # single run per commit can never disagree with itself, so counting
        # it would just dilute the score.
        informative = [(p, f) for p, f in groups.values() if p + f >= 2]
        stats.informative_commits = len(informative)
        flips = sum(min(passes, fails) for passes, fails in informative)
        decided = sum(passes + fails for passes, fails in informative)
        stats.score = min(1.0, 2.0 * flips / decided) if decided else 0.0

        # Frequency over *every* decided run - deliberately not restricted to
        # informative commits, because this answers "how often", not "how sure".
        total = stats.considered
        stats.rate = min(stats.passed, stats.failures) / total if total else 0.0

    return sorted(
        agg.values(),
        key=lambda s: (s.rate, s.score, s.failures),
        reverse=True,
    )
