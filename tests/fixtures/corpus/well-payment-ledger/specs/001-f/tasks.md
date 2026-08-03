# Tasks: Double-Entry Payment Ledger

## Phase 1
- [ ] T001 Define the account and entry schema with per-currency balance invariants in src/models/
- [ ] T002 Implement the balanced-transaction validator rejecting non-zero sums in src/ledger/validate.py
- [ ] T003 Implement idempotent posting keyed by an external reference in src/ledger/post.py
- [ ] T004 Implement optimistic concurrency so retried postings cannot double-apply in src/ledger/post.py
- [ ] T005 Implement point-in-time balance reconstruction from the entry log in src/ledger/balances.py
- [ ] T006 Implement currency conversion with banker's rounding and residual entries in src/ledger/fx.py
- [ ] T007 Implement the settlement reconciliation report in src/reconcile/report.py
- [ ] T008 Add property-based tests asserting the ledger stays balanced in tests/property/
- [ ] T009 Add a concurrency test posting the same key from many workers in tests/integration/
