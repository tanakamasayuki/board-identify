from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import usb.core

from board_identify.probes.wch_chips import resolve_chip
from board_identify.probes.wch_link import (
    ATTACH_CHIP,
    CHIP_INFO,
    CLEAR_STATE,
    PROBE_INFO,
    REDETECT_CHIP,
    SET_SPEED,
    ChipSignature,
    ProbeInfo,
    TargetInfo,
    WchLinkProbe,
)
from board_identify.usbinfo import UsbDevice

Reply = Callable[[str], bytes]
Sysfs = Callable[..., Path]

DEVICE = UsbDevice(
    path=Path("/sys/devices/usb1/1-8"),
    vid=0x1A86,
    pid=0x8010,
    bus=1,
    address=22,
    serial="FC928F068181",
    product="WCH-Link",
)
SIGNATURE = ChipSignature(family_id=0x0D, chip_id=0x03510601)


class FakeHandle:
    """A claimed vendor interface that answers from a recorded script.

    With ``after_reset`` it answers differently once REDETECT_CHIP has been sent,
    which is how a probe holding a corrupted readback behaves.
    """

    def __init__(
        self,
        replies: dict[bytes, bytes],
        fail_on: bytes | None = None,
        after_reset: dict[bytes, bytes] | None = None,
    ) -> None:
        self.replies = replies
        self.fail_on = fail_on
        self.after_reset = after_reset
        self.sent: list[bytes] = []
        self._pending = b""

    def write(self, endpoint: int, payload: bytes, timeout: int) -> int:
        payload = bytes(payload)
        self.sent.append(payload)
        if self.fail_on is not None and payload == self.fail_on:
            raise usb.core.USBError("boom")
        if payload == REDETECT_CHIP and self.after_reset is not None:
            self.replies = self.after_reset
        self._pending = self.replies.get(payload, b"")
        return len(payload)

    def read(self, endpoint: int, size: int, timeout: int) -> bytes:
        return self._pending


@pytest.fixture
def replies(wch_reply: Reply) -> dict[bytes, bytes]:
    return {
        CLEAR_STATE: wch_reply("clear-state.txt"),
        PROBE_INFO: wch_reply("probe-info-linke.txt"),
        SET_SPEED: wch_reply("set-speed.txt"),
        ATTACH_CHIP: wch_reply("attach-ch32x035c8t6.txt"),
        CHIP_INFO: wch_reply("chip-info-ch32x035c8t6.txt"),
    }


def test_parse_probe_info(wch_reply: Reply) -> None:
    info = WchLinkProbe.parse_probe_info(wch_reply("probe-info-linke.txt"))

    assert info == ProbeInfo(variant="wch-linke", firmware="2.12")


def test_parse_probe_info_of_another_variant(wch_reply: Reply) -> None:
    info = WchLinkProbe.parse_probe_info(wch_reply("probe-info-ch32v307.txt"))

    assert info == ProbeInfo(variant="wch-link-ch32v307", firmware="2.8")


def test_parse_probe_info_of_an_unknown_variant() -> None:
    info = WchLinkProbe.parse_probe_info(bytes.fromhex("82 0d 04 03 00 7f 00"))

    assert info is not None
    assert info.variant == "wch-link"


@pytest.mark.parametrize("reply", [b"", b"\x82\x0d", b"\x81\x55\x01\x00", b"\x00" * 8])
def test_parse_probe_info_rejects_anything_else(reply: bytes) -> None:
    assert WchLinkProbe.parse_probe_info(reply) is None


def test_parse_attach(wch_reply: Reply) -> None:
    assert WchLinkProbe.parse_attach(wch_reply("attach-ch32x035c8t6.txt")) == SIGNATURE


def test_parse_attach_without_a_target(wch_reply: Reply) -> None:
    assert WchLinkProbe.parse_attach(wch_reply("attach-no-target.txt")) is None


def test_parse_attach_rejects_a_truncated_reply() -> None:
    assert WchLinkProbe.parse_attach(b"\x82\x0d\x05\x0d") is None


def test_parse_chip_info(wch_reply: Reply) -> None:
    target = WchLinkProbe.parse_chip_info(wch_reply("chip-info-ch32x035c8t6.txt"), SIGNATURE)

    assert target == TargetInfo(chip="CH32X035C8T6", uuid="1ff9abcd880ebc48", flash_kb=62)


def test_parse_chip_info_rejects_the_wrong_length() -> None:
    assert WchLinkProbe.parse_chip_info(b"\xff\xff\x00\x3e", SIGNATURE) is None


def test_parse_chip_info_rejects_an_unanswered_read() -> None:
    assert WchLinkProbe.parse_chip_info(bytes(20), SIGNATURE) is None


@pytest.mark.parametrize("uuid", [bytes(8), b"\xff" * 8])
def test_parse_chip_info_rejects_a_constant_uuid(uuid: bytes) -> None:
    reply = b"\xff\xff\x00\x3e" + uuid + b"\xff\xff\xff\xff\x03\x51\x06\x01"

    assert WchLinkProbe.parse_chip_info(reply, SIGNATURE) is None


def test_session_follows_the_command_order(replies: dict[bytes, bytes]) -> None:
    handle = FakeHandle(replies)

    info, target = WchLinkProbe().session(handle)

    assert info == ProbeInfo(variant="wch-linke", firmware="2.12")
    assert target is not None
    assert target.chip == "CH32X035C8T6"
    assert handle.sent == [
        CLEAR_STATE,
        PROBE_INFO,
        SET_SPEED,
        ATTACH_CHIP,
        CHIP_INFO,
        CLEAR_STATE,
    ]


def test_session_detaches_even_when_the_target_is_absent(
    replies: dict[bytes, bytes], wch_reply: Reply
) -> None:
    handle = FakeHandle({**replies, ATTACH_CHIP: wch_reply("attach-no-target.txt")})

    info, target = WchLinkProbe().session(handle)

    assert info is not None
    assert target is None
    # Attaching holds the core, so the last thing sent must release it.
    assert handle.sent[-1] == CLEAR_STATE
    assert CHIP_INFO not in handle.sent


def test_session_detaches_after_a_failure(replies: dict[bytes, bytes]) -> None:
    handle = FakeHandle(replies, fail_on=CHIP_INFO)

    with pytest.raises(usb.core.USBError):
        WchLinkProbe().session(handle)

    assert handle.sent[-1] == CLEAR_STATE


def test_transport_identification_names_the_probe_by_its_serial() -> None:
    result = WchLinkProbe.transport_identification(
        Path("/dev/ttyACM4"), DEVICE, ProbeInfo(variant="wch-linke", firmware="2.12")
    )

    assert result is not None
    assert result.board_id == "wch-link-fc928f068181"
    assert result.id_source == "transport-serial"
    # The variant is metadata, so a busy vendor interface cannot rename the link.
    assert result.transport == "wch-linke"
    assert (result.usb_vid, result.usb_pid) == ("1a86", "8010")


def test_transport_identification_without_a_probe_info() -> None:
    result = WchLinkProbe.transport_identification(Path("/dev/ttyACM4"), DEVICE, None)

    assert result is not None
    assert result.board_id == "wch-link-fc928f068181"
    assert result.transport is None


def test_transport_identification_needs_a_serial_number() -> None:
    anonymous = UsbDevice(path=Path("/sys"), vid=0x1A86, pid=0x8010, bus=1, address=22)

    assert WchLinkProbe.transport_identification(Path("/dev/ttyACM4"), anonymous, None) is None


def test_target_identification_names_the_board_by_its_uuid() -> None:
    target = TargetInfo(chip="CH32X035C8T6", uuid="1ff9abcd880ebc48", flash_kb=62)

    result = WchLinkProbe.target_identification(Path("/dev/ttyACM4"), DEVICE, None, target)

    assert result is not None
    assert result.board_id == "ch32x035c8t6-1ff9abcd880ebc48"
    assert result.id_source == "target-cpu-id"
    assert result.usb_serial == "FC928F068181"


def test_target_identification_without_a_target() -> None:
    assert WchLinkProbe.target_identification(Path("/dev/ttyACM4"), DEVICE, None, None) is None


def test_supports_a_wch_link(sysfs: Sysfs) -> None:
    probe = WchLinkProbe(sysfs_root=sysfs())

    assert probe.supports(Path("/dev/ttyACM4"))


def test_does_not_support_another_wch_adapter(sysfs: Sysfs) -> None:
    root = sysfs(
        port_name="ttyUSB0",
        attributes={
            "idVendor": "1a86",
            "idProduct": "7523",
            "busnum": "001",
            "devnum": "006",
        },
    )
    probe = WchLinkProbe(sysfs_root=root)

    # A CH340 is a plain bridge, so this probe must let the next one try.
    assert not probe.supports(Path("/dev/ttyUSB0"))


def test_identify_returns_the_target_first(
    monkeypatch: pytest.MonkeyPatch, sysfs: Sysfs, replies: dict[bytes, bytes]
) -> None:
    probe = WchLinkProbe(sysfs_root=sysfs())
    monkeypatch.setattr(probe, "query", lambda device: probe.session(FakeHandle(replies)))

    results = probe.identify(Path("/dev/ttyACM4"))

    assert [result.board_id for result in results] == [
        "ch32x035c8t6-1ff9abcd880ebc48",
        "wch-link-fc928f068181",
    ]


def test_identify_publishes_the_probe_alone_when_no_target_answers(
    monkeypatch: pytest.MonkeyPatch, sysfs: Sysfs
) -> None:
    probe = WchLinkProbe(sysfs_root=sysfs())
    monkeypatch.setattr(probe, "query", lambda device: (None, None))

    results = probe.identify(Path("/dev/ttyACM4"))

    assert [result.board_id for result in results] == ["wch-link-fc928f068181"]


def test_identify_without_target_probing_stays_on_sysfs(sysfs: Sysfs) -> None:
    def forbidden(device: UsbDevice) -> tuple[Any, Any]:
        raise AssertionError("must not touch USB")

    probe = WchLinkProbe(probe_target=False, sysfs_root=sysfs())
    probe.query = forbidden  # type: ignore[method-assign]

    results = probe.identify(Path("/dev/ttyACM4"))

    assert [result.board_id for result in results] == ["wch-link-fc928f068181"]


def test_identify_skips_the_target_on_an_arm_mode_probe(sysfs: Sysfs) -> None:
    root = sysfs(
        attributes={
            "idVendor": "1a86",
            "idProduct": "8011",
            "busnum": "001",
            "devnum": "022",
            "serial": "FC928F068181",
        }
    )

    def forbidden(device: UsbDevice) -> tuple[Any, Any]:
        raise AssertionError("CMSIS-DAP does not speak this protocol")

    probe = WchLinkProbe(sysfs_root=root)
    probe.query = forbidden  # type: ignore[method-assign]

    results = probe.identify(Path("/dev/ttyACM4"))

    assert [result.board_id for result in results] == ["wch-link-fc928f068181"]


def test_identify_ignores_a_port_that_is_not_a_wch_link(sysfs: Sysfs) -> None:
    root = sysfs(
        attributes={
            "idVendor": "10c4",
            "idProduct": "ea60",
            "busnum": "001",
            "devnum": "007",
            "serial": "0001B2C3",
        }
    )

    assert WchLinkProbe(sysfs_root=root).identify(Path("/dev/ttyACM4")) == []


@pytest.fixture
def corrupted_replies(replies: dict[bytes, bytes], wch_reply: Reply) -> dict[bytes, bytes]:
    """What the probe answers while it holds a broken readback of its target."""
    return {
        **replies,
        REDETECT_CHIP: wch_reply("redetect-chip.txt"),
        ATTACH_CHIP: wch_reply("attach-corrupted.txt"),
        CHIP_INFO: wch_reply("chip-info-corrupted.txt"),
    }


@pytest.fixture
def healthy_v003_replies(replies: dict[bytes, bytes], wch_reply: Reply) -> dict[bytes, bytes]:
    return {
        **replies,
        REDETECT_CHIP: wch_reply("redetect-chip.txt"),
        ATTACH_CHIP: wch_reply("attach-ch32v003f4p6.txt"),
        CHIP_INFO: wch_reply("chip-info-ch32v003f4p6.txt"),
    }


def test_parse_chip_info_of_a_ch32v003(wch_reply: Reply) -> None:
    signature = WchLinkProbe.parse_attach(wch_reply("attach-ch32v003f4p6.txt"))
    assert signature == ChipSignature(family_id=0x09, chip_id=0x00300500)

    target = WchLinkProbe.parse_chip_info(wch_reply("chip-info-ch32v003f4p6.txt"), signature)
    assert target == TargetInfo(chip="CH32V003F4P6", uuid="f9e1abcd6201bc53", flash_kb=16)


def test_parse_chip_info_rejects_a_repeating_readback(wch_reply: Reply) -> None:
    """The corrupted reply is one four byte word repeated, never a real UUID."""
    signature = WchLinkProbe.parse_attach(wch_reply("attach-corrupted.txt"))
    assert signature is not None

    assert WchLinkProbe.parse_chip_info(wch_reply("chip-info-corrupted.txt"), signature) is None


def test_a_corrupted_signature_resolves_to_no_chip(wch_reply: Reply) -> None:
    signature = WchLinkProbe.parse_attach(wch_reply("attach-corrupted.txt"))
    assert signature is not None
    # The family byte survives, which is what makes the chip ID look plausible.
    assert signature.family_id == 0x09
    assert resolve_chip(signature.family_id, signature.chip_id) is None


def test_session_retries_a_corrupted_readback(
    corrupted_replies: dict[bytes, bytes], healthy_v003_replies: dict[bytes, bytes]
) -> None:
    handle = FakeHandle(corrupted_replies, after_reset=healthy_v003_replies)

    _, target = WchLinkProbe().session(handle)

    assert target == TargetInfo(chip="CH32V003F4P6", uuid="f9e1abcd6201bc53", flash_kb=16)
    assert REDETECT_CHIP in handle.sent


def test_session_publishes_nothing_when_the_retry_does_not_help(
    corrupted_replies: dict[bytes, bytes],
) -> None:
    handle = FakeHandle(corrupted_replies)

    _, target = WchLinkProbe().session(handle)

    # A bogus UUID is shared by every board in this state, so it must not be published.
    assert target is None
    assert REDETECT_CHIP in handle.sent
    assert handle.sent[-1] == CLEAR_STATE


def test_session_does_not_retry_a_healthy_target(replies: dict[bytes, bytes]) -> None:
    handle = FakeHandle(replies)

    _, target = WchLinkProbe().session(handle)

    assert target is not None
    assert REDETECT_CHIP not in handle.sent


def test_session_does_not_retry_when_no_target_answers(
    replies: dict[bytes, bytes], wch_reply: Reply
) -> None:
    handle = FakeHandle({**replies, ATTACH_CHIP: wch_reply("attach-no-target.txt")})

    WchLinkProbe().session(handle)

    assert REDETECT_CHIP not in handle.sent
