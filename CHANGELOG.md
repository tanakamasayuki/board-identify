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
- Recover from a WCH-Link left holding a corrupted readback of its target, where the
  family byte stays correct but the chip ID and UUID come back as one repeating word.
  Reject the repeating reply, and make the probe look again when a signature resolves to
  no chip at all. Reproduced with probe-rs 0.32 on a CH32V003, from a read alone; the
  state survives detaching and power cycling the target, because it is the probe that is
  confused. Recovery uses `81 0d 01 03`, which clears it without resetting the target,
  rather than `wlink reset`, which clears it by resetting.
- Add `pyusb` as a dependency.
- Recognise boards from their USB VID/PID, held as a committed table in `arduino_ids`.
  `scripts/generate_usb_ids.py` merges it from `board_details.json`, a published dump of
  `arduino-cli board details`. Deliberately not read from a local Arduino installation: a
  board only appears there once its core is installed, and the boards worth identifying
  are the ones that have not been set up yet. 825 pairs, 677 of which name a board.
- Merge the table append-only and sorted by VID then PID, so a correction made by hand
  survives every later run, a board keeps the name it was published under even if upstream
  renames it, and a hand-added line in the wrong place is tidied up rather than rejected.
  Adding a pair to `GENERIC_BRIDGE_IDS` is how to make the table forget one.
- Add `UsbDescriptorProbe`, which names a board from that table plus its USB serial
  number. No USB traffic, no open of the tty, and no reset: an Arduino UNO R4 WiFi is
  published as `arduino-uno-r4-wifi-<serial>` from sysfs alone.
- Skip `esptool` on a port whose VID/PID a board definition attributes to another family.
  An Arduino UNO or a Nano Every is no longer bounced into its bootloader on every plug
  event to learn what its descriptors already said. An unknown pair still goes to
  `esptool`, and so does a board behind a stock USB-UART bridge.
- Never let a stock USB-UART bridge ID speak for the board behind it. CH340, CP2102,
  FT232, and PL2303 pairs are dropped during the merge and rejected again at lookup time,
  in both directions, so such a port is neither named from the table nor kept away from
  `esptool`. The Sony Spresense claims the stock CP2102 `10c4:ea60`, so without this every
  CP2102 board would be published as a Spresense and never reach `esptool`.
- Drop a pair Espressif and another family both claim, because leaving it out is what
  leaves the port open to `esptool`. Let an architecture named after a core rather than
  after silicon — `mbed`, `zephyr`, `host` — lose the tie instead of contesting it, so a
  Seeed XIAO nRF52840 packaged under both `mbed` and `nrf52` resolves to `nrf52`. A pair
  several boards of one family share keeps the family and loses the name.
- Leave Espressif boards to `esptool` even when the table names them, because the eFuse
  MAC outlives a bridge chip being replaced and a board must not have two names depending
  on which probe got there first.
- Drop accents in `normalize_component()` rather than treating them as punctuation, so
  `Arduino Yún` folds to `arduino-yun` instead of `arduino-y-n`.
