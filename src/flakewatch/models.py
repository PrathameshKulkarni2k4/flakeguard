"""Core data types shared across parsers, scoring and reporting."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Outcome(str, Enum):
    """The result of a single test in a single run."""

    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    SKIPPED = "skipped"


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
        """A stable identity for this test across runs.

        We join whatever parts the framework gave us, skipping blanks and
        collapsing a suite name that repeats the classname (common in
        pytest/JUnit output), so the key stays readable.
        """
        head: list[str] = []
        for part in (self.suite, self.classname):
            if part and part not in head:
                head.append(part)
        if self.name:
            head.append(self.name)
        return "::".join(head) if head else "<unnamed>"

    @property
    def display_name(self) -> str:
        parts = [p for p in (self.classname, self.name) if p]
        return "::".join(parts) if parts else self.name or "<unnamed>"
