# Choosing a local judge

SpecJudge asks a model running on your machine how demanding your project is. That model
is called the **judge**, and which one you pick changes the answer — so this page says
what to pick and, more usefully, how to find out for yourself.

The short version: **an 8B judge gives very good results, and a 24B-class judge gives
perfect ones** on our regression corpus. Both run on a laptop. Neither sends your specs
anywhere.

```bash
ollama pull llama3.1:8b       # very good, 4.9 GB
ollama pull devstral-small-2  # perfect on our corpus, 15 GB
```

## What actually matters

**Ollama 0.5.0 or newer.** The judge's answer is constrained by a JSON Schema. Before
that existed, an 8B judge would rate a project correctly and then put `[true]` where a
fragment id belongs, and the whole run was rejected — 0 of 9 valid answers became 9 of 9
once generation was constrained ([#14]). On older Ollama, SpecJudge stops and says so.

**Size, but less than you would expect.** Judges at or below
`judge.compact_prompt_at_or_below_params_b` parameters (70B by default) get the *compact*
prompt: a structured digest of your project instead of its raw markdown. Small models lose
the instructions inside a long document and start continuing it rather than evaluating it.
A small judge is a first-class path here, not a fallback.

**Whether it can cite.** Every rated dimension must cite a fragment that exists in your
project, and a dimension the judge cannot ground comes back `unsupported` and drops out of
the calculation. If your judge cannot manage citations at all, set
`evidence.require_spans: false` in `data/rating-rules.yaml` — you get a rating without the
grounding check, which is a real loss and an honest trade.

## Measured

Every figure below comes from `scripts/eval_judge.py` over the regression corpus of **18
projects** with expected profiles, on one machine. Reproduce any row with:

```bash
uv run python scripts/eval_judge.py --judge <model> --markdown-row
```

| Judge | Params | Dimensions in band | Ordinal distance | Answers refused |
|---|---|---|---|---|
| `devstral-small-2` | 24B | 32/32 (100%) | 0 | 0 |
| `qwen3:8b` | 8B | 26/30 (87%) | 4 steps | 1 |
| `llama3.1:8b-instruct-q4_K_M` | 8B | 24/32 (75%) | 8 steps | 0 |

<sub>SpecJudge 0.5.3 · Ollama 0.32.6 · Apple silicon · corpus of
18 cases · measured 2026-08-12</sub>

**In band** — the demand level landed inside the range the corpus expects. Ranges rather
than exact levels, because the labels are human judgement on a four-point scale.
**Ordinal distance** — how far outside the band the misses fell. **Answers refused** — the
judge produced something SpecJudge would not accept, so the run exits 3 instead of
recommending anything.

That last column is the one worth understanding before you pick. A small judge's failure
mode here is *no answer*, not *a confident wrong answer*: an assessment that cannot be
grounded in your own text is rejected rather than shown to you. That is Principle IV of
the [project constitution](../.specify/memory/constitution.md), and it is what makes an
8B judge a reasonable thing to trust.

**Which 8B matters more than the fact that it is an 8B.** The two in that table are the
same size and the same price and do not perform the same. Whatever the numbers say next
year, that is the part worth carrying away.

Today, between those two, **`qwen3:8b` is the one to pick — and the trade is worth stating
rather than hiding**. It is wrong half as often and half as far off, and where it cannot
cope it refuses instead of answering: a failure you can see. What it costs is that
refusal, roughly one project in eighteen that gets no recommendation at all. If you would
rather always get an answer and judge it yourself, `llama3.1` is the other side of that
trade, and you would not be wrong.

What it is **not** is twelve points better. Read the denominators: they differ across rows
because a judge that refuses has fewer dimensions graded. `qwen3` was scored on 30, and
`llama3.1` on 32 — more of the corpus answered, more of it wrong. Comparing the
percentages alone would flatter one of them for giving up.

Two honest caveats. The 8B runs are not perfectly reproducible: repeating `llama3.1` gave
the same totals but failed on a different case. And `devstral-small-2` is a code model, so
part of its margin may be that rather than its size.

### What a bigger judge additionally gets you

Judges above `execution.request_bulk_above_params_b` (20B by default) are also asked to
separate the bulk of the work from its hardest part, which is what fills in the escalation
triggers of the [budget envelope](../README.md#one-project-two-complexities). Smaller
judges are not asked, and this is measured rather than assumed: on the same corpus the
extra fields cost `qwen3:8b` five points of accuracy (89% → 84%) and doubled its refused
answers, while `devstral-small-2` answered them correctly and lost nothing.

So an 8B judge still ranks and still cites; it reports one level for the project instead of
a range, and says so rather than leaving you to infer it.

## Reported by the community

Numbers from hardware and quantisations the maintainer does not have. Send a row — see
[CONTRIBUTING.md](../CONTRIBUTING.md) — and it goes here with your name on it.

| Judge | Params | Dimensions in band | Ordinal distance | Answers refused | Reported by |
|---|---|---|---|---|---|
| _(yours here)_ | | | | | |

## Switching judges

```bash
specjudge . --judge qwen3:8b   # once, not persisted
specjudge . --set-judge        # pick again and remember the choice
```

[#14]: https://github.com/JoaquinRuiz/SpecJudge/issues/14
