import pytest

from board_identify.normalize import normalize_component, normalize_unique_id


def test_normalize_component() -> None:
    assert normalize_component("ESP32-S3") == "esp32-s3"


def test_normalize_unique_id() -> None:
    assert normalize_unique_id("7C:DF:A1:12:34:56") == "7cdfa1123456"


def test_short_unique_id_is_rejected() -> None:
    with pytest.raises(ValueError):
        normalize_unique_id("123")
