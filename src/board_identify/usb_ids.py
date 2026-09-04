"""Boards recognised from their USB VID/PID alone.

Arduino board definitions record the VID/PID each board reports, one entry per
bootloader state. Held as a table, that answers two questions before anything is
opened or reset:

* which board a port is, when exactly one board claims the pair, and
* which board it is *not*, which is what keeps ``esptool`` off a port whose
  descriptors a definition attributes to another family.

The table lives in :mod:`board_identify.arduino_ids`, merged from a published
dump of ``arduino-cli board details`` by ``scripts/generate_usb_ids.py``. It is
deliberately not read from a local Arduino installation: a board only appears
there once its core is installed, and the boards worth identifying are the ones
that have not been set up yet.

This module holds what does not come from Arduino: the generic USB-UART bridges,
whose VID/PID identifies the cable and says nothing at all about the board behind
it. A CH340 is a CH340 whether it is soldered to an ESP32 module or to a bare
AVR, so such a pair must never name a board and must never rule a family out
either. Board definitions do claim stock bridge IDs from time to time — the Sony
Spresense claims the stock CP2102 ``10c4:ea60`` — which is what makes the check
below load bearing rather than theoretical.
"""

from dataclasses import dataclass
from pathlib import Path

from board_identify.arduino_ids import ARDUINO_USB_IDS
from board_identify.usbinfo import SYSFS_ROOT, usb_device_for_port

# The family EspressifProbe answers for; see board_for_usb_id() callers.
ESPRESSIF_FAMILY = "espressif"

# Vendors whose USB-UART bridges turn up on boards of every family. A pair from
# one of these is only trusted when its product ID is not a stock bridge ID: a
# vendor that bothers to program its own PID is naming its board, not its cable.
BRIDGE_VENDORS: dict[int, str] = {
    0x0403: "FTDI",
    0x067B: "Prolific",
    0x10C4: "Silicon Labs",
    0x1A86: "WCH",
    0x4348: "WCH",
}

# Stock IDs of those bridges, as they ship. Never a board identity.
GENERIC_BRIDGE_IDS: frozenset[tuple[int, int]] = frozenset(
    {
        (0x0403, 0x6001),  # FT232R
        (0x0403, 0x6010),  # FT2232
        (0x0403, 0x6011),  # FT4232
        (0x0403, 0x6014),  # FT232H
        (0x0403, 0x6015),  # FT230X / FT231X
        (0x067B, 0x2303),  # PL2303
        (0x067B, 0x23A3),  # PL2303GC
        (0x067B, 0x23B3),  # PL2303GB
        (0x067B, 0x23C3),  # PL2303GT
        (0x067B, 0x23D3),  # PL2303GL
        (0x067B, 0x23E3),  # PL2303GE
        (0x067B, 0x23F3),  # PL2303GS
        (0x10C4, 0xEA60),  # CP2102 / CP2109
        (0x10C4, 0xEA61),  # CP2101
        (0x10C4, 0xEA63),  # CP2102N
        (0x10C4, 0xEA70),  # CP2105
        (0x10C4, 0xEA71),  # CP2108
        (0x1A86, 0x5523),  # CH341 in serial mode
        (0x1A86, 0x55D2),  # CH9102
        (0x1A86, 0x55D3),  # CH343
        (0x1A86, 0x55D4),  # CH9102F
        (0x1A86, 0x55D5),  # CH344
        (0x1A86, 0x7522),  # CH340
        (0x1A86, 0x7523),  # CH340
        (0x1A86, 0x7584),  # CH340S
        (0x4348, 0x5523),  # CH341
    }
)

__all__ = [
    "BRIDGE_VENDORS",
    "ESPRESSIF_FAMILY",
    "GENERIC_BRIDGE_IDS",
    "UsbBoard",
    "board_for_port",
    "board_for_usb_id",
    "is_generic_bridge",
]


@dataclass(frozen=True)
class UsbBoard:
    """What the board definitions say about one VID/PID pair.

    ``variant`` is None when several boards share the pair. The family is still
    known in that case, which is enough to rule a probe out even though it is
    not enough to name the board.
    """

    vid: int
    pid: int
    family: str
    platform: str
    variant: str | None = None

    @property
    def is_espressif(self) -> bool:
        return self.family == ESPRESSIF_FAMILY


def is_generic_bridge(vid: int, pid: int) -> bool:
    """Return whether the pair is a stock USB-UART bridge rather than a board."""
    return (vid, pid) in GENERIC_BRIDGE_IDS


def board_for_usb_id(vid: int, pid: int) -> UsbBoard | None:
    """The board claiming this VID/PID, or None when nothing may be concluded.

    The generic-bridge check is repeated here rather than left to the generator,
    so that a table regenerated against a package that does register a stock
    bridge ID still cannot make this function speak for a CH340.
    """
    if is_generic_bridge(vid, pid):
        return None
    entry = ARDUINO_USB_IDS.get((vid, pid))
    if entry is None:
        return None
    family, platform, variant = entry
    return UsbBoard(vid=vid, pid=pid, family=family, platform=platform, variant=variant)


def board_for_port(port: Path, sysfs_root: Path = SYSFS_ROOT) -> UsbBoard | None:
    """The board claiming the descriptors of ``port``, read from sysfs only."""
    device = usb_device_for_port(port, sysfs_root)
    if device is None:
        return None
    return board_for_usb_id(device.vid, device.pid)
