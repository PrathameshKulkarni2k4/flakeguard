"""Tests for failure-signature clustering."""

from flakeguard.clustering import cluster, signature
from flakeguard.scoring import FlakeStats


def stat(key, message, score=0.5):
    return FlakeStats(
        key=key, name=key, suite="s", classname="c",
        passed=1, failed=1, score=score, last_message=message,
    )


def test_signature_strips_numbers():
    assert signature("AssertionError: expected 100 but got 99") == (
        "AssertionError: expected <n> but got <n>"
    )


def test_signature_strips_hex_and_paths():
    sig = signature("crashed at /home/runner/app/src/x.py with 0xdeadbeefcafe")
    assert "/home" not in sig
    assert "deadbeefcafe" not in sig
    assert "<path>" in sig and "<hex>" in sig


def test_signature_of_empty_is_empty():
    assert signature("") == ""


def test_cluster_groups_similar_failures():
    stats = [
        stat("a", "AssertionError: expected 1 but got 2"),
        stat("b", "AssertionError: expected 3 but got 4"),
        stat("c", "Connection refused"),
    ]
    clusters = cluster(stats)
    assert len(clusters) == 2
    assert clusters[0].count == 2  # biggest group first
    assert clusters[0].signature == "AssertionError: expected <n> but got <n>"
    assert clusters[1].signature == "Connection refused"


def test_cluster_orders_by_size_then_score():
    stats = [
        stat("a", "boom", score=0.2),
        stat("b", "boom", score=0.9),
        stat("c", "other", score=0.1),
    ]
    clusters = cluster(stats)
    assert clusters[0].count == 2
    assert clusters[0].display == "boom"


def test_cluster_display_when_no_message():
    clusters = cluster([stat("a", None), stat("b", None)])
    assert clusters[0].count == 2
    assert clusters[0].display == "(no failure message)"
