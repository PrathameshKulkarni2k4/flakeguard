"""Persistent history: remember test results across runs.

Flakiness needs several runs to see. Collecting report files by hand is
awkward, so instead point flakeguard at a history file and run it once per
build. Each run is appended, and every analysis sees everything stored so
far - so the picture sharpens on its own.

Storage is a single SQLite file (standard library, no dependencies), which
is small and fast even for tens of thousands of tests.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Iterable, List, Optional

from .models import Outcome, TestCase

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    label      TEXT
);
CREATE TABLE IF NOT EXISTS results (
    run_id    INTEGER NOT NULL,
    test_key  TEXT    NOT NULL,
    outcome   TEXT    NOT NULL,
    duration  REAL,
    message   TEXT,
    name      TEXT,
    suite     TEXT,
    classname TEXT,
    PRIMARY KEY (run_id, test_key)
);
CREATE INDEX IF NOT EXISTS idx_results_key ON results(test_key);
"""

_INSERT = (
    "INSERT OR REPLACE INTO results "
    "(run_id, test_key, outcome, duration, message, name, suite, classname) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
)


class History:
    """A growing record of test results, one run at a time."""

    def __init__(self, path: str):
        self.path = path
        self._conn = sqlite3.connect(path)
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    # -- lifecycle ---------------------------------------------------------
    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "History":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- writing -----------------------------------------------------------
    def add_run(self, cases: Iterable[TestCase], label: Optional[str] = None) -> int:
        """Append one run's worth of results. Returns the new run id."""
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO runs (created_at, label) VALUES (?, ?)",
            (datetime.now(timezone.utc).isoformat(timespec="seconds"), label),
        )
        run_id = int(cur.lastrowid or 0)

        rows, seen = [], set()
        for case in cases:
            if case.key in seen:
                continue
            seen.add(case.key)
            rows.append(
                (run_id, case.key, case.outcome.value, case.duration, case.message,
                 case.name, case.suite, case.classname)
            )
        cur.executemany(_INSERT, rows)
        self._conn.commit()
        return run_id

    def prune(self, keep: int) -> int:
        """Keep only the most recent ``keep`` runs. Returns how many were dropped."""
        total = self.run_count()
        if keep < 0 or total <= keep:
            return 0
        cur = self._conn.cursor()
        cutoff = "SELECT run_id FROM runs ORDER BY run_id DESC LIMIT -1 OFFSET ?"
        cur.execute(f"DELETE FROM results WHERE run_id IN ({cutoff})", (keep,))
        cur.execute(f"DELETE FROM runs WHERE run_id IN ({cutoff})", (keep,))
        self._conn.commit()
        return total - keep

    def clear(self) -> int:
        """Delete every stored run. Returns how many were removed."""
        total = self.run_count()
        self._conn.executescript("DELETE FROM results; DELETE FROM runs;")
        self._conn.commit()
        return total

    # -- reading -----------------------------------------------------------
    def run_count(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0])

    def test_count(self) -> int:
        return int(self._conn.execute("SELECT COUNT(DISTINCT test_key) FROM results").fetchone()[0])

    def load_runs(self, max_runs: Optional[int] = None) -> List[List[TestCase]]:
        """Load stored runs as lists of TestCase, oldest first."""
        cur = self._conn.cursor()
        if max_runs:
            query = (
                "SELECT run_id FROM (SELECT run_id FROM runs ORDER BY run_id DESC "
                f"LIMIT {int(max_runs)}) ORDER BY run_id"
            )
        else:
            query = "SELECT run_id FROM runs ORDER BY run_id"
        run_ids = [row[0] for row in cur.execute(query).fetchall()]

        runs: List[List[TestCase]] = []
        for run_id in run_ids:
            cases: List[TestCase] = []
            for key, outcome, duration, message, name, suite, classname in cur.execute(
                "SELECT test_key, outcome, duration, message, name, suite, classname "
                "FROM results WHERE run_id = ? ORDER BY test_key",
                (run_id,),
            ):
                cases.append(
                    TestCase(
                        name=name or "",
                        suite=suite or "",
                        classname=classname or "",
                        outcome=Outcome(outcome),
                        duration=duration or 0.0,
                        message=message,
                    )
                )
            runs.append(cases)
        return runs
