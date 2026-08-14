# Architecture

*[English](architecture.md) | [日本語](architecture.ja.md)*

`board-identify` separates three identities:

- **Port**: the transient kernel node, such as `/dev/ttyUSB2`.
- **Transport**: the USB interface or USB-UART bridge, such as CH340 or FTDI.
- **Target**: the microcontroller board behind the transport.

A target probe produces a stable board identifier. The publisher then creates an atomic symlink in `/run/board-identify/by-id/` and stores state keyed by the transient port name.

## Modules

| Module | Responsibility |
| --- | --- |
| `paths` | Runtime layout: `by-id/` links and `state/` files. |
| `model` | `Identification`, the result of one probe. |
| `normalize` | Folding chip names and unique IDs into safe components. |
| `probes/` | One class per target family, selected by `identify_port()`. |
| `identify` | Probe dispatch, `publish()`, `remove_port()`. |
| `cleanup` | Sweep of links and state left behind by disconnected devices. |
| `cli` | `identify`, `remove`, and `cleanup` subcommands. |

## Runtime layout

```text
/run/board-identify/
├── by-id/
│   └── esp32-s3-7cdfa1123456 -> /dev/ttyUSB2
└── state/
    └── ttyUSB2.json
```

The link is keyed by board, the state file by port. Both are written to a temporary
name and moved into place with `os.replace()`, so a reader never observes a partial
link or a half-written state file.

## Lifecycle

1. udev sees a new `ttyUSB*` or `ttyACM*` node and starts `board-identify@<port>.service`.
2. `identify_port()` asks each probe whether it supports the port, then to identify it.
3. `publish()` writes the link and the state file. A link previously published for the
   same port under a different board ID is removed first.
4. When the device disappears, the unit is stopped through `BindsTo=`, and its
   `ExecStop=` runs `board-identify remove <port>`.
5. `board-identify cleanup` additionally sweeps links and state that were left behind,
   for instance after a reboot of the daemon or an unclean stop.

## Known limitations

- Probing is intrusive. `esptool` toggles DTR/RTS, which resets the attached board and
  can interrupt an application running on a non-Espressif device on the same port.
- A stale link cannot be detected once the kernel has handed the same node name to
  another device. That case is resolved by the next `publish()` for that port, not by
  `cleanup`.
- Two ports reporting the same board ID share one link; the last publish wins and the
  state of the older port is dropped by the next cleanup.

See also [Identifier format](identifier-format.md) and [Adding a probe](adding-a-probe.md).
