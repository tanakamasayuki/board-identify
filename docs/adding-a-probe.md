# Adding a probe

*[English](adding-a-probe.md) | [日本語](adding-a-probe.ja.md)*

1. Add a class under `src/board_identify/probes/`.
2. Implement `supports(port)` and `identify(port)`, matching the `Probe` protocol in
   `probes/base.py`.
3. Return an `Identification` for each identity the port has, most specific first, and
   an empty list when nothing is positively identified.
4. Register the probe in `default_probes()` in `identify.py`.
5. Add fixture-based unit tests.

A transport USB serial number is normally recorded as metadata rather than used as the
target unique ID. A debug probe is the exception: it is a device in its own right, so it
earns its own `Identification` alongside the target's.

## Contract

- `supports()` must be cheap and must not open the port. It is a pre-filter, not a
  positive match. Reading sysfs through `usbinfo` is cheap enough; opening the tty or
  talking over USB is not.
- `identify()` must return an empty list for anything it does not recognise, including
  timeouts, non-zero exit statuses of external tools, and output it cannot parse. It
  must not raise for an unresponsive device.
- `identify()` runs on a live device; assume any other probe may have reset it first.
  Keep probes ordered from least to most intrusive in `default_probes()`.
- Every returned `Identification` must describe the port that was passed in; `publish()`
  rejects a mixed set.
- Anything that disturbs the target belongs behind `probe_target`, which
  `default_probes()` passes on and `--no-target-probe` turns off. With it off a probe must
  do no more than read descriptors.
- Normalise through `normalize_component()` and `normalize_unique_id()`, and treat
  their `ValueError` as "not identified".

## Testable structure

Keep parsing separate from I/O so tests do not need hardware. `EspressifProbe` splits
into `identify()` (runs the subprocess) and `parse()` / `extract_*()` (pure functions
over captured output). `WchLinkProbe` splits three ways: `query()` opens the device,
`session()` drives the command sequence against any object with `read`/`write`, and the
`parse_*()` functions decode single replies.

Record real device output under `tests/fixtures/<tool>/` and load it with the
`esptool_output` or `wch_reply` fixture pattern in `tests/conftest.py`. Include at least
one success case and one failure case, such as a device that did not answer. A probe that
reads sysfs can be tested against the `sysfs` fixture, which builds a tree shaped like a
real USB serial port.

See also [Architecture](architecture.md) and [Identifier format](identifier-format.md).
