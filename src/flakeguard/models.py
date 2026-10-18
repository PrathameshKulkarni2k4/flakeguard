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
