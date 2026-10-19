# Changelog

All notable changes to this project are documented here. The format is based
on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
aims to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.8.0] - 2026-10-19

### Added

- **Runs manifest** (`--manifest FILE`): declare each run and its commit
  instead of having them inferred from files and environment variables. This
  is the root-cause fix for two earlier bugs - one report file per test class
  (Surefire) and an environment commit applied to reports from many builds.
  Each manifest entry is one run, and the reports it lists are merged into it.

## [0.7.0] - 2026-10-19

### Fixed

- **Score diluted by single-run commits.** A commit that ran a test once can
  never show a flip, so it only inflated the denominator: a real flake with
  one informative commit among 30 scored 0.06 instead of 0.67, and a test
  failing ~20% of the time with one run per commit scored 0.0 and was never
  flagged. Only commits with two or more decided runs now count.
- Quarantine patterns for parametrised tests (`test_x[1-2]`) never matched -
  `fnmatch` read the brackets as a character class. Keys are now escaped.
- `--update-quarantine` overwrote the whole file, deleting hand-written globs
  and comments. It now merges and preserves what is already there.
- Surefire `<flakyFailure>` / `<rerunFailure>` were parsed as passes, throwing
  away the strongest flake signal there is. They are now `FLAKY`, and count as
  decisive evidence on their own.
- An auto-detected `GITHUB_SHA` applied to several report files could label
  runs from different builds as one commit, hiding regressions. It now warns.
- Duplicate keys within a run kept the first outcome, hiding a failing second
  variant; the most severe outcome now wins.
- `action.yml` expanded `$QFLAG` unquoted, breaking paths containing spaces.

### Added

- Tests that changed across commits but were never run twice on one commit
  are reported as **unconfirmed** rather than silently scoring 0.
- `--single-run` merges many report files into one run (Maven and Gradle
  Surefire write one XML per test class).

### Changed

- JSON `schema_version` is now 4; each test carries `flaky_retries`.

## [0.6.0] - 2026-10-19

### Changed

- **Flakiness is now scored within a commit.** Previously every run was
  pooled, so a test that passed for 20 builds and then failed for 20 after a
  real change scored 1.0 and was reported as "maximally flaky" - a
  regression mistaken for a flake, which is exactly the problem the tool
  exists to prevent. The score is now
  `2 * Σ(per-commit flips) / Σ(per-commit decided runs)`, which reduces to
  the old formula when only one commit is involved.

### Added

- `--commit SHA` (and automatic detection from `GITHUB_SHA`,
  `CI_COMMIT_SHA`, `GIT_COMMIT`, `CIRCLE_SHA1`, ...). History records the
  commit per run. Reports state whether scoring was commit-aware, and warn
  on stderr when runs are pooled. JSON `schema_version` is now 3.

## [0.5.0] - 2026-10-19

### Added

- Jest-style JSON report parser (`.json`, `jest --json`). Test keys are made
  relative to the suite directory so they stay stable across machines.
- Failure-signature clustering: flaky tests that fail the same way are
  grouped, so many flakes collapse into a few root causes. Shown in the
  text and Markdown reports and as `clusters` in JSON.

## [0.4.0] - 2026-10-19

### Added

- Persistent history: `--history FILE` accumulates results across runs in a
  single SQLite file, so you run flakeguard once per build and it learns over
  time. Adds a `flakeguard history` command to inspect or clear it, and
  `--history-keep N` to bound how many runs are stored.

## [0.3.0] - 2026-10-19

### Added

- Quarantine: a plain-text file of known-flaky tests (glob patterns).
  `--quarantine FILE` sets them aside so only NEW flakes are reported;
  `--update-quarantine` records the current flakes; `--fail-on-flaky` now
  fails only on non-quarantined flakes. The GitHub Action gained a
  `quarantine` input.

### Fixed

- `flakeguard --version` now reports the real installed version, read from
  the package metadata, instead of a hard-coded value that could drift.

## [0.2.0] - 2026-10-18

### Added

- TAP report parser (Node's test runner, `tap`/`tape`, Perl Test::More).

### Fixed

- Test identity when a framework repeats the name in both `classname` and
  `name` (e.g. jest-junit), which could otherwise merge distinct tests.
- Clearer CLI errors when report files are missing or not valid JUnit XML.

### Changed

- Hardened the parser against real reports from pytest and jest-junit, with
  regression fixtures captured from those tools.

## [0.1.0] - 2026-10-18

### Added

- JUnit XML parser, so one tool serves every language.
- Explainable flakiness scoring:
  `2 * min(passes, failures) / (passes + failures)`.
- CLI: `flakeguard scan` with `text`, `json`, and `markdown` output.
- `--min-runs`, `--min-score`, `--output`, and `--fail-on-flaky` options.
- GitHub Action: analyses reports, comments on pull requests, and enforces a
  flakiness budget.
- Test suite, MIT license, and CI workflow.

[Unreleased]: https://github.com/PrathameshKulkarni2k4/flakeguard/compare/v0.8.0...HEAD
[0.8.0]: https://github.com/PrathameshKulkarni2k4/flakeguard/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/PrathameshKulkarni2k4/flakeguard/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/PrathameshKulkarni2k4/flakeguard/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/PrathameshKulkarni2k4/flakeguard/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/PrathameshKulkarni2k4/flakeguard/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/PrathameshKulkarni2k4/flakeguard/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/PrathameshKulkarni2k4/flakeguard/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/PrathameshKulkarni2k4/flakeguard/releases/tag/v0.1.0
