"""Parser for JUnit XML - the de-facto interchange format for test results.

Almost every test framework can emit this: pytest (``--junitxml``), Maven
and Gradle Surefire, Go's ``gotestsum --junitfile``, Jest
(``jest-junit``), RSpec (``rspec_junit_formatter``), .NET, PHPUnit, and
more. That is what makes flakewatch language-agnostic.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Iterator, List, Optional, Tuple

from ..models import Outcome, TestCase


def _localname(tag: str) -> str:
    """Strip an XML namespace, if present (``{ns}testcase`` -> ``testcase``)."""
    return tag.split("}")[-1].lower()


def _outcome_and_message(case: ET.Element) -> Tuple[Outcome, Optional[str]]:
    """Decide a test's outcome from its child elements.

    Per the JUnit schema, a ``<failure>`` means an assertion failed, an
    ``<error>`` means the test blew up unexpectedly, and a ``<skipped>``
    means it did not run. A ``<testcase>`` with none of these passed.
    """
    for child in case:
        tag = _localname(child.tag)
        if tag in ("failure", "error"):
            text = (child.get("message") or (child.text or "").strip())
            text = " ".join(text.split())  # collapse whitespace/newlines
            return (
                Outcome.FAILED if tag == "failure" else Outcome.ERROR,
                text[:300] or None,
            )
        if tag == "skipped":
            return Outcome.SKIPPED, child.get("message")
    return Outcome.PASSED, None


def _iter_suites(suite: ET.Element) -> Iterator[ET.Element]:
    """Yield every ``<testsuite>`` at any depth (they can nest)."""
    yield suite
    for child in suite:
        if _localname(child.tag) == "testsuite":
            yield from _iter_suites(child)


def _collect_cases(container: ET.Element, suite_name: str) -> Iterator[TestCase]:
    for child in container:
        tag = _localname(child.tag)
        if tag == "testcase":
            outcome, message = _outcome_and_message(child)
            raw_time = child.get("time")
            try:
                duration = float(raw_time) if raw_time else 0.0
            except ValueError:
                duration = 0.0
            yield TestCase(
                name=child.get("name") or "",
                suite=suite_name,
                classname=child.get("classname") or "",
                outcome=outcome,
                duration=duration,
                message=message,
            )
        elif tag == "testsuite":
            nested_name = child.get("name") or suite_name
            yield from _collect_cases(child, nested_name)


def parse_junit_xml(path: str) -> List[TestCase]:
    """Parse a JUnit XML file into a list of test cases.

    Handles the three common root shapes: ``<testsuites>`` (a bundle of
    suites), a bare ``<testsuite>``, and nested suites.
    """
    root = ET.parse(path).getroot()
    root_tag = _localname(root.tag)

    cases: List[TestCase] = []

    if root_tag == "testsuites":
        for suite in root:
            if _localname(suite.tag) == "testsuite":
                cases.extend(_collect_cases(suite, suite.get("name") or ""))
    elif root_tag == "testsuite":
        cases.extend(_collect_cases(root, root.get("name") or ""))
    else:
        # Unknown root: be permissive and look for testcases anywhere.
        cases.extend(_collect_cases(root, ""))

    return cases
