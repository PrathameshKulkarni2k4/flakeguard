"""Tests for the flakiness scoring engine."""

from flakewatch.models import Outcome, TestCase
from flakewatch.scoring import _score, analyze


def case(name, outcome, suite="s", classname="c", message=None):
    return TestCase(name=name, suite=suite, classname=classname, outcome=outcome, message=message)


def test_score_all_pass_is_zero():
    assert _score(10, 0) == 0.0


def test_score_all_fail_is_zero():
    assert _score(0, 10) == 0.0


def test_score_coin_flip_is_one():
    assert _score(5, 5) == 1.0


def test_score_two_of_three():
    # 2 passes, 1 failure -> 2 * 1 / 3
    assert round(_score(2, 1), 4) == 0.6667


def test_analyze_ranks_flaky_first():
    runs = [
        [case("stable", Outcome.PASSED), case("flaky", Outcome.PASSED)],
        [case("stable", Outcome.PASSED), case("flaky", Outcome.FAILED)],
        [case("stable", Outcome.PASSED), case("flaky", Outcome.PASSED)],
    ]
    stats = analyze(runs)
    by_name = {s.name: s for s in stats}

    assert stats[0].name == "flaky"
    assert by_name["flaky"].passed == 2
    assert by_name["flaky"].failed == 1
    assert round(by_name["flaky"].score, 4) == 0.6667
    assert by_name["flaky"].is_flaky()

    assert by_name["stable"].score == 0.0
    assert not by_name["stable"].is_flaky()


def test_skips_are_ignored_for_flakiness():
    runs = [
        [case("t", Outcome.PASSED)],
        [case("t", Outcome.SKIPPED)],
        [case("t", Outcome.PASSED)],
    ]
    stats = {s.name: s for s in analyze(runs)}
    assert stats["t"].skipped == 1
    assert stats["t"].considered == 2
    assert stats["t"].score == 0.0
    assert not stats["t"].is_flaky()


def test_errors_count_as_failures():
    runs = [
        [case("t", Outcome.PASSED)],
        [case("t", Outcome.ERROR)],
    ]
    stats = {s.name: s for s in analyze(runs)}
    assert stats["t"].failures == 1
    assert stats["t"].is_flaky()


def test_duplicate_key_in_one_run_counted_once():
    runs = [[case("dup", Outcome.PASSED), case("dup", Outcome.PASSED)]]
    stats = {s.name: s for s in analyze(runs)}
    assert stats["dup"].runs == 1


def test_always_failing_test_is_not_flaky():
    runs = [[case("broken", Outcome.FAILED)], [case("broken", Outcome.FAILED)]]
    stats = {s.name: s for s in analyze(runs)}
    assert stats["broken"].score == 0.0
    assert not stats["broken"].is_flaky()
