"""Render analysis results as text, JSON, or Markdown."""

from __future__ import annotations

import json
from typing import List, Optional, Sequence, Tuple

from .clustering import Cluster, cluster
from .quarantine import is_quarantined
from .scoring import FlakeStats

_MAX_CLUSTERS = 10
_MAX_NAMES = 4
_MAX_UNCONFIRMED = 10


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


def _unconfirmed(stats: Sequence[FlakeStats], min_runs: int) -> List[FlakeStats]:
    """Tests that changed across commits but were never run twice on one.

    We can see they behaved differently, but a flake and a regression look
    identical, so we report them separately instead of guessing.
    """
    return [
        s for s in stats
        if s.is_unconfirmed() and s.considered >= min_runs
    ]


def render_text(
    stats: Sequence[FlakeStats],
    min_runs: int,
    quarantine: Sequence[str] = (),
    commits: Optional[int] = None,
) -> str:
    """A human-readable terminal report."""
    new, quar = _split(stats, min_runs, quarantine)
    clusters = _clusters(new, quar)
    unconfirmed = _unconfirmed(stats, min_runs)

    lines: List[str] = [""]
    lines.append("flakeguard report")
    lines.append("=" * 60)
    lines.append(f"tests analysed : {len(stats)}")
    lines.append(f"new flaky      : {len(new)}")
    if quarantine:
        lines.append(f"quarantined    : {len(quar)}")
    if unconfirmed:
        lines.append(f"unconfirmed    : {len(unconfirmed)}")
    if commits:
        lines.append(f"scored within  : {commits} commit(s)")
    else:
        lines.append("scored within  : all runs pooled (no commit info)")
    lines.append("")

    if not new and not unconfirmed:
        if quar:
            lines.append(f"No new flaky tests. {len(quar)} known flake(s) quarantined.")
        else:
            lines.append("No flaky tests found. Your suite is behaving.")
        lines.append("")
        return "\n".join(lines)

    if new:
        lines.append(
            f"{'score':>6}  {'rate':>5}  {'bar':<10}  {'runs':>4}  "
            f"{'pass':>4}  {'fail':>4}  test"
        )
        lines.append("-" * 74)
        for s in new:
            lines.append(
                f"{s.score:>6.2f}  {s.rate * 100:>4.0f}%  {_bar(s.score):<10}  "
                f"{s.considered:>4}  {s.passed:>4}  {s.failures:>4}  {s.display_name}"
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

    if unconfirmed:
        lines.append("")
        lines.append(
            f"{len(unconfirmed)} test(s) behaved differently across commits, but no "
            "commit ran them"
        )
        lines.append("more than once - so flakeguard cannot tell a flake from a regression:")
        for s in unconfirmed[:_MAX_UNCONFIRMED]:
            lines.append(f"    {s.display_name}")
        if len(unconfirmed) > _MAX_UNCONFIRMED:
            lines.append(f"    ... and {len(unconfirmed) - _MAX_UNCONFIRMED} more")
        lines.append(
            "  -> run the suite more than once per commit (or enable retries) to confirm."
        )

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
        "flaky_retries": s.flaky_retries,
        "score": round(s.score, 4),
        "rate": round(s.rate, 4),
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
    unconfirmed = _unconfirmed(stats, min_runs)
    payload = {
        "schema_version": 5,
        "summary": {
            "tests_analysed": len(stats),
            "flaky": len(new) + len(quar),
            "new_flaky": len(new),
            "quarantined": len(quar),
            "unconfirmed": len(unconfirmed),
            "commits": commits,
            "min_runs": min_runs,
        },
        "flaky_tests": [_stats_to_dict(s, False) for s in new]
        + [_stats_to_dict(s, True) for s in quar],
        "unconfirmed_tests": [_stats_to_dict(s) for s in unconfirmed],
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
    unconfirmed = _unconfirmed(stats, min_runs)
    lines = ["## flakeguard report", ""]
    if commits:
        lines.extend([f"_Scored within {commits} commit(s)._"])
    if unconfirmed:
        lines.append(f"_{len(unconfirmed)} test(s) unconfirmed - see below._")
    if commits or unconfirmed:
        lines.append("")

    if not new:
        lines.append("No new flaky tests found." if quar else "No flaky tests found.")
        if quar:
            lines.extend(["", f"_{len(quar)} known flake(s) quarantined._"])
        if unconfirmed:
            lines.extend(["", "### Unconfirmed", ""])
            lines.append(
                "These changed across commits, but no commit ran them more than "
                "once, so a flake cannot be told from a regression:"
            )
            lines.append("")
            for s in unconfirmed[:_MAX_UNCONFIRMED]:
                lines.append(f"- `{s.display_name}`")
        return "\n".join(lines)

    lines.append(f"**{len(new)}** new flaky test(s) found across {len(stats)} analysed.")
    lines.append("")
    lines.append("| score | rate | runs | pass | fail | test |")
    lines.append("|------:|-----:|-----:|-----:|-----:|:-----|")
    for s in new:
        lines.append(
            f"| {s.score:.2f} | {s.rate * 100:.0f}% | {s.considered} | "
            f"{s.passed} | {s.failures} | `{s.display_name}` |"
        )

    if clusters:
        lines.extend(["", "### Failure clusters", ""])
        lines.append("| tests | signature |")
        lines.append("|------:|:----------|")
        for c in clusters:
            lines.append(f"| {c.count} | `{c.display}` |")

    if unconfirmed:
        lines.extend(["", "### Unconfirmed", ""])
        lines.append(
            "Changed across commits, but no commit ran them more than once - "
            "cannot tell a flake from a regression:"
        )
        lines.append("")
        for s in unconfirmed[:_MAX_UNCONFIRMED]:
            lines.append(f"- `{s.display_name}`")

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
