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

specify extension add specjudge --from https://github.com/JoaquinRuiz/SpecJudge/releases/latest/download/spec-kit-specjudge.zip
```

Requires spec-kit 0.13.0 or newer, SpecJudge 0.5.0+, and [Ollama](https://ollama.com)
0.5.0+ with a local model. An 8B judge is enough; see
[choosing a judge](https://github.com/JoaquinRuiz/SpecJudge/blob/main/docs/judges.md).

### "discovery only — not installable"

If you found this by searching the catalog, you will have seen that next to the name:

```
Catalog: community (discovery only — not installable)
⚠  Not directly installable from 'community'.
```

**Nothing is wrong with the extension.** spec-kit ships two catalogs: `catalog.json`, the
one GitHub maintains, is installable by default; `catalog.community.json`, where every
third-party extension lives, is discovery-only. That applies to all ~150 entries in it,
not to this one. Catalog acceptance checks that the metadata is right and the archive
downloads — it does not audit anyone's code — so installing from it by name is a decision
each project makes for itself rather than a default.

The command above sidesteps it: `--from <url>` takes no position on catalogs, because you
supplied the URL yourself.

To install by name instead, approve the community catalog once:

```bash
specify extension catalog add https://raw.githubusercontent.com/github/spec-kit/main/extensions/catalog.community.json \
  --name community-approved --priority 5 --install-allowed

specify extension add specjudge
```

That approves **the whole catalog**, not just this extension — every third-party entry in
it becomes installable by name in this project. Worth knowing before you run it; if you
would rather not, the `--from` line stays the smaller commitment.

**Tested against spec-kit 0.13.0 and 0.15.2.** The manifest declares a floor and no
ceiling: it uses only `provides.commands` and `hooks`, the most stable part of the
extension format, and an upper bound would stop the extension installing every time
spec-kit ships a minor release. If a future version does break it, that is a bug to fix,
not a prediction to encode.

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
