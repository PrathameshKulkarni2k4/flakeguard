"""A runs manifest: declare runs and commits instead of inferring them.

By default flakeguard guesses. It treats every report file as one run, and
takes the commit from an environment variable applied to all of them. Those
guesses are wrong often enough to matter: Maven and Gradle write one XML per
test class, and a folder of historical reports spans many builds.

A manifest states the structure plainly:

    {
      "runs": [
        {"commit": "abc123", "label": "build 42", "reports": ["ci/42"]},
        {"commit": "def456", "label": "build 43", "reports": ["ci/43/*.xml"]}
      ]
    }

**Each entry is one run**, and the reports it lists are merged into it - so
one build that writes fifty class files is a single run, not fifty. Give
each entry a commit and flakiness is judged within it, exactly as it should
be.
"""

from __future__ import annotations

import json
from typing import List, NamedTuple, Optional


class ManifestRun(NamedTuple):
    commit: Optional[str]
    label: Optional[str]
    reports: List[str]


def load_manifest(path: str) -> List[ManifestRun]:
    """Read and validate a runs manifest."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        raise ValueError(f"not valid JSON ({exc})") from exc

    if not isinstance(data, dict) or not isinstance(data.get("runs"), list):
        raise ValueError("a manifest needs a top-level 'runs' list")

    runs: List[ManifestRun] = []
    for index, entry in enumerate(data["runs"], start=1):
        if not isinstance(entry, dict):
            raise ValueError(f"run {index}: expected an object")
        reports = entry.get("reports")
        if not isinstance(reports, list) or not reports:
            raise ValueError(f"run {index}: needs a non-empty 'reports' list")
        commit = entry.get("commit")
        label = entry.get("label")
        runs.append(
            ManifestRun(
                commit=str(commit) if commit is not None else None,
                label=str(label) if label is not None else None,
                reports=[str(r) for r in reports],
            )
        )

    if not runs:
        raise ValueError("the manifest lists no runs")
    return runs
