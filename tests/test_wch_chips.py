import pytest

from board_identify.probes.wch_chips import chip_name


def test_captured_target_resolves_to_an_orderable_part_number() -> None:
    # Recorded from a WCH-LinkE: family 0x0d, chip ID 03-51-06-01.
    assert chip_name(0x0D, 0x03510601) == "CH32X035C8T6"


@pytest.mark.parametrize("revision", range(16))
@pytest.mark.parametrize(
    ("family_id", "chip_id", "expected"),
    [
        (0xCE, 0x20510500, "CH32V205RCT6"),
        (0xE6, 0x31500000, "CH32X315MCU6"),
    ],
)
def test_v205_x315_ignore_silicon_revision(
    family_id: int, chip_id: int, expected: str, revision: int
) -> None:
    assert chip_name(family_id, chip_id | (revision << 4)) == expected


@pytest.mark.parametrize(
    ("family_id", "chip_id", "expected"),
    [
        (0x09, 0x00330500, "CH32V003J4M6"),
        (0x4E, 0x00730800, "CH32M007E8R6"),
        (0x06, 0x30700508, "CH32V307VCT6"),
    ],
)
def test_part_numbers_from_device_data(family_id: int, chip_id: int, expected: str) -> None:
    assert chip_name(family_id, chip_id) == expected


def test_falls_back_to_the_series_for_an_unlisted_part() -> None:
    # A CH32X035 signature whose exact chip ID is not in any table.
    assert chip_name(0x0D, 0x03500000) == "CH32X035"
    assert chip_name(0xCE, 0x205F0500) == "CH32V205"
    assert chip_name(0xE6, 0x315F000F) == "CH32X315"


def test_falls_back_to_hex_for_an_unknown_chip() -> None:
    assert chip_name(0x99, 0x12345678) == "WCH 99-12345678"


@pytest.mark.parametrize(
    ("family_id", "chip_id", "expected"),
    [
        (0x0C, 0x64300601, "WCH 0c-64300601"),
        (0x49, 0x64100500, "WCH 49-64100500"),
        (0x8B, 0x70000000, "WCH 8b-70000000"),
        (0x8B, 0x72000000, "WCH 8b-72000000"),
        (0x04, 0x20004102, "WCH 04-20004102"),
    ],
)
def test_parts_absent_from_device_data_use_raw_signature(
    family_id: int, chip_id: int, expected: str
) -> None:
    assert chip_name(family_id, chip_id) == expected
