# Tasks: Team Task Manager

## Phase 1: Setup

- [ ] T001 Create the project structure with `src/` and `tests/` and wire the test runner
- [ ] T002 Add the web framework and database driver dependencies and pin them
- [ ] T003 Configure the database connection and migration tooling

## Phase 2: Core

- [ ] T004 Implement the Task model with title, assignee, due date and completion state in `src/models/task.py`
- [ ] T005 Implement the team member model and the assignee relation in `src/models/member.py`
- [ ] T006 Implement the task creation endpoint with title validation in `src/api/tasks.py`
- [ ] T007 Implement the assignment endpoint rejecting unknown members in `src/api/tasks.py`
- [ ] T008 Implement complete and reopen transitions in `src/api/tasks.py`
- [ ] T009 Implement the persistence layer with the task repository in `src/storage/repo.py`
- [ ] T010 Implement board filtering by assignee and completion state in `src/api/board.py`

## Phase 3: Polish

- [ ] T011 Add integration tests for the create, assign and complete flow in `tests/integration/test_tasks.py`
- [ ] T012 Add error responses naming the offending field for every rejected operation
- [ ] T013 Add an index on assignee and completion state to keep board queries under 200 ms
