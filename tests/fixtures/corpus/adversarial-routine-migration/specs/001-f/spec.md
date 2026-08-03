# Feature Specification: Move Sessions to the New Store

## Summary
Move the session table from the old database to the new one. Straightforward
data migration: read, write, switch the pointer.

## Requirements
- **FR-001**: All existing sessions MUST be preserved.
- **FR-002**: The cutover MUST happen with zero downtime and MUST be reversible
  at any point, including after writes have landed in the new store.
- **FR-003**: During the transition both stores MUST accept writes and MUST NOT
  diverge; a session written to either store MUST be readable from both.
- **FR-004**: The old table MUST be dropped once traffic is fully migrated.
