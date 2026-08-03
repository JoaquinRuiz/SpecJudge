# Feature Specification: Team Notes

## Summary
A notes app where a team writes shared notes. Clean CRUD over a small data model.

## Requirements
- **FR-001**: Users MUST be able to create a note with a title and body.
- **FR-002**: Users MUST be able to edit and delete their own notes.
- **FR-003**: Notes MUST be listed newest first.
- **FR-004**: Two people editing the same note offline MUST both keep their work,
  and the merged result MUST converge to the same state on every device without
  a server round trip to arbitrate.
- **FR-005**: The UI MUST show a note's edit history.

## Success Criteria
- **SC-001**: A note opens in under 200 ms.
