"""Parser for JSON test reports.

Understands the JSON emitted by Jest's ``--json`` flag (and compatible
runners), which is the most widely used machine-readable JSON report:

    jest --json > report.json

The shape is::

    {"testResults": [{"name": "<file>", "assertionResults": [
        {"fullName": "...", "status": "passed|failed|pending", "failureMessages": [...]}
    ]}]}
"""

from __future__ import annotations

import json
import os
import re
from typing import List

from ..models import Outcome, TestCase

_PASSED = {"passed", "pass", "success"}
_FAILED = {"failed", "fail", "failure", "error"}
_SKIPPED = {"pending", "skipped", "todo", "disabled"}
_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def _clean(text: str) -> str:
    """Strip ANSI colour codes and collapse whitespace."""
    return " ".join(_ANSI.sub("", text).split())


def _common_dir(paths: List[str]) -> str:
    """The directory all report files share, so keys stay machine-independent."""
    dirs = [os.path.dirname(p) for p in paths if p]
    if not dirs:
        return ""
    try:
        return os.path.commonpath(dirs)
    except ValueError:
        return ""


def _relative(path: str, prefix: str) -> str:
    if not path or not prefix:
        return path
    try:
        return os.path.relpath(path, prefix)
    except ValueError:
        return path


def parse_json_report(path: str) -> List[TestCase]:
    """Parse a Jest-style JSON report into test cases."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        raise ValueError(f"not valid JSON ({exc})") from exc

    if not isinstance(data, dict) or not isinstance(data.get("testResults"), list):
        raise ValueError(
            "not a recognised JSON test report (expected a top-level "
            "'testResults' list, as produced by 'jest --json')"
        )

    results = [r for r in data["testResults"] if isinstance(r, dict)]
    prefix = _common_dir([r.get("name") or "" for r in results])

    cases: List[TestCase] = []
    for suite in results:
        suite_name = _relative(suite.get("name") or "", prefix)
        for assertion in suite.get("assertionResults") or []:
            if not isinstance(assertion, dict):
                continue
            status = str(assertion.get("status") or "").strip().lower()
            if status in _FAILED:
                outcome = Outcome.FAILED
            elif status in _SKIPPED:
                outcome = Outcome.SKIPPED
            else:
                outcome = Outcome.PASSED

            messages = [m for m in (assertion.get("failureMessages") or []) if m]
            # Keep just the first line - the useful part; the rest is a stack.
            first_line = _clean(messages[0]).split(" at ")[0] if messages else ""
            message = first_line[:300] or None

            name = assertion.get("fullName") or assertion.get("title") or ""
            cases.append(
                TestCase(name=name, suite=suite_name, outcome=outcome, message=message)
            )
    return cases
