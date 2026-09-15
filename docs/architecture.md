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

One board can be reachable through more than one port, which is the same thing from the
other side. An ESP32-S3 with its own USB peripheral wired up next to a CH340 on the same
UART answers on two ports at once, and both read the same eFuse MAC, so both resolve to
the same board ID. Each identification therefore also carries the **kind** of transport it
came through — `uart`, `usb` or `probe` — and publishes a qualified link of its own
alongside the shared board name. See [Two ports, one board](#two-ports-one-board).

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
| `usb_ids` | What a VID/PID pair may be taken to mean, and what it may not, and which kind of transport it is. |
| `arduino_ids` | Generated: the pairs the installed Arduino board definitions claim. |
| `probes/` | One class per target family, selected by `identify_port()`. |
| `identify` | Probe dispatch, `publish()`, `remove_port()`. |
| `variants` | Chip names learned from a target, for the ports that cannot ask. |
| `cleanup` | Sweep of links and state left behind by disconnected devices. |
| `cli` | `identify`, `remove`, and `cleanup` subcommands. |

## Runtime layout

```text
/run/board-identify/
├── by-id/
│   ├── esp32-s3-7cdfa1123456 -> /dev/ttyUSB2
│   ├── esp32-s3-7cdfa1123456-uart -> /dev/ttyUSB2
│   ├── esp32-s3-7cdfa1123456-usb -> /dev/ttyACM12
│   ├── ch32x035c8t6-1ff9abcd880ebc48 -> /dev/ttyACM4
│   ├── ch32x035c8t6-1ff9abcd880ebc48-probe -> /dev/ttyACM4
│   ├── wch-link-fc928f068181 -> /dev/ttyACM4
│   └── wch-link-fc928f068181-probe -> /dev/ttyACM4
├── state/
│   ├── ttyACM4.json
│   ├── ttyACM12.json
│   └── ttyUSB2.json
└── variants.json
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

## Two ports, one board

A board ID names the board. It says nothing about how the host reaches it, which is
deliberate — the whole point is that the name survives a re-attach — but it means two
ports onto one chip produce one name between them. The qualified name closes that gap:
`<board-id>-<transport kind>` belongs to a single port, so a script that means *the CH340
in front of this ESP32-S3* can say so, and a script that just means *this board* uses the
unqualified name.

The unqualified name goes to the preferred claimant while several hold the board at once:

| Kind | | Why |
| --- | --- | --- |
| `uart` | a USB-UART bridge | Stays enumerated while the target resets. |
| `probe` | a debug probe's serial interface | The same, and it survives the target being held. |
| `usb` | the target's own USB peripheral | Goes down with the chip, taking its tty with it. |

A name pinned to a native USB port would blink out on every reset and every upload, so
the bridge wins. Between two claims of the same kind the more recent one wins, and the
port name breaks a remaining tie, so the answer never depends on the order events arrived
in. The qualified names stay valid either way; this only decides which link is the
convenient one.

A state file is therefore a **claim** and not a receipt. A port that lost the shared name
to another port keeps its record, which is what lets the name come back when the holder
goes away: `settle()` re-points the unqualified link at the best remaining live claimant,
and removes it only when nothing claims the board any more. `publish()`, `remove_port()`
and `cleanup()` all end by settling every name they touched.

## Lifecycle

1. udev sees a new `ttyUSB*` or `ttyACM*` node and starts `board-identify@<port>.service`.
2. `identify_port()` asks each probe whether it supports the port, then to identify it.
3. `publish()` writes the state file first, then one qualified link per identification,
   then settles each unqualified name. A name the port claimed last time but not this
   time is released first, so a target unplugged from its debug probe does not leave a
   link behind.
4. When the device disappears, the unit is stopped through `BindsTo=`, and its
   `ExecStop=` runs `board-identify remove <port>`.
5. `board-identify cleanup` additionally sweeps links and state that were left behind,
   for instance after a reboot of the daemon or an unclean stop.

## The descriptor table

`arduino_ids` maps a USB VID/PID pair to `(family, platform, variant)`. It is merged from
[`board_details.json`](https://tanakamasayuki.github.io/arduino-cli-helper/board_details.json),
a published dump of `arduino-cli board details`, by `scripts/generate_usb_ids.py`, and
committed.

Reading a local Arduino installation instead would have been the obvious thing to do and
is the wrong answer twice over. A board only appears under `~/.arduino15` once its core is
installed, and the boards worth identifying are the ones that have not been set up yet.
Identification also runs from udev, where `$HOME` is not the user who installed anything,
so a name must not depend on which machine, or which user, the port was plugged into.

Two of the three fields are load bearing:

- `variant` names the board, and is None when several boards share the pair.
- `family` is the coarser claim, and the one that matters even when the name is missing:
  a pair that belongs to another family cannot be an Espressif target, so `EspressifProbe`
  declines the port instead of resetting a board to find out.

The merge is append-only. An entry already in the table may have been corrected by hand,
and a board already published under one name must keep it even if upstream renames the
board, so the generator only ever adds. Entries are sorted by VID then PID on the way out,
which keeps hand editing and machine merging from fighting over the file.

A board's family comes from the architecture of the platform its FQBN names. Architectures
named after a core or an OS rather than after silicon — `mbed`, `zephyr`, `host` — still
produce a family, but lose the tie when another claimant of the same pair disagrees: a
Seeed XIAO nRF52840 is packaged under both `mbed` and `nrf52`, and only the second says
what the chip is.

`usb_ids` holds what does not come from Arduino. Stock USB-UART bridge IDs — CH340,
CP2102, FT232, PL2303 — name the cable, so they are filtered out during the merge *and*
rejected again in `board_for_usb_id()`. The second check is not redundant: it keeps a
table merged against a future source that does claim a stock bridge ID from speaking for
every board behind one. The filter is deliberately symmetric — such a pair neither names
a board nor rules a probe out — because a CH340 in front of an ESP32 is the case this
project exists for.

That guard is load bearing today, not a precaution: the Sony Spresense claims the stock
CP2102 `10c4:ea60`. Without it, every CP2102 board on the machine would be published as a
Spresense and kept away from `esptool`. Dropping it costs a real Spresense its descriptor
name and an `esptool` connect attempt, which is the cheaper mistake by a wide margin.

A pair Espressif and another family both claim is dropped rather than resolved, because
leaving it out of the table is what leaves the port open to `esptool` — the only thing
left that can tell the two apart.

## Espressif native USB

An Espressif chip with its own USB peripheral publishes its eFuse MAC as the USB serial
descriptor: `/dev/serial/by-id/usb-Espressif_USB_JTAG_serial_debug_unit_30:ED:A0:E3:14:78`
is the same identifier `esptool` reads, sitting in sysfs. What is *not* in the descriptors
is the chip name, because every ESP32 with a USB-Serial/JTAG reports `303a:1001`, S3, C3
and P4 alike — which is why `arduino_ids` holds that pair with no variant.

Running `esptool` on such a port to find out costs the port itself. The reset at the end of
the run re-enumerates the device, the tty disappears a second or two after it was named,
`ExecStop=` drops the link, and the re-enumeration starts the whole thing again. Left
alone it does not converge.

So `EspressifProbe` takes the descriptor path whenever it can, and only the chip name has
to come from somewhere else. `variants` is that somewhere: every identification made from
the silicon records `unique ID -> chip name`, so the CH340 in front of the same chip, or
the same native port after it re-enumerated, names the board from sysfs alone — no USB
traffic, no reset. A target nothing has ever reached still falls back to `esptool`, once,
and fills the cache on the way through.

The cache lives in the runtime directory and does not survive a reboot. It does not need
to: at boot udev walks every tty again, and the first port to reach the target refills it.

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

A third step runs only when it has to. Some tools leave the *probe* holding a broken
readback of its target: the family byte stays correct, but the chip ID and the UUID come
back as one four-byte word repeated, and stay that way across further attach cycles.
Detaching does not clear it, and neither does power cycling the target — it is the probe
that is confused, not the board. Publishing that reading would be worse than publishing
nothing, because the bogus UUID is identical for every board in that state, so when a
signature resolves to no chip at all the probe is told to look again with `81 0d 01 03`
and the target is read once more. `wlink reset` also clears it, but only as a side effect
of forcing the re-read: measured through the debug module's sticky `havereset` bits,
`81 0b 01 01` resets the target and `81 0d 01 03` does not. Recovery uses the one that
does not, so identification still never resets a WCH target.

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
- The descriptor table is only as current as the last merge, and only as broad as the
  board list upstream covers. A board neither lists is probed by talking to it, as before.
- Descriptors name a model, not a unit. A board that reports no USB serial number, such as
  many Arduino UNO R3 revisions, is recognised well enough to keep `esptool` away from it
  and still cannot be published under a stable name.
- A family is inferred from the architecture an entry's platform names. A package that
  mixed silicon families under one architecture would attribute its boards to the wrong
  one, and an Espressif board in such a package would lose its `esptool` pass.
- A board whose descriptors are only claimed by a stock USB-UART bridge ID cannot be
  recognised at all, by construction. The Sony Spresense is the current example.
- Naming a target from a lookup table means a chip the table does not list falls back to
  its series, or to its raw signature. Adding the entry later renames the link: a name
  change across an upgrade rather than across a re-attach.
- A debug probe whose vendor interface is already claimed, by a running debug session,
  cannot be asked about its target. The probe itself is still named from its descriptors,
  so that port publishes fewer links than usual until the next plug event.
- A stale link cannot be detected once the kernel has handed the same node name to
  another device. That case is resolved by the next `publish()` for that port, not by
  `cleanup`.
- The descriptor path needs a serial descriptor that is the MAC, which is what the
  USB-Serial/JTAG peripheral reports. Firmware that brings up a CDC class of its own can
  put anything there, and such a port goes to `esptool` with the re-enumeration that costs.
- A claim is only as fresh as the plug event that made it. A board moved from one debug
  probe to another, both of them still connected, leaves the first probe claiming a target
  that is no longer on its pins, and that claim can take the board name back when the
  second probe is unplugged. Only re-triggering the first port corrects it.

See also [Identifier format](identifier-format.md), [Adding a probe](adding-a-probe.md), and
[Operations](operations.md).
