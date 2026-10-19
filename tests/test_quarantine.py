"""Tests for the quarantine feature."""

import pathlib

from flakeguard.cli import main
from flakeguard.quarantine import is_quarantined, load_patterns, write_patterns

REPORTS = pathlib.Path(__file__).resolve().parents[1] / "examples" / "reports"


def test_load_patterns_ignores_comments_and_blanks(tmp_path):
    f = tmp_path / "q.txt"
    f.write_text("# a comment\n\n  \nfoo::bar\nbaz::*\n")
    assert load_patterns(str(f)) == ["foo::bar", "baz::*"]


def test_is_quarantined_exact_and_glob():
    patterns = ["a::b", "pkg::test_*"]
    assert is_quarantined("a::b", patterns)
    assert is_quarantined("pkg::test_thing", patterns)
    assert not is_quarantined("other::test_thing", patterns)
    assert not is_quarantined("a::b", [])


def test_write_patterns_round_trips(tmp_path):
    f = tmp_path / "q.txt"
    n = write_patterns(str(f), ["b::z", "a::y", "b::z"])
    assert n == 2  # de-duplicated
    assert load_patterns(str(f)) == ["a::y", "b::z"]


def test_quarantined_test_is_hidden_from_new_flaky(capsys):
    # examples/reports has one flaky test: test_applies_coupon
    rc = main(["scan", str(REPORTS), "--quarantine", "/dev/null"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "test_applies_coupon" in out
    assert "new flaky      : 1" in out


def test_quarantine_file_suppresses_a_known_flake(tmp_path, capsys):
    q = tmp_path / "q.txt"
    q.write_text("tests.test_checkout::test_applies_coupon\n")
    rc = main(["scan", str(REPORTS), "--quarantine", str(q)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "new flaky      : 0" in out
    assert "quarantined    : 1" in out
    assert "No new flaky tests" in out


def test_fail_on_flaky_ignores_quarantined(tmp_path, capsys):
    q = tmp_path / "q.txt"
    q.write_text("tests.test_checkout::test_applies_coupon\n")
    rc = main(["scan", str(REPORTS), "--quarantine", str(q), "--fail-on-flaky"])
    capsys.readouterr()
    assert rc == 0  # the only flake is quarantined -> CI stays green


def test_fail_on_flaky_still_fails_on_new_flakes(capsys):
    rc = main(["scan", str(REPORTS), "--quarantine", "/dev/null", "--fail-on-flaky"])
    capsys.readouterr()
    assert rc == 1


def test_update_quarantine_writes_file(tmp_path, capsys):
    target = tmp_path / "q.txt"
    rc = main(["scan", str(REPORTS), "--update-quarantine", "--quarantine", str(target)])
    capsys.readouterr()
    assert rc == 0
    assert "tests.test_checkout::test_applies_coupon" in load_patterns(str(target))
