"""WCH chip names for the signatures a WCH-Link reports when it attaches.

The attach reply carries a family byte and a four byte chip ID, which name the
part at two levels of detail:

* ``CHIP_ID_NAMES`` resolves the full chip ID to an orderable part number such
  as ``CH32X035C8T6``. Each table masks the ID before the lookup, because some
  families encode a revision in bits the part number does not depend on. The
  entries are transcribed from the ``chip_detection`` sections of probe-rs'
  target descriptions (probe-rs, MIT / Apache-2.0).
* ``SERIES_NAMES`` resolves the coarser ``(family, model)`` signature to a
  series such as ``CH32X035``, and covers parts the tables above do not list.
  The entries are transcribed from ch32fun's ``minichlink`` (MIT).

Masks are tried most specific first, so a narrow table always wins over a wide
one.
"""

__all__ = ["CHIP_ID_NAMES", "SERIES_NAMES", "chip_name", "resolve_chip"]

# (mask, {chip_id & mask: part number})
CHIP_ID_NAMES: tuple[tuple[int, dict[int, str]], ...] = (
    (
        0xFFFFFFFF,
        {
            0x64300601: "CH643W",
            0x64310601: "CH643Q",
            0x64330601: "CH643L",
            0x64340601: "CH643U",
        },
    ),
    (
        0xFFFFFF0F,
        {
            0x00200600: "CH32V002F4P6",
            0x00210600: "CH32V002F4U6",
            0x00220600: "CH32V002A4M6",
            0x00230600: "CH32V002D4U6",
            0x00240600: "CH32V002J4M6",
            0x00300500: "CH32V003F4P6",
            0x00310500: "CH32V003F4U6",
            0x00320500: "CH32V003A4M6",
            0x00330500: "CH32V003J4M6",
            0x00400600: "CH32V004F6P1",
            0x00410600: "CH32V004F6U1",
            0x00500600: "CH32V005E6R6",
            0x00510600: "CH32V005F6U6",
            0x00520600: "CH32V005F6P6",
            0x00530600: "CH32V005D6U6",
            0x00600600: "CH32V006K8U6",
            0x00610600: "CH32V006E8R6",
            0x00620600: "CH32V006F8U6",
            0x00630600: "CH32V006F8P6",
            0x00700800: "CH32M007G8R6",
            0x00710600: "CH32V007E8R6",
            0x00720600: "CH32V007K8U6",
            0x00730800: "CH32M007E8R6",
            0x00740800: "CH32M007E8U6",
            0x03500601: "CH32X035R8T6",
            0x03510601: "CH32X035C8T6",
            0x03560601: "CH32X035G8U6",
            0x03570601: "CH32X035F7P6",
            0x035A0601: "CH32X033F8P6",
            0x035B0601: "CH32X035G8R6",
            0x035E0601: "CH32X035F8U6",
            0x10310700: "CH32L103C8T6",
            0x10320700: "CH32L103K8U6",
            0x10370700: "CH32L103F7P6",
            0x103A0700: "CH32L103F8P6",
            0x103B0700: "CH32L103G8R6",
            0x103D0700: "CH32L103F8U6",
            0x20004102: "CH32F103C8T6",
            0x2000410F: "CH32F103R8T6",
            0x20300500: "CH32V203C8U6",
            0x20310500: "CH32V203C8T6",
            0x20320500: "CH32V203K8T6",
            0x20330500: "CH32V203C6T6",
            0x2034050C: "CH32V203RBT6",
            0x20350500: "CH32V203K6T6",
            0x20360500: "CH32V203G6U6",
            0x20370500: "CH32V203F6P6",
            0x203A0500: "CH32V203F8P6",
            0x203B0500: "CH32V203G8R6",
            0x203D0500: "CH32V203F8U6",
            0x2080050C: "CH32V208WBU6",
            0x2081050C: "CH32V208RBT6",
            0x2082050C: "CH32V208CBU6",
            0x2083050C: "CH32V208GBU6",
            0x25004102: "CH32V103C8T6",
            0x2500410F: "CH32V103R8T6",
            0x30300504: "CH32V303VCT6",
            0x30310504: "CH32V303RCT6",
            0x30320504: "CH32V303RBT6",
            0x30330504: "CH32V303CBT6",
            0x30500508: "CH32V305RBT6",
            0x30520508: "CH32V305FBP6",
            0x305B0508: "CH32V305GBU6",
            0x30700508: "CH32V307VCT6",
            0x30710508: "CH32V307RCT6",
            0x30730508: "CH32V307WCU6",
            0x3170B508: "CH32V317VCT6",
            0x3173B508: "CH32V317WCU6",
            0x4150050D: "CH32H415REU6",
            0x4160050D: "CH32H416RDU6",
            0x4170050D: "CH32H417QEU6",
            0x4171050D: "CH32H417MEU6",
            0x4172050D: "CH32H417WEU6",
            0x64100500: "CH641F",
            0x64110500: "CH641D",
            0x64120500: "CH641X",
            0x64150500: "CH641U",
            0x64160500: "CH641P",
        },
    ),
    (
        0xFF000000,
        {
            0x70000000: "CH570",
            0x72000000: "CH572",
        },
    ),
)

# (family byte, model) -> series, where model is the chip ID's top half masked
# with 0xfff0. CH573 and CH573Q share a signature; the base part wins.
SERIES_NAMES: dict[tuple[int, int], str] = {
    (0x01, 0x2500): "CH32V103",
    (0x02, 0x7100): "CH571",
    (0x02, 0x7300): "CH573",
    (0x03, 0x6500): "CH565",
    (0x03, 0x6900): "CH569",
    (0x05, 0x2030): "CH32V203",
    (0x05, 0x2080): "CH32V208",
    (0x06, 0x3030): "CH32V303",
    (0x06, 0x3050): "CH32V305",
    (0x06, 0x3070): "CH32V307",
    (0x06, 0x3170): "CH32V317",
    (0x07, 0x8100): "CH581",
    (0x07, 0x8200): "CH582",
    (0x07, 0x8300): "CH583",
    (0x09, 0x0030): "CH32V003",
    (0x0B, 0x9100): "CH591",
    (0x0B, 0x9200): "CH592",
    (0x0C, 0x6430): "CH643",
    (0x0D, 0x0330): "CH32X033",
    (0x0D, 0x0350): "CH32X035",
    (0x0E, 0x1030): "CH32L103",
    (0x0F, 0x6400): "CH564",
    (0x0F, 0x64C0): "CH564C",
    (0x46, 0x6450): "CH645",
    (0x49, 0x6410): "CH641",
    (0x4B, 0x8400): "CH584",
    (0x4B, 0x9300): "CH585",
    (0x4E, 0x0020): "CH32V002",
    (0x4E, 0x0040): "CH32V004",
    (0x4E, 0x0050): "CH32V005",
    (0x4E, 0x0060): "CH32V006",
    (0x4E, 0x0070): "CH32V007",
    (0x8B, 0x7000): "CH570",
    (0x8B, 0x7200): "CH572",
    (0x8E, 0x0300): "CH32M030",
    (0xC6, 0x4150): "CH32H415",
    (0xC6, 0x4160): "CH32H416",
    (0xC6, 0x4170): "CH32H417",
    (0xCE, 0x2050): "CH32V205",
}


def resolve_chip(family_id: int, chip_id: int) -> str | None:
    """Name a target from its attach signature, as specifically as the tables allow.

    Returns an orderable part number, or the series when only that is listed, or
    None when neither table recognises the signature. A None is worth acting on:
    a signature that resolves nowhere is as likely to be a corrupted readback as
    a chip newer than these tables.
    """
    for mask, names in CHIP_ID_NAMES:
        part_number = names.get(chip_id & mask)
        if part_number is not None:
            return part_number

    model_id = (chip_id >> 16) & 0xFFF0
    return SERIES_NAMES.get((family_id, model_id))


def chip_name(family_id: int, chip_id: int) -> str:
    """Like :func:`resolve_chip`, falling back to the raw signature in hex.

    The fallback keeps an unlisted chip nameable, and stable, rather than
    unpublishable.
    """
    return resolve_chip(family_id, chip_id) or f"WCH {family_id:02x}-{chip_id:08x}"
