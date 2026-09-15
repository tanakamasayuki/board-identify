"""Identify Espressif targets by their eFuse MAC, from descriptors or through esptool.

An Espressif chip with its own USB peripheral publishes that MAC as its USB
serial descriptor, so on such a port the identifier is readable from sysfs. That
path is taken whenever the chip name behind the MAC is already known, because
running ``esptool`` on a native-USB port destroys the port: the reset at the end
of the run re-enumerates the device, and the link published seconds earlier goes
with it. Every other port still goes to ``esptool``, which is also what fills in
the chip name the descriptor path needs.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

from board_identify.model import Identification, TransportKind
from board_identify.normalize import normalize_component, normalize_unique_id
from board_identify.paths import RUNTIME_DIR
from board_identify.usb_ids import ESPRESSIF_FAMILY, board_for_port, transport_kind_for_device
from board_identify.usbinfo import SYSFS_ROOT, usb_device_for_port
from board_identify.variants import recall_variant

# Espressif's own vendor ID, which a board reports when the tty is the chip's
# USB-Serial/JTAG peripheral rather than a bridge in front of it.
ESPRESSIF_VENDOR_ID = 0x303A

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
        runtime_dir: Path = RUNTIME_DIR,
    ) -> None:
        self.baud = baud
        self.timeout = timeout
        self.sysfs_root = sysfs_root
        self.runtime_dir = runtime_dir

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

    def identify_from_descriptors(self, port: Path) -> Identification | None:
        """Name the board from sysfs alone, or None when that is not enough.

        Answers only for a port that is the target's own USB peripheral, whose
        serial descriptor is the eFuse MAC — the same identifier ``esptool``
        would read, without the traffic and without the reset. The chip name is
        not in the descriptors, because every ESP32 with a USB-Serial/JTAG
        reports ``303a:1001``, so this returns None until something has learned
        it and the caller falls back to ``esptool``.
        """
        device = usb_device_for_port(port, self.sysfs_root)
        if device is None or device.vid != ESPRESSIF_VENDOR_ID:
            return None
        if device.serial is None or not MAC_PATTERN.fullmatch(device.serial):
            return None

        try:
            unique_id = normalize_unique_id(device.serial)
        except ValueError:
            return None

        variant = recall_variant(unique_id, self.runtime_dir)
        if variant is None:
            return None

        return Identification(
            port=port,
            family="espressif",
            variant=variant,
            unique_id=unique_id,
            # The MAC is the chip's, not an adapter's, however it was read.
            id_source="target-mac",
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
