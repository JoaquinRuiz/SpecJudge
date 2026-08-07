# AGENTS.md

## What this repository is

A clearing engine for intraday securities settlement. It reconciles trade
messages against custodian statements and produces the end-of-day net
obligations that get sent to the central counterparty.

## Rules for changes

- Money is represented as integer minor units, never as a float. A change that
  introduces a floating-point amount anywhere in the settlement path will be
  rejected in review regardless of how well it is tested.
- Every reconciliation rule must cite the market convention it implements, by
  name, in a comment above it. "Because the tests pass" is not a justification
  for a rule that decides whose money moves.
- Replaying a day must be deterministic: given the same message log, the netting
  output must be byte-identical. Anything that reads the clock or the network
  during netting belongs behind an injected port.

## Testing

- Property tests are required for anything touching netting. Example-based tests
  are accepted only as regression pins for bugs already found in production.
- The golden day-file suite must pass unchanged; updating a golden file requires
  a written explanation of why the previous output was wrong.

## Things that are not obvious

- `settlement/legacy_bridge/` speaks a fixed-width format from the 1990s that is
  still authoritative for two markets. It looks dead. It is not.
- Timezones are per-market, not per-user, and the trading day does not align with
  the calendar day in Tokyo.
