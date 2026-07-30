<div align="center">

# 🧑‍⚖️ SpecJudge

**Stop guessing which AI model to use. Ask your specs.**

SpecJudge reads your Spec-Driven Development artifacts and tells you which AI model actually
fits the job — before you spend a single token implementing it.

[![PyPI](https://img.shields.io/pypi/v/specjudge.svg)](https://pypi.org/project/specjudge/)
[![CI](https://github.com/JoaquinRuiz/SpecJudge/actions/workflows/ci.yml/badge.svg)](https://github.com/JoaquinRuiz/SpecJudge/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](./LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![Local-first](https://img.shields.io/badge/local--first-your%20specs%20never%20leave-brightgreen.svg)](#privacy)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](#contributing)

</div>

---

Here it is on a real spec — [`examples/task-manager`](./examples/task-manager), a small
CRUD web app, is included in this repo so you can run it yourself:

<!-- BEGIN generated-example: run `uv run python scripts/render_example.py --write` -->
```console
$ specjudge examples/task-manager

                   Model comparison (SpecJudge) - judge: devstral-small-2                   
┏━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃    ┃ Model                         ┃ Rating   ┃ Price                       ┃ Priced on  ┃
┡━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ 🥇 │ Mistral Small 3.2 24B (local) │ good     │ open-source/free            │ 2026-07-20 │
│ 🥈 │ DeepSeek V4 Flash             │ good     │ 0.28 out / 0.14 in USD/1M   │ 2026-07-28 │
│ 🥉 │ Gemma 4 26B MoE               │ good     │ 0.33 out / 0.06 in USD/1M   │ 2026-07-20 │
│    │ Claude Fable 5                │ overkill │ 50.00 out / 10.00 in USD/1M │ 2026-07-28 │
└────┴───────────────────────────────┴──────────┴─────────────────────────────┴────────────┘

🥇 Gold: Mistral Small 3.2 24B (local)
   Mistral Small 3.2 24B (local) is a good fit for this project. Right-sized: capability 
matches demand exactly in every dimension. Deciding dimension: 'reasoning' (demand=medium, 
capability=medium -> good).
🥈 Silver: DeepSeek V4 Flash
   DeepSeek V4 Flash is a good fit for this project. Right-sized: capability matches demand 
exactly in every dimension. Deciding dimension: 'reasoning' (demand=medium, 
capability=medium -> good).
🥉 Bronze: Gemma 4 26B MoE
   Gemma 4 26B MoE is a good fit for this project. Right-sized: capability matches demand 
exactly in every dimension. Deciding dimension: 'reasoning' (demand=medium, 
capability=medium -> good).
```

Abridged: the real run scores all 37 models in the catalog and lists every one of them. Prices and ratings above are generated from [`data/models.yaml`](./data/models.yaml), so they cannot go stale silently.

**Mistral Small 3.2 24B (local)** is right-sized for this project and costs nothing per token — it runs on your own hardware. **Claude Fable 5**, the priciest option this project does not need, bills $50.00/M output, $10.00/M input. If you would rather not self-host, the cheapest hosted model that still fits is **DeepSeek V4 Flash** at $0.28/M output, $0.14/M input — **179× cheaper on output** than reaching for the frontier.
<!-- END generated-example -->

The demand profile was estimated once by a local judge and pinned, so this example is
reproducible without Ollama; everything else is generated from the live catalog.

Add `--open` for a visual matrix in your browser, filterable by model family and by open source.

## The problem

You've finished defining a project with Spec-Driven Development. Now you have to pick a model to
implement it. Two expensive mistakes are waiting:

| Mistake | Cost |
|---|---|
| Model **too powerful** for the job | You pay for capability the project never uses |
| Model **too limited** for the job | It doesn't produce the result — you pay *and* get nothing |

SpecJudge puts that decision at the one moment it's cheapest to make it: the specs exist, but
nothing has been spent yet. And it grounds the answer in *your* project, not a generic benchmark.

## Quick start

**Requirements:** Python 3.11+, [uv](https://docs.astral.sh/uv/), and
[Ollama](https://ollama.com) with at least one local model.

```bash
ollama pull llama3.1:8b            # a judge to evaluate your project
uv tool install specjudge
specjudge /path/to/your/project
```

That's it. On first run SpecJudge lists your local models, asks which one to use as the judge,
and remembers your choice.

<details>
<summary><b>Run without installing, with pipx, or from source</b></summary>

```bash
# Ephemeral run, no install
uvx specjudge /path/to/your/project

# pipx works too
pipx install specjudge

# From source
git clone https://github.com/JoaquinRuiz/SpecJudge.git && cd SpecJudge
uv sync --extra dev
uv run specjudge --help
```
</details>

📺 Prefer to watch? There's a
[walkthrough on YouTube](https://www.youtube.com/watch?v=T53zvm08zUg) — in Spanish.

## Roadmap

What's being worked on, what's next, and where help is wanted lives in a single
[public roadmap issue](https://github.com/JoaquinRuiz/SpecJudge/issues/8) — kept current there
rather than duplicated here, where it would rot.

The most useful contribution is keeping the model catalog accurate: models and prices change every
few weeks, and updating them takes **zero Python**. Several issues tagged
[`good first issue`](https://github.com/JoaquinRuiz/SpecJudge/labels/good%20first%20issue) don't
require touching the code either.

## Privacy

The judge runs **on your machine** through Ollama. Your specs — your business logic, your design
decisions — never touch a third-party service, and deciding which model to buy costs you nothing
in API calls. The browser report is a self-contained HTML file that loads nothing from the network.

This isn't a nice-to-have; it's Principle I of the [project constitution](./.specify/memory/constitution.md).

## How it works

```
  your project                  local judge                  model catalog
┌───────────────┐            ┌───────────────┐            ┌────────────────┐
│ constitution  │            │  Ollama, on   │            │  models.yaml   │
│ spec          │──────────► │ your machine  │──────────► │  (community-   │
│ tasks         │  how hard  │  estimates    │  compare   │   maintained)  │
└───────────────┘  is this?  │  the demand   │  capability└────────────────┘
                             └───────────────┘  vs demand         │
                                                                  ▼
                                                          🥇 🥈 🥉 podium
```

The judge estimates how demanding your project is across a few dimensions. Declarative rules in
`rating-rules.yaml` cross that demand against each model's declared capability. The best **fit**
wins — no black box, and every verdict comes with a reason you can read.

## Reading the output

Every model gets a rating on a fixed scale:

| Rating | Meaning |
|--------|---------|
| `good` | Capable enough — **the sweet spot** |
| `overkill` | Capable, but you're paying for headroom you won't use |
| `fair` | Falls somewhat short |
| `poor` | Not capable enough |

The podium ranks models by **how well they fit your project's complexity** — neither under-capable
nor more powerful than needed.

> **Price does not decide the ranking.** It's shown for every model so you can see what each option
> costs, and it only breaks ties between models that fit *equally well*. A cheaper model never wins
> over one that fits better — recommending something that can't do the job is the most expensive
> mistake of all. Right-sizing is what keeps you from overpaying.

If no model in the catalog is capable enough, SpecJudge **says so** instead of recommending one
anyway. Same when your project is too thinly specified to judge — see *Data states* below.

<details>
<summary><b>Options, data states and exit codes</b></summary>

```bash
specjudge [PROJECT_PATH] [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--open`, `-o` | Also open a visual matrix in your browser |
| `--judge <model>` | Force the judge model for this run (not persisted) |
| `--set-judge` | Re-run judge selection and save it |
| `--catalog <path>` | Use an alternative model catalog |
| `--json` | Emit the result as JSON (for scripting) |
| `--no-color` | Disable color/highlighting |

**Data states** — SpecJudge is explicit about how much it can be trusted:

- **Sufficient** — constitution, spec and tasks present: reliable recommendation.
- **Scarce** — artifacts missing or thin on detail: recommendation issued, with a warning.
- **Insufficient** — no tasks to evaluate: no recommendation at all.

**Exit codes** — degradation is distinguishable programmatically:

| Code | Meaning |
|------|---------|
| `0` | Success (includes *scarce* and "no model is sufficient") |
| `2` | Insufficient project information — no recommendation |
| `3` | Judge unavailable (Ollama not running, no local models, unusable answer) |
| `4` | Model catalog missing or empty |
</details>

## Contributing

**Models and prices change every few weeks. That's the whole reason this project needs you.**

The most valuable contribution requires **zero Python** — SpecJudge keeps everything volatile in
human-readable data files, deliberately separate from the code. Adding a model is one YAML block:

```yaml
- id: my-new-model
  name: My New Model
  family: MyFamily         # groups it in the report's filters (Claude, GPT, Qwen...)
  open_source: false       # open weights you can download and self-host?
  provider: SomeAI
  capabilities:
    reasoning: high        # low | medium | high | top
    size: high
    domain_specialization: medium
  price:
    input_per_million: 1.50
    output_per_million: 6.00
    currency: USD
    pricing_date: 2026-07-28   # required — makes freshness verifiable
```

Open `data/models.yaml`, add it, send the PR. Contract tests validate the schema automatically,
so a mistake can't slip through unnoticed.

### Good first contributions

| Difficulty | What | Where |
|---|---|---|
| 🟢 No code | Update a price that has changed | `data/models.yaml` |
| 🟢 No code | Add a model that's missing | `data/models.yaml` |
| 🟢 No code | Fix a capability rating you disagree with | `data/models.yaml` |
| 🟡 No code | Tune the rating rules or thresholds | `data/rating-rules.yaml` |
| 🟡 Light | Improve the judge prompt for small models | `src/specjudge/judge/evaluator.py` |
| 🔴 Code | Support another local runtime besides Ollama | `src/specjudge/judge/` |

Disagree with a rating? **That's a contribution, not a complaint** — the catalog is opinion made
inspectable. Open a PR with your reasoning.

### Before you send a PR

```bash
uv run pytest        # full suite — Ollama is mocked, no local models needed
uv run ruff check .
```

See [`CONTRIBUTING.md`](./CONTRIBUTING.md) for the full schemas and project governance.

### What won't be merged

Contributions that add **mandatory paid dependencies** to the core. A tool whose purpose is to save
you money must not require money to run. That's Principle III, and it isn't negotiable.

## About the author

**Joaquín Ruiz** — [jokiruiz.com](https://jokiruiz.com) ·
[youtube.com/@jokioki](https://youtube.com/@jokioki)

📗 [Del vibe coding al Spec-Driven Development](https://amzn.eu/d/02csLpKC)
📙 [El motor de la Inteligencia Artificial](https://amzn.eu/d/083CTN3U)
📘 [Programar con Inteligencia Artificial](https://amzn.eu/d/eK4f73N)
📙 [Explora la Inteligencia Artificial](https://amzn.eu/d/dSwYhue)

## License

[MIT](./LICENSE) © Joaquín Ruiz

<div align="center">
<sub>If SpecJudge saved you from overpaying for a model, consider giving it a ⭐</sub>
</div>
