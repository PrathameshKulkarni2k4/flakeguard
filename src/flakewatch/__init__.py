"""flakewatch - find, rank, and quarantine flaky tests.

A language-agnostic tool: point it at the test reports your CI already
produces (JUnit XML and friends) and it tells you which tests are flaky,
how flaky, and why it thinks so.
"""

__version__ = "0.1.0"

from .models import Outcome, TestCase
from .scoring import FlakeStats, analyze
from .parsers.junit_xml import parse_junit_xml

__all__ = [
    "__version__",
    "Outcome",
    "TestCase",
    "FlakeStats",
    "analyze",
    "parse_junit_xml",
]
