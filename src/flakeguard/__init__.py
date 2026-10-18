"""flakeguard - find, rank, and quarantine flaky tests.

A language-agnostic tool: point it at the test reports your CI already
produces (JUnit XML and friends) and it tells you which tests are flaky,
how flaky, and why it thinks so.
"""

from importlib.metadata import PackageNotFoundError, version as _pkg_version

try:
    __version__ = _pkg_version("flakeguard")
except PackageNotFoundError:  # running from a source checkout, not installed
    __version__ = "0.0.0+unknown"

from .models import Outcome, TestCase
from .scoring import FlakeStats, analyze
from .parsers.junit_xml import parse_junit_xml
from .parsers.tap import parse_tap

__all__ = [
    "__version__",
    "Outcome",
    "TestCase",
    "FlakeStats",
    "analyze",
    "parse_junit_xml",
    "parse_tap",
]
