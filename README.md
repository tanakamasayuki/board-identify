# board-identify

*[English](README.md) | [日本語](README.ja.md)*

Identify microcontroller boards connected through serial devices and publish stable symlinks based on hardware identifiers.

## Initial scope

The starter implementation identifies Espressif devices through `esptool` and creates links such as:

```text
/run/board-identify/by-id/esp32-s3-7cdfa1123456 -> /dev/ttyUSB2
```

The USB transport and the target board are treated separately. A CH340, FTDI, or CP210x serial number identifies the adapter, not necessarily the board behind it.

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
3. Generate `<variant>-<unique-id>`.
4. Atomically publish a symlink under `/run/board-identify/by-id/`.
5. Store current state under `/run/board-identify/state/`.

## Scope: development environments only

Anything that cannot be pinned down by USB VID/PID is identified by talking to the
target, and that probe **resets the board**: `esptool` drives DTR/RTS to enter the
bootloader, so the running firmware is restarted every time the port appears.

Consequences to accept before installing this:

- A board plugged into this machine will reboot, including boards that are not the one
  you care about, because the probe runs on every `ttyUSB*` and `ttyACM*` port.
- A device that is mid-measurement, logging, or driving hardware will be interrupted.
- Serial output produced during the probe window is lost.

Use it on a development machine. Do not use it where an environment has to stay stable —
production, unattended test rigs, or anything driving hardware that must not restart.
There, pin the devices with `/dev/serial/by-id/` or a udev rule as shown above.

Current status: the VID/PID fast path is not implemented yet, so **every** supported port
is probed today, including devices that could have been identified from their descriptors
alone. See [Planned probes](#planned-probes).

## Planned probes

- [x] Espressif ESP32 family via eFuse MAC
- [ ] Native USB serial descriptors
- [ ] Arduino boards
- [ ] RP2040
- [ ] STM32
- [ ] Generic firmware identification protocol

See [`docs/adding-a-probe.md`](docs/adding-a-probe.md).

## Documentation

- [Architecture](docs/architecture.md)
- [Identifier format](docs/identifier-format.md)
- [Operations](docs/operations.md)
- [Adding a probe](docs/adding-a-probe.md)
- [Changelog](CHANGELOG.md)
