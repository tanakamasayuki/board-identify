from pathlib import Path

import pytest

from board_identify.model import Identification
from board_identify.normalize import normalize_component, normalize_unique_id


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("ESP32-S3", "esp32-s3"),
        ("  ESP32 S3  ", "esp32-s3"),
        ("ESP32-C3 (QFN32)", "esp32-c3-qfn32"),
        ("ＥＳＰ３２", "esp32"),  # noqa: RUF001 - full-width input is folded by NFKD
        ("--esp32--", "esp32"),
        ("Arduino Yún", "arduino-yun"),  # an accent is dropped, not split on
        ("Arduino Yún Mini", "arduino-yun-mini"),
    ],
)
def test_normalize_component(value: str, expected: str) -> None:
    assert normalize_component(value) == expected


@pytest.mark.parametrize("value", ["", "   ", "---", "??"])
def test_empty_component_is_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        normalize_component(value)


def test_normalize_unique_id() -> None:
    assert normalize_unique_id("7C:DF:A1:12:34:56") == "7cdfa1123456"


def test_normalize_unique_id_keeps_alphanumerics() -> None:
    assert normalize_unique_id("E6-61-64-07 E3:39/8C_2F") == "e6616407e3398c2f"


@pytest.mark.parametrize("value", ["123", "", "::::"])
def test_short_unique_id_is_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        normalize_unique_id(value)


def test_board_id_is_variant_and_unique_id() -> None:
    result = Identification(
        port=Path("/dev/ttyUSB0"),
        family="espressif",
        variant="esp32-s3",
        unique_id="7cdfa1123456",
        id_source="target-mac",
    )
    assert result.board_id == "esp32-s3-7cdfa1123456"
    assert result.to_dict()["port"] == "/dev/ttyUSB0"


@pytest.mark.parametrize(("variant", "unique_id"), [("../esc", "7cdfa1123456"), ("esp32", "")])
def test_unsafe_board_id_is_rejected(variant: str, unique_id: str) -> None:
    with pytest.raises(ValueError):
        Identification(
            port=Path("/dev/ttyUSB0"),
            family="espressif",
            variant=variant,
            unique_id=unique_id,
            id_source="target-mac",
        )
