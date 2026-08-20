# Changelog

*[English](CHANGELOG.md) | [日本語](CHANGELOG.ja.md)*

## Unreleased

- Add initial Espressif identification scaffold.
- Add udev and systemd integration examples.
- Add a `remove` subcommand and a global `--runtime-dir` option.
- Follow the esptool 4/5 subcommand rename and force plain, unwrapped tool output.
- Prefer the `MAC:` line over `BASE MAC:` when reading the target MAC.
- Drop the previously published link when a port is republished under a new board ID.
- Remove the matching link together with the state of a disconnected port.
- Publish English and Japanese documentation side by side.
- Document the standard alternatives (`/dev/serial/by-id`, `by-path`, udev rules) and
  when to prefer them.
- Document the WSL + USB/IP target environment, where the Windows bus ID is invisible to
  Linux and `by-path` follows the attach order.
- State that probing disturbs the board and that this is a development-environment tool.
- Document the USB/IP auto-attach trade-off: arbitrary attach order versus a fixed manual
  ritual, and the occasional lost attachment that auto-attach recovers from.
- Identify WCH-Link debug probes from their USB descriptors in sysfs, with no USB traffic
  and without opening the port. This is the first non-invasive identification path, and it
  ends the probe chain before `esptool` runs on a probe's UART.
- Identify the WCH RISC-V target behind a WCH-Link from its chip signature and factory
  UUID, naming it by orderable part number where the signature is known, and falling back
  to the series and then to raw hex.
- Publish one link per identity of a port, so a debug probe and the board on its debug
  pins each get their own name pointing at the same tty. `publish()`, `identify_port()`,
  and `Probe.identify()` now work in lists, and a state file records `board_ids` rather
  than a single `board_id`.
- Drop only the names a port stops claiming when it is republished, so unplugging a target
  from its probe leaves the probe's own link alone.
- Add `identify --no-target-probe`, which stays on USB descriptors and issues no USB
  traffic at all.
- Add `usbinfo`, which reads a port's USB metadata from sysfs without opening it.
- Report `identify --json` as a list of identifications under a single `port`.
- Add `pyusb` as a dependency.
