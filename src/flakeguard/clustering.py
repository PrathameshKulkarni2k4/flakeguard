"""Failure-signature clustering.

When a suite has hundreds of flaky tests, they are usually a handful of
root causes wearing different names - one flaky database, one slow network,
one shared fixture. Clustering groups flaky tests whose failure messages
look the same, so "200 flaky tests" becomes "5 causes".

The signature is deliberately simple and explainable: take the first line
of the error, replace the parts that vary run-to-run (numbers, hashes, file
paths), and use what's left as the fingerprint.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Sequence

from .scoring import FlakeStats

_HEX = re.compile(r"[0-9a-fA-F]{8,}")
_PATH = re.compile(r"(?:/[\w.\-]+){2,}")
_NUM = re.compile(r"\d+")
_WS = re.compile(r"\s+")


def signature(message: str) -> str:
    """A stable fingerprint of an error message, with variable parts removed."""
    if not message:
        return ""
    first_line = message.strip().splitlines()[0] if message.strip() else ""
    text = _HEX.sub("<hex>", first_line)
    text = _PATH.sub("<path>", text)
    text = _NUM.sub("<n>", text)
    return _WS.sub(" ", text).strip()[:160]


@dataclass
class Cluster:
    """A group of flaky tests that appear to share a root cause."""

    signature: str
    sample_message: str = ""
    tests: List[FlakeStats] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.tests)

    @property
    def display(self) -> str:
        return self.signature or "(no failure message)"


def cluster(stats: Sequence[FlakeStats], min_size: int = 1) -> List[Cluster]:
    """Group flaky tests by failure signature, biggest group first."""
    groups: Dict[str, Cluster] = {}
    for stat in stats:
        sig = signature(stat.last_message or "")
        group = groups.get(sig)
        if group is None:
            group = Cluster(signature=sig, sample_message=stat.last_message or "")
            groups[sig] = group
        group.tests.append(stat)

    clusters = [c for c in groups.values() if c.count >= min_size]
    clusters.sort(key=lambda c: (c.count, sum(t.score for t in c.tests)), reverse=True)
    return clusters
