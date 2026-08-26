# Operations

*[English](operations.md) | [日本語](operations.ja.md)*

## Before installing

Probing disturbs the target: `esptool` restarts the firmware on every plug event, and a
WCH-Link attach halts the target's core and releases it again. Install this on a
development machine only, and prefer `/dev/serial/by-id/` or a udev rule matching USB
descriptors wherever those work. See the README section
[Use the standard mechanisms first](../README.md#use-the-standard-mechanisms-first).

## WSL and USB/IP

On the main target environment, devices are forwarded from Windows with
[usbipd-win](https://github.com/dorssel/usbipd-win):

```powershell
usbipd list                        # note the BUSID, for example 1-4
usbipd bind --busid 1-4            # once, as administrator
usbipd attach --wsl --busid 1-4
usbipd attach --wsl --busid 1-4 --auto-attach   # keeps re-attaching, runs until stopped
```

### Auto-attach or a fixed order

Auto-attach forwards a device as soon as it appears and brings it back after a
disconnect, but the order is whatever the devices happen to arrive in. For adapters
without a serial number, such as most CH340 modules, the resulting `/dev/ttyUSB*` numbers
are then unattributable. The two workable setups are:

| Setup | Port numbers | Cost |
| --- | --- | --- |
| Manual attach, always in the same order | Predictable | A fixed ritual every session; a lost attachment must be noticed and redone by hand |
| Auto-attach plus `board-identify` | Arbitrary, and irrelevant | The probe disturbs boards on every attach |

Attachments are lost from time to time — a suspend, a Wi-Fi or VPN change on the Windows
side, or a USB glitch. Auto-attach restores them without intervention, which is why it is
usually kept on and the ordering problem is solved on the Linux side instead.

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
before it can answer. A WCH-Link is recognised from its descriptors and answers in well
under a second, so it never comes close.

## USB permissions for debug probes

Identifying the board behind a debug probe needs access to the probe's vendor USB
interface, not just to the tty. The systemd unit runs as root, so the installed setup
needs nothing extra. Running `board-identify identify` by hand as an ordinary user does,
and without it the probe itself is still named but its target is not:

```bash
# Whether the interface is reachable: if only the wch-link entry comes back, the
# vendor interface could not be opened.
board-identify identify --json --no-publish /dev/ttyACM4

# A rule granting access to a WCH-Link in RISC-V mode.
sudo tee /etc/udev/rules.d/99-wch-link.rules <<'RULE'
SUBSYSTEM=="usb", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="8010", GROUP="plugdev", MODE="0660"
SUBSYSTEM=="usb", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="8012", GROUP="plugdev", MODE="0660"
RULE
sudo udevadm control --reload
```

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

### A debug probe that reports the wrong chip

Some tools leave the WCH-Link's readback of its target broken. Observed with probe-rs
0.32 on a CH32V003 over its single-wire SWIO connection, from a plain `probe-rs read` — no
flashing needed. A CH32V103 driven the same way is unaffected, so this looks specific to
the single-wire path:

```text
attach     82 0d 05 09 00 00 03 07          family 0x09 correct, chip ID garbage
chip info  00 00 03 07 ... (repeated x5)    UUID reads as 0000030700000307
```

The family byte stays right, which is what makes the reading look plausible. The rest is
one four-byte word repeated, it survives further attach and detach cycles, and the same
bogus UUID comes back for every board in this state. It is the probe that is confused,
not the board: power cycling the target does not clear it. `board-identify` detects it
and reads again, so nothing extra is needed.

What clears it, and what that costs:

| Command | Clears it | Resets the target |
| --- | --- | --- |
| `81 0d 01 03` — what recovery uses | Yes | No |
| `81 0b 01 01` — `wlink reset`, probe-rs `ResetTarget` | Yes | Yes |
| `81 0d 01 ff` — detach | No | No |
| `81 0d 01 13` — reset line low | No | No |
| A debug-module `ndmreset` | No | Yes |
| `probe-rs reset` | No | Yes |
| Power cycling the target | No | — |

Measured through the debug module's sticky `havereset` bits. Note that resetting the
target is neither necessary nor sufficient: `81 0d 01 03` clears it without a reset, while
`ndmreset` resets the target and does not clear it. `probe-rs reset` goes through
`core.reset()` rather than the probe's own reset command, so it does not help either.

To clear it by hand:

```bash
wlink reset      # sends 81 0b 01 01; clears it, at the cost of resetting the target
```

A debug probe whose vendor interface is already claimed — by a running `gdb`,
`minichlink`, `wlink`, or OpenOCD session — cannot be asked about its target. That is not
an error: the probe itself is still published from its descriptors, and the target link
reappears on the next plug event or on a manual re-run once the session ends. To publish
the probe alone on purpose, or to leave a running target strictly alone:

```bash
sudo /opt/board-identify/.venv/bin/board-identify identify --no-target-probe /dev/ttyACM4
```

If identification fails with exit code 2, the port answered nothing that a probe
recognised. Common causes: the board is running an application that holds the port, the
board needs manual bootloader entry, or another process (a serial monitor, ModemManager)
opened the port first. Excluding your boards from ModemManager with a udev rule such as
`ENV{ID_MM_DEVICE_IGNORE}="1"` avoids the last case.

Probing disturbs the target. Do not install this on a machine where boards are expected
to keep running undisturbed while being plugged in.

See also [Architecture](architecture.md).
