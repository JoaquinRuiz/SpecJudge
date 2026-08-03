# Feature Specification: YAML Config Linter


    ## Summary
    A command-line linter for a fixed YAML configuration schema. Reads a file,
    reports rule violations with line numbers, exits non-zero when any error-level
    rule fires.

    ## Requirements
    - **FR-001**: The linter MUST report the line and column of each violation.
    - **FR-002**: Rules MUST be individually disableable from the config file.
    - **FR-003**: The exit code MUST distinguish clean, warnings-only and errors.
