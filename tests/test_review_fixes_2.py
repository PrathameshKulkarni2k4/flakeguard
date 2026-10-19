"""Regression tests for the second round of review findings."""

import datetime
import pathlib

from flakeguard.cli import main
from flakeguard.history import History
from flakeguard.models import Outcome, TestCase
from flakeguard.quarantine import stale_patterns, update_quarantine
from flakeguard.scoring import analyze

REPORTS = pathlib.Path(__file__).resolve().parents[1] / "examples" / "reports"


def case(name, outcome, message=None):
    return TestCase(name=name, classname="c", outcome=outcome, message=message)


# --- #1: a retry flake must not inflate the run count or claim frequency ----


def test_retry_flake_does_not_inflate_the_run_count():
    runs = [[case("t", Outcome.PASSED)] for _ in range(99)]
    runs.append([case("t", Outcome.FLAKY, message="boom")])
    commits = [f"c{i}" for i in range(100)]

    stats = analyze(runs, commits)[0]
    assert stats.considered == 100  # 100 real runs, not 101
    assert stats.score == 1.0  # certain it is flaky...
    assert round(stats.rate, 4) == 0.01  # ...but only 1% of the time


def test_frequent_flake_outranks_a_rare_one():
    rare = [[case("rare", Outcome.PASSED)] for _ in range(99)]
    rare.append([case("rare", Outcome.FLAKY)])
    rare_commits = [f"r{i}" for i in range(100)]

    freq_runs, freq_commits = [], []
    for i in range(30):
        freq_runs.append([case("freq", Outcome.FAILED if i % 3 == 0 else Outcome.PASSED)])
        freq_commits.append(f"f{i}")

    stats = analyze(rare + freq_runs, rare_commits + freq_commits)
    by_name = {s.name: s for s in stats}

    assert round(by_name["rare"].rate, 3) == 0.01
    assert round(by_name["freq"].rate, 3) == 0.333
    assert stats[0].name == "freq"  # frequency, not certainty, leads


# --- #2: one <testcase> per attempt is a flake, not a hard failure ----------


def test_pass_and_fail_in_one_run_collapse_to_a_flake():
    run = [case("t", Outcome.FAILED), case("t", Outcome.PASSED)]
    stats = analyze([run], ["A"])[0]
    assert stats.flaky_retries == 1
    assert stats.is_flaky()
    assert stats.score == 1.0


# --- #3: history and scoring must agree ------------------------------------


def test_history_collapses_the_same_way_as_scoring(tmp_path):
    run = [case("t", Outcome.FAILED), case("t", Outcome.PASSED)]
    db = str(tmp_path / "h.db")
    with History(db) as hist:
        hist.add_run(run)
        stored = hist.load_runs()

    _, cases = stored[0]
    assert len(cases) == 1
    assert cases[0].outcome is Outcome.FLAKY

    # ...and the scoring path reaches the same conclusion.
    assert analyze([run], ["A"])[0].flaky_retries == 1


# --- #5: quarantine entries age -------------------------------------------


def test_stale_quarantine_entries_are_flagged(tmp_path):
    q = tmp_path / "q.txt"
    update_quarantine(str(q), ["old::test"], today=datetime.date(2020, 1, 1))

    assert stale_patterns(str(q), 90, today=datetime.date(2026, 1, 1)) == ["old::test"]
    assert stale_patterns(str(q), 90, today=datetime.date(2020, 2, 1)) == []


def test_hand_written_patterns_are_never_called_stale(tmp_path):
    q = tmp_path / "q.txt"
    q.write_text("# no date here\nhand::written\n")
    assert stale_patterns(str(q), 0, today=datetime.date(2026, 1, 1)) == []


def test_cli_warns_about_stale_quarantine(tmp_path, capsys):
    q = tmp_path / "q.txt"
    update_quarantine(str(q), ["old::test"], today=datetime.date(2020, 1, 1))

    rc = main(["scan", str(REPORTS), "--quarantine", str(q)])
    err = capsys.readouterr().err

    assert rc == 0
    assert "please review" in err
