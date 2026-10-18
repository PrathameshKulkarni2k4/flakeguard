# Changelog

All notable changes to this project are documented here. The format is based
on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
aims to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-10-18

### Added

- JUnit XML parser, so one tool serves every language.
- Explainable flakiness scoring:
  `2 * min(passes, failures) / (passes + failures)`.
- CLI: `flakewatch scan` with `text`, `json`, and `markdown` output.
- `--min-runs`, `--min-score`, `--output`, and `--fail-on-flaky` options.
- GitHub Action: analyses reports, comments on pull requests, and enforces a
  flakiness budget.
- Test suite, MIT license, and CI workflow.

[Unreleased]: https://github.com/PrathameshKulkarni2k4/flakewatch/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/PrathameshKulkarni2k4/flakewatch/releases/tag/v0.1.0
