# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Entries before 0.1.4 were reconstructed from the git tags and the GitHub releases.

## [Unreleased]

## [0.1.4] - 2026-07-30

Two things stop going stale on their own: the prices in the catalog, and the
example in the README.

### Added

- Warn when the catalog's prices have aged past a threshold. The warning names how
  many entries are stale and the age of the oldest, rather than just asserting that
  the catalog is old ([#6], [#9]).
- `catalog_freshness.max_age_days` in `data/rating-rules.yaml`, defaulting to 90
  days. Tuning it is a data edit, no Python. A missing, malformed or non-positive
  value falls back to the default rather than stopping a recommendation ([#6], [#9]).
- `examples/task-manager/`, a small CRUD spec checked into the repo, so the README
  example can be run by the reader instead of taken on faith ([#7], [#10]).
- `scripts/render_example.py`, which regenerates the README's worked example from
  the live catalog, plus a contract test that fails when the two drift apart
  ([#7], [#10]).
- A Roadmap section and a link to the walkthrough video in the README.

### Changed

- The README's front-page sample is now generated from `data/models.yaml` instead of
  being hand-written. It runs against `examples/task-manager`, shows an `overkill`
  row, and quotes a cost gap computed from the catalog ([#7], [#10]).
- `CONTRIBUTING.md` tells catalog contributors to regenerate that block, and
  documents the new freshness knob.
- The shipped catalog is now held to its own freshness bar by a contract test, so a
  neglected catalog fails CI instead of shipping a confidently outdated
  recommendation ([#6], [#9]).

### Fixed

- Warnings are printed whatever the project's data state. They were gated on
  `scarce`, which silently swallowed catalog warnings on healthy projects — exactly
  the runs where the price data is actually used. The pre-existing
  "no `pricing_date`" warning had never been visible on a `sufficient` project
  either ([#9]).

### Compatibility

No breaking changes; upgrading needs no action. The `--json` contract is unchanged,
including `price_stale`, which still means "this entry carries no date" and **not**
"this price is old" — the two are reported separately and deliberately.

One behavioural change worth knowing if you scrape the terminal output rather than
using `--json`: warnings now appear on `sufficient` projects, where previously
nothing was printed above the table.

## [0.1.3] - 2026-07-28

Catalog-only release: no code, CLI or schema changes.

### Added

- Claude Fable 5 and Claude Opus 5; Gemini 3.6 Flash and Gemini 3.5 Flash-Lite;
  GPT-5.4 mini; Kimi K3 (new `Kimi` family in the report filters); DeepSeek V4 Pro.

### Changed

- GPT-4.1 nano replaced by GPT-5.4 nano as the budget floor. Prices verified against
  provider sources; only entries actually re-checked carry a bumped `pricing_date`.

### Removed

- Claude Opus 4.8, Gemini 3.5 Flash and DeepSeek V3, each superseded by a newer
  entry at the same or a better rate.

## [0.1.2] - 2026-07-21

### Added

- Filter the HTML report by model family, with a count per family.
- An "open source only" toggle for models with downloadable, self-hostable weights.
- A running "showing X of Y models" count.

Both facts live in `data/models.yaml`, so correcting a misfiled model is a one-line
PR. The report remains a single self-contained HTML file that loads nothing from the
network.

## [0.1.1] - 2026-07-20

First public release. Reads Spec-Driven Development artifacts, estimates how
demanding the work is with a judge running locally through Ollama, and ranks a
community-maintained catalog by how well each model **fits** the job.

### Added

- Gold/silver/bronze podium in the terminal plus a self-contained HTML report.
- Fit-based recommendation: price is shown for every model but never overrides fit.
- Models, prices and rating rules in editable YAML, so contributing needs no Python.
- Explicit degradation with distinct exit codes when project data is insufficient,
  the judge is unavailable, or the catalog is empty.

[Unreleased]: https://github.com/JoaquinRuiz/SpecJudge/compare/v0.1.4...HEAD
[0.1.4]: https://github.com/JoaquinRuiz/SpecJudge/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/JoaquinRuiz/SpecJudge/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/JoaquinRuiz/SpecJudge/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/JoaquinRuiz/SpecJudge/releases/tag/v0.1.1
[#6]: https://github.com/JoaquinRuiz/SpecJudge/issues/6
[#7]: https://github.com/JoaquinRuiz/SpecJudge/issues/7
[#9]: https://github.com/JoaquinRuiz/SpecJudge/pull/9
[#10]: https://github.com/JoaquinRuiz/SpecJudge/pull/10
