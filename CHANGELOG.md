# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Entries before 0.1.4 were reconstructed from the git tags and the GitHub releases.

## [Unreleased]

## [0.5.1] - 2026-08-12

**Integration with [spec-kit](https://github.com/github/spec-kit).** SpecJudge now runs
itself at the moment the decision is actually made: right after `/speckit.tasks`, when the
spec, the plan and the task list exist and no tokens have been spent.

### Added

- **[`extensions/spec-kit/`](extensions/spec-kit)** — one command and one hook, so the
  recommendation arrives at the moment it is worth having: right after `/speckit.tasks`,
  when the spec, the plan and the task list exist and no tokens have been spent
  ([#27], [#28]).

  ```bash
  specify extension add --from https://github.com/JoaquinRuiz/SpecJudge/releases/latest/download/spec-kit-specjudge.zip
  ```

  It asks before running, because the judge is a local model. It writes nothing
  (`effect: read-only`). And it never blocks: no judge, no Ollama, or a project too thin
  to judge, and it says so in one line and gets out of the way — a recommendation nobody
  asked for should not be the reason an implementation did not start.

  No product code was needed. The integration surface is the versioned `--json` payload
  and the distinguishable exit codes, both contract since 0.3.0.

- The release workflow builds and attaches `spec-kit-specjudge.zip`, refusing to upload an
  archive whose `extension.yml` is not at the root — the packaging mistake that would fail
  in a user's project rather than in ours ([#27], [#28]).

### Compatibility

Nothing to do. `extensions/` is not part of the wheel, so the installed package is
identical to 0.5.0 apart from its metadata. The extension carries its own version (0.1.0),
independent of SpecJudge's: it is a manifest and a prompt, and changes far less often than
the tool it wraps.

## [0.5.0] - 2026-08-10

One project rarely has one complexity. This release stops pretending it does: the demand
comes back as an envelope — what the bulk of the work needs, what the hardest part needs,
and which fragment of your project is responsible for each — and you say whether you will
implement it with one model or switch model per task.

### Added

- **The budget envelope** ([#3], [#25]). Every rated dimension now comes with the fragment
  that demands it and whether that fragment states a requirement or describes a habit:

  ```
  Budget envelope (escalating: ranked on the bulk of the work)
     default: reasoning medium, size low
     reasoning: top — S:FR-001 (requirement)
     size: low — T:T002 (customary)
     escalate for:
       • S:FR-001 — needs reasoning top
  ```

  Hard versus customary is derived from the cited text (RFC 2119 wording, or a numbered
  requirement id) rather than asked of the judge: a user can open a fragment and disagree
  with it, and cannot do that with an opinion.

- **`--execution-model single|escalating`** ([#3], [#25]). Whether one demanding task is
  decisive is not a property of the spec, it is a property of whoever implements it. With
  `single` — the default, and the previous behaviour — the podium is ranked on the hardest
  part, because one model has to clear it. With `escalating` it is ranked on the bulk and
  the outliers become explicit triggers, which is how you stop paying frontier prices for
  twenty mechanical edits.

- **`envelope` in the JSON payload, schema 1.2** ([#3], [#25]). Additive. Carries the
  demand the ranking used, the demand the hardest part needs, the constraint table behind
  both, and `execution_model` — which matters, because it changes what `best_choice` means.

- `Envelope`, `Constraint` and `ExecutionModel` on the public API, and an
  `execution_model` argument to `api.analyze` ([#3], [#25]).

- **[`docs/judges.md`](docs/judges.md)** — what makes a good judge for this task, measured
  results for three local models, and the command that reproduces any row ([#23], [#24]).
  Reported by [@rmarable]. An 8B judge lands 81–89% of demand levels inside the band the
  corpus expects; a 24B-class judge lands 100%.

- `--markdown-row` on `scripts/eval_judge.py`, so numbers contributed from other hardware
  are computed the same way rather than transcribed by hand ([#23], [#24]).

- `execution.*` in `data/rating-rules.yaml`: the default execution model, whether the
  judge is asked for the bulk at all, and the judge size above which it is asked.

### Changed

- The README quick start explains why it recommends an 8B judge instead of leaving the
  choice looking arbitrary ([#23], [#24]).

- **Catalog prices refreshed** against the providers' own pricing pages: GPT-5.6 Terra
  2.50/15.00 → 2.00/12.00, GPT-5.6 Luna 1.00/6.00 → 0.20/1.20, GLM-5.1 0.97/3.04 →
  1.40/4.40, and Claude Sonnet 5 3.00/15.00 → 2.00/10.00 — the last of which corrects an
  entry that contradicted its own note about introductory pricing. `pricing_date` moved
  only on the entries actually re-checked; the ones whose cost depends on which host serves
  them keep their earlier date, because that field means "verified on" and moving it
  without looking would be the exact rot it exists to prevent.

- **Only judges above 20B parameters are asked to separate the bulk from the peak**
  ([#3], [#25]). Measured, not assumed: the extra fields cost `qwen3:8b` five points of
  accuracy and doubled its refused answers, while `devstral-small-2` answered them
  correctly and lost nothing. A smaller judge still ranks and still cites; it reports one
  level for the project instead of a range, and an escalating run says so rather than
  leaving you to infer it from an empty trigger list. Same shape as the existing compact
  prompt threshold, and configurable next to it.

### Measured

`scripts/eval_judge.py` over the regression corpus, grown to 17 cases: `devstral-small-2`
30/30 dimensions in band with the bulk correct, `qwen3:8b` 25/28, `llama3.1:8b` (q4) 22/27.
No existing case regressed.

### Compatibility

**Nothing moves unless you ask.** Without `--execution-model`, the podium is ranked exactly
as in 0.4.0 — there is a test that fails if that changes. `envelope` is an additive payload
field, so a 1.1 consumer is unaffected, and the three new public types are additions to
`specjudge.api`, not changes to it.

If you automate spend, `envelope.execution_model` is the field to branch on: under
`escalating`, `best_choice` answers "what should implement most of this" rather than "what
can implement all of it".

## [0.4.0] - 2026-08-07

A spec is no longer the price of entry. SpecJudge reads whatever written context a
repository already has — `AGENTS.md`, `CLAUDE.md`, editor rules, architecture decision
records, and spec-kit's `plan.md` — so a project that never adopted Spec-Driven
Development gets an answer instead of exit code 2.

The reason this is safe to do is [#1], shipped in 0.2.0: every rated dimension must cite
a fragment that exists in the input, and a dimension that cannot be grounded drops out of
the calculation. The source stops mattering; only what is citable does. Without that,
mixing formats would have needed per-format trust rules — deciding in advance how much to
believe a `.cursorrules` file versus a spec — which is unmaintainable across formats that
each evolve separately.

### Added

- **Context files are read wherever they are** ([#16], [#21], [#22]):

  | Source | Where it looks |
  |---|---|
  | spec-kit artifacts | `constitution.md`, `spec.md`, `plan.md`, `tasks.md` |
  | agent-context files | `AGENTS.md`, `CLAUDE.md`, including nested ones in a monorepo |
  | editor rules | `.cursorrules`, `.github/copilot-instructions.md` |
  | decision records | `docs/adr/`, `docs/decisions/`, `adr/` |

  They are read *together*, never one instead of another: the artifacts describe the work
  about to be done, the rest describes how demanding the codebase is to work in at all.
  `plan.md` had been sitting beside the spec and the tasks all along, unread.

- **A repository with no spec now gets a floor**, not a refusal ([#16], [#21]). When
  nothing describes the work, the run is `scarce` and says out loud that the answer is a
  floor for the codebase rather than a recommendation for a piece of work, and the gap
  block asks for the one thing that would change that.

- **`sources_read` and `environment_only` in the JSON payload**, schema **1.1** ([#16],
  [#21]). Both additive, so a 1.0 consumer is unaffected. `sources_read` lists the kinds
  that contributed, deduplicated; `environment_only` is the flag worth branching on,
  because it marks the run that answers a different question than usual.

- **`sources.max_context_files`** in `data/rating-rules.yaml` ([#16], [#22]).

### Changed

- **Context sources share one prompt budget** instead of each getting its own cap
  ([#16], [#22]). Twelve caps of 8000 characters is a 96k-character prompt, which is not a
  cap. Sharing is by water-filling, so a 200-character `.cursorrules` costs 200 characters
  and the room it does not need goes to a long root `AGENTS.md`. Work artifacts keep their
  own cap. Truncation now lands on a line boundary rather than mid-clause.

- **The files read are named in the output** — `Read: 3× AGENTS.md, ADR` in the terminal
  and in the HTML report ([#16], [#21], [#22]). A thin answer should be traceable to a
  thin input rather than looking like a confident one.

- **Discovery is bounded and says so.** Dependency and build directories are pruned, depth
  is limited, at most 12 context files are read with reserved room for both agent-context
  files and ADRs — so a monorepo's 88 `AGENTS.md` cannot bury its decisions — and anything
  left out is reported rather than silently dropped ([#16], [#22]).

- **Context files that announce a tool generated them are skipped**, with a warning
  ([#16], [#22]). Generated context largely restates what the code already shows, and it
  would take its share of the budget from the hand-written file next to it. Detection is
  limited to an explicit marker; guessing from similarity to the README would infer intent
  from style, and the cost of a false positive is discarding a repository's only context.

- `docs/` is **not** read wholesale — only decision records, by convention. A user guide is
  length with little bearing on how demanding the work is, and every low-signal character
  is one the judge can cite instead of something that matters ([#16], [#22]).

### Fixed

- **Fragment prefixes were assigned per source kind**, so several files of one kind would
  have shared a prefix ([#16], [#22]). Latent while a project had one file of each; with
  nested discovery it would have made one file's citable fragments disappear into
  another's, and the judge is then either rejected for citing a fragment it was shown or
  validated against text it never saw. Prefixes are now per file, and uniqueness is
  enforced rather than assumed.

### Measured

`scripts/eval_judge.py --judge devstral-small-2` over the corpus, grown from 12 cases to
16: **28/28 dimensions in band**, 0 steps of ordinal distance, over-abstention 1. No
existing case regressed.

One regression was caught by that harness during development and fixed before merge:
labelling every source with its path moved `thin-no-constitution` from correct to
over-abstaining, on a project whose input had not changed at all. Prompt text is an input.
Labels now disambiguate only when a kind has more than one file.

Over-confidence rose from 1 to 4: the three environment-only cases answer `size` rather
than abstaining when nothing in the input describes an amount of work. That is a real
prompt-calibration gap, left visible in the corpus rather than labelled away.

### Compatibility

No action needed to keep current behaviour: a project with `.specify/` artifacts is read
exactly as before, and the two new payload fields are additive.

Worth knowing if you run SpecJudge on a large repository: it now reads context files
outside `.specify/`, so a run in a monorepo may pick up per-package `AGENTS.md` files it
previously ignored. Set `sources.max_context_files` in `data/rating-rules.yaml` to bound
that.

## [0.3.1] - 2026-08-07

A correctness fix that had been quietly degrading every cited assessment since 0.2.0, and a
warning that finally says something you can act on.

Nothing covered by semantic versioning changed: no `specjudge.api` symbol, no JSON schema
field, no exit code. What changed is terminal and HTML output, the judge prompt, and fragment
extraction — all of which [`docs/api.md`](docs/api.md) lists as explicitly outside the
contract.

### Fixed

- **Cited evidence was half a sentence.** Fragment extraction matched bullets with a
  line-anchored pattern, so any requirement wrapped across lines lost everything after the
  wrap — 140 of 160 fragments in the evaluation corpus were affected. The judge has been
  reading truncated requirements, and quoting them back, since #1 shipped in 0.2.0. Bullets
  now absorb their continuation lines ([#19], [#20]).

### Added

- A thin project now says **what** is missing rather than only that something is, and says it
  after the table instead of above it. One line of caveat above a ranked podium loses to the
  podium; the actionable block is now the last thing on screen ([#11], [#18]).

  ```
  This ranking rests on a thin definition. Before acting on it:
     • the spec declares no numbered requirements (looked for FR-NNN)
       → state what the system must do, one numbered requirement per behaviour
  ```

  Each message names what it searched for, so a project numbering its requirements another way
  can dismiss the warning instead of being accused of not having written them. The HTML report
  gets the same treatment.

- `scarce_thresholds.min_spec_chars` in `data/rating-rules.yaml`, so the "too short to judge
  on" bar is a data edit like every other threshold ([#11], [#18]).

### Changed

- The judge is asked for the fragment **most relevant** to a dimension rather than one that
  *supports* the rating. Requiring support made any whole-project dimension unanswerable:
  every over-abstention measured across two judges was `domain_specialization`, which no single
  sentence supports. Measured on `devstral-small-2`: accuracy 19/19 → 20/20 with one more
  dimension answered, over-abstention 2 → 1 ([#19], [#20]).
- Contradiction between requirements is offered as a reason to abstain. This part does not work
  yet — two prompt formulations produced identical results — and is documented in [#19] rather
  than claimed as fixed.

### Compatibility

No action needed. Terminal output gains a block on thin projects and cited evidence gets longer
(because it is no longer truncated), but nothing under `specjudge.api`, the JSON schema or the
exit codes moved.

## [0.3.0] - 2026-08-06

You can now build on SpecJudge instead of only running it: the machine-readable output
has a versioned schema you can fetch without touching Python, and there is a small
documented Python entry point with an explicit list of what semver covers.

Nothing here is breaking. Upgrading from 0.2.0 needs no action.

### Added

- A versioned JSON output contract. Every `--json` payload now carries
  `schema_version` (currently `1.0`), independent of the package version ([#2], [#17]).
- A formal JSON Schema for that payload, shipped inside the package and printable with
  **`specjudge --print-schema`** — so a TypeScript, Go or shell consumer can target the
  contract without cloning the repo or reading Python ([#2], [#17]).
- `specjudge.api`, a documented public Python surface: `analyze()` runs the same
  pipeline as the CLI and returns a `Comparison`, `to_dict()` produces the same payload
  as `--json`, and the typed errors carry the CLI's exit codes so a caller can branch on
  the failure without parsing messages ([#2], [#17]).
- [`docs/api.md`](docs/api.md), listing exactly what semantic versioning covers — and
  what it deliberately does not ([#2], [#17]).

### Changed

- The README states the **Ollama 0.5.0+** requirement introduced in 0.2.0, which had
  only ever appeared in the changelog and in the error message, and documents the cited
  evidence the judge now has to provide.
- `data_state` semantics are spelled out in the README: an ungrounded dimension degrades
  a run to `scarce` even when all three artifacts are present.

### Fixed

- The HTML report advertised *Del vibe coding al Spec-Driven Development* as forthcoming,
  with no link, when it had been on sale since July, and omitted *Explora la Inteligencia
  Artificial* altogether. Both shipped that way in 0.1.4 and 0.2.0. The cause was the same
  list living in two places with nothing tying them together; a contract test now compares
  them and rejects a book that is both linked and marked as forthcoming.

### Compatibility

No breaking changes. `schema_version` is a new field, and adding one is additive by the
contract's own rules — a consumer written against the 0.2.0 payload keeps working
unchanged, it simply gains a version to pin against.

The public Python surface is `specjudge.api` and nothing else. Anything imported from
another `specjudge.*` module is internal and may change in any release, including patch
ones; if you were reaching into `specjudge.cli` for the serialiser, it now lives in
`specjudge.serialize` and is re-exported as `api.to_dict`.

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

[Unreleased]: https://github.com/JoaquinRuiz/SpecJudge/compare/v0.5.1...HEAD
[0.5.1]: https://github.com/JoaquinRuiz/SpecJudge/compare/v0.5.0...v0.5.1
[0.5.0]: https://github.com/JoaquinRuiz/SpecJudge/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/JoaquinRuiz/SpecJudge/compare/v0.3.1...v0.4.0
[0.3.1]: https://github.com/JoaquinRuiz/SpecJudge/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/JoaquinRuiz/SpecJudge/compare/v0.2.0...v0.3.0
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
[#17]: https://github.com/JoaquinRuiz/SpecJudge/pull/17
[#11]: https://github.com/JoaquinRuiz/SpecJudge/issues/11
[#18]: https://github.com/JoaquinRuiz/SpecJudge/pull/18
[#19]: https://github.com/JoaquinRuiz/SpecJudge/issues/19
[#20]: https://github.com/JoaquinRuiz/SpecJudge/pull/20
[#2]: https://github.com/JoaquinRuiz/SpecJudge/issues/2
[#16]: https://github.com/JoaquinRuiz/SpecJudge/issues/16
[#21]: https://github.com/JoaquinRuiz/SpecJudge/pull/21
[#22]: https://github.com/JoaquinRuiz/SpecJudge/pull/22
[#3]: https://github.com/JoaquinRuiz/SpecJudge/issues/3
[#23]: https://github.com/JoaquinRuiz/SpecJudge/issues/23
[#24]: https://github.com/JoaquinRuiz/SpecJudge/pull/24
[#25]: https://github.com/JoaquinRuiz/SpecJudge/pull/25
[@rmarable]: https://github.com/rmarable
[#27]: https://github.com/JoaquinRuiz/SpecJudge/issues/27
[#28]: https://github.com/JoaquinRuiz/SpecJudge/pull/28
