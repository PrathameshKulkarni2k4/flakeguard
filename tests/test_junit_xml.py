"""Tests for the JUnit XML parser."""

import pathlib

from flakeguard.models import Outcome
from flakeguard.parsers.junit_xml import parse_junit_xml

REPORTS = pathlib.Path(__file__).resolve().parents[1] / "examples" / "reports"


def test_parses_all_cases():
    cases = parse_junit_xml(str(REPORTS / "run1.xml"))
    assert len(cases) == 3
    names = {c.name for c in cases}
    assert names == {"test_adds_item", "test_applies_coupon", "test_totals_are_stable"}


def test_outcomes_are_correct():
    cases = {c.name: c for c in parse_junit_xml(str(REPORTS / "run1.xml"))}
    assert cases["test_adds_item"].outcome is Outcome.PASSED
    assert cases["test_totals_are_stable"].outcome is Outcome.FAILED
    assert cases["test_totals_are_stable"].message.startswith("AssertionError")


def test_durations_parsed():
    cases = {c.name: c for c in parse_junit_xml(str(REPORTS / "run2.xml"))}
    assert cases["test_applies_coupon"].duration == 0.019


def test_handles_nested_suites(tmp_path):
    xml = """<?xml version="1.0"?>
    <testsuites>
      <testsuite name="outer">
        <testsuite name="inner">
          <testcase classname="a.b" name="t1"/>
        </testsuite>
      </testsuite>
    </testsuites>"""
    p = tmp_path / "nested.xml"
    p.write_text(xml)
    cases = parse_junit_xml(str(p))
    assert len(cases) == 1
    assert cases[0].name == "t1"
    assert cases[0].suite == "inner"
