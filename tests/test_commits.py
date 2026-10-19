"""Commit-aware scoring: the difference between a flake and a regression.

A test that passed for 15 builds and then failed for 15 more, after a real
change landed, is a regression - not flakiness. These tests pin that down.
"""

import pathlib

import pytest

from flakeguard.cli import main
from flakeguard.models import Outcome, TestCase
from flakeguard.scoring import analyze

REPORTS = pathlib.Path(__file__).resolve().parents[1] / "examples" / "reports"


def case(name, outcome):
    return TestCase(name=name, classname="c", outcome=outcome)


def test_regression_across_commits_is_not_flaky():
    # 15 green builds on commit A, a real bug lands, 15 red builds on commit B.
    runs = [[case("t", Outcome.PASSED)]] * 15 + [[case("t", Outcome.FAILED)]] * 15
    commits = ["A"] * 15 + ["B"] * 15

    stats = analyze(runs, commits)[0]
    assert stats.score == 0.0
    assert not stats.is_flaky()


def test_pooled_without_commits_cannot_tell_flake_from_regression():
    # The same data with no commit information: the weaker, pooled view.
    runs = [[case("t", Outcome.PASSED)]] * 15 + [[case("t", Outcome.FAILED)]] * 15
    stats = analyze(runs)[0]
    assert stats.score == 1.0  # looks maximally flaky - why commits matter


def test_flaky_within_a_single_commit_is_detected():
    outcomes = [Outcome.PASSED, Outcome.FAILED, Outcome.PASSED, Outcome.FAILED]
    runs = [[case("t", o)] for o in outcomes]
    stats = analyze(runs, ["A"] * 4)[0]
    assert stats.score == 1.0
    assert stats.is_flaky()


def test_flake_and_regression_together_only_counts_the_flake():
    # commit A: flaky (2 pass, 2 fail). commit B: consistent failure (regression).
    runs = [
        [case("t", Outcome.PASSED)], [case("t", Outcome.FAILED)],
        [case("t", Outcome.PASSED)], [case("t", Outcome.FAILED)],
        [case("t", Outcome.FAILED)], [case("t", Outcome.FAILED)],
    ]
    commits = ["A", "A", "A", "A", "B", "B"]
    stats = analyze(runs, commits)[0]
    assert round(stats.score, 3) == 0.667  # 2 flips in A out of 6 decided
    assert stats.commit_groups == 2


def test_commits_and_runs_must_align():
    with pytest.raises(ValueError):
        analyze([[case("t", Outcome.PASSED)]], ["A", "B"])


def test_cli_scores_within_the_given_commit(capsys):
    rc = main(["scan", str(REPORTS), "--commit", "abc123"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "scored within  : 1 commit(s)" in out


def test_cli_warns_when_pooling_without_commits(capsys, monkeypatch):
    # CI sets GITHUB_SHA, which would auto-detect a commit - clear them so we
    # really are testing the "no commit info" path.
    for name in ("FLAKEGUARD_COMMIT", "GITHUB_SHA", "CI_COMMIT_SHA",
                 "GIT_COMMIT", "BUILD_SOURCEVERSION", "CIRCLE_SHA1"):
        monkeypatch.delenv(name, raising=False)
    rc = main(["scan", str(REPORTS)])
    err = capsys.readouterr().err
    assert rc == 0
    assert "no commit information" in err
