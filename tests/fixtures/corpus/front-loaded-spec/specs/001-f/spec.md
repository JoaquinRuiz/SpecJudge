# Feature Specification: Cross-market netting rewrite

## Context

The settlement team reviewed this in the January planning round and asked for the behaviour to be spelled out before implementation begins, because the previous attempt was reverted after a production incident.
The risk team reviewed this in the February planning round and asked for the behaviour to be spelled out before implementation begins, because the previous attempt was reverted after a production incident.
The compliance team reviewed this in the March planning round and asked for the behaviour to be spelled out before implementation begins, because the previous attempt was reverted after a production incident.
The treasury team reviewed this in the April planning round and asked for the behaviour to be spelled out before implementation begins, because the previous attempt was reverted after a production incident.
The operations team reviewed this in the May planning round and asked for the behaviour to be spelled out before implementation begins, because the previous attempt was reverted after a production incident.
The desk team reviewed this in the June planning round and asked for the behaviour to be spelled out before implementation begins, because the previous attempt was reverted after a production incident.

## User Scenarios

### Scenario 1 — the ordinary day
A trader opens the blotter, sees the day's positions per market, and closes it again.
The settlement team reviewed this in the January planning round and asked for the behaviour to be spelled out before implementation begins, because the previous attempt was reverted after a production incident.
The risk team reviewed this in the February planning round and asked for the behaviour to be spelled out before implementation begins, because the previous attempt was reverted after a production incident.
The compliance team reviewed this in the March planning round and asked for the behaviour to be spelled out before implementation begins, because the previous attempt was reverted after a production incident.
The treasury team reviewed this in the April planning round and asked for the behaviour to be spelled out before implementation begins, because the previous attempt was reverted after a production incident.
The operations team reviewed this in the May planning round and asked for the behaviour to be spelled out before implementation begins, because the previous attempt was reverted after a production incident.
The desk team reviewed this in the June planning round and asked for the behaviour to be spelled out before implementation begins, because the previous attempt was reverted after a production incident.

### Scenario 2 — the day a market is closed
The settlement team reviewed this in the January planning round and asked for the behaviour to be spelled out before implementation begins, because the previous attempt was reverted after a production incident.
The risk team reviewed this in the February planning round and asked for the behaviour to be spelled out before implementation begins, because the previous attempt was reverted after a production incident.
The compliance team reviewed this in the March planning round and asked for the behaviour to be spelled out before implementation begins, because the previous attempt was reverted after a production incident.
The treasury team reviewed this in the April planning round and asked for the behaviour to be spelled out before implementation begins, because the previous attempt was reverted after a production incident.
The operations team reviewed this in the May planning round and asked for the behaviour to be spelled out before implementation begins, because the previous attempt was reverted after a production incident.
The desk team reviewed this in the June planning round and asked for the behaviour to be spelled out before implementation begins, because the previous attempt was reverted after a production incident.

## Requirements
- **FR-001**: Netting MUST produce byte-identical output when a trading day is replayed
  from the same message log, across every supported market.
- **FR-002**: Cross-market positions MUST resolve without assuming a global ordering of
  events; per-market trading days do not align on the calendar.
- **FR-003**: Every write MUST be attributable to a signing desk; an unattributable entry
  is a data integrity incident, not a defect to patch quietly.
- **FR-004**: A correction MUST be a new entry referencing the one it corrects, and both
  MUST stay visible.

## Acceptance criteria
- **SC-001**: A replay of any day in the last quarter reproduces the published net
  obligations exactly.
