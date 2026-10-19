"""Render analysis results as text, JSON, or Markdown."""

from __future__ import annotations

import json
from typing import List, Optional, Sequence, Tuple

from .clustering import Cluster, cluster
from .quarantine import is_quarantined
from .scoring import FlakeStats

_MAX_CLUSTERS = 10
_MAX_NAMES = 4


def _bar(score: float, width: int = 10) -> str:
    filled = round(score * width)
    return "#" * filled + "." * (width - filled)


def _split(
    stats: Sequence[FlakeStats], min_runs: int, quarantine: Sequence[str]
) -> Tuple[List[FlakeStats], List[FlakeStats]]:
    """Return (new_flaky, quarantined) - flaky tests, partitioned."""
    flaky = [s for s in stats if s.is_flaky() and s.considered >= min_runs]
    new = [s for s in flaky if not is_quarantined(s.key, quarantine)]
    quar = [s for s in flaky if is_quarantined(s.key, quarantine)]
    return new, quar


def _clusters(new: List[FlakeStats], quar: List[FlakeStats]) -> List[Cluster]:
    """Cluster all flaky tests - but only once there is more than one."""
    flaky = new + quar
    if len(flaky) < 2:
        return []
    return cluster(flaky)[:_MAX_CLUSTERS]


def render_text(
    stats: Sequence[FlakeStats],
    min_runs: int,
    quarantine: Sequence[str] = (),
    commits: Optional[int] = None,
) -> str:
    """A human-readable terminal report."""
    new, quar = _split(stats, min_runs, quarantine)
    clusters = _clusters(new, quar)

    lines: List[str] = [""]
    lines.append("flakeguard report")
    lines.append("=" * 60)
    lines.append(f"tests analysed : {len(stats)}")
    lines.append(f"new flaky      : {len(new)}")
    if quarantine:
        lines.append(f"quarantined    : {len(quar)}")
    if commits:
        lines.append(f"scored within  : {commits} commit(s)")
    else:
        lines.append("scored within  : all runs pooled (no commit info)")
    lines.append("")

    if not new:
        if quar:
            lines.append(f"No new flaky tests. {len(quar)} known flake(s) quarantined.")
        else:
            lines.append("No flaky tests found. Your suite is behaving.")
        lines.append("")
        return "\n".join(lines)

    lines.append(f"{'score':>6}  {'bar':<10}  {'runs':>4}  {'pass':>4}  {'fail':>4}  test")
    lines.append("-" * 60)
    for s in new:
        lines.append(
            f"{s.score:>6.2f}  {_bar(s.score):<10}  {s.considered:>4}  "
            f"{s.passed:>4}  {s.failures:>4}  {s.display_name}"
        )

    worst = new[0]
    if worst.last_message:
        lines.append("")
        lines.append(f"latest failure in {worst.display_name}:")
        lines.append(f"  {worst.last_message}")

    if clusters:
        lines.append("")
        lines.append(f"failure clusters ({len(clusters)}) - similar flakes, likely one cause:")
        for c in clusters:
            lines.append(f"  {c.count}x  {c.display}")
            for s in c.tests[:_MAX_NAMES]:
                lines.append(f"        {s.display_name}")
            if c.count > _MAX_NAMES:
                lines.append(f"        ... and {c.count - _MAX_NAMES} more")

    if quar:
        lines.append("")
        lines.append(f"{len(quar)} known flake(s) hidden by the quarantine file.")

    lines.append("")
    return "\n".join(lines)


def _stats_to_dict(s: FlakeStats, quarantined: bool = False) -> dict:
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
        "quarantined": quarantined,
        "last_message": s.last_message,
    }


def render_json(
    stats: Sequence[FlakeStats],
    min_runs: int,
    quarantine: Sequence[str] = (),
    commits: Optional[int] = None,
) -> str:
    new, quar = _split(stats, min_runs, quarantine)
    clusters = _clusters(new, quar)
    payload = {
        "schema_version": 3,
        "summary": {
            "tests_analysed": len(stats),
            "flaky": len(new) + len(quar),
            "new_flaky": len(new),
            "quarantined": len(quar),
            "commits": commits,
            "min_runs": min_runs,
        },
        "flaky_tests": [_stats_to_dict(s, False) for s in new]
        + [_stats_to_dict(s, True) for s in quar],
        "clusters": [
            {
                "signature": c.signature,
                "count": c.count,
                "sample_message": c.sample_message,
                "tests": [s.key for s in c.tests],
            }
            for c in clusters
        ],
        "all_tests": [_stats_to_dict(s) for s in stats],
    }
    return json.dumps(payload, indent=2)


def render_markdown(
    stats: Sequence[FlakeStats],
    min_runs: int,
    quarantine: Sequence[str] = (),
    commits: Optional[int] = None,
) -> str:
    new, quar = _split(stats, min_runs, quarantine)
    clusters = _clusters(new, quar)
    lines = ["## flakeguard report", ""]
    if commits:
        lines.extend([f"_Scored within {commits} commit(s)._", ""])

    if not new:
        lines.append("No new flaky tests found." if quar else "No flaky tests found.")
        if quar:
            lines.extend(["", f"_{len(quar)} known flake(s) quarantined._"])
        return "\n".join(lines)

    lines.append(f"**{len(new)}** new flaky test(s) found across {len(stats)} analysed.")
    lines.append("")
    lines.append("| score | runs | pass | fail | test |")
    lines.append("|------:|-----:|-----:|-----:|:-----|")
    for s in new:
        lines.append(
            f"| {s.score:.2f} | {s.considered} | {s.passed} | {s.failures} | `{s.display_name}` |"
        )

    if clusters:
        lines.extend(["", "### Failure clusters", ""])
        lines.append("| tests | signature |")
        lines.append("|------:|:----------|")
        for c in clusters:
            lines.append(f"| {c.count} | `{c.display}` |")

    if quar:
        lines.extend(["", f"_{len(quar)} known flake(s) quarantined._"])
    lines.append("")
    return "\n".join(lines)


RENDERERS = {
    "text": render_text,
    "json": render_json,
    "markdown": render_markdown,
    "md": render_markdown,
}
