# AGENTS.md

## Repository

A monorepo for a clinical trial data platform. Two deployable packages plus a
shared schema, all released together.

## Rules that apply everywhere

- Patient identifiers never leave the `ledger` package unhashed. A change that
  moves a raw identifier across a package boundary is rejected in review.
- Every schema change ships with a forward and a backward migration. Sites run
  a year-old build for months at a time.
- No test may reach the network. The trial sites' firewalls are not reproducible
  in CI, so a test that passes here and fails there is worse than no test.
