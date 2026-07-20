# Contributing to SpecJudge

Thanks for wanting to improve SpecJudge. The volatile information — models, capabilities, prices and
rating rules — lives in **data files**, separate from the code: you can keep it up to date **without
touching `src/`** (Principle V of the constitution / FR-017).

## Adding or updating a model — `data/models.yaml`

Each model is an entry under `models:`:

```yaml
- id: my-model             # required, unique, stable (kebab-case)
  name: My Model           # required
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

## Tuning the rating rules — `data/rating-rules.yaml`

- `mapping.per_dimension` translates the difference (capability − demand) into a partial label.
- `mapping.aggregation` combines the dimensions (`worst_dimension` by default).
- `scarce_thresholds.min_detailed_tasks` sets when a project counts as "thin on detail".

The rating scale is a **fixed, closed vocabulary** — `poor` / `fair` / `good` / `overkill` — defined
in the project constitution. Changing it requires a constitution amendment, not just a data edit.

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
