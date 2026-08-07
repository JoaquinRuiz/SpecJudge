# Feature Specification: Offline Audit Log Export

## Summary
Ward tablets record every medication dispensing event locally. Pharmacy needs to
pull those events off a tablet that has not been online for days, as a signed
export a reviewer can open without the app.

## Requirements
- **FR-001**: The export MUST include every dispensing event recorded on the
  device since the last successful export, in the order they were recorded.
- **FR-002**: The export MUST be produced with no network access, since the
  tablets being exported are by definition the ones that cannot reach the server.
- **FR-003**: Each export MUST carry a signature a reviewer can verify against
  the device certificate, so an edited file is detectable.
- **FR-004**: A partially written export MUST NOT be readable as a valid one; an
  interrupted export leaves the device exactly as it was.

## Acceptance criteria
- **SC-001**: An export of 30 days of events on the oldest supported tablet
  completes in under 90 seconds without the app becoming unresponsive.
- **SC-002**: Verification of a tampered export fails, and the failure names the
  first event that does not match.
