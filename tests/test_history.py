"""Tests for the persistent history feature."""

import pathlib

from flakeguard.cli import main
from flakeguard.history import History
from flakeguard.models import Outcome, TestCase

REPORTS = pathlib.Path(__file__).resolve().parents[1] / "examples" / "reports"


def case(name, outcome):
    return TestCase(name=name, classname="c", outcome=outcome)


def test_add_and_load_round_trip(tmp_path):
    db = str(tmp_path / "h.db")
    with History(db) as h:
        h.add_run([case("a", Outcome.PASSED), case("b", Outcome.FAILED)])
        h.add_run([case("a", Outcome.PASSED), case("b", Outcome.PASSED)])
        assert h.run_count() == 2
        assert h.test_count() == 2
        runs = h.load_runs()

    assert len(runs) == 2
    assert runs[0][0].name == "a"
    assert runs[1][1].outcome is Outcome.PASSED


def test_prune_keeps_newest(tmp_path):
    db = str(tmp_path / "h.db")
    with History(db) as h:
        for _ in range(5):
            h.add_run([case("a", Outcome.PASSED)])
        removed = h.prune(2)
        assert removed == 3
        assert h.run_count() == 2


def test_clear_empties(tmp_path):
    db = str(tmp_path / "h.db")
    with History(db) as h:
        h.add_run([case("a", Outcome.PASSED)])
        assert h.clear() == 1
        assert h.run_count() == 0
        assert h.test_count() == 0


def test_scan_history_accumulates(tmp_path, capsys):
    db = str(tmp_path / "h.db")
    one = str(REPORTS / "run1.xml")

    main(["scan", one, "--history", db])
    capsys.readouterr()
    main(["scan", one, "--history", db])
    err = capsys.readouterr().err
    assert "history has 2 run(s)" in err


def test_history_becomes_flaky_over_multiple_scans(tmp_path, capsys):
    # run1 has test_applies_coupon passing; run2 has it failing.
    db = str(tmp_path / "h.db")
    main(["scan", str(REPORTS / "run1.xml"), "--history", db])
    capsys.readouterr()
    main(["scan", str(REPORTS / "run2.xml"), "--history", db, "--format", "json", "-o", str(tmp_path / "o.json")])
    capsys.readouterr()

    import json

    data = json.loads((tmp_path / "o.json").read_text())
    names = {t["name"]: t for t in data["flaky_tests"]}
    assert "test_applies_coupon" in names  # flaky once both runs are known


def test_history_subcommand_reports_counts(tmp_path, capsys):
    db = str(tmp_path / "h.db")
    main(["scan", str(REPORTS / "run1.xml"), "--history", db])
    capsys.readouterr()
    rc = main(["history", db])
    out = capsys.readouterr().out
    assert rc == 0
    assert "runs stored   : 1" in out


def test_history_subcommand_clear(tmp_path, capsys):
    db = str(tmp_path / "h.db")
    main(["scan", str(REPORTS / "run1.xml"), "--history", db])
    capsys.readouterr()
    rc = main(["history", db, "--clear"])
    capsys.readouterr()
    assert rc == 0
    with History(db) as h:
        assert h.run_count() == 0
