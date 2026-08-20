# Architecture

*[English](architecture.md) | [日本語](architecture.ja.md)*

`board-identify` separates three identities:

- **Port**: the transient kernel node, such as `/dev/ttyUSB2`.
- **Transport**: the USB interface or USB-UART bridge, such as CH340, FTDI, or a
  WCH-Link debug probe.
- **Target**: the microcontroller board behind the transport.

One port can be worth naming more than once. A plain USB-UART bridge is not interesting
in itself, but a debug probe is: it has its own serial number, and the board on its debug
pins can be swapped for another. A probe therefore returns a list of identifications,
most specific first, and each one becomes its own link to the same port.

The publisher creates one atomic symlink per identification in
`/run/board-identify/by-id/` and records the whole set as state keyed by the transient
port name.

## Modules

| Module | Responsibility |
| --- | --- |
| `paths` | Runtime layout: `by-id/` links and `state/` files. |
| `model` | `Identification`, the result of one probe. |
| `normalize` | Folding chip names and unique IDs into safe components. |
| `usbinfo` | USB metadata for a port, read from sysfs without opening it. |
| `probes/` | One class per target family, selected by `identify_port()`. |
| `identify` | Probe dispatch, `publish()`, `remove_port()`. |
| `cleanup` | Sweep of links and state left behind by disconnected devices. |
| `cli` | `identify`, `remove`, and `cleanup` subcommands. |

## Runtime layout

```text
/run/board-identify/
├── by-id/
│   ├── esp32-s3-7cdfa1123456 -> /dev/ttyUSB2
│   ├── ch32x035c8t6-1ff9abcd880ebc48 -> /dev/ttyACM4
│   └── wch-link-fc928f068181 -> /dev/ttyACM4
└── state/
    ├── ttyACM4.json
    └── ttyUSB2.json
```

Links are keyed by board, state files by port, and one state file can claim several
links:

```json
{
  "port": "/dev/ttyACM4",
  "board_ids": [
    "ch32x035c8t6-1ff9abcd880ebc48",
    "wch-link-fc928f068181"
  ],
  "identifications": [ ... ]
}
```

Both are written to a temporary name and moved into place with `os.replace()`, so a
reader never observes a partial link or a half-written state file.

## Lifecycle

1. udev sees a new `ttyUSB*` or `ttyACM*` node and starts `board-identify@<port>.service`.
2. `identify_port()` asks each probe whether it supports the port, then to identify it.
3. `publish()` writes one link per identification plus the state file. A name the port
   claimed last time but not this time is dropped first, so a target unplugged from its
   debug probe does not leave a link behind.
4. When the device disappears, the unit is stopped through `BindsTo=`, and its
   `ExecStop=` runs `board-identify remove <port>`.
5. `board-identify cleanup` additionally sweeps links and state that were left behind,
   for instance after a reboot of the daemon or an unclean stop.

## Debug probes

A debug probe is a transport that knows what is on the other end of itself, so it is
identified in two steps.

1. **From descriptors, always.** sysfs gives the VID/PID and the serial number without
   any USB traffic and without opening the tty, which names the probe itself. This step
   cannot fail and cannot disturb anything.
2. **From the target, when asked to.** Claiming the probe's vendor interface and running
   a short command sequence yields the attached chip's signature and its factory UUID,
   which names the board. `--no-target-probe` skips this step entirely, leaving the run
   with no USB traffic at all.

The probe's own link is named from descriptors alone on purpose. The model letter a
WCH-Link reports over its vendor interface would be a nicer name, but it is unavailable
whenever a debug session already holds that interface, and a name that depends on who
else is running is not a stable name. It is recorded as the transport instead.

## Why not the standard mechanisms

`/dev/serial/by-id/`, `/dev/serial/by-path/`, and a udev rule matching
`ATTRS{idVendor}`, `ATTRS{idProduct}`, and `ATTRS{serial}` are the right answer whenever
they apply, and they cost nothing at plug time. This project targets what is left:

- Adapters that report no serial number, such as most CH340 modules, so `by-id` collapses
  several boards onto one name.
- Devices forwarded into WSL over USB/IP, where the Windows bus ID is invisible to Linux
  and `by-path` reflects the attach order on `vhci_hcd` rather than physical topology.

In both cases the only identifier that survives a re-attach comes from the target itself,
which is what a probe reads.

## Known limitations

- Talking to a target disturbs it. `esptool` toggles DTR/RTS to enter the bootloader, so
  the firmware restarts on every plug event; a WCH-Link attach holds the core and
  releases it again, which interrupts timing rather than restarting. Either way this is a
  development-environment tool, not something for an environment that must stay stable.
- Descriptors are enough for some devices — a WCH-Link is recognised by VID/PID, which
  ends the probe chain before `esptool` runs — but there is no general descriptor fast
  path yet. A port that no probe recognises from sysfs is still identified by talking to
  it.
- Naming a target from a lookup table means a chip the table does not list falls back to
  its series, or to its raw signature. Adding the entry later renames the link: a name
  change across an upgrade rather than across a re-attach.
- A debug probe whose vendor interface is already claimed, by a running debug session,
  cannot be asked about its target. The probe itself is still named from its descriptors,
  so that port publishes fewer links than usual until the next plug event.
- A stale link cannot be detected once the kernel has handed the same node name to
  another device. That case is resolved by the next `publish()` for that port, not by
  `cleanup`.
- Two ports reporting the same board ID share one link; the last publish wins. The older
  port keeps the links it still owns, and its state is dropped by the next cleanup once
  it owns none of them.

See also [Identifier format](identifier-format.md), [Adding a probe](adding-a-probe.md), and
[Operations](operations.md).
