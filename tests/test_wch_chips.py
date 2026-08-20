import pytest

from board_identify.probes.wch_chips import CHIP_ID_NAMES, chip_name


def test_captured_target_resolves_to_an_orderable_part_number() -> None:
    # Recorded from a WCH-LinkE: family 0x0d, chip ID 03-51-06-01.
    assert chip_name(0x0D, 0x03510601) == "CH32X035C8T6"


@pytest.mark.parametrize(
    ("family_id", "chip_id", "expected"),
    [
        (0x09, 0x00330500, "CH32V003J4M6"),
        (0x0C, 0x64300601, "CH643W"),
        (0x8B, 0x70000000, "CH570"),
        (0x4E, 0x00730800, "CH32M007E8R6"),
        (0x06, 0x30700508, "CH32V307VCT6"),
    ],
)
def test_part_numbers_across_the_masks(family_id: int, chip_id: int, expected: str) -> None:
    assert chip_name(family_id, chip_id) == expected


def test_falls_back_to_the_series_for_an_unlisted_part() -> None:
    # A CH32X035 signature whose exact chip ID is not in any table.
    assert chip_name(0x0D, 0x03500000) == "CH32X035"


def test_falls_back_to_hex_for_an_unknown_chip() -> None:
    assert chip_name(0x99, 0x12345678) == "WCH 99-12345678"


def test_every_chip_id_entry_is_reachable() -> None:
    """A wider mask must not shadow a narrower table's entry."""
    shadowed = [
        (hex(mask), hex(chip_id), name)
        for mask, names in CHIP_ID_NAMES
        for chip_id, name in names.items()
        if chip_name(0x00, chip_id) != name
    ]
    assert shadowed == []
