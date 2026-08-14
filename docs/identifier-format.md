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
rp2040-e6616407e3398c2f
arduino-uno-r4-85735313331351f0
```

## Normalisation

`normalize_component()` applies NFKC, lowercases, and replaces every run of
non-alphanumeric characters with a single `-`. `normalize_unique_id()` removes
everything that is not alphanumeric and lowercases the rest. Both raise
`ValueError` when nothing usable remains, and a probe that cannot produce a valid
component returns `None` instead of publishing a questionable name.

| Input | Output |
| --- | --- |
| `ESP32-S3` | `esp32-s3` |
| `ESP32-C3 (QFN32)` | `esp32-c3-qfn32` |
| `7C:DF:A1:12:34:56` | `7cdfa1123456` |

See also [Architecture](architecture.md).
