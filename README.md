<div align="center">

# 🧑‍⚖️ SpecJudge

**Stop guessing which AI model to use. Ask your specs.**

SpecJudge reads your Spec-Driven Development artifacts and tells you which AI model actually
fits the job — before you spend a single token implementing it.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](./LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![Local-first](https://img.shields.io/badge/local--first-your%20specs%20never%20leave-brightgreen.svg)](#privacy)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](#contributing)

</div>

---

```console
$ specjudge .

             Model comparison (SpecJudge) - judge: devstral-small-2
┏━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃    ┃ Model                    ┃ Rating ┃ Price                  ┃ Priced on  ┃
┡━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ 🥇 │ Gemma 4 31B (local)      │ good   │ open-source/free       │ 2026-07-20 │
│ 🥈 │ Gemma 4 31B              │ good   │ 0.35 out / 0.12 in     │ 2026-07-20 │
│ 🥉 │ Qwen 3.6-35B-A3B (local) │ good   │ open-source/free       │ 2026-07-20 │
│    │ GLM-5.1                  │ good   │ 3.04 out / 0.97 in     │ 2026-07-20 │
│    │ Claude Opus 4.8          │overkill│ 25.00 out / 5.00 in    │ 2026-07-20 │
└────┴──────────────────────────┴────────┴────────────────────────┴────────────┘

🥇 Gold: Gemma 4 31B (local)
   Right-sized: capability matches demand exactly in every dimension.
```

Add `--open` for a visual matrix in your browser.

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
uv tool install git+https://github.com/JoaquinRuiz/SpecJudge.git
specjudge /path/to/your/project
```

That's it. On first run SpecJudge lists your local models, asks which one to use as the judge,
and remembers your choice.

> **PyPI release pending** — once published, this becomes `uv tool install specjudge`.

<details>
<summary><b>Run without installing, or from source</b></summary>

```bash
# Ephemeral run, no install
uvx --from git+https://github.com/JoaquinRuiz/SpecJudge.git specjudge /path/to/project

# From source
git clone https://github.com/JoaquinRuiz/SpecJudge.git && cd SpecJudge
uv sync --extra dev
uv run specjudge --help
```
</details>

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
  provider: SomeAI
  capabilities:
    reasoning: high        # low | medium | high | top
    size: high
    domain_specialization: medium
  price:
    input_per_million: 1.50
    output_per_million: 6.00
    currency: USD
    pricing_date: 2026-07-20   # required — makes freshness verifiable
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

📙 [El motor de la Inteligencia Artificial](https://amzn.eu/d/083CTN3U)
📘 [Programar con Inteligencia Artificial](https://amzn.eu/d/eK4f73N)
📗 *Del vibe coding al Spec-Driven Development* — **coming soon**

## License

[MIT](./LICENSE) © Joaquín Ruiz

<div align="center">
<sub>If SpecJudge saved you from overpaying for a model, consider giving it a ⭐</sub>
</div>
