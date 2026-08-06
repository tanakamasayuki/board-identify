# board-identify

Identify microcontroller boards connected through serial devices and publish stable symlinks based on hardware identifiers.

## Initial scope

The starter implementation identifies Espressif devices through `esptool` and creates links such as:

```text
/run/board-identify/by-id/esp32-s3-7cdfa1123456 -> /dev/ttyUSB2
```

The USB transport and the target board are treated separately. A CH340, FTDI, or CP210x serial number identifies the adapter, not necessarily the board behind it.

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
uv run mypy src
```

## Manual use

```bash
sudo uv run board-identify identify /dev/ttyUSB0
```

Machine-readable output:

```bash
uv run board-identify identify --json /dev/ttyUSB0
```

## OS integration

The installer creates a uv-managed environment under `/opt/board-identify` and installs the supplied udev rules and systemd units.

```bash
sudo ./scripts/install.sh
```

The systemd service executes:

```text
/opt/board-identify/.venv/bin/board-identify
```

To uninstall:

```bash
sudo ./scripts/uninstall.sh
```

## Identification policy

1. Inspect the serial device and USB metadata.
2. Run target-specific probes when needed.
3. Generate `<variant>-<unique-id>`.
4. Atomically publish a symlink under `/run/board-identify/by-id/`.
5. Store current state under `/run/board-identify/state/`.

## Planned probes

- [x] Espressif ESP32 family via eFuse MAC
- [ ] Native USB serial descriptors
- [ ] Arduino boards
- [ ] RP2040
- [ ] STM32
- [ ] Generic firmware identification protocol

See [`docs/adding-a-probe.md`](docs/adding-a-probe.md).
