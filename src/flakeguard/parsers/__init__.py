"""Report parsers.

Each parser turns a framework's native test report into a list of
:class:`flakeguard.models.TestCase`. Adding support for a new framework
means adding one module here and registering it in ``by_suffix``.
"""

from __future__ import annotations

from typing import Callable, List

from ..models import TestCase
from .junit_xml import parse_junit_xml
from .tap import parse_tap

# Map of file suffix -> parser callable. Used by the CLI to auto-detect
# the format of each report file it is handed.
by_suffix: dict[str, Callable[[str], List[TestCase]]] = {
    ".xml": parse_junit_xml,
    ".tap": parse_tap,
}

__all__ = ["parse_junit_xml", "parse_tap", "by_suffix"]
