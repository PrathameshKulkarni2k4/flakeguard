"""Tests for the TAP parser, using real output from Node's test runner."""

import pathlib

from flakeguard.models import Outcome
from flakeguard.parsers.tap import parse_tap

FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"


def test_parses_all_cases():
    cases = parse_tap(str(FIXTURES / "node-tap.tap"))
    assert len(cases) == 4


def test_outcomes():
    cases = {c.name: c for c in parse_tap(str(FIXTURES / "node-tap.tap"))}
    assert cases["adds two numbers"].outcome is Outcome.PASSED
    assert cases["subtracts two numbers"].outcome is Outcome.PASSED
    assert cases["a failing one"].outcome is Outcome.FAILED
    assert cases["a skipped one"].outcome is Outcome.SKIPPED


def test_failure_message_is_extracted():
    cases = {c.name: c for c in parse_tap(str(FIXTURES / "node-tap.tap"))}
    msg = cases["a failing one"].message
    assert msg and "strictly equal" in msg


def test_todo_directive_is_skipped(tmp_path):
    p = tmp_path / "x.tap"
    p.write_text(
        "TAP version 13\n"
        "ok 1 - fine\n"
        "not ok 2 - todo one # TODO later\n"
        "1..2\n"
    )
    cases = {c.name: c for c in parse_tap(str(p))}
    assert cases["fine"].outcome is Outcome.PASSED
    assert cases["todo one"].outcome is Outcome.SKIPPED


def test_cli_discovers_tap_files(tmp_path, capsys):
    from flakeguard.cli import main

    (tmp_path / "run.tap").write_text("ok 1 - a\nnot ok 2 - b\n")
    rc = main(["scan", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "tests analysed : 2" in out
