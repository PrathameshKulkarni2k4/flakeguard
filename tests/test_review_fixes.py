"""Regression tests for bugs found in code review.

Each one was a real defect; each is pinned here so it cannot come back.
"""

import json
import pathlib
import shutil

from flakeguard.cli import main
from flakeguard.models import Outcome, TestCase
from flakeguard.parsers.junit_xml import parse_junit_xml
from flakeguard.report import render_text
from flakeguard.scoring import analyze

REPORTS = pathlib.Path(__file__).resolve().parents[1] / "examples" / "reports"


def case(name, outcome, message=None):
    return TestCase(name=name, classname="c", outcome=outcome, message=message)


# --- bug 1: single-run commits must not dilute the score --------------------


def test_single_run_commits_do_not_dilute_the_score():
    # A real flake on one commit (pass, fail, pass), then 29 commits that ran
    # it once each. Only the first commit can possibly show a flip.
    runs = (
        [[case("t", Outcome.PASSED)], [case("t", Outcome.FAILED)], [case("t", Outcome.PASSED)]]
        + [[case("t", Outcome.PASSED)]] * 29
    )
    commits = ["A", "A", "A"] + [f"c{i}" for i in range(29)]

    stats = analyze(runs, commits)[0]
    assert round(stats.score, 3) == 0.667  # not 0.062
    assert stats.informative_commits == 1
    assert stats.is_flaky()


def test_one_run_per_commit_is_surfaced_as_unconfirmed():
    # ~20% failure with one run per commit - the most common CI shape. It
    # cannot be told from a regression, so it must be reported, not hidden.
    runs, commits = [], []
    for i in range(30):
        runs.append([case("t", Outcome.FAILED if i % 5 == 0 else Outcome.PASSED)])
        commits.append(f"c{i}")

    stats = analyze(runs, commits)[0]
    assert stats.score == 0.0
    assert not stats.is_flaky()
    assert stats.is_unconfirmed()


def test_report_says_it_cannot_tell_flake_from_regression():
    runs, commits = [], []
    for i in range(10):
        runs.append([case("t", Outcome.FAILED if i % 3 == 0 else Outcome.PASSED)])
        commits.append(f"c{i}")

    out = render_text(analyze(runs, commits), 2, (), 10)
    assert "unconfirmed" in out.lower()
    assert "cannot tell a flake from a regression" in out


# --- bug 4: retries are the strongest signal --------------------------------


def test_flaky_failure_parses_as_flaky(tmp_path):
    xml = (
        '<?xml version="1.0"?>\n'
        "<testsuites><testsuite name=\"s\">\n"
        '  <testcase classname="c" name="test_retried">\n'
        '    <flakyFailure message="Connection reset">trace</flakyFailure>\n'
        "  </testcase>\n"
        "</testsuite></testsuites>"
    )
    p = tmp_path / "r.xml"
    p.write_text(xml)
    assert parse_junit_xml(str(p))[0].outcome is Outcome.FLAKY


def test_retry_flake_is_decisive_from_a_single_run():
    stats = analyze([[case("t", Outcome.FLAKY, message="boom")]], ["A"])[0]
    assert stats.flaky_retries == 1
    assert stats.score == 1.0
    assert stats.is_flaky()


# --- minor: duplicate keys keep the most severe outcome ---------------------


def test_duplicate_keys_in_a_run_keep_the_worst():
    run = [case("dup", Outcome.PASSED), case("dup", Outcome.FAILED)]
    stats = analyze([run], ["A"])[0]
    assert stats.failed == 1
    assert stats.passed == 0


# --- bug 4b: one build can write many files ---------------------------------


def test_single_run_merges_files(tmp_path, capsys):
    for name in ("run1.xml", "run2.xml", "run3.xml"):
        shutil.copy(REPORTS / name, tmp_path / name)
    out_file = tmp_path / "o.json"

    rc = main(["scan", str(tmp_path), "--single-run", "--format", "json", "-o", str(out_file)])
    err = capsys.readouterr().err

    assert rc == 0
    assert "treating 3 file(s) as one run" in err
    data = json.loads(out_file.read_text())
    assert data["summary"]["tests_analysed"] == 3


# --- bug 5: an environment commit applied to many files ----------------------


def test_env_commit_on_many_files_warns(tmp_path, capsys, monkeypatch):
    for name in ("run1.xml", "run2.xml"):
        shutil.copy(REPORTS / name, tmp_path / name)
    monkeypatch.setenv("GITHUB_SHA", "deadbeef")

    rc = main(["scan", str(tmp_path)])
    err = capsys.readouterr().err

    assert rc == 0
    assert "labelled with the same commit" in err
