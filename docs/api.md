# Using SpecJudge from code

Two ways to build on SpecJudge, in the order most people should try them.

## 1. The JSON output — any language

The fastest path, and the one that needs nothing from Python:

```bash
specjudge /path/to/project --judge llama3.1:8b --json
```

The payload has its own schema, which you can fetch without cloning anything:

```bash
specjudge --print-schema > specjudge.schema.json
```

Generate types from it, validate against it, pin to its version. It is also in the
repo at [`src/specjudge/_schema/output.schema.json`](../src/specjudge/_schema/output.schema.json).

### Versioning

Every payload carries `schema_version`, currently **1.2**. It is deliberately
independent of the package version — otherwise the contract would appear to change
on every catalog-only release.

| Change | Bump |
|---|---|
| A field is added | MINOR |
| A field is removed, retyped, or an existing value changes meaning | MAJOR |

Releases 0.1.x and 0.2.0 emitted this same payload without the `schema_version`
field. Adding it is additive, so consumers written against those releases keep
working.

**1.1** adds two fields, both additive:

- `sources_read` — which written sources the assessment actually came from
  (`constitution`, `spec`, `tasks`, `plan`, `agents` for an `AGENTS.md`, `claude`
  for a `CLAUDE.md`, `cursor` for a `.cursorrules`, `copilot` for
  `.github/copilot-instructions.md`, `adr` for an architecture decision record).
  One entry per kind, however many files of that kind were read — a monorepo with
  eight `AGENTS.md` still lists `agents` once. The list is open-ended: new source
  kinds arrive in MINOR releases, so treat an unfamiliar value as a source you do
  not recognise rather than as an error.
- `environment_only` — true when every source read describes the *repository* and
  none describes the *work*. The result is then a floor (how demanding this codebase
  is to work in at all), not a recommendation for a specific piece of work. Worth
  branching on: it is the one case where the ranking answers a different question
  than usual.

**1.2** adds `envelope`, additive: the demand as a range rather than a single verdict.

- `envelope.default_demand` — the levels the ranking was actually built on
- `envelope.peak_demand` — the levels the hardest part of the work needs
- `envelope.constraints` — one row per rated dimension: the level, the fragment behind it,
  and `hard` (the cited text states an obligation rather than a habit, derived from the
  text rather than asked of the judge)
- `envelope.escalations` — the constraints whose peak sits above the default; always empty
  under the `single` execution model, where there is nothing to escalate to
- `envelope.execution_model` — `single` or `escalating`, i.e. which of the two readings
  produced `best_choice`

Worth branching on if you automate spend: under `escalating`, `best_choice` answers "what
should implement most of this" and `escalations` tells you what to reach for on the rest.
Under `single` it answers "what can implement all of it", which is the older meaning and
the default.

### What the schema does not pin

- **Free text.** `justification`, `coverage` and `warnings` are for humans; their
  wording changes without a version bump. Branch on `data_state`, `evidence.status`
  and `rating` instead.
- **Demand levels.** `demand.dimensions` values and dimension names both come from
  `data/rating-rules.yaml`, which a user can edit, so the schema types them as
  strings rather than enumerating them.
- **`rating`** *is* enumerated: the scale is fixed by the project constitution, and
  changing it requires a constitutional amendment rather than a release.

## 2. The Python API

```python
from specjudge import api

comparison = api.analyze("path/to/project", judge_model="llama3.1:8b")
print(comparison.best_choice)

payload = api.to_dict(comparison)   # same shape as --json
```

Like the CLI, this needs Ollama running locally with the model installed: the
assessment comes from a judge on your machine, not from a bundled heuristic.

### Covered by semantic versioning

Everything exported from `specjudge.api`, and nothing else:

| Name | What it is |
|---|---|
| `analyze` | Run the full analysis and return a `Comparison` |
| `to_dict` | A `Comparison` as the documented JSON payload |
| `json_schema` | The schema describing that payload |
| `SCHEMA_VERSION` | Version of the payload contract |
| `Comparison` | The result: evaluations, podium, best choice, warnings, demand, sources read, envelope |
| `Envelope` | The demand as a range: default level, peak, constraint table, escalation triggers |
| `Constraint` | One row of that table: dimension, level, the fragment behind it, whether it is a stated requirement |
| `ExecutionModel` | `single` / `escalating` — which reading the ranking is built on |
| `Evaluation` | One model's rating, price and justification |
| `DemandProfile` | The judge's assessment and its evidence |
| `Evidence` | One dimension's citation |
| `EvidenceStatus` | `grounded` / `quote_unverified` / `unsupported` |
| `Price` | Per-million rates and the date they were verified |
| `Rating` | `poor` / `fair` / `good` / `overkill` |
| `DataState` | `sufficient` / `scarce` / `insufficient` |
| `SpecJudgeError` | Base class for everything below |
| `CatalogError` | Catalog missing, empty or malformed (exit 4) |
| `InsufficientInfoError` | Not enough project, or nothing the judge could ground (exit 2) |
| `JudgeUnavailableError` | Ollama missing, too old, or answering unusably (exit 3) |

Each error carries the CLI's `exit_code`, so you can branch on the failure without
parsing messages:

```python
try:
    comparison = api.analyze(path, judge_model="llama3.1:8b")
except api.InsufficientInfoError:
    ...   # the project cannot be judged as it stands
except api.JudgeUnavailableError:
    ...   # the environment is the problem, not the project
```

### Not covered

Everything else. Specifically:

- Any module under `specjudge.*` other than `specjudge.api` — importing
  `specjudge.rating` or `specjudge.judge.evaluator` is using internals, and they
  change in patch releases.
- Terminal and HTML output: layout, colour and wording.
- The judge prompt, and the contents of `data/models.yaml` and
  `data/rating-rules.yaml`.
- The result dataclasses are **read-only in practice**: mutating a `Comparison` and
  expecting anything sensible is not supported.

If you need something that is not on the list, open an issue rather than importing
around it — a promise that gets made by accident is a promise nobody wrote down.
