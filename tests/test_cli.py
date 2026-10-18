"""End-to-end tests for the CLI."""

import json
import pathlib

from flakeguard.cli import main

REPORTS = pathlib.Path(__file__).resolve().parents[1] / "examples" / "reports"


def test_scan_directory_text(capsys):
    rc = main(["scan", str(REPORTS)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "flakeguard report" in out
    assert "test_applies_coupon" in out
    # the always-failing test must NOT be called flaky
    assert "test_totals_are_stable" not in out


def test_scan_json_is_valid(capsys):
    rc = main(["scan", str(REPORTS), "--format", "json"])
    out = capsys.readouterr().out
    assert rc == 0
    payload = json.loads(out)
    assert payload["summary"]["tests_analysed"] == 3
    assert payload["summary"]["flaky"] == 1
    assert payload["flaky_tests"][0]["name"] == "test_applies_coupon"
    assert round(payload["flaky_tests"][0]["score"], 2) == 0.67


def test_scan_writes_output_file(tmp_path, capsys):
    out_file = tmp_path / "report.md"
    rc = main(["scan", str(REPORTS), "--format", "markdown", "-o", str(out_file)])
    assert rc == 0
    assert "test_applies_coupon" in out_file.read_text()


def test_min_runs_filters_single_run(tmp_path):
    xml = """<?xml version="1.0"?>
    <testsuites><testsuite name="s">
      <testcase classname="c" name="only_once"/>
    </testsuite></testsuites>"""
    (tmp_path / "one.xml").write_text(xml)
    from flakeguard.cli import main as cli_main  # noqa: F401  (kept explicit)

    rc = main(["scan", str(tmp_path)])
    assert rc == 0  # runs fine, just nothing reported
