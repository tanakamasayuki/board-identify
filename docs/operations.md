# Operations

*[English](operations.md) | [日本語](operations.ja.md)*

## Before installing

Probing resets the target: every plug event restarts the firmware on the board. Install
this on a development machine only, and prefer `/dev/serial/by-id/` or a udev rule
matching USB descriptors wherever those work. See the README section
[Use the standard mechanisms first](../README.md#use-the-standard-mechanisms-first).

## WSL and USB/IP

On the main target environment, devices are forwarded from Windows with
[usbipd-win](https://github.com/dorssel/usbipd-win):

```powershell
usbipd list                        # note the BUSID, for example 1-4
usbipd bind --busid 1-4            # once, as administrator
usbipd attach --wsl --busid 1-4
```

Inside WSL the device then appears as `/dev/ttyUSB0` or `/dev/ttyACM0`:

```bash
# The Windows BUSID is not represented here; the path follows the attach order.
udevadm info -q property -n /dev/ttyUSB0 | grep -E 'ID_PATH|ID_SERIAL'
# ID_PATH=platform-vhci_hcd.0-usb-0:1:1.0
```

Notes for this environment:

- Detaching on the Windows side, or `wsl --shutdown`, produces the same `remove` event as
  unplugging, so links and state are cleaned up normally.
- Re-attaching in a different order changes `ID_PATH` and therefore
  `/dev/serial/by-path/`, which is the reason this tool exists.
- udev must be running inside the distribution for the rules to fire. Check with
  `systemctl status systemd-udevd`; on older WSL setups enable systemd through
  `/etc/wsl.conf` (`[boot]` / `systemd=true`) and restart with `wsl --shutdown`.
- The links live under `/run`, so they are recreated from scratch on every WSL start.

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
