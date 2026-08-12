# Changelog — SpecJudge for spec-kit

Versioned independently of SpecJudge itself: the extension is a manifest and a prompt,
and changes far less often than the tool it wraps.

## [0.1.2] - 2026-08-12

### Fixed

- **The install command in this README was wrong.** `--from` supplies the source, it does
  not replace the name, so the line published with 0.1.1 fails on the first try. The
  archive is republished under a new version rather than replaced in place: two different
  zips answering to 0.1.1 is worse than a version number spent on a one-line fix.

## [0.1.1] - 2026-08-12

### Fixed

- **The extension would not install on spec-kit 0.14 or newer.** The manifest pinned
  `>=0.13.0,<0.14.0`, so a compatible extension was refused over an upper bound that was a
  guess rather than a finding. It now declares a floor and no ceiling, and the README says
  which versions were actually tested. Verified installing on 0.15.2.

## [0.1.0] - 2026-08-12

### Added

- `speckit.specjudge.recommend` — runs SpecJudge over the current project and reports the
  podium, the budget envelope and the fragment behind each level.
- An optional `after_tasks` hook, so the recommendation arrives at the one moment it is
  both informed and free: the tasks exist, nothing has been implemented.
