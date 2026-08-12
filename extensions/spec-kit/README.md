# SpecJudge for spec-kit

Right-size the model **before** you implement.

You finish `/speckit.tasks`. The spec, the plan and the task list exist, and not a token
has been spent. This extension asks [SpecJudge](https://github.com/JoaquinRuiz/SpecJudge)
which model actually fits that work, and shows you the fragment of your own spec behind
every level:

```
Budget envelope
   default: reasoning medium, size low
   reasoning: top — S:FR-001 (requirement)
   size: low — T:T002 (customary)
```

`S:FR-001` is a line in your spec. If the recommendation looks too expensive, you can go
and read the sentence that made it expensive.

The judge runs on your machine through Ollama. Your specs never leave it.

## Install

```bash
uv tool install specjudge          # the CLI this wraps
specjudge --set-judge              # pick a local judge, once

specify extension add --from https://github.com/JoaquinRuiz/SpecJudge/releases/latest/download/spec-kit-specjudge.zip
```

Requires spec-kit 0.13.x, SpecJudge 0.5.0+, and [Ollama](https://ollama.com) 0.5.0+ with a
local model. An 8B judge is enough; see
[choosing a judge](https://github.com/JoaquinRuiz/SpecJudge/blob/main/docs/judges.md).

## Use

It runs itself. After `/speckit.tasks` you are asked:

```
Recommend a model for these tasks? [y/N]
```

Say no and nothing happens. Or run it whenever you like:

```
/speckit.specjudge.recommend
```

## What it does not do

- **Writes nothing.** `effect: read-only`. The recommendation is reported, not archived.
- **Blocks nothing.** No judge, no Ollama, too thin a spec — it says so in one line and
  gets out of the way. You came here to implement.
- **Decides nothing.** Price never overrides fit, and the tool says when it is unsure
  rather than picking anyway.

## Licence

MIT, same as SpecJudge.
