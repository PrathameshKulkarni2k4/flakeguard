"""Command-line entry point.

    flakeguard scan ./reports
    flakeguard scan ./reports --commit "$GITHUB_SHA"
    flakeguard scan ./reports --quarantine flakeguard-quarantine.txt
    flakeguard scan ./reports --history .flakeguard/history.db
    flakeguard scan --manifest flakeguard-runs.json
    flakeguard history .flakeguard/history.db
"""

from __future__ import annotations

import argparse
import glob
import os
import sys
from typing import List, Optional, Tuple

from . import __version__
from .history import History
from .manifest import load_manifest
from .parsers import by_suffix
from .quarantine import is_quarantined, load_patterns, update_quarantine
from .report import RENDERERS
from .scoring import analyze

DEFAULT_QUARANTINE = "flakeguard-quarantine.txt"

# Environment variables we'll read a commit from, if the user doesn't pass one.
_COMMIT_ENV = (
    "FLAKEGUARD_COMMIT",
    "GITHUB_SHA",
    "CI_COMMIT_SHA",
    "GIT_COMMIT",
    "BUILD_SOURCEVERSION",
    "CIRCLE_SHA1",
)


def _detect_commit(explicit: Optional[str]):
    """The commit for this run: explicit flag, else a common CI variable.

    Returns ``(commit, source)`` so the caller can warn when a value guessed
    from the environment is applied to several report files at once.
    """
    if explicit:
        return explicit, "flag"
    for name in _COMMIT_ENV:
        value = os.environ.get(name)
        if value:
            return value, f"env:{name}"
    return None, None


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


def _parse_file(path: str) -> Tuple[Optional[list], Optional[str]]:
    """Parse one report file. Returns (cases, error)."""
    suffix = os.path.splitext(path)[1].lower()
    parser = by_suffix.get(suffix)
    if parser is None:
        return None, f"{path}: unsupported format '{suffix}'"
    if not os.path.exists(path):
        return None, f"{path}: file not found"
    try:
        return parser(path), None
    except Exception as exc:  # noqa: BLE001 - report, don't crash
        return None, f"{path}: {exc}"


def _load_runs(files: List[str]) -> tuple[list, list]:
    """Parse each file into a run. Returns (runs, errors)."""
    runs, errors = [], []
    for path in files:
        cases, error = _parse_file(path)
        if error:
            errors.append(error)
        else:
            runs.append(cases)
    return runs, errors


def _gather(args: argparse.Namespace):
    """Work out (runs, commits, errors) from report paths or a manifest."""
    runs: List[list] = []
    commits: List[Optional[str]] = []
    errors: List[str] = []

    if args.manifest:
        for index, entry in enumerate(load_manifest(args.manifest), start=1):
            files = _discover(entry.reports)
            if not files:
                errors.append(
                    f"run {index} ({entry.label or entry.commit or 'no label'}): "
                    "no report files found"
                )
                continue
            merged: list = []
            for path in files:
                cases, error = _parse_file(path)
                if error:
                    errors.append(error)
                else:
                    merged.extend(cases)
            if merged:
                runs.append(merged)
                commits.append(entry.commit)
        return runs, commits, errors

    files = _discover(args.paths)
    if not files:
        return [], [], []

    parsed, errors = _load_runs(files)
    commit, commit_source = _detect_commit(args.commit)

    if args.single_run and len(parsed) > 1:
        print(
            f"flakeguard: --single-run: treating {len(parsed)} file(s) as one run",
            file=sys.stderr,
        )
        parsed = [[case for run in parsed for case in run]]

    if commit_source and commit_source.startswith("env:") and len(parsed) > 1:
        print(
            f"flakeguard: warning: {commit_source.split(':', 1)[1]} is set, so all "
            f"{len(parsed)} report file(s) were labelled with the same commit "
            f"({commit}). If they come from different builds that hides "
            "regressions - pass --commit explicitly, use --manifest, or scan one "
            "build at a time.",
            file=sys.stderr,
        )

    return parsed, [commit] * len(parsed), errors


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="flakeguard",
        description="Find, rank, and quarantine flaky tests from test reports.",
    )
    p.add_argument("--version", action="version", version=f"flakeguard {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="analyse one or more report files/dirs")
    scan.add_argument(
        "paths",
        nargs="*",
        help="report files, globs, or directories (or use --manifest)",
    )
    scan.add_argument(
        "--manifest",
        metavar="FILE",
        default=None,
        help=(
            "a JSON runs manifest that declares each run and its commit, instead "
            "of guessing from files and environment variables"
        ),
    )
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
        "--commit",
        metavar="SHA",
        default=None,
        help=(
            "commit these results belong to. Flakiness is only counted within a "
            "commit, so a regression is not mistaken for a flake. Falls back to "
            "GITHUB_SHA / CI_COMMIT_SHA / GIT_COMMIT if not given"
        ),
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
            "add every currently-flaky test to the quarantine file and exit 0 "
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
        "--single-run",
        action="store_true",
        help=(
            "treat every report file as part of ONE run. Use this when a single "
            "build writes many files - Maven and Gradle Surefire write one XML "
            "per test class"
        ),
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
        print(f"commits       : {hist.commit_count()}")
    return 0


def _cmd_scan(args: argparse.Namespace) -> int:
    if not args.manifest and not args.paths:
        print(
            "flakeguard: give me report files/directories, or --manifest FILE",
            file=sys.stderr,
        )
        return 2
    if args.manifest and args.paths:
        print(
            "flakeguard: give either report paths or --manifest, not both",
            file=sys.stderr,
        )
        return 2

    if args.manifest:
        try:
            runs, commits, errors = _gather(args)
        except (ValueError, OSError) as exc:
            print(f"flakeguard: {args.manifest}: {exc}", file=sys.stderr)
            return 2
        for err in errors:
            print(f"flakeguard: warning: {err}", file=sys.stderr)
        if not runs:
            print("flakeguard: the manifest produced no usable runs", file=sys.stderr)
            return 2
    else:
        runs, commits, errors = _gather(args)
        for err in errors:
            print(f"flakeguard: warning: {err}", file=sys.stderr)
        if not runs and errors:
            print(
                f"flakeguard: none of the {len(errors)} file(s) could be parsed.\n"
                "  See the warnings above - is the file a valid report?",
                file=sys.stderr,
            )
            return 2
        if not runs:
            print(
                "flakeguard: no test report files found.\n"
                "  I read JUnit XML (.xml), TAP (.tap) and Jest-style JSON (.json) -\n"
                "  give me a file, a glob, or a directory. Need to make one? e.g.\n"
                "      pytest --junitxml=report.xml\n"
                "      jest --json > report.json",
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

    # With a history file, remember these runs and analyse everything stored.
    if args.history:
        with History(args.history) as hist:
            for run, commit in zip(runs, commits):
                hist.add_run(run, commit=commit)
            pruned = hist.prune(args.history_keep)
            if pruned:
                print(f"flakeguard: pruned {pruned} old run(s) from history", file=sys.stderr)
            stored = hist.load_runs()
            print(f"flakeguard: history has {hist.run_count()} run(s)", file=sys.stderr)
        analysis_commits = [c for c, _ in stored]
        analysis_runs = [r for _, r in stored]
    else:
        analysis_runs, analysis_commits = runs, commits

    known_commits = {c for c in analysis_commits if c}
    commit_count = len(known_commits) or None
    if commit_count:
        print(
            f"flakeguard: scoring within {commit_count} commit(s) - "
            "disagreement across commits is a regression, not a flake",
            file=sys.stderr,
        )
    elif len(analysis_runs) > 1:
        print(
            "flakeguard: no commit information, so runs are pooled - a regression "
            "could look flaky. Pass --commit (or use --manifest / --history).",
            file=sys.stderr,
        )

    stats = analyze(analysis_runs, analysis_commits)
    if args.min_score > 0:
        stats = [s for s in stats if s.score >= args.min_score or not s.is_flaky()]

    report = RENDERERS[args.format](stats, args.min_runs, patterns, commit_count)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(report + "\n")
        print(f"flakeguard: wrote {args.output} ({len(analysis_runs)} runs)", file=sys.stderr)
    else:
        print(report)

    flaky = [s for s in stats if s.is_flaky() and s.considered >= args.min_runs]

    if args.update_quarantine:
        target = args.quarantine or DEFAULT_QUARANTINE
        added = update_quarantine(target, (s.key for s in flaky))
        print(
            f"flakeguard: added {added} test(s) to {target} (existing entries kept)",
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
