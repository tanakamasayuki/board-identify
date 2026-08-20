"""Identify a WCH-Link debug probe and, through it, the target it is attached to.

Two identities come out of one port. The probe itself is named from USB
descriptors alone, which costs nothing and cannot fail. The target behind it is
named from its factory UUID, which needs a short conversation on the probe's
vendor interface.

The command bytes are documented in ch32fun's ``minichlink`` (MIT) and in
probe-rs' ``wlink`` backend (MIT / Apache-2.0); this module speaks the small
subset that answers "what is this, and what is it plugged into".
"""

import contextlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import usb.core
import usb.util

from board_identify.model import Identification
from board_identify.normalize import normalize_component, normalize_unique_id
from board_identify.probes.wch_chips import chip_name
from board_identify.usbinfo import SYSFS_ROOT, UsbDevice, usb_device_for_port

VENDOR_ID = 0x1A86
# RISC-V mode, where the vendor interface speaks the protocol below. minichlink
# opens both of these for the WCH-Link programmer.
RISCV_PRODUCT_IDS = frozenset({0x8010, 0x8012})
# ARM mode is CMSIS-DAP and answers none of these commands, so such a probe is
# named from its descriptors and its target is left alone.
PRODUCT_IDS = RISCV_PRODUCT_IDS | frozenset({0x8011})

VENDOR_INTERFACE = 0
ENDPOINT_OUT = 0x01
ENDPOINT_IN = 0x81
REPLY_SIZE = 64
DEFAULT_TIMEOUT_MS = 3000

# Commands, in the order the probe expects them.
CLEAR_STATE = b"\x81\x0d\x01\xff"
PROBE_INFO = b"\x81\x0d\x01\x01"
SET_SPEED = b"\x81\x0c\x02\x01\x02"
ATTACH_CHIP = b"\x81\x0d\x01\x02"
CHIP_INFO = b"\x81\x11\x01\x05"

# Replies to the 0x0d command group carry this header.
REPLY_HEADER = (0x82, 0x0D)
CHIP_INFO_REPLY_SIZE = 20
UUID_LENGTH = 8

# reply[5] of PROBE_INFO. Values 1 to 5 name the MCU inside the probe, 0x12 is
# the WCH-LinkE.
PROBE_VARIANTS = {
    0x01: "wch-link-ch549",
    0x02: "wch-link-ch32v307",
    0x03: "wch-link-ch32v203",
    0x04: "wch-linkb",
    0x05: "wch-linkw",
    0x12: "wch-linke",
}
UNKNOWN_VARIANT = "wch-link"

__all__ = ["ChipSignature", "ProbeInfo", "TargetInfo", "WchLinkProbe"]


@dataclass(frozen=True)
class ProbeInfo:
    """What the probe says about itself."""

    variant: str
    firmware: str


@dataclass(frozen=True)
class ChipSignature:
    """The identity bytes of the target, as reported by the attach reply."""

    family_id: int
    chip_id: int


@dataclass(frozen=True)
class TargetInfo:
    """The target behind the probe."""

    chip: str
    uuid: str
    flash_kb: int


class WchLinkProbe:
    name = "wch-link"

    def __init__(
        self,
        probe_target: bool = True,
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
        sysfs_root: Path = SYSFS_ROOT,
    ) -> None:
        self.probe_target = probe_target
        self.timeout_ms = timeout_ms
        self.sysfs_root = sysfs_root

    def supports(self, port: Path) -> bool:
        # sysfs only: no USB traffic, and the port is not opened.
        device = usb_device_for_port(port, self.sysfs_root)
        return device is not None and device.vid == VENDOR_ID and device.pid in PRODUCT_IDS

    def identify(self, port: Path) -> list[Identification]:
        device = usb_device_for_port(port, self.sysfs_root)
        if device is None or device.vid != VENDOR_ID or device.pid not in PRODUCT_IDS:
            return []

        probe_info: ProbeInfo | None = None
        target: TargetInfo | None = None
        if self.probe_target and device.pid in RISCV_PRODUCT_IDS:
            probe_info, target = self.query(device)

        results = [
            self.transport_identification(port, device, probe_info),
            self.target_identification(port, device, probe_info, target),
        ]
        # Most specific first: the target names the board, the probe names the cable.
        return [result for result in reversed(results) if result is not None]

    def query(self, device: UsbDevice) -> tuple[ProbeInfo | None, TargetInfo | None]:
        """Ask the probe about itself and about its target. Never raises."""
        try:
            handle = usb.core.find(
                bus=device.bus,
                address=device.address,
                idVendor=device.vid,
                idProduct=device.pid,
            )
        except (usb.core.USBError, usb.core.NoBackendError):
            return None, None
        if handle is None:
            return None, None

        try:
            # Read the active configuration before claiming. Claiming without it
            # can make pyusb send SET_CONFIGURATION, which would bounce the
            # cdc_acm driver holding the very tty being identified.
            handle.get_active_configuration()
            usb.util.claim_interface(handle, VENDOR_INTERFACE)
        except (usb.core.USBError, usb.core.NoBackendError, ValueError):
            # Busy usually means a debug session already owns the probe.
            return None, None

        try:
            return self.session(handle)
        except (usb.core.USBError, ValueError):
            return None, None
        finally:
            with contextlib.suppress(usb.core.USBError):
                usb.util.release_interface(handle, VENDOR_INTERFACE)
            usb.util.dispose_resources(handle)

    def session(self, handle: Any) -> tuple[ProbeInfo | None, TargetInfo | None]:
        """Run the command sequence on a claimed vendor interface."""
        self.command(handle, CLEAR_STATE)
        probe_info = self.parse_probe_info(self.command(handle, PROBE_INFO))

        target = None
        try:
            self.command(handle, SET_SPEED)
            signature = self.parse_attach(self.command(handle, ATTACH_CHIP))
            if signature is not None:
                target = self.parse_chip_info(self.command(handle, CHIP_INFO), signature)
        finally:
            # Attaching holds the target core; this releases it again. It runs
            # even on failure so a half finished probe does not leave it halted.
            with contextlib.suppress(usb.core.USBError):
                self.command(handle, CLEAR_STATE)
        return probe_info, target

    def command(self, handle: Any, payload: bytes) -> bytes:
        """Send one command and return its reply."""
        handle.write(ENDPOINT_OUT, payload, self.timeout_ms)
        return bytes(handle.read(ENDPOINT_IN, REPLY_SIZE, self.timeout_ms))

    @staticmethod
    def parse_probe_info(reply: bytes) -> ProbeInfo | None:
        """Decode a PROBE_INFO reply such as ``82 0d 04 02 0c 12 00``."""
        if len(reply) < 6 or (reply[0], reply[1]) != REPLY_HEADER:
            return None
        return ProbeInfo(
            variant=PROBE_VARIANTS.get(reply[5], UNKNOWN_VARIANT),
            firmware=f"{reply[3]}.{reply[4]}",
        )

    @staticmethod
    def parse_attach(reply: bytes) -> ChipSignature | None:
        """Decode an ATTACH_CHIP reply such as ``82 0d 05 0d 03 51 06 01``.

        With nothing on the debug pins the probe answers four bytes, or a reply
        starting ``81 55 01``; neither passes the header and length check.
        """
        if len(reply) < 8 or (reply[0], reply[1]) != REPLY_HEADER:
            return None
        return ChipSignature(family_id=reply[3], chip_id=int.from_bytes(reply[4:8], "big"))

    @staticmethod
    def parse_chip_info(reply: bytes, signature: ChipSignature) -> TargetInfo | None:
        """Decode a CHIP_INFO reply, which is 20 bytes and carries no header:

        ``ff ff 00 3e | 1f f9 ab cd 88 0e bc 48 | ff ff ff ff | 03 51 06 01``
        is flash size in kB, the part UUID, protection flags, and the chip ID
        again.
        """
        if len(reply) != CHIP_INFO_REPLY_SIZE or reply[0] == 0x00:
            return None

        uuid = reply[4 : 4 + UUID_LENGTH]
        # A part that did not answer, or refused to, returns a constant.
        if uuid in (bytes(UUID_LENGTH), b"\xff" * UUID_LENGTH):
            return None

        return TargetInfo(
            chip=chip_name(signature.family_id, signature.chip_id),
            uuid=uuid.hex(),
            flash_kb=int.from_bytes(reply[2:4], "big"),
        )

    @classmethod
    def transport_identification(
        cls, port: Path, device: UsbDevice, probe_info: ProbeInfo | None
    ) -> Identification | None:
        """Name the probe itself from its USB serial number.

        The name deliberately ignores the variant the probe reports, so that it
        does not change when the vendor interface happens to be busy. The
        variant is recorded as the transport instead.
        """
        if device.serial is None:
            return None
        try:
            unique_id = normalize_unique_id(device.serial)
        except ValueError:
            return None

        return Identification(
            port=port,
            family="wch-link",
            variant=UNKNOWN_VARIANT,
            unique_id=unique_id,
            id_source="transport-serial",
            transport=probe_info.variant if probe_info is not None else None,
            usb_vid=f"{device.vid:04x}",
            usb_pid=f"{device.pid:04x}",
            usb_serial=device.serial,
        )

    @classmethod
    def target_identification(
        cls,
        port: Path,
        device: UsbDevice,
        probe_info: ProbeInfo | None,
        target: TargetInfo | None,
    ) -> Identification | None:
        """Name the target board from the UUID programmed into it at the factory."""
        if target is None:
            return None
        try:
            variant = normalize_component(target.chip)
            unique_id = normalize_unique_id(target.uuid)
        except ValueError:
            return None

        return Identification(
            port=port,
            family="wch",
            variant=variant,
            unique_id=unique_id,
            id_source="target-cpu-id",
            transport=probe_info.variant if probe_info is not None else UNKNOWN_VARIANT,
            usb_vid=f"{device.vid:04x}",
            usb_pid=f"{device.pid:04x}",
            usb_serial=device.serial,
        )
