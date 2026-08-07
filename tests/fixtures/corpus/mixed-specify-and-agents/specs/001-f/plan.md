# Implementation Plan: Offline Audit Log Export

## Stack
Kotlin on Android, SQLDelight over the existing local event store, signing via the
platform keystore. No new third-party dependency: the AGENTS.md rule against
non-platform crypto applies here.

## Architecture decisions
- The export is written to a temporary file and atomically renamed, so FR-004 is
  a filesystem property rather than something the code has to remember to do.
- Signing happens over the serialized bytes, not over the in-memory model, so
  what is verified is exactly what is on disk.
- Streaming rather than materializing: 30 days of events on the oldest tablet does
  not fit comfortably in memory alongside the app.
