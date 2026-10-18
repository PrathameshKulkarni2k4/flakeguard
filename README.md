# flakewatch

**Find, rank, and quarantine flaky tests — in any language.**

Flaky tests are a tax on every team that writes tests. A test that passes
nine times and fails the tenth erodes trust in your whole suite, wastes CI
minutes, and trains people to hit "re-run" instead of investigating.

`flakewatch` reads the test reports your CI *already produces* and tells
you which tests are flaky, how flaky they are, and why it thinks so.

## Why it's language-agnostic

It works from **JUnit XML**, the interchange format almost every framework
can emit:

| Language / framework | How to produce the report |
|---|---|
| Python (pytest) | `pytest --junitxml=report.xml` |
| Java (Maven / Gradle) | Surefire writes JUnit XML automatically |
| Go | `gotestsum --junitfile report.xml` |
| JavaScript (Jest) | `jest-junit` reporter |
| Ruby (RSpec) | `rspec_junit_formatter` |
| .NET, PHPUnit, … | built-in or plugin JUnit output |

One tool, every language.

## Install

```bash
pip install flakewatch
```

## Use

Collect a few runs of reports, then point flakewatch at them:

```bash
flakewatch scan ./ci-artifacts
flakewatch scan run1.xml run2.xml run3.xml
flakewatch scan ./reports --min-runs 5 --format json -o flaky.json
```

Example output:

```
flakewatch report
============================================================
tests analysed : 3
flaky (>= 2 runs): 1

 score  bar         runs  pass  fail  test
------------------------------------------------------------
  0.67  #######...     3     2     1  tests.test_checkout::test_applies_coupon

latest failure in tests.test_checkout::test_applies_coupon:
  AssertionError: coupon discount not applied
```

## How the score works

For each test we count passes vs. non-passes across all runs (skips are
ignored). The flakiness score is:

```
score = 2 * min(passes, failures) / (passes + failures)
```

- always passes, or always fails → **0.0** (consistent, *not* flaky)
- flips on every run (50/50) → **1.0** (maximally flaky)

It's deliberately explainable — no black box. You can read the number and
know exactly how it was derived.

## Use in GitHub Actions

Flakewatch ships as a composite Action. It analyses your reports, posts the
result as a pull-request comment, and can fail the check when flakiness
exceeds a budget you set.

```yaml
- name: Flakewatch
  uses: PrathameshKulkarni2k4/flakewatch@main
  with:
    reports: reports      # dir/glob of JUnit XML files
    min-runs: 3           # ignore tests seen in fewer runs
    max-flaky: 0          # fail if any flaky test is found (-1 = never fail)
    comment: "true"       # post the report as a PR comment
```

See [`.github/workflows/example.yml`](.github/workflows/example.yml) for a
complete workflow that runs a suite five times and feeds the reports in.

To gate locally or in any other CI, use the exit code:

```bash
flakewatch scan ./reports --fail-on-flaky   # exits 1 if anything is flaky
```

## Roadmap

- [x] JUnit XML parsing, flakiness scoring, text/JSON/Markdown reports
- [x] GitHub Action with PR comments and a flakiness budget
- [ ] TAP and native JSON report formats
- [ ] SQLite history so it learns across builds
- [ ] Quarantine file so known flakes are set aside, not deleted
- [ ] Failure-signature clustering (group the *same* flake)

## Development

```bash
git clone https://github.com/PrathameshKulkarni2k4/flakewatch
cd flakewatch
pip install -e ".[dev]"
pytest
```

## License

MIT
