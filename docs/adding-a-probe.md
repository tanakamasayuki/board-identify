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
earns its own `Identification` alongside the target's. A board whose USB device is the
board — the case `UsbDescriptorProbe` covers — is the other: there is no transport to
confuse it with, so the serial number identifies the unit and `id_source` is `usb-serial`.

A probe that can read an identifier out of the silicon should take precedence over the
descriptors even so. `UsbDescriptorProbe` declines Espressif boards for that reason: the
eFuse MAC outlives a bridge chip being replaced, and a board must not have two names
depending on which probe got there first.

## Contract

- `supports()` must be cheap and must not open the port. It is a pre-filter, not a
  positive match. Reading sysfs through `usbinfo` is cheap enough; opening the tty or
  talking over USB is not.
- A probe that talks to the target should decline a port whose descriptors already name
  another family. `board_for_port()` in `usb_ids` answers that from sysfs, and returns
  None for anything it may not speak for, including stock USB-UART bridge IDs. Ruling a
  port out this way is what keeps a board that cannot answer from being reset to prove it.
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

A probe backed by a lookup table keeps the table in its own module and the decisions in
code, the way `UsbDescriptorProbe` splits into `arduino_ids` (data, merged and committed),
`usb_ids` (what a pair may be taken to mean), and the probe itself (what to publish).

Record real device output under `tests/fixtures/<tool>/` and load it with the
`esptool_output` or `wch_reply` fixture pattern in `tests/conftest.py`. Include at least
one success case and one failure case, such as a device that did not answer. A probe that
reads sysfs can be tested against the `sysfs` fixture, which builds a tree shaped like a
real USB serial port.

See also [Architecture](architecture.md) and [Identifier format](identifier-format.md).
