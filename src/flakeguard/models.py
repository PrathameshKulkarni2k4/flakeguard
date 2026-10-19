"""Core data types shared across parsers, scoring and reporting."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Optional


class Outcome(str, Enum):
    """The result of a single test in a single run."""

    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    SKIPPED = "skipped"
    # Failed at least once and passed on a retry within the same run. This is
    # direct evidence of flakiness - it needs no comparison across runs.
    FLAKY = "flaky"


# How bad each outcome is, used to pick a winner when a run reports the same
# test more than once.
SEVERITY = {
    Outcome.SKIPPED: 0,
    Outcome.PASSED: 1,
    Outcome.FLAKY: 2,
    Outcome.FAILED: 3,
    Outcome.ERROR: 4,
}


def join_unique(parts: Iterable[str]) -> str:
    """Join non-empty parts with '::', dropping repeats.

    Frameworks disagree about how they name things: pytest sets a suite and
    a classname, while jest-junit sets classname == name. Dropping repeats
    keeps a test's identity stable and readable for both.
    """
    seen: list[str] = []
    for part in parts:
        if part and part not in seen:
            seen.append(part)
    return "::".join(seen)


@dataclass(frozen=True)
class TestCase:
    """One test's result, as observed in one run.

    ``suite`` is the file/grouping the framework reported (e.g. a test
    file), ``classname`` is the class or module, and ``name`` is the test
    itself. Together they form a stable identity so the same test can be
    matched across runs.
    """

    name: str
    suite: str = ""
    classname: str = ""
    outcome: Outcome = Outcome.PASSED
    duration: float = 0.0
    message: Optional[str] = None

    # Not a field (no annotation): tells pytest this is data, not a test.
    __test__ = False

    @property
    def key(self) -> str:
        """A stable identity for this test across runs."""
        return join_unique([self.suite, self.classname, self.name]) or "<unnamed>"

    @property
    def display_name(self) -> str:
        return join_unique([self.classname, self.name]) or self.name or "<unnamed>"


def collapse_run(cases: Iterable[TestCase]) -> List[TestCase]:
    """Reduce one run's cases to one per test key.

    Frameworks disagree about how to record retries. Some emit a single
    ``<testcase>`` carrying a ``<flakyFailure>``; others emit one
    ``<testcase>`` per attempt. Both mean the same thing - the test passed
    *and* failed inside one run - so a key that both passed and failed in a
    run is ``FLAKY``, not simply its most severe outcome. Treating it as a
    plain failure would turn a flake into a hard failure.

    This lives in one place so the scoring path and the history path cannot
    drift apart.
    """
    grouped: dict[str, List[TestCase]] = {}
    order: List[str] = []
    for case in cases:
        if case.key not in grouped:
            grouped[case.key] = []
            order.append(case.key)
        grouped[case.key].append(case)

    collapsed: List[TestCase] = []
    for key in order:
        group = grouped[key]
        outcomes = {c.outcome for c in group}
        has_pass = Outcome.PASSED in outcomes or Outcome.FLAKY in outcomes
        has_fail = Outcome.FLAKY in outcomes or bool(
            outcomes & {Outcome.FAILED, Outcome.ERROR}
        )

        if has_pass and has_fail:
            outcome = Outcome.FLAKY
        else:
            outcome = max((c.outcome for c in group), key=lambda o: SEVERITY[o])

        message = None
        for case in group:
            if case.message:
                message = case.message

        first = group[0]
        collapsed.append(
            TestCase(
                name=first.name,
                suite=first.suite,
                classname=first.classname,
                outcome=outcome,
                duration=sum(c.duration for c in group),
                message=message,
            )
        )
    return collapsed
