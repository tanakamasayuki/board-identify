"""WCH chip names resolved from the WCH-Link attach signature.

Device IDs and series/family names come from ch32-device-data via
wch_chips_data. Revision bits [7:4] are ignored for CH32 IDs.
Unknown parts fall back to the series or shared peripheral family,
then to the raw signature.
"""

from board_identify.probes.wch_chips_data import CHIP_NAMES, SERIES_NAMES

__all__ = ["CHIP_NAMES", "SERIES_NAMES", "chip_name", "resolve_chip"]


def resolve_chip(family_id: int, chip_id: int) -> str | None:
    """Name a target from its attach signature, as specifically as the tables allow.

    Returns an orderable part number, or the series when only that is listed, or
    None when neither table recognises the signature. A None is worth acting on:
    a signature that resolves nowhere is as likely to be a corrupted readback as
    a chip newer than these tables.
    """
    name = CHIP_NAMES.get(chip_id & 0xFFFFFF0F)
    if name is not None:
        return name

    model_id = (chip_id >> 16) & 0xFFF0
    return SERIES_NAMES.get((family_id, model_id))


def chip_name(family_id: int, chip_id: int) -> str:
    """Like :func:`resolve_chip`, falling back to the raw signature in hex.

    The fallback keeps an unlisted chip nameable, and stable, rather than
    unpublishable.
    """
    return resolve_chip(family_id, chip_id) or f"WCH {family_id:02x}-{chip_id:08x}"
