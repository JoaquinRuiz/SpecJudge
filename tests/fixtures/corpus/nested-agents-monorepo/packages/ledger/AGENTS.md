# AGENTS.md — ledger

The append-only record of every observation recorded at a trial site. It is the
regulatory artifact: what this package writes is what an auditor reads years later.

- Nothing here is ever updated or deleted. A correction is a new entry that
  references the one it corrects, and both stay visible forever.
- Ordering is per site and per subject, not global. Two sites recording at the
  same instant is normal and must not be resolved by inventing a total order.
- Every write is signed with the site key. An entry that cannot be attributed to
  a site is a data integrity incident, not a bug to patch quietly.
