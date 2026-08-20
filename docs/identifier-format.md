# Identifier format

*[English](identifier-format.md) | [日本語](identifier-format.ja.md)*

Stable names use:

```text
<variant>-<unique-id>
```

Rules:

- lowercase ASCII
- components separated with `-`
- punctuation removed from unique IDs
- the unique ID must originate from the target when possible
- a unique ID shorter than 6 characters is rejected
- `/` and NUL never appear, because the identifier is used as a file name

Examples:

```text
esp32-s3-7cdfa1123456
ch32x035c8t6-1ff9abcd880ebc48
wch-link-fc928f068181
rp2040-e6616407e3398c2f
arduino-uno-r4-85735313331351f0
```

## More than one name for one port

A port can be published under several identifiers at once, most specific first. A
WCH-Link debug probe gives two: the board on its debug pins, named from the UUID
programmed into it at the factory, and the probe itself, named from its USB serial
number.

```text
ch32x035c8t6-1ff9abcd880ebc48 -> /dev/ttyACM4
wch-link-fc928f068181         -> /dev/ttyACM4
```

The first follows the board to whichever probe it is plugged into. The second stays with
the probe whatever is attached to it, and is published even when nothing is. Use whichever
one matches what you mean by "that device".

## How specific a variant gets

A variant is as specific as the target can be pinned down. For a WCH target the attach
signature resolves to an orderable part number when it is listed, and otherwise falls back
to the series and then to the raw signature:

| Signature | Variant |
| --- | --- |
| family `0x0d`, chip ID `0x03510601` | `ch32x035c8t6` |
| family `0x0d`, chip ID not listed | `ch32x035` |
| neither listed | `wch-0d-03510601` |

## Normalisation

`normalize_component()` applies NFKC, lowercases, and replaces every run of
non-alphanumeric characters with a single `-`. `normalize_unique_id()` removes
everything that is not alphanumeric and lowercases the rest. Both raise
`ValueError` when nothing usable remains, and a probe that cannot produce a valid
component leaves that identification out rather than publishing a questionable name.

| Input | Output |
| --- | --- |
| `ESP32-S3` | `esp32-s3` |
| `ESP32-C3 (QFN32)` | `esp32-c3-qfn32` |
| `CH32X035C8T6` | `ch32x035c8t6` |
| `7C:DF:A1:12:34:56` | `7cdfa1123456` |

See also [Architecture](architecture.md).
