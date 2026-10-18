"""Tests for CI gating (--fail-on-flaky)."""

import pathlib

from flakewatch.cli import main

REPORTS = pathlib.Path(__file__).resolve().parents[1] / "examples" / "reports"


def test_fail_on_flaky_returns_1_when_flaky_found(capsys):
    rc = main(["scan", str(REPORTS), "--fail-on-flaky"])
    capsys.readouterr()
    assert rc == 1


def test_fail_on_flaky_returns_0_when_clean(tmp_path, capsys):
    xml = """<?xml version="1.0"?>
    <testsuites><testsuite name="s">
      <testcase classname="c" name="always_green"/>
      <testcase classname="c" name="always_green"/>
    </testsuite></testsuites>"""
    (tmp_path / "a.xml").write_text(xml)
    (tmp_path / "b.xml").write_text(xml)
    rc = main(["scan", str(tmp_path), "--fail-on-flaky"])
    capsys.readouterr()
    assert rc == 0
