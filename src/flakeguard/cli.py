"""Command-line entry point.

    flakeguard scan ./reports
    flakeguard scan run1.xml run2.xml run3.xml --format json
    flakeguard scan ./ci-artifacts --min-runs 5 --min-score 0.2
"""

from __future__ import annotations

import argparse
import glob
import os
import sys
from typing import List

from . import __version__
from .parsers import by_suffix
from .report import RENDERERS
from .scoring import analyze


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
        "--fail-on-flaky",
        action="store_true",
        help="exit with code 1 if any flaky tests are found (for CI gating)",
    )
    return p


def main(argv: List[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    files = _discover(args.paths)
    if not files:
        print(
            "flakeguard: no test report files found.\n"
            "  I look for JUnit XML (.xml) files - give me a file, a glob, or a\n"
            "  directory. Need to make one? Most frameworks can, for example:\n"
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
            "  See the warnings above - is the file valid JUnit XML?",
            file=sys.stderr,
        )
        return 2

    stats = analyze(runs)
    # Apply the minimum-score filter on top of the renderers' min-runs filter.
    if args.min_score > 0:
        stats = [s for s in stats if s.score >= args.min_score or not s.is_flaky()]

    report = RENDERERS[args.format](stats, args.min_runs)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(report + "\n")
        print(f"flakeguard: wrote {args.output} ({len(runs)} runs)", file=sys.stderr)
    else:
        print(report)

    flaky_count = sum(1 for s in stats if s.is_flaky() and s.considered >= args.min_runs)
    if args.fail_on_flaky and flaky_count > 0:
        print(f"flakeguard: {flaky_count} flaky test(s) found", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
