# Contributing to flakeguard

Thanks for wanting to help — genuinely. This project exists for the
developer community, and it only gets better with more hands on it.

## The quickest way to help

If you are new to open source, the best first contribution is **adding
support for a new test-report format**. The parsers are deliberately small
and self-contained, and there is a clear pattern to follow (see below).

Look for issues labelled **`good first issue`**.

## Setting up a development environment

```bash
git clone https://github.com/PrathameshKulkarni2k4/flakeguard
cd flakeguard
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest -q
```

You should see all tests pass. If they don't, that's a bug — please open an
issue.

## Running the tool on the examples

```bash
flakeguard scan examples/reports
flakeguard scan examples/reports --format json
flakeguard scan examples/reports --fail-on-flaky
```

## Adding a new report format

1. Create `src/flakeguard/parsers/<format>.py` with a function that takes a
   file path and returns a list of `flakeguard.models.TestCase`.
2. Register it in `src/flakeguard/parsers/__init__.py` under `by_suffix`.
3. Add a fixture file under `examples/reports/` and a test under `tests/`.

That's the whole job. A good parser is small and boring, which is exactly
what we want.

## Guidelines

- **Keep the score explainable.** Never replace the flakiness formula with a
  black box. Trust is the product.
- **Never be confidently wrong.** If a parser is unsure, it should error
  clearly rather than guess.
- **Small pull requests.** One change per PR is easier to review and merge.
- **Add a test** for anything you change. Tests are how we keep the promise
  that the tool is trustworthy.
- **Match the existing style.** No configs to fight — just read the file you
  are editing.

## Commit messages

A short imperative summary is enough:

```
Add TAP report parser
Fix crash on reports with no <testsuite>
```

## Reporting bugs

Please include:

- what you ran (the exact command),
- what happened,
- what you expected,
- a snippet of the report file if you can share it (redact anything
  sensitive).

## Code of Conduct

By taking part, you agree to follow our
[Code of Conduct](CODE_OF_CONDUCT.md). Be kind — we were all beginners once.
