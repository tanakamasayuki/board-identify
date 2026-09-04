# board-identify

*[English](README.md) | [日本語](README.ja.md)*

Identify microcontroller boards connected through serial devices and publish stable symlinks based on hardware identifiers.

## Initial scope

Espressif devices are identified through `esptool`, WCH-Link debug probes are identified
along with whatever board is on their debug pins, and a board whose USB descriptors an
installed Arduino board definition recognises is named from sysfs alone:

```text
/run/board-identify/by-id/esp32-s3-7cdfa1123456          -> /dev/ttyUSB2
/run/board-identify/by-id/ch32x035c8t6-1ff9abcd880ebc48  -> /dev/ttyACM4
/run/board-identify/by-id/wch-link-fc928f068181          -> /dev/ttyACM4
/run/board-identify/by-id/arduino-uno-r4-wifi-3436733... -> /dev/ttyACM0
```

The USB transport and the target board are treated separately. A CH340, FTDI, or CP210x
serial number identifies the adapter, not necessarily the board behind it. A debug probe
is both at once, so it gets a link of its own next to the one for its target.

## Use the standard mechanisms first

This tool exists for the cases the standard Linux mechanisms cannot cover. **If any of
the following works for your boards, use it instead** — it is stable, non-intrusive, and
needs nothing installed:

```bash
# A per-device link built from USB VID/PID and the iSerial descriptor.
ls -l /dev/serial/by-id/

# A link built from the physical USB port path.
ls -l /dev/serial/by-path/

# What udev knows about a port.
udevadm info -q property -n /dev/ttyUSB0 | grep -E 'ID_VENDOR_ID|ID_MODEL_ID|ID_SERIAL_SHORT|ID_PATH'
```

A udev rule pinning one adapter by its descriptors:

```udev
SUBSYSTEM=="tty", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", ATTRS{serial}=="0001B2C3", SYMLINK+="esp32-lab1"
```

That covers adapters with a unique serial number (most FTDI, most CP210x, native-USB
boards such as the ESP32-S3/C3 USB-Serial/JTAG, RP2040, and many Arduino boards), and
fixed physical ports through `by-path`.

Reach for `board-identify` only when neither applies, for example a CH340 that reports no
serial number at all, several identical adapters, or the WSL + USB/IP case below.

A debug probe is a case of its own: `by-id` names the probe, which is often not what you
mean. The UART on a WCH-LinkE already appears as
`/dev/serial/by-id/usb-wch.cn_WCH-Link_FC928F068181-if01`, but that name follows the
probe, not the board. Swap the board on its debug pins and the name does not change. If
you want a name that follows the board instead, that is what the WCH-Link probe below is
for.

## Target environment: Linux on WSL over USB/IP

The main target is Linux running under WSL with devices forwarded by
[usbipd-win](https://github.com/dorssel/usbipd-win). This is where the standard
mechanisms break down:

- The Windows-side bus ID (`1-4` in `usbipd list`) does not exist inside Linux, so it
  cannot be matched in a udev rule.
- Forwarded devices appear on the virtual host controller, so `ID_PATH` and
  `/dev/serial/by-path/` look like `platform-vhci_hcd.0-usb-0:1:1.0`. The port number
  comes from the attach order, not from physical topology, and changes when devices are
  attached in a different order.
- `/dev/serial/by-id/` still works when the adapter reports a serial number, and is the
  preferred option when it does.

`board-identify` therefore asks the target board itself for an identifier that survives
re-attach in any order.

### The auto-attach trade-off

`usbipd attach --auto-attach` is convenient — it forwards devices as they appear and
re-attaches them after a disconnect — but it attaches in whatever order the devices show
up. With adapters that report no serial number, such as most CH340 modules, there is then
no way to tell which `/dev/ttyUSB*` is which. You have to pick one of two:

- **Attach manually, always in the same order.** Port numbers become predictable, at the
  cost of a fixed ritual every session.
- **Use auto-attach together with a tool like this one**, which identifies the board
  itself so the order stops mattering.

USB/IP also drops attachments occasionally — a suspend, a Wi-Fi or VPN change on the
Windows side, or a USB glitch is enough. Without auto-attach, recovering means noticing
the loss and re-running the attach command by hand, which is the main reason to keep
auto-attach on and solve the ordering problem here instead.

## Debug probes

A WCH-Link is identified in two steps, and each step produces its own link.

```bash
sudo .venv/bin/board-identify identify /dev/ttyACM4
# /run/board-identify/by-id/ch32x035c8t6-1ff9abcd880ebc48 -> /dev/ttyACM4
# /run/board-identify/by-id/wch-link-fc928f068181         -> /dev/ttyACM4
```

- **The probe itself**, from USB descriptors in sysfs. No USB traffic, the tty is never
  opened, and nothing can be disturbed.
- **The board on its debug pins**, from the chip signature and the UUID programmed into
  it at the factory. This needs a short conversation on the probe's vendor interface,
  which holds the target's core for the duration and releases it again.

Some tools leave the probe holding a broken readback of its target, so that the chip ID
and the UUID come back as a repeating pattern that is the same for every board in that
state. When a signature resolves to no chip at all, the probe is told to look again and
the target is read once more, without resetting it; see
[A debug probe that reports the wrong chip](docs/operations.md#a-debug-probe-that-reports-the-wrong-chip).

Only the second step touches the target, and `--no-target-probe` turns it off:

```bash
sudo .venv/bin/board-identify identify --no-target-probe /dev/ttyACM4
# /run/board-identify/by-id/wch-link-fc928f068181 -> /dev/ttyACM4
```

The target link is named as specifically as the chip can be pinned down —
`ch32x035c8t6` rather than `ch32x035` when the signature is one this tool has a part
number for. Chip signatures are transcribed from
[probe-rs](https://github.com/probe-rs/probe-rs) and
[ch32fun](https://github.com/cnlohr/ch32fun); a signature neither of them lists falls
back to the series, and then to raw hex.

RISC-V mode (`1a86:8010`, `1a86:8012`) is what the target step needs. In ARM mode
(`1a86:8011`) the probe speaks CMSIS-DAP instead, so only the probe itself is named.

## Boards recognised from their USB descriptors

Arduino board definitions already record which VID/PID each board reports, one entry per
bootloader state. [`src/board_identify/arduino_ids.py`](src/board_identify/arduino_ids.py)
holds 825 of those pairs, 677 of which name a single board.

The table is **not** read from a local Arduino installation, and installing a core is not
what puts a board in it. A board only appears under `~/.arduino15` once its core has been
set up, and the boards worth identifying are exactly the ones that have not been set up
yet — you plug an unfamiliar board in *to find out what it is*. The table is merged
instead from [`board_details.json`](https://tanakamasayuki.github.io/arduino-cli-helper/board_details.json),
a periodically refreshed dump of `arduino-cli board details` covering a curated board
list, and committed.

It does two things, both from sysfs and both before the port is opened:

- **It names a board.** One with a unique USB serial number is published straight from its
  descriptors — an Arduino UNO R4 WiFi becomes
  `arduino-uno-r4-wifi-34367333130351f0c1c1` with no USB traffic and no reset.
- **It rules `esptool` out.** A pair a board definition attributes to another family is
  not an Espressif target, so the port is never opened and the board is never reset to
  learn what its descriptors already said. An Arduino UNO, a Raspberry Pi Pico, or an
  STM32 Nucleo is left alone instead of being bounced into its bootloader on every plug
  event.

Only the second point applies to Espressif boards themselves. Their eFuse MAC comes from
the silicon and outlives a bridge chip being replaced, so it is the better unique ID, and
a pair the table attributes to an ESP32 still goes to `esptool`. That includes
Arduino-branded ones: `2341:0070` is the Arduino Nano ESP32.

### What the table refuses to say

A stock USB-UART bridge ID — CH340, CP2102, FT232, PL2303 — identifies the cable and not
the board in front of it. Those pairs are dropped while the table is merged and rejected
again at lookup time, in both directions: such a port is never named from the table, and
it is never kept away from `esptool` either, because a CH340 in front of an ESP32 is the
case this project exists for.

This is not a theoretical guard. The Sony Spresense claims the stock CP2102 ID
`10c4:ea60`, so without it every CP2102 board on the machine — a large share of ESP32
development boards among them — would be published as a Spresense and would never reach
`esptool`. The price of dropping it is that a real Spresense is not recognised from its
descriptors either, and still gets an `esptool` connect attempt.

Two more cases are handled without dropping anything:

- **Espressif against another family.** A pair both claim is dropped, because leaving it
  out is what leaves the port open to `esptool`, the only thing left that can tell them
  apart. None currently exists.
- **Several boards, one pair.** `303a:1001` is the generic ESP32 family device and
  `0483:5740` the generic STM32 virtual COM port; 148 pairs are shared like this. The
  family is kept, which is all that is needed to rule a probe in or out, and the name is
  dropped.

### Updating the table

```bash
uv run python scripts/generate_usb_ids.py            # fetch and merge
uv run python scripts/generate_usb_ids.py --check    # fail if anything would change
uv run python scripts/generate_usb_ids.py --input board_details.json   # offline
```

The merge is **append-only**: an existing entry is never rewritten or removed, so a
correction made by hand survives every later run, and a board already published under one
name keeps it even if upstream renames the board. Entries are sorted by VID then PID
before the file is written, so a hand-added line in the wrong place is tidied up rather
than rejected. What was dropped, and why, is reported on stderr.

To make the table forget a pair, add it to `GENERIC_BRIDGE_IDS` in
[`src/board_identify/usb_ids.py`](src/board_identify/usb_ids.py) — deleting the line by
hand only lasts until the next run.

## Requirements

Install [uv](https://docs.astral.sh/uv/) before setting up the project.

## Development setup

```bash
uv sync
```

Run the checks:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
```

The version lives in `src/board_identify/__init__.py` and nowhere else;
`pyproject.toml` reads it from there. Releases are cut by the `Release` workflow from the
Actions tab, which runs those checks, moves the changelog's `## Unreleased` entries into a
`## <version>` section, tags `v<version>`, and publishes the wheel and sdist. See
[Releasing](docs/releasing.md).

## Manual use

```bash
sudo .venv/bin/board-identify identify /dev/ttyUSB0
```

Machine-readable output:

```bash
sudo .venv/bin/board-identify identify --json /dev/ttyUSB0
```

Identify without publishing anything, or publish somewhere other than `/run`:

```bash
sudo .venv/bin/board-identify identify --no-publish /dev/ttyUSB0
sudo .venv/bin/board-identify --runtime-dir /tmp/board-identify identify /dev/ttyUSB0
```

Drop the link and state of one port, or sweep everything that has gone stale:

```bash
sudo .venv/bin/board-identify remove ttyUSB0
sudo .venv/bin/board-identify cleanup
```

Skip the step that talks to a board behind a debug probe:

```bash
sudo .venv/bin/board-identify identify --no-target-probe /dev/ttyACM4
```

Exit codes: `0` success, `1` error, `2` the board could not be identified.

## OS integration

The installer creates a uv-managed environment under `/opt/board-identify` and installs the supplied udev rules and systemd units.

```bash
sudo UV_BIN="$(command -v uv)" ./scripts/install.sh
```

The systemd service executes:

```text
/opt/board-identify/.venv/bin/board-identify
```

To uninstall:

```bash
sudo ./scripts/uninstall.sh
```

See [`docs/operations.md`](docs/operations.md) for details and troubleshooting.

## Identification policy

1. Inspect the serial device and USB metadata.
2. Run target-specific probes when needed.
3. Generate `<variant>-<unique-id>` for every identity the port has.
4. Atomically publish one symlink each under `/run/board-identify/by-id/`.
5. Store current state under `/run/board-identify/state/`.

## Scope: development environments only

Anything that cannot be pinned down by USB VID/PID is identified by talking to the
target, and that **disturbs the board**. `esptool` drives DTR/RTS to enter the
bootloader, so the running firmware is restarted every time the port appears. A WCH-Link
attach holds the target's core and releases it again, which interrupts what it was doing
rather than restarting it.

Consequences to accept before installing this:

- A board plugged into this machine will reboot, including boards that are not the one
  you care about, because the probe runs on every `ttyUSB*` and `ttyACM*` port that is
  not recognised from its descriptors.
- A device that is mid-measurement, logging, or driving hardware will be interrupted.
- Serial output produced during the probe window is lost.

Use it on a development machine. Do not use it where an environment has to stay stable —
production, unattended test rigs, or anything driving hardware that must not restart.
There, pin the devices with `/dev/serial/by-id/` or a udev rule as shown above.

Current status: a port whose VID/PID a WCH-Link or a known Arduino board definition claims
is settled from sysfs, which ends the probe chain before `esptool` runs. What still
reaches `esptool` is what the descriptors genuinely leave open: a pair the table does not
list, and any board behind a stock USB-UART bridge. See [Planned probes](#planned-probes).

## Planned probes

- [x] Espressif ESP32 family via eFuse MAC
- [x] WCH-Link debug probes, and WCH RISC-V targets behind them via the part UUID
- [x] Native USB serial descriptors
- [x] Arduino boards, from the published `arduino-cli board details` VID/PID table
- [x] RP2040, STM32, SAMD and nRF52 boards, from the same table
- [ ] RP2040 and STM32 unique IDs read from the target
- [ ] Generic firmware identification protocol

See [`docs/adding-a-probe.md`](docs/adding-a-probe.md).

## Documentation

- [Architecture](docs/architecture.md)
- [Identifier format](docs/identifier-format.md)
- [Operations](docs/operations.md)
- [Adding a probe](docs/adding-a-probe.md)
- [Releasing](docs/releasing.md)
- [Changelog / 変更履歴](CHANGELOG.md)
