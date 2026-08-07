# 2. No shared database between services

## Status
Accepted, superseding the shared-schema approach in 0001's era.

## Context
Billing and provisioning both wrote to the same tables, and a schema migration
required deploying both at the same minute or taking the platform down.

## Decision
- Each service owns its schema. Cross-service reads go through an API.
- Data another service needs is published as an event, not exposed as a table.

## Consequences
- Some data is duplicated and eventually consistent, which the UI must show
  honestly rather than pretending otherwise.
- Migrations stop being cross-team events.
