# Feature Specification: Export screen and netting rewrite

## Summary
Two pieces of work shipped together: a straightforward export screen, and a rewrite of
the intraday netting algorithm that sits behind it.

## Requirements
- **FR-001**: The netting engine MUST produce byte-identical output when a trading day
  is replayed from the same message log, across all supported markets.
- **FR-002**: Netting MUST resolve cross-market positions without assuming a global
  ordering of events; per-market trading days do not align on the calendar.
- **FR-003**: The export screen MUST list the ten most recent exports, newest first.
- **FR-004**: The export button MUST be disabled while an export is running.

## Acceptance criteria
- **SC-001**: A replay of any day in the last quarter reproduces the published net
  obligations exactly.
- **SC-002**: The export screen renders in under 200 ms with a hundred rows.
