"""Render analysis results as text, JSON, or Markdown."""

from __future__ import annotations

import json
from typing import List, Sequence

from .scoring import FlakeStats


def _bar(score: float, width: int = 10) -> str:
    filled = round(score * width)
    return "#" * filled + "." * (width - filled)


def render_text(stats: Sequence[FlakeStats], min_runs: int) -> str:
    """A human-readable terminal report."""
    flaky = [s for s in stats if s.is_flaky() and s.considered >= min_runs]

    lines: List[str] = []
    total = len(stats)
    lines.append("")
    lines.append("flakewatch report")
    lines.append("=" * 60)
    lines.append(f"tests analysed : {total}")
    lines.append(f"flaky (>= {min_runs} runs): {len(flaky)}")
    lines.append("")

    if not flaky:
        lines.append("No flaky tests found. Your suite is behaving.")
        lines.append("")
        return "\n".join(lines)

    lines.append(f"{'score':>6}  {'bar':<10}  {'runs':>4}  {'pass':>4}  {'fail':>4}  test")
    lines.append("-" * 60)
    for s in flaky:
        lines.append(
            f"{s.score:>6.2f}  {_bar(s.score):<10}  {s.considered:>4}  "
            f"{s.passed:>4}  {s.failures:>4}  {s.display_name}"
        )

    # Show the most recent failure message for the worst offender - the
    # thing a developer actually wants to read.
    worst = flaky[0]
    if worst.last_message:
        lines.append("")
        lines.append(f"latest failure in {worst.display_name}:")
        lines.append(f"  {worst.last_message}")

    lines.append("")
    return "\n".join(lines)


def _stats_to_dict(s: FlakeStats) -> dict:
    return {
        "key": s.key,
        "name": s.name,
        "suite": s.suite,
        "classname": s.classname,
        "runs": s.considered,
        "passed": s.passed,
        "failed": s.failed,
        "errored": s.errored,
        "skipped": s.skipped,
        "score": round(s.score, 4),
        "last_message": s.last_message,
    }


def render_json(stats: Sequence[FlakeStats], min_runs: int) -> str:
    flaky = [s for s in stats if s.is_flaky() and s.considered >= min_runs]
    payload = {
        "schema_version": 1,
        "summary": {
            "tests_analysed": len(stats),
            "flaky": len(flaky),
            "min_runs": min_runs,
        },
        "flaky_tests": [_stats_to_dict(s) for s in flaky],
        "all_tests": [_stats_to_dict(s) for s in stats],
    }
    return json.dumps(payload, indent=2)


def render_markdown(stats: Sequence[FlakeStats], min_runs: int) -> str:
    flaky = [s for s in stats if s.is_flaky() and s.considered >= min_runs]
    lines = ["## flakewatch report", ""]
    if not flaky:
        lines.append("No flaky tests found.")
        return "\n".join(lines)
    lines.append(f"**{len(flaky)}** flaky test(s) found across {len(stats)} analysed.")
    lines.append("")
    lines.append("| score | runs | pass | fail | test |")
    lines.append("|------:|-----:|-----:|-----:|:-----|")
    for s in flaky:
        lines.append(
            f"| {s.score:.2f} | {s.considered} | {s.passed} | {s.failures} | `{s.display_name}` |"
        )
    lines.append("")
    return "\n".join(lines)


RENDERERS = {
    "text": render_text,
    "json": render_json,
    "markdown": render_markdown,
    "md": render_markdown,
}
