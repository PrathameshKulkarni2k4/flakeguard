"""Tests for the quarantine feature."""

import pathlib

from flakeguard.cli import main
from flakeguard.quarantine import is_quarantined, load_patterns, update_quarantine

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


def test_update_quarantine_adds_and_dedupes(tmp_path):
    f = tmp_path / "q.txt"
    assert update_quarantine(str(f), ["b::z", "a::y", "b::z"]) == 2
    assert load_patterns(str(f)) == ["a::y", "b::z"]
    assert update_quarantine(str(f), ["a::y"]) == 0  # already covered


def test_update_quarantine_escapes_parametrised_keys(tmp_path):
    # pytest keys contain [ ] which fnmatch would read as a character class.
    f = tmp_path / "q.txt"
    update_quarantine(str(f), ["tests.test_x::test_param[1-2]"])
    patterns = load_patterns(str(f))

    assert is_quarantined("tests.test_x::test_param[1-2]", patterns)
    assert not is_quarantined("tests.test_x::test_param1", patterns)
    assert not is_quarantined("tests.test_x::test_param2", patterns)


def test_update_quarantine_preserves_existing_content(tmp_path):
    f = tmp_path / "q.txt"
    f.write_text("# owner: @team\npkg::test_ranking_*\n")

    added = update_quarantine(str(f), ["pkg::test_ranking_a", "other::test_b"])

    assert added == 1  # only other::test_b is new; the glob already covers the first
    text = f.read_text()
    assert "# owner: @team" in text
    assert "pkg::test_ranking_*" in text
    assert "other::test_b" in text


def test_cli_update_quarantine_keeps_existing(tmp_path, capsys):
    q = tmp_path / "q.txt"
    q.write_text("# keep me\nunrelated::pattern\n")

    rc = main(["scan", str(REPORTS), "--update-quarantine", "--quarantine", str(q)])
    capsys.readouterr()

    assert rc == 0
    text = q.read_text()
    assert "# keep me" in text
    assert "unrelated::pattern" in text
    assert "tests.test_checkout::test_applies_coupon" in text


def test_quarantined_test_is_hidden_from_new_flaky(capsys):
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
