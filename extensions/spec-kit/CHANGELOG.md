# Changelog — SpecJudge for spec-kit

Versioned independently of SpecJudge itself: the extension is a manifest and a prompt,
and changes far less often than the tool it wraps.

## [0.1.0] - 2026-08-12

### Added

- `speckit.specjudge.recommend` — runs SpecJudge over the current project and reports the
  podium, the budget envelope and the fragment behind each level.
- An optional `after_tasks` hook, so the recommendation arrives at the one moment it is
  both informed and free: the tasks exist, nothing has been implemented.
