# AGENTS.md

## Regulatory context

This is medical device software (IEC 62304, safety class B). Two consequences
apply to every change, including ones the feature spec does not mention:

- Every commit references the requirement id it implements. A change with no
  traceable requirement cannot ship, however small it is.
- Crypto comes from the platform keystore only. Bundling a crypto library, or
  vendoring one, requires a supplier assessment that takes months.

## Working in this repo

- The oldest supported tablet is a 2019 device with 2 GB of RAM. "It works on my
  emulator" has never once predicted whether something works on the ward.
- Changes to `data/` require a schema migration with a downgrade path: tablets
  come back from wards running builds a year old.
