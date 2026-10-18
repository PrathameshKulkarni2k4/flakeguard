"""Parser for TAP - the Test Anything Protocol.

TAP is a simple, line-based format produced by tools like Node's built-in
test runner (``node --test --test-reporter=tap``), the ``tap``/``tape``
libraries, Perl's Test::More, and several others.

A line like ``ok 1 - adds two numbers`` is a pass; ``not ok 3 - x`` is a
failure; a ``# SKIP`` or ``# TODO`` directive marks a test as not run.
Diagnostic details (the error message) live in a YAML block between ``---``
and ``...`` lines.
"""

from __future__ import annotations

import re
from typing import List, Optional

from ..models import Outcome, TestCase

# "ok 1 - name", "not ok 1 - name", "ok 1 name", "not ok 1"
_TEST_RE = re.compile(r"^(not\s+)?ok\b(?:\s+(\d+))?\s*(?:-\s*)?(.*)$", re.IGNORECASE)
_ERROR_RE = re.compile(r"^\s*error:\s*(.*)$")
_BLOCK_SCALAR = {"|", "|-", "|+", ">", ">-", ">+"}


def _split_directive(text: str) -> tuple[str, str]:
    """Split ``name # SKIP reason`` into (name, directive)."""
    if "#" in text:
        name, _, directive = text.partition("#")
        return name.strip(), directive.strip()
    return text.strip(), ""


def _extract_error(block: List[str]) -> Optional[str]:
    """Pull a readable error message out of a TAP YAML diagnostic block."""
    for idx, line in enumerate(block):
        m = _ERROR_RE.match(line)
        if not m:
            continue
        value = m.group(1).strip()
        if value in _BLOCK_SCALAR:
            base = len(line) - len(line.lstrip())
            parts: List[str] = []
            for sub in block[idx + 1:]:
                if not sub.strip():
                    parts.append("")
                    continue
                indent = len(sub) - len(sub.lstrip())
                if indent <= base:
                    break
                parts.append(sub.strip())
            joined = " ".join(p for p in parts if p)
            return joined[:300] or None
        return value[:300] or None
    return None


def _parse_lines(lines: List[str], allow_indent: bool) -> List[TestCase]:
    cases: List[TestCase] = []
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        if not allow_indent and line[:1] in (" ", "\t"):
            i += 1
            continue
        m = _TEST_RE.match(line.strip() if allow_indent else line)
        if not m:
            i += 1
            continue

        failed = bool(m.group(1))
        name, directive = _split_directive(m.group(3) or "")
        name = name or (f"test {m.group(2)}" if m.group(2) else "<unnamed>")

        outcome = Outcome.FAILED if failed else Outcome.PASSED
        message: Optional[str] = None

        if directive:
            upper = directive.upper()
            if upper.startswith("SKIP") or upper.startswith("TODO"):
                outcome = Outcome.SKIPPED
                message = directive.split(None, 1)[1].strip() if " " in directive else None

        # Collect the YAML diagnostic block that follows a failing test.
        if failed and i + 1 < n and lines[i + 1].strip() == "---":
            j = i + 2
            block: List[str] = []
            while j < n and lines[j].strip() != "...":
                block.append(lines[j])
                j += 1
            message = _extract_error(block) or message
            i = j

        cases.append(TestCase(name=name, outcome=outcome, message=message))
        i += 1
    return cases


def parse_tap(path: str) -> List[TestCase]:
    """Parse a TAP file into a list of test cases.

    Top-level tests are lines starting in column zero. If a file yields
    nothing that way (some producers indent everything), we retry allowing
    leading whitespace so we never silently return nothing.
    """
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        lines = fh.read().splitlines()

    cases = _parse_lines(lines, allow_indent=False)
    if not cases:
        cases = _parse_lines(lines, allow_indent=True)
    return cases
