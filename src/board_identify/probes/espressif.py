"""Identify Espressif targets by their eFuse MAC, from descriptors or through esptool.

An Espressif chip with its own USB peripheral publishes that MAC as its USB
serial descriptor, so on such a port the identifier is readable from sysfs. Such
a port is not opened at all by default: pyserial raises DTR and RTS on open, and
on a board wired for native USB that reboots it, on top of the reset ``esptool``
performs deliberately. The board would also take its own tty down with it, so
the link published seconds earlier goes too.

Such a port is named from its descriptors alone instead, down to the series
rather than the chip. A port in front of the target — a CH340, a CP2102 — has no
such descriptors and still goes to ``esptool``, which does read the chip.

``probe_target`` turns that off as well, leaving every port on descriptors.
``probe_native_usb`` is the escape hatch for a native port whose descriptors say
nothing either, which is firmware that brought up a CDC class of its own rather
than the USB-Serial/JTAG peripheral; a port that does report its MAC is named
without it, and names itself the same way with or without it.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

from board_identify.model import Identification, TransportKind
from board_identify.normalize import normalize_component, normalize_unique_id
from board_identify.usb_ids import ESPRESSIF_FAMILY, board_for_port, transport_kind_for_device
from board_identify.usbinfo import SYSFS_ROOT, usb_device_for_port

# Espressif's own vendor ID, which a board reports when the tty is the chip's
# USB-Serial/JTAG peripheral rather than a bridge in front of it.
ESPRESSIF_VENDOR_ID = 0x303A

# What such a port can be called without asking the chip anything. Every ESP32
# with a USB-Serial/JTAG reports 303a:1001, so the descriptors go no further than
# the series — but the eFuse MAC beside it is what makes the name unique, and
# that is the whole job. Nothing will refine this later either, because nothing
# opens the port, so the name a board gets here it keeps.
#
# Not plain "esp32": that is what esptool calls the original ESP32, so a board
# that was never asked must not borrow the name of one that was. The suffix says
# the series is as far as this got.
NATIVE_USB_VARIANT = "esp32-series"

DEFAULT_BAUD = 115200
DEFAULT_CONNECT_ATTEMPTS = 2
DEFAULT_TIMEOUT = 30.0

MAC_PATTERN = re.compile(r"\b([0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5})\b")

# The MAC that identifies the target, in decreasing order of preference.
# esptool 5 may also print BASE MAC and MAC_EXT lines for some chips.
LABELLED_MAC_PATTERNS = (
    re.compile(rf"^MAC:\s*{MAC_PATTERN.pattern}", re.MULTILINE),
    re.compile(rf"^BASE MAC:\s*{MAC_PATTERN.pattern}", re.MULTILINE),
)

CHIP_PATTERNS = (
    re.compile(r"^Chip is\s+(.+?)(?:\s+\(|$)", re.MULTILINE),
    re.compile(r"^Chip type:\s+(.+?)(?:\s+\(|$)", re.MULTILINE),
    re.compile(r"^Detecting chip type\.\.\.\s+(.+?)(?:\s+\(|$)", re.MULTILINE),
)


def esptool_command_name() -> str:
    """The read-MAC subcommand name, which was renamed in esptool 5."""
    try:
        import esptool
    except ImportError:  # pragma: no cover - esptool is a hard dependency
        return "read-mac"

    version = getattr(esptool, "__version__", "")
    major = version.split(".", 1)[0]
    return "read_mac" if major.isdigit() and int(major) < 5 else "read-mac"


def esptool_environment() -> dict[str, str]:
    """Environment that keeps esptool output plain and unwrapped so it can be parsed."""
    env = dict(os.environ)
    env["NO_COLOR"] = "1"
    env["TERM"] = "dumb"
    # esptool 5 renders through rich, which wraps to the terminal width.
    env["COLUMNS"] = "200"
    return env


class EspressifProbe:
    name = "espressif"

    def __init__(
        self,
        baud: int = DEFAULT_BAUD,
        timeout: float = DEFAULT_TIMEOUT,
        sysfs_root: Path = SYSFS_ROOT,
        probe_target: bool = True,
        probe_native_usb: bool = False,
    ) -> None:
        self.baud = baud
        self.timeout = timeout
        self.sysfs_root = sysfs_root
        self.probe_target = probe_target
        self.probe_native_usb = probe_native_usb

    def supports(self, port: Path) -> bool:
        # Any USB-serial port may hide an Espressif target behind the bridge, so
        # this is a cheap pre-filter rather than a positive match.
        if not port.name.startswith(("ttyUSB", "ttyACM")):
            return False

        # Unless the descriptors say otherwise. A board definition that claims
        # this VID/PID for another family settles it from sysfs, which saves the
        # connect attempt and, more to the point, saves the reset it costs a
        # board that was never going to answer. An unknown pair, and a stock
        # USB-UART bridge shared across families, both leave the question open,
        # so those still go to esptool.
        board = board_for_port(port, self.sysfs_root)
        return board is None or board.family == ESPRESSIF_FAMILY

    def identify(self, port: Path) -> list[Identification]:
        from_descriptors = self.identify_from_descriptors(port)
        if from_descriptors is not None:
            return [from_descriptors]
        if not self.may_open(port):
            return []

        try:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "esptool",
                    "--port",
                    str(port),
                    "--baud",
                    str(self.baud),
                    "--connect-attempts",
                    str(DEFAULT_CONNECT_ATTEMPTS),
                    esptool_command_name(),
                ],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
                env=esptool_environment(),
            )
        except (subprocess.TimeoutExpired, OSError):
            return []

        if completed.returncode != 0:
            return []

        kind = transport_kind_for_device(usb_device_for_port(port, self.sysfs_root))
        result = self.parse(port, completed.stdout + completed.stderr, transport_kind=kind)
        return [] if result is None else [result]

    def may_open(self, port: Path) -> bool:
        """Whether this run is allowed to open ``port`` and talk to the target.

        Opening a port resets the board behind it, so the question is asked per
        port rather than once: the native USB ports are the ones where the reset
        is not only disruptive but takes the port away, and they are held back
        unless the caller asks for them.
        """
        if not self.probe_target:
            return False
        if self.probe_native_usb:
            return True
        return transport_kind_for_device(usb_device_for_port(port, self.sysfs_root)) != "usb"

    def native_usb_unique_id(self, port: Path) -> str | None:
        """The eFuse MAC in the serial descriptor of a native USB port, or None.

        This is the whole unique half of the board's name, readable without
        opening anything. What is missing on such a port is only the chip name.
        """
        device = usb_device_for_port(port, self.sysfs_root)
        if device is None or device.vid != ESPRESSIF_VENDOR_ID:
            return None
        if device.serial is None or not MAC_PATTERN.fullmatch(device.serial):
            return None
        try:
            return normalize_unique_id(device.serial)
        except ValueError:
            return None

    def identify_from_descriptors(self, port: Path) -> Identification | None:
        """Name the board from sysfs alone, or None when that is not enough.

        Answers only for a port that is the target's own USB peripheral, whose
        serial descriptor is the eFuse MAC — the same identifier ``esptool``
        would read, without the traffic and without the reset. The chip name is
        not in the descriptors, because every ESP32 with a USB-Serial/JTAG
        reports ``303a:1001``, so the name stops at the series. That is enough:
        the MAC is what makes it unique, and a board named here keeps that name,
        because nothing will ever open the port to refine it.
        """
        unique_id = self.native_usb_unique_id(port)
        if unique_id is None:
            return None
        device = usb_device_for_port(port, self.sysfs_root)
        if device is None or device.serial is None:
            return None

        return Identification(
            port=port,
            family="espressif",
            variant=NATIVE_USB_VARIANT,
            unique_id=unique_id,
            # The board's own USB, so the serial number is the unit and not a
            # cable — the same sense UsbDescriptorProbe uses it in.
            id_source="usb-serial",
            transport_kind="usb",
            usb_vid=f"{device.vid:04x}",
            usb_pid=f"{device.pid:04x}",
            usb_serial=device.serial,
        )

    @classmethod
    def parse(
        cls,
        port: Path,
        output: str,
        transport_kind: TransportKind | None = None,
    ) -> Identification | None:
        """Build an Identification from esptool output, or return None."""
        chip = cls.extract_chip(output)
        mac = cls.extract_mac(output)
        if not chip or not mac:
            return None

        try:
            variant = normalize_component(chip)
            unique_id = normalize_unique_id(mac)
        except ValueError:
            return None

        return Identification(
            port=port,
            family="espressif",
            variant=variant,
            unique_id=unique_id,
            id_source="target-mac",
            transport_kind=transport_kind,
        )

    @staticmethod
    def extract_chip(output: str) -> str | None:
        for pattern in CHIP_PATTERNS:
            match = pattern.search(output)
            if match:
                return match.group(1).strip()
        return None

    @staticmethod
    def extract_mac(output: str) -> str | None:
        for pattern in LABELLED_MAC_PATTERNS:
            match = pattern.search(output)
            if match:
                return match.group(1)

        matches = MAC_PATTERN.findall(output)
        return matches[-1] if matches else None
