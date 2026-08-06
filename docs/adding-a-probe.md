# Adding a probe

1. Add a class under `src/board_identify/probes/`.
2. Implement `supports(port)` and `identify(port)`.
3. Return `Identification` only when the target is positively identified.
4. Register the probe in `default_probes()`.
5. Add fixture-based unit tests.

A transport USB serial number should normally be recorded as metadata rather than used as the target unique ID.
