# Changelog

All notable changes to this project are documented here. The format is based
on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
aims to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/PrathameshKulkarni2k4/flakeguard/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/PrathameshKulkarni2k4/flakeguard/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/PrathameshKulkarni2k4/flakeguard/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/PrathameshKulkarni2k4/flakeguard/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/PrathameshKulkarni2k4/flakeguard/releases/tag/v0.1.0
