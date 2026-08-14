# Adding a probe

*[English](adding-a-probe.md) | [日本語](adding-a-probe.ja.md)*

1. Add a class under `src/board_identify/probes/`.
2. Implement `supports(port)` and `identify(port)`, matching the `Probe` protocol in
   `probes/base.py`.
3. Return `Identification` only when the target is positively identified.
4. Register the probe in `default_probes()` in `identify.py`.
5. Add fixture-based unit tests.

A transport USB serial number should normally be recorded as metadata rather than used as the target unique ID.

## Contract

- `supports()` must be cheap and must not open the port. It is a pre-filter, not a
  positive match.
- `identify()` must return `None` for anything it does not recognise, including
  timeouts, non-zero exit statuses of external tools, and output it cannot parse. It
  must not raise for an unresponsive device.
- `identify()` runs on a live device; assume any other probe may have reset it first.
  Keep probes ordered from least to most intrusive in `default_probes()`.
- Normalise through `normalize_component()` and `normalize_unique_id()`, and treat
  their `ValueError` as "not identified".

## Testable structure

Keep parsing separate from I/O so tests do not need hardware. `EspressifProbe` splits
into `identify()` (runs the subprocess) and `parse()` / `extract_*()` (pure functions
over captured output).

Record real tool output under `tests/fixtures/<tool>/` and load it with the
`esptool_output` fixture pattern in `tests/conftest.py`. Include at least one success
case and one failure case, such as a device that did not answer.

See also [Architecture](architecture.md) and [Identifier format](identifier-format.md).
