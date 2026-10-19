"""Tests for the JSON (Jest-style) report parser, using real jest output."""

import pathlib

from flakeguard.models import Outcome
from flakeguard.parsers.json_report import parse_json_report

FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"


def test_parses_all_cases():
    cases = parse_json_report(str(FIXTURES / "jest-json.json"))
    assert len(cases) == 4


def test_outcomes():
    cases = {c.name: c for c in parse_json_report(str(FIXTURES / "jest-json.json"))}
    assert cases["math adds two numbers"].outcome is Outcome.PASSED
    assert cases["math subtracts two numbers"].outcome is Outcome.PASSED
    assert cases["math a skipped one"].outcome is Outcome.SKIPPED  # jest "pending"
    assert cases["math a failing one"].outcome is Outcome.FAILED


def test_key_is_machine_independent():
    # The report has an absolute path; the key must be relative to the suite.
    cases = {c.name: c for c in parse_json_report(str(FIXTURES / "jest-json.json"))}
    assert cases["math adds two numbers"].key == "sum.test.js::math adds two numbers"


def test_failure_message_is_first_line_only():
    cases = {c.name: c for c in parse_json_report(str(FIXTURES / "jest-json.json"))}
    msg = cases["math a failing one"].message
    assert msg and "expect(received)" in msg
    assert "at Object" not in msg  # stack stripped


def test_rejects_non_report_json(tmp_path):
    p = tmp_path / "package.json"
    p.write_text('{"name": "x", "version": "1.0.0"}')
    try:
        parse_json_report(str(p))
    except ValueError as exc:
        assert "testResults" in str(exc)
    else:
        raise AssertionError("should have rejected a non-report JSON file")


def test_cli_scans_json_report(tmp_path, capsys):
    import shutil

    from flakeguard.cli import main

    shutil.copy(FIXTURES / "jest-json.json", tmp_path / "report.json")
    rc = main(["scan", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "tests analysed : 4" in out
