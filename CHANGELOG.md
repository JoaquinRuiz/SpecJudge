# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Entries before 0.1.4 were reconstructed from the git tags and the GitHub releases.

## [Unreleased]

## [0.2.0] - 2026-08-03

The judge now has to show its work. Every dimension it rates must cite the fragment of
your spec that supports it, and the citation is checked against the text it was actually
given — so a fluent explanation is no longer enough to pass for an assessment.

**This release has breaking changes. See [Migration](#migration-from-014) below.**

### Added

- The judge must cite a project fragment per dimension, and code verifies the fragment
  exists in the text it was given. A citation naming something absent invalidates the
  whole assessment rather than that one field ([#1], [#12]).
- `unsupported` as a peer value in the judge's answer vocabulary: a dimension it cannot
  ground is answered, not guessed. Ungrounded dimensions leave the fit calculation
  instead of quietly counting as low demand ([#1], [#12]).
- `demand` in `--json`, carrying the assessment, its evidence and a coverage summary. The
  profile was previously computed and discarded ([#1], [#12]).
- Evidence coverage in the terminal output, so the grounding is visible without `--json`
  ([#1], [#12]).
- `evidence.require_spans` in `data/rating-rules.yaml` — set it to `false` to rate without
  citations if your judge cannot manage the schema ([#1], [#12]).
- A judge evaluation corpus of twelve projects with expected profiles, covering
  well-specified, thin, task-less and adversarial specs ([#5], [#13]).
- A deterministic regression suite running in CI as its own `Judge regression` job:
  classification, frozen rankings and prompt invariants ([#5], [#13]).
- `scripts/eval_judge.py`, which runs the corpus against a real local judge and reports
  accuracy and abstention quality separately ([#5], [#13]).

### Changed

- **Ollama 0.5.0 or newer is required** for the default cited-assessment mode. The judge
  request now carries a JSON schema, which older versions reject ([#14], [#15]).
- Judge sampling is pinned (`temperature: 0`, fixed seed), so the same project and judge
  produce the same assessment twice. Two runs could previously recommend different models
  ([#5], [#13]).
- A project whose judge could not ground every dimension is reported as `scarce` rather
  than `sufficient`, with a warning naming the dimensions ([#1], [#12]).
- Fragment ids are offered to the judge without surrounding brackets, and citations are
  normalised before lookup ([#14], [#15]).
- The project constitution is amended to 3.1.0: changes to the judge prompt or the rating
  rules must be evaluated against the corpus ([#5], [#13]).

### Fixed

- Citations were impossible for 8B judges, the most common local setup. `format: "json"`
  guarantees valid JSON but not the requested shape, so the model returned the right
  ratings with `[true]` where a fragment id belonged, and every run was rejected with no
  recommendation. Measured on the corpus: `llama3.1` went from 0 of 9 usable cases to 9 of
  9, `devstral-small-2` from 5 of 9 to 9 of 9 ([#14], [#15]).
- An Ollama too old for structured outputs now produces an error naming the version
  requirement and both ways out, instead of a bare HTTP failure ([#14], [#15]).

### Migration from 0.1.4

**Upgrade Ollama to 0.5.0 or newer.** This is the one change that turns a working setup
into a failing one: the judge request now carries a JSON schema, and older versions reject
it. You will get exit code 3 with an error naming the requirement. If you cannot upgrade,
set `require_spans: false` (below).

**Expect some judges to be refused.** A judge that cannot cite evidence now fails loudly
rather than returning an unverified assessment:

| What the judge does | Result |
|---|---|
| Cites a fragment that does not exist | Exit 3, naming the dimension and the invented id |
| Answers `unsupported` for every dimension | Exit 2, no recommendation |
| Grounds some dimensions but not all | Exit 0, warning, `data_state` becomes `scarce` |

If your judge cannot manage this, add to `data/rating-rules.yaml`:

```yaml
evidence:
  require_spans: false
```

That restores 0.1.4 behaviour and loses the grounding check with it.

**If you script against `--json`:** the schema gains a `demand` key — additive, nothing
was removed. But `data_state` can now be `scarce` on a project that reported `sufficient`
in 0.1.4, when the judge grounds only part of its assessment. `price_stale` is unchanged
and still means "this entry carries no date", not "this price is old".

**If you compare runs:** results are now deterministic for a given project, judge and
catalog. A recommendation that used to vary between runs will settle on one answer — which
may not be the one you saw last time.

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

[Unreleased]: https://github.com/JoaquinRuiz/SpecJudge/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/JoaquinRuiz/SpecJudge/compare/v0.1.4...v0.2.0
[0.1.4]: https://github.com/JoaquinRuiz/SpecJudge/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/JoaquinRuiz/SpecJudge/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/JoaquinRuiz/SpecJudge/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/JoaquinRuiz/SpecJudge/releases/tag/v0.1.1
[#6]: https://github.com/JoaquinRuiz/SpecJudge/issues/6
[#7]: https://github.com/JoaquinRuiz/SpecJudge/issues/7
[#9]: https://github.com/JoaquinRuiz/SpecJudge/pull/9
[#10]: https://github.com/JoaquinRuiz/SpecJudge/pull/10
[#1]: https://github.com/JoaquinRuiz/SpecJudge/issues/1
[#5]: https://github.com/JoaquinRuiz/SpecJudge/issues/5
[#12]: https://github.com/JoaquinRuiz/SpecJudge/pull/12
[#13]: https://github.com/JoaquinRuiz/SpecJudge/pull/13
[#14]: https://github.com/JoaquinRuiz/SpecJudge/issues/14
[#15]: https://github.com/JoaquinRuiz/SpecJudge/pull/15
