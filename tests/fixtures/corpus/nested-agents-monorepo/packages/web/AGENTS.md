# AGENTS.md — web

The tablet interface nurses use at the bedside, offline for most of a shift.

- Every form saves locally first and syncs later. A save that depends on the
  network is a bug, however fast the network is in the office.
- Nothing is auto-corrected. A value that looks wrong is shown as entered, with a
  warning; silently fixing a dose is the failure mode this package exists to avoid.
- Supported hardware is a 2019 tablet with 2 GB of RAM.
