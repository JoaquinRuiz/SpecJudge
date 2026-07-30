# Feature Specification: Team Task Manager

## Summary

A small web application where a team creates tasks, assigns them to members and
tracks completion. Single service, single relational database, no real-time
collaboration and no offline mode.

## User Scenarios

- **US1**: As a team member I create a task with a title and an optional due date,
  so the work is recorded somewhere the team can see.
- **US2**: As a team member I assign a task to a colleague, so ownership is explicit.
- **US3**: As a team member I mark a task complete, so the board reflects reality.
- **US4**: As a team lead I filter the board by assignee and by state, so I can see
  what a given person still owes.

## Requirements

- **FR-001**: Users MUST be able to create a task with a title; the title MUST be
  non-empty and at most 200 characters.
- **FR-002**: Users MUST be able to assign a task to exactly one team member.
- **FR-003**: Users MUST be able to mark a task complete, and to reopen it.
- **FR-004**: The system MUST persist tasks across restarts.
- **FR-005**: The board MUST be filterable by assignee and by completion state.
- **FR-006**: Rejected operations MUST return an error naming the field at fault.

## Out of Scope

Real-time collaboration, offline mode, recurring tasks, notifications, and any
form of permission model beyond "member of the team".

## Success Criteria

- **SC-001**: A user can create and complete a task in under 10 seconds.
- **SC-002**: The board renders in under 200 ms for a team of 20 with 500 tasks.
