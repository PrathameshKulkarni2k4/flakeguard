"""Tests for the runs manifest - declaring runs and commits instead of guessing."""

import json
import pathlib

import pytest

from flakeguard.cli import main
from flakeguard.manifest import load_manifest

PASS = (
    '<?xml version="1.0"?><testsuites><testsuite name="s">'
    '<testcase classname="c" name="t"/></testsuite></testsuites>'
)
FAIL = (
    '<?xml version="1.0"?><testsuites><testsuite name="s">'
    '<testcase classname="c" name="t"><failure message="boom"/></testcase>'
    "</testsuite></testsuites>"
)


def write_manifest(tmp_path, runs):
    mf = tmp_path / "manifest.json"
    mf.write_text(json.dumps({"runs": runs}))
    return str(mf)


def test_load_manifest_rejects_bad_shapes(tmp_path):
    p = tmp_path / "m.json"

    p.write_text("{}")
    with pytest.raises(ValueError):
        load_manifest(str(p))

    p.write_text('{"runs": []}')
    with pytest.raises(ValueError):
        load_manifest(str(p))

    p.write_text('{"runs": [{"label": "no reports"}]}')
    with pytest.raises(ValueError):
        load_manifest(str(p))

    p.write_text('{"runs": [{"reports": ["a.xml"]}]}')
    entry = load_manifest(str(p))[0]
    assert entry.reports == ["a.xml"]
    assert entry.commit is None


def test_manifest_declares_commits_so_a_regression_is_not_a_flake(tmp_path, capsys):
    (tmp_path / "a.xml").write_text(PASS)
    (tmp_path / "b.xml").write_text(FAIL)
    mf = write_manifest(tmp_path, [
        {"commit": "aaa111", "reports": [str(tmp_path / "a.xml")]},
        {"commit": "bbb222", "reports": [str(tmp_path / "b.xml")]},
    ])
    out = tmp_path / "o.json"

    rc = main(["scan", "--manifest", mf, "--format", "json", "-o", str(out)])
    capsys.readouterr()

    assert rc == 0
    data = json.loads(out.read_text())
    assert data["summary"]["commits"] == 2
    assert data["summary"]["new_flaky"] == 0  # passed on one commit, failed on another


def test_manifest_detects_a_flake_within_one_commit(tmp_path, capsys):
    files = []
    for i in range(4):
        f = tmp_path / f"r{i}.xml"
        f.write_text(PASS if i % 2 == 0 else FAIL)
        files.append(str(f))
    mf = write_manifest(tmp_path, [{"commit": "same", "reports": [f]} for f in files])
    out = tmp_path / "o.json"

    rc = main(["scan", "--manifest", mf, "--format", "json", "-o", str(out)])
    capsys.readouterr()

    assert rc == 0
    data = json.loads(out.read_text())
    assert data["summary"]["commits"] == 1
    assert data["summary"]["new_flaky"] == 1
    assert data["flaky_tests"][0]["name"] == "t"


def test_manifest_merges_reports_into_one_run(tmp_path, capsys):
    reports = tmp_path / "reports"
    reports.mkdir()
    for i in range(3):
        (reports / f"c{i}.xml").write_text(PASS)
    mf = write_manifest(tmp_path, [{"commit": "x", "reports": [str(reports)]}])
    out = tmp_path / "o.json"

    rc = main(["scan", "--manifest", mf, "--format", "json", "-o", str(out)])
    capsys.readouterr()

    assert rc == 0
    data = json.loads(out.read_text())
    assert data["summary"]["tests_analysed"] == 1  # three files, one run, one test
    assert data["summary"]["commits"] == 1


def test_manifest_and_paths_are_mutually_exclusive(tmp_path, capsys):
    mf = write_manifest(tmp_path, [{"reports": ["a.xml"]}])
    rc = main(["scan", str(tmp_path), "--manifest", mf])
    err = capsys.readouterr().err
    assert rc == 2
    assert "not both" in err
