# Tasks: Offline Audit Log Export

## Phase 1
- [ ] T001 Add the incremental event query with a since-cursor in data/EventStore.kt
- [ ] T002 Implement streaming serialization of events in export/ExportWriter.kt
- [ ] T003 Sign the serialized bytes with the device key in export/ExportSigner.kt
- [ ] T004 Write to a temporary file and rename atomically in export/ExportFile.kt

## Phase 2
- [ ] T005 Add the verification CLI reviewers run off-device in tools/verify/
- [ ] T006 Add property tests for interrupted exports in test/export/
