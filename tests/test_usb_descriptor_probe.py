from collections.abc import Callable
from pathlib import Path

import pytest

from board_identify import arduino_ids
from board_identify.probes.usb_descriptor import UsbDescriptorProbe

Sysfs = Callable[..., Path]

PORT = Path("/dev/ttyACM0")


def descriptors(vid: str, pid: str, serial: str | None = "34367333130351F0C1C1") -> dict[str, str]:
    attributes = {"idVendor": vid, "idProduct": pid, "busnum": "001", "devnum": "007"}
    if serial is not None:
        attributes["serial"] = serial
    return attributes


def test_identifies_an_arduino_uno_r4_wifi(sysfs: Sysfs) -> None:
    root = sysfs(port_name="ttyACM0", attributes=descriptors("2341", "006d"))
    results = UsbDescriptorProbe(sysfs_root=root).identify(PORT)
    assert len(results) == 1
    assert results[0].board_id == "arduino-uno-r4-wifi-34367333130351f0c1c1"
    assert results[0].family == "renesas"
    assert results[0].id_source == "usb-serial"
    assert results[0].usb_vid == "2341"
    assert results[0].usb_pid == "006d"


def test_bootloader_pid_names_the_same_board(sysfs: Sysfs) -> None:
    # A board in its bootloader enumerates as a different PID; both must fold to
    # one name, or the link would change under the user mid-upload.
    root = sysfs(port_name="ttyACM0", attributes=descriptors("2341", "1002"))
    results = UsbDescriptorProbe(sysfs_root=root).identify(PORT)
    assert results[0].variant == "arduino-uno-r4-wifi"


def test_espressif_board_is_left_to_esptool(sysfs: Sysfs) -> None:
    # 2341:0070 is the Arduino Nano ESP32. Its eFuse MAC is a better unique ID
    # than a USB serial number, so this probe must not claim the port first.
    root = sysfs(port_name="ttyACM0", attributes=descriptors("2341", "0070"))
    probe = UsbDescriptorProbe(sysfs_root=root)
    assert not probe.supports(PORT)
    assert probe.identify(PORT) == []


def test_unknown_pair_is_not_supported(sysfs: Sysfs) -> None:
    root = sysfs(port_name="ttyACM0", attributes=descriptors("1a86", "7523"))
    assert not UsbDescriptorProbe(sysfs_root=root).supports(PORT)


def test_board_without_a_serial_number_is_not_named(sysfs: Sysfs) -> None:
    root = sysfs(port_name="ttyACM0", attributes=descriptors("2341", "0043", serial=None))
    probe = UsbDescriptorProbe(sysfs_root=root)
    assert probe.supports(PORT)
    assert probe.identify(PORT) == []


def test_too_short_a_serial_number_is_not_named(sysfs: Sysfs) -> None:
    root = sysfs(port_name="ttyACM0", attributes=descriptors("2341", "0043", serial="1"))
    assert UsbDescriptorProbe(sysfs_root=root).identify(PORT) == []


def test_pair_shared_by_several_boards_is_not_named(
    sysfs: Sysfs, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(arduino_ids.ARDUINO_USB_IDS, (0x2341, 0x0043), ("avr", "arduino:avr", None))
    root = sysfs(port_name="ttyACM0", attributes=descriptors("2341", "0043"))
    probe = UsbDescriptorProbe(sysfs_root=root)
    assert not probe.supports(PORT)
    assert probe.identify(PORT) == []


def test_port_without_usb_descriptors_is_not_supported() -> None:
    assert not UsbDescriptorProbe(sysfs_root=Path("/nonexistent")).supports(PORT)
