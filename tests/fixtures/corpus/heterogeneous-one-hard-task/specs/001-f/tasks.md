# Tasks: Export screen and netting rewrite

## Phase 1 — netting
- [ ] T001 Rewrite the netting algorithm for deterministic replay in src/netting/engine.py
- [ ] T002 Model per-market trading days without a global clock in src/netting/calendar.py

## Phase 2 — screen
- [ ] T003 Add the export list component in src/ui/ExportList.tsx
- [ ] T004 Wire the newest-first ordering in src/ui/ExportList.tsx
- [ ] T005 Disable the export button while running in src/ui/ExportButton.tsx
- [ ] T006 Add the empty state copy in src/ui/strings.ts
- [ ] T007 Add component tests for the list in tests/ui/ExportList.test.tsx
- [ ] T008 Add a screenshot test for the empty state in tests/ui/empty.test.tsx
