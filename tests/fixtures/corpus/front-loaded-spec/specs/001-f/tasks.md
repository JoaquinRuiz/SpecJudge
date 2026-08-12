# Tasks: Cross-market netting rewrite

## Format
`[ID] [P?] [Story] Description with path`

## Path Conventions
Source lives in `src/`, tests in `tests/`.

## Phase 1 — Setup
- [ ] T001 Take a database backup before any migration in scripts/backup.sh
- [ ] T002 Capture the current netting output as a baseline in tests/golden/

## Phase 2 — Cosmetic
- [ ] T003 Rename the blotter label in src/ui/strings.ts
- [ ] T004 Rename the export label in src/ui/strings.ts
- [ ] T005 Rename the filter label in src/ui/strings.ts
- [ ] T006 Rename the header label in src/ui/strings.ts
- [ ] T007 Rename the footer label in src/ui/strings.ts
- [ ] T008 Rename the tooltip label in src/ui/strings.ts
- [ ] T009 Rename the legend label in src/ui/strings.ts
- [ ] T010 Rename the empty state label in src/ui/strings.ts

## Phase 3 — The rewrite
- [ ] T011 Rewrite netting for deterministic replay across markets in src/netting/engine.py
- [ ] T012 Model per-market trading days without a global clock in src/netting/calendar.py
- [ ] T013 Sign every write with the desk key and reject unattributable entries in src/netting/audit.py
