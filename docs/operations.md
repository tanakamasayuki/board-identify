# Operations

*[English](operations.md) | [日本語](operations.ja.md)*

## Install

```bash
sudo UV_BIN="$(command -v uv)" ./scripts/install.sh
```

The installer copies the source tree (excluding `.git`, the development `.venv`, and
caches) to `/opt/board-identify`, runs `uv sync --no-dev --frozen`, and installs:

| File | Destination |
| --- | --- |
| `udev/90-board-identify.rules` | `/etc/udev/rules.d/` |
| `systemd/board-identify@.service` | `/etc/systemd/system/` |
| `systemd/board-identify-cleanup.service` | `/etc/systemd/system/` |

Set `BOARD_IDENTIFY_INSTALL_ROOT` to install elsewhere. Uninstall with
`sudo ./scripts/uninstall.sh`, which also removes `/run/board-identify`.

## What happens on plug and unplug

- Plug: udev sets `SYSTEMD_WANTS` and systemd starts `board-identify@ttyUSB0.service`,
  which runs `board-identify identify /dev/ttyUSB0`.
- Unplug: `BindsTo=dev-ttyUSB0.device` stops the unit, whose `ExecStop=` runs
  `board-identify remove ttyUSB0`. The udev `remove` rule additionally starts
  `board-identify-cleanup.service`.

`TimeoutStartSec=60` in the unit must stay above the probe timeout in
`board_identify.probes.espressif` (30 s by default), otherwise a slow probe is killed
before it can answer.

## Troubleshooting

```bash
# Re-run identification for everything currently attached.
sudo udevadm trigger --subsystem-match=tty

# Watch one port.
journalctl -u board-identify@ttyUSB0.service -f

# See what was decided, without touching /run.
sudo /opt/board-identify/.venv/bin/board-identify identify --json --no-publish /dev/ttyUSB0

# Sweep stale links and state by hand.
sudo /opt/board-identify/.venv/bin/board-identify cleanup
```

If identification fails with exit code 2, the port answered nothing that a probe
recognised. Common causes: the board is running an application that holds the port, the
board needs manual bootloader entry, or another process (a serial monitor, ModemManager)
opened the port first. Excluding your boards from ModemManager with a udev rule such as
`ENV{ID_MM_DEVICE_IGNORE}="1"` avoids the last case.

Probing resets the target. Do not install this on a machine where boards are expected to
keep running undisturbed while being plugged in.

See also [Architecture](architecture.md).
