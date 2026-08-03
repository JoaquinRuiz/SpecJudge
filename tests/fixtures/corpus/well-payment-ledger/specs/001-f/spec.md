# Feature Specification: Double-Entry Payment Ledger


    ## Summary
    A ledger recording money movements between accounts as balanced double entries,
    with idempotent posting, multi-currency balances and a reconciliation report
    against an external processor's settlement file.

    ## Requirements
    - **FR-001**: Every transaction MUST consist of entries that sum to zero per currency.
    - **FR-002**: Posting MUST be idempotent under a caller-supplied key, including
      under concurrent retries of the same key.
    - **FR-003**: Balances MUST be derivable at any past instant without mutating history.
    - **FR-004**: Reconciliation MUST classify each settlement line as matched,
      missing or disputed, and MUST NOT auto-correct a discrepancy.
    - **FR-005**: Rounding on currency conversion MUST NOT create or destroy value
      across a transaction.

    ## Success Criteria
    - **SC-001**: Ten thousand concurrent postings leave the ledger balanced.
