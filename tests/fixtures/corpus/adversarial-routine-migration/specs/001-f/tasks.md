# Tasks: Move Sessions to the New Store

## Phase 1
- [ ] T001 Add the session table to the new store with a matching schema
- [ ] T002 Implement the backfill job copying existing sessions in src/migrate/backfill.py
- [ ] T003 Implement dual-write so both stores stay consistent under concurrent writes in src/session/store.py
- [ ] T004 Implement the read path with reconciliation when the two stores disagree in src/session/read.py
- [ ] T005 Implement the reversible cutover switch and its rollback in src/migrate/cutover.py
- [ ] T006 Drop the old table once traffic is fully migrated
- [ ] T007 Add tests for the dual-write and rollback paths in tests/integration/
