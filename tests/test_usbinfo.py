from collections.abc import Callable
from pathlib import Path

from board_identify.usbinfo import usb_device_dir, usb_device_for_port

Sysfs = Callable[..., Path]


def test_reads_the_device_behind_a_tty(sysfs: Sysfs) -> None:
    root = sysfs()

    device = usb_device_for_port(Path("/dev/ttyACM4"), sysfs_root=root)

    assert device is not None
    assert (device.vid, device.pid) == (0x1A86, 0x8010)
    assert (device.bus, device.address) == (1, 22)
    assert device.serial == "FC928F068181"
    assert device.product == "WCH-Link"
    assert device.bcd_device == "0212"


def test_walks_up_from_the_interface_to_the_device(sysfs: Sysfs) -> None:
    root = sysfs()

    directory = usb_device_dir(Path("/dev/ttyACM4"), sysfs_root=root)

    # The tty hangs off an interface, but the attributes live on its parent.
    assert directory == root / "devices" / "usb1" / "1-8"


def test_unknown_port_has_no_device(sysfs: Sysfs) -> None:
    root = sysfs()

    assert usb_device_for_port(Path("/dev/ttyACM9"), sysfs_root=root) is None


def test_port_without_a_device_link_has_no_device(tmp_path: Path) -> None:
    (tmp_path / "class" / "tty" / "ttyS0").mkdir(parents=True)

    assert usb_device_for_port(Path("/dev/ttyS0"), sysfs_root=tmp_path) is None


def test_missing_attributes_are_not_a_device(sysfs: Sysfs) -> None:
    # A tty on a bus that is not USB has none of the attributes to walk up to.
    root = sysfs(attributes={"driver": "serial"})

    assert usb_device_for_port(Path("/dev/ttyACM4"), sysfs_root=root) is None


def test_unreadable_attributes_are_rejected(sysfs: Sysfs) -> None:
    root = sysfs(
        attributes={
            "idVendor": "not hex",
            "idProduct": "8010",
            "busnum": "001",
            "devnum": "022",
        }
    )

    assert usb_device_for_port(Path("/dev/ttyACM4"), sysfs_root=root) is None


def test_a_serial_free_adapter_is_still_described(sysfs: Sysfs) -> None:
    root = sysfs(
        port_name="ttyUSB0",
        attributes={
            "idVendor": "1a86",
            "idProduct": "7523",
            "busnum": "001",
            "devnum": "006",
        },
    )

    device = usb_device_for_port(Path("/dev/ttyUSB0"), sysfs_root=root)

    assert device is not None
    assert (device.vid, device.pid) == (0x1A86, 0x7523)
    assert device.serial is None
