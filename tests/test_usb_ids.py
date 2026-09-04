from collections.abc import Callable
from pathlib import Path

import pytest

from board_identify.arduino_ids import ARDUINO_USB_IDS
from board_identify.normalize import normalize_component
from board_identify.usb_ids import (
    GENERIC_BRIDGE_IDS,
    board_for_port,
    board_for_usb_id,
    is_generic_bridge,
)

Sysfs = Callable[..., Path]

CH340 = (0x1A86, 0x7523)
UNO_R4_WIFI = (0x2341, 0x006D)
NANO_ESP32 = (0x2341, 0x0070)


def test_table_holds_no_stock_bridge_id() -> None:
    # The point of the table is to rule a family out. A CH340 rules nothing out,
    # so letting one in would suppress esptool for every board behind one.
    assert not set(ARDUINO_USB_IDS) & GENERIC_BRIDGE_IDS


def test_table_entries_are_well_formed() -> None:
    for (vid, pid), (family, platform, variant) in ARDUINO_USB_IDS.items():
        assert 0 <= vid <= 0xFFFF and 0 <= pid <= 0xFFFF
        assert family and family == normalize_component(family)
        assert ":" in platform
        assert variant is None or variant == normalize_component(variant)


def test_known_arduino_board_resolves() -> None:
    board = board_for_usb_id(*UNO_R4_WIFI)
    assert board is not None
    assert board.family == "renesas"
    assert board.variant == "arduino-uno-r4-wifi"
    assert not board.is_espressif


def test_arduino_branded_esp32_board_stays_espressif() -> None:
    board = board_for_usb_id(*NANO_ESP32)
    assert board is not None
    assert board.is_espressif


def test_unknown_pair_resolves_to_nothing() -> None:
    assert board_for_usb_id(0x0000, 0x0000) is None


def test_stock_bridge_is_never_a_board(monkeypatch: pytest.MonkeyPatch) -> None:
    # Even a table that did list one, because a future board package registered
    # it, must not let a CH340 speak for the board behind it.
    assert is_generic_bridge(*CH340)
    monkeypatch.setitem(ARDUINO_USB_IDS, CH340, ("avr", "vendor:avr", "some-board"))
    assert board_for_usb_id(*CH340) is None


def test_board_for_port_reads_sysfs(sysfs: Sysfs) -> None:
    root = sysfs(
        port_name="ttyACM0",
        attributes={
            "idVendor": "2341",
            "idProduct": "006d",
            "busnum": "001",
            "devnum": "007",
            "serial": "34367333130351F0C1C1",
        },
    )
    board = board_for_port(Path("/dev/ttyACM0"), sysfs_root=root)
    assert board is not None
    assert board.variant == "arduino-uno-r4-wifi"


def test_board_for_port_without_usb_device() -> None:
    assert board_for_port(Path("/dev/ttyS0"), sysfs_root=Path("/nonexistent")) is None
