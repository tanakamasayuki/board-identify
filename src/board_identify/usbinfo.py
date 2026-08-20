"""USB metadata for a serial port, read from sysfs without opening the port."""

from dataclasses import dataclass
from pathlib import Path

SYSFS_ROOT = Path("/sys")

# These live on a USB device directory. A USB *interface* directory has none of
# them, which is what makes them usable to tell the two apart while walking up.
DEVICE_ATTRIBUTES = ("idVendor", "idProduct", "busnum", "devnum")

__all__ = ["SYSFS_ROOT", "UsbDevice", "usb_device_for_port"]


@dataclass(frozen=True)
class UsbDevice:
    """The USB device a tty hangs off, as sysfs describes it.

    ``bus`` and ``address`` are the kernel's ``busnum`` and ``devnum``, which is
    what libusb matches on. Selecting a device that way rather than by VID/PID
    keeps the right one in view when several identical probes are plugged in.
    """

    path: Path
    vid: int
    pid: int
    bus: int
    address: int
    serial: str | None = None
    manufacturer: str | None = None
    product: str | None = None
    bcd_device: str | None = None


def usb_device_for_port(port: Path, sysfs_root: Path = SYSFS_ROOT) -> UsbDevice | None:
    """Describe the USB device behind a tty, or None when there is none to read.

    Reads sysfs only: no USB traffic, and the port itself is never opened.
    """
    directory = usb_device_dir(port, sysfs_root)
    if directory is None:
        return None

    try:
        return UsbDevice(
            path=directory,
            vid=int(_attribute(directory, "idVendor") or "", 16),
            pid=int(_attribute(directory, "idProduct") or "", 16),
            bus=int(_attribute(directory, "busnum") or ""),
            address=int(_attribute(directory, "devnum") or ""),
            serial=_attribute(directory, "serial"),
            manufacturer=_attribute(directory, "manufacturer"),
            product=_attribute(directory, "product"),
            bcd_device=_attribute(directory, "bcdDevice"),
        )
    except ValueError:
        # An attribute was missing or unreadable, so this is not a USB device we
        # can describe.
        return None


def usb_device_dir(port: Path, sysfs_root: Path = SYSFS_ROOT) -> Path | None:
    """The sysfs directory of the USB device owning ``port``, or None."""
    root = sysfs_root.resolve()
    try:
        # This points at the USB *interface* holding the tty, for example
        # .../usb1/1-8/1-8:1.1 for a CDC-ACM port. What we want sits above it.
        start = (root / "class" / "tty" / port.name / "device").resolve(strict=True)
    except OSError:
        return None

    for directory in (start, *start.parents):
        if not directory.is_relative_to(root):
            break
        if all((directory / name).is_file() for name in DEVICE_ATTRIBUTES):
            return directory
    return None


def _attribute(directory: Path, name: str) -> str | None:
    """One sysfs attribute as text, or None when absent or empty."""
    try:
        value = (directory / name).read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None
    return value or None
