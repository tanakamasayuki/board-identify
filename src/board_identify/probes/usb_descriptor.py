"""Name a board from its USB descriptors alone, using the Arduino board table.

This is the general descriptor fast path: sysfs already knows the VID/PID and
the serial number of the device behind a tty, and the board definitions
installed with Arduino IDE already say which board reports which pair. Putting
the two together names an Arduino UNO R4 or a Nano Every without opening the
port, without USB traffic, and without the reset that talking to a board costs.

It answers only for families whose target cannot be asked directly. An
Espressif board is left to :class:`~board_identify.probes.espressif.EspressifProbe`,
because the eFuse MAC it reads comes from the silicon and outlives a bridge
chip being reflashed or replaced.
"""

from pathlib import Path

from board_identify.model import Identification
from board_identify.normalize import normalize_unique_id
from board_identify.usb_ids import UsbBoard, board_for_usb_id
from board_identify.usbinfo import SYSFS_ROOT, UsbDevice, usb_device_for_port

__all__ = ["UsbDescriptorProbe"]


class UsbDescriptorProbe:
    name = "usb-descriptor"

    def __init__(self, sysfs_root: Path = SYSFS_ROOT) -> None:
        self.sysfs_root = sysfs_root

    def supports(self, port: Path) -> bool:
        # sysfs only: no USB traffic, and the port is not opened.
        return self.match(port) is not None

    def identify(self, port: Path) -> list[Identification]:
        match = self.match(port)
        if match is None:
            return []
        device, board = match

        # Without a serial number the descriptors name the model but not the
        # unit, and a name shared by every board of that model is not a name.
        if device.serial is None or board.variant is None:
            return []
        try:
            unique_id = normalize_unique_id(device.serial)
        except ValueError:
            return []

        return [
            Identification(
                port=port,
                family=board.family,
                variant=board.variant,
                unique_id=unique_id,
                id_source="usb-serial",
                usb_vid=f"{device.vid:04x}",
                usb_pid=f"{device.pid:04x}",
                usb_serial=device.serial,
            )
        ]

    def match(self, port: Path) -> tuple[UsbDevice, UsbBoard] | None:
        """The device and the board its descriptors name, when this probe answers."""
        device = usb_device_for_port(port, self.sysfs_root)
        if device is None:
            return None
        board = board_for_usb_id(device.vid, device.pid)
        if board is None or board.variant is None or board.is_espressif:
            return None
        return device, board
