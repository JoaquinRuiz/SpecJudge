# 1. Event sourcing for pricing

## Status
Accepted

## Context
Prices are renegotiated per customer and backdated regularly. Auditors ask what a
customer was charged on a given day two years ago, and the previous CRUD model
could only answer what they are charged now.

## Decision
- Pricing state is derived from an append-only event log; the current price table
  is a projection that can be rebuilt from scratch.
- Backdating is a new event with an effective date, never an edit of an old one.

## Consequences
- Any query about "the price then" is a fold over events, which is slower and has
  to be cached deliberately.
- A bug in a projection is repairable by replay; a bug in an event is not.
