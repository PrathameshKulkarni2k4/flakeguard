"""Command-line entry point.

    flakeguard scan ./reports
    flakeguard scan run1.xml run2.xml run3.xml --format json
    flakeguard scan ./reports --quarantine flakeguard-quarantine.txt
    flakeguard scan ./reports --history .flakeguard/history.db
    flakeguard history .flakeguard/history.db
"""

from __future__ import annotations

import argparse
import glob
import os
import sys
from typing import List

from . import __version__
from .history import History
from .parsers import by_suffix
from .quarantine import is_quarantined, load_patterns, write_patterns
from .report import RENDERERS
from .scoring import analyze

DEFAULT_QUARANTINE = "flakeguard-quarantine.txt"


def _discover(paths: List[str]) -> List[str]:
    """Expand the given paths into a sorted list of report files.

    Directories are walked recursively; files are taken as-is. Sorting
    keeps run order deterministic so results are reproducible.
    """
    found: List[str] = []
    for path in paths:
        if os.path.isdir(path):
            for root, _dirs, files in os.walk(path):
                for fname in files:
                    if os.path.splitext(fname)[1].lower() in by_suffix:
                        found.append(os.path.join(root, fname))
        else:
            matches = sorted(glob.glob(path))
            if matches:
                found.extend(matches)
            elif os.path.exists(path):
                found.append(path)
    return sorted(set(found))


def _load_runs(files: List[str]) -> tuple[list, list]:
    """Parse each file into a run. Returns (runs, errors)."""
    runs, errors = [], []
    for path in files:
        suffix = os.path.splitext(path)[1].lower()
        parser = by_suffix.get(suffix)
        if parser is None:
            errors.append(f"{path}: unsupported format '{suffix}'")
            continue
        if not os.path.exists(path):
            errors.append(f"{path}: file not found")
            continue
        try:
            runs.append(parser(path))
        except Exception as exc:  # noqa: BLE001 - report, don't crash
            errors.append(f"{path}: {exc}")
    return runs, errors


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="flakeguard",
        description="Find, rank, and quarantine flaky tests from test reports.",
    )
    p.add_argument("--version", action="version", version=f"flakeguard {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="analyse one or more report files/dirs")
    scan.add_argument("paths", nargs="+", help="report files, globs, or directories")
    scan.add_argument(
        "--min-runs",
        type=int,
        default=2,
        help="minimum runs a test must appear in to be reported (default: 2)",
    )
    scan.add_argument(
        "--min-score",
        type=float,
        default=0.0,
        help="only report tests at or above this flakiness score, 0-1 (default: 0)",
    )
    scan.add_argument(
        "--format",
        choices=sorted(RENDERERS),
        default="text",
        help="output format (default: text)",
    )
    scan.add_argument(
        "--output", "-o", default=None, help="write the report to a file instead of stdout"
    )
    scan.add_argument(
        "--quarantine",
        metavar="FILE",
        default=None,
        help="file of glob patterns for known-flaky tests (one per line)",
    )
    scan.add_argument(
        "--update-quarantine",
        action="store_true",
        help=(
            "write every currently-flaky test to the quarantine file and exit 0 "
            f"(default file: {DEFAULT_QUARANTINE})"
        ),
    )
    scan.add_argument(
        "--history",
        metavar="FILE",
        default=None,
        help=(
            "SQLite file that accumulates results across runs; each scan appends "
            "this run and analyses everything stored so far"
        ),
    )
    scan.add_argument(
        "--history-keep",
        type=int,
        default=30,
        help="maximum number of runs to keep in the history file (default: 30)",
    )
    scan.add_argument(
        "--fail-on-flaky",
        action="store_true",
        help="exit with code 1 if any NEW (non-quarantined) flaky tests are found",
    )

    hist = sub.add_parser("history", help="inspect or clear a history file")
    hist.add_argument("path", help="the history file to inspect")
    hist.add_argument("--clear", action="store_true", help="delete all stored runs")
    return p


def _cmd_history(args: argparse.Namespace) -> int:
    if not args.clear and not os.path.exists(args.path):
        print(f"flakeguard: no history file at {args.path}", file=sys.stderr)
        return 2
    with History(args.path) as hist:
        if args.clear:
            removed = hist.clear()
            print(f"flakeguard: cleared {removed} run(s) from {args.path}", file=sys.stderr)
            return 0
        print(f"history file  : {args.path}")
        print(f"runs stored   : {hist.run_count()}")
        print(f"distinct tests: {hist.test_count()}")
    return 0


def _cmd_scan(args: argparse.Namespace) -> int:
    files = _discover(args.paths)
    if not files:
        print(
            "flakeguard: no test report files found.\n"
            "  I look for JUnit XML (.xml) and TAP (.tap) files - give me a file,\n"
            "  a glob, or a directory. Need to make one? Most frameworks can, e.g.\n"
            "      pytest --junitxml=report.xml",
            file=sys.stderr,
        )
        return 2

    runs, errors = _load_runs(files)
    for err in errors:
        print(f"flakeguard: warning: {err}", file=sys.stderr)
    if not runs:
        print(
            f"flakeguard: none of the {len(files)} file(s) could be parsed.\n"
            "  See the warnings above - is the file a valid report?",
            file=sys.stderr,
        )
        return 2

    patterns: List[str] = []
    if args.quarantine:
        if os.path.exists(args.quarantine):
            patterns = load_patterns(args.quarantine)
        else:
            print(
                f"flakeguard: warning: quarantine file '{args.quarantine}' not found "
                "(treating as empty)",
                file=sys.stderr,
            )

    # With a history file, remember this run and analyse everything stored.
    analysis_runs = runs
    if args.history:
        with History(args.history) as hist:
            for run in runs:
                hist.add_run(run)
            pruned = hist.prune(args.history_keep)
            if pruned:
                print(f"flakeguard: pruned {pruned} old run(s) from history", file=sys.stderr)
            analysis_runs = hist.load_runs()
            print(f"flakeguard: history has {hist.run_count()} run(s)", file=sys.stderr)

    stats = analyze(analysis_runs)
    if args.min_score > 0:
        stats = [s for s in stats if s.score >= args.min_score or not s.is_flaky()]

    report = RENDERERS[args.format](stats, args.min_runs, patterns)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(report + "\n")
        print(f"flakeguard: wrote {args.output} ({len(analysis_runs)} runs)", file=sys.stderr)
    else:
        print(report)

    flaky = [s for s in stats if s.is_flaky() and s.considered >= args.min_runs]

    if args.update_quarantine:
        target = args.quarantine or DEFAULT_QUARANTINE
        written = write_patterns(target, (s.key for s in flaky))
        print(
            f"flakeguard: wrote {written} test(s) to {target} - they are now quarantined",
            file=sys.stderr,
        )
        return 0

    new_flaky = [s for s in flaky if not is_quarantined(s.key, patterns)]
    if args.fail_on_flaky and new_flaky:
        print(f"flakeguard: {len(new_flaky)} new flaky test(s) found", file=sys.stderr)
        return 1
    return 0


def main(argv: List[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "history":
        return _cmd_history(args)
    return _cmd_scan(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
