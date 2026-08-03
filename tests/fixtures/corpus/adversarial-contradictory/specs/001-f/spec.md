# Feature Specification: Usage Reports

## Summary
Generate weekly usage reports per customer and email them.

## Requirements
- **FR-001**: Reports MUST be generated weekly for every customer.
- **FR-002**: Report generation MUST run entirely on the user's device, since no
  personal data may leave it.
- **FR-003**: Reports MUST aggregate usage across all of a customer's devices,
  including devices that have been offline for the whole week.
- **FR-004**: The weekly email MUST be sent from the server even when the user's
  device has not been online.

## Notes
FR-002 and FR-003 have not been reconciled.
