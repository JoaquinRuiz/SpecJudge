# Contributing to SpecJudge

Thanks for wanting to improve SpecJudge. The volatile information — models, capabilities, prices and
rating rules — lives in **data files**, separate from the code: you can keep it up to date **without
touching `src/`** (Principle V of the constitution / FR-017).

## Adding or updating a model — `data/models.yaml`

Each model is an entry under `models:`:

```yaml
- id: my-model             # required, unique, stable (kebab-case)
  name: My Model           # required
  family: MyFamily         # optional; groups the model in the report filters
                           # (Claude, GPT, Gemini, Qwen...). Falls back to `provider`.
  open_source: false       # optional; true for downloadable, self-hostable weights
  provider: MyProvider     # optional
  capabilities:            # one key per dimension declared in `dimensions`
    reasoning: high        # valid levels: low | medium | high | top
    size: medium
    domain_specialization: medium
  price:
    input_per_million: 0.50
    output_per_million: 1.50
    currency: USD
    pricing_date: 2026-07-01   # REQUIRED: date of the pricing information (FR-018)
  notes: >
    Optional note (e.g. justification for the price or the capabilities).
```

**Important rules:**

- Any price change MUST update `pricing_date` so its freshness stays verifiable.
- `capabilities` MUST cover every dimension declared in `dimensions`.
- The `dimensions` set in `models.yaml` and in `rating-rules.yaml` MUST match.
- The README's worked example is generated from this catalog. If your edit changes the
  podium or the prices it quotes, regenerate it — a contract test fails otherwise:

  ```bash
  uv run python scripts/render_example.py --write
  ```

## Tuning the rating rules — `data/rating-rules.yaml`

- `mapping.per_dimension` translates the difference (capability − demand) into a partial label.
- `mapping.aggregation` combines the dimensions (`worst_dimension` by default).
- `scarce_thresholds.min_detailed_tasks` sets when a project counts as "thin on detail".
- `catalog_freshness.max_age_days` sets how old a `pricing_date` may get before the tool
  warns that the catalog is going stale.

The rating scale is a **fixed, closed vocabulary** — `poor` / `fair` / `good` / `overkill` — defined
in the project constitution. Changing it requires a constitution amendment, not just a data edit.

## Changing the judge prompt or the rating rules

These two decide the recommendation, so a change to either is evaluated against a
corpus of projects with expected profiles (`tests/fixtures/corpus/`).

```bash
# Deterministic half — runs in CI too. Contract, not judgement.
uv run pytest tests/regression

# Live half — needs Ollama. This is the one that tells you whether your change
# is an improvement.
uv run python scripts/eval_judge.py --judge <your-model>
```

The live run reports **accuracy** (did the level land in the expected band) and
**abstention quality** (did it abstain when it should, and only then) separately,
because they fail in opposite directions: a judge that abstains on everything
scores perfectly on accuracy alone.

Run it before and after your change and compare. Sampling is pinned, but Ollama
version and quantisation are not, so compare against **your own** baseline rather
than someone else's numbers.

If you intentionally change how the rules rank models, regenerate the snapshot and
read the diff:

```bash
uv run pytest tests/regression/test_rules_golden.py --snapshot-update
```

Adding a corpus case is a welcome contribution and needs no Python: a project
directory plus an `expected.yaml` with a `rationale` explaining the label.

## Before opening a PR

```bash
uv run pytest        # the whole suite must pass (Ollama is mocked; no local models needed)
uv run ruff check .  # style
```

Contract tests automatically validate that `data/models.yaml` conforms to the schema and that the
catalog and rules dimensions match, so a data mistake never slips through unnoticed.

## Project governance

SpecJudge follows Spec-Driven Development. The [project constitution](./.specify/memory/constitution.md)
takes precedence over any other practice or style preference.
Contributions that add mandatory paid dependencies to the core are rejected on principle
(Principle III).

---

Maintained by **Joaquín Ruiz** — [jokiruiz.com](https://jokiruiz.com) ·
[youtube.com/@jokioki](https://youtube.com/@jokioki)

📙 [El motor de la Inteligencia Artificial](https://amzn.eu/d/083CTN3U) ·
📘 [Programar con Inteligencia Artificial](https://amzn.eu/d/eK4f73N) ·
📗 *Del vibe coding al Spec-Driven Development* (coming soon)
