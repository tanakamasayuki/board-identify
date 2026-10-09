#!/usr/bin/env python3
"""Generate CH32 identification tables from GitHub's ch32-device-data.

    python scripts/generate_wch_chips.py

The default fetches the latest upstream HEAD. --revision pins a commit.
The generated module is committed and used offline at runtime.
"""

import argparse
import csv
import io
import re
import subprocess
import urllib.request
from collections import defaultdict
from pathlib import Path

# AttachChip protocol values from ch32rv crates/wchlink/src/probe.rs.
# The device data's family names describe shared peripherals, not these bytes.
FAMILY_BYTES = {
    "CH32H417": (0xC6,),
    "CH32L103": (0x0E,),
    "CH32V003": (0x09,),
    "CH32V006": (0x4E,),
    "CH32V103": (0x01,),
    "CH32V205": (0xCE,),
    "CH32V20x": (0x05,),
    "CH32V307": (0x06,),
    "CH32X035": (0x0D,),
    "CH32X315": (0xE6,),
}
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "src/board_identify/probes/wch_chips_data.py"
REPOSITORY = "https://github.com/ch32-riscv-ug/ch32-device-data"


def fetch(revision: str, path: str) -> str:
    url = f"https://raw.githubusercontent.com/ch32-riscv-ug/ch32-device-data/{revision}/{path}"
    with urllib.request.urlopen(url, timeout=30) as response:
        return str(response.read().decode("utf-8"))


def generate(revision: str, parts_csv: str, ids_csv: str) -> str:
    parts = {row["part_number"]: row for row in csv.DictReader(io.StringIO(parts_csv))}
    signatures: dict[int, set[str]] = defaultdict(set)
    models: dict[tuple[int, int], set[str]] = defaultdict(set)
    families: dict[tuple[int, int], set[str]] = defaultdict(set)
    for row in csv.DictReader(io.StringIO(ids_csv)):
        chip_id = int(row["device_id"], 0)
        if chip_id in (0, 0xFFFFFFFF):
            continue
        if row["dont_care_bits"] != "[7:4]":
            raise ValueError(f"Unsupported revision mask: {row}")
        chip_id &= 0xFFFFFF0F
        name = row["part_number"]
        part = parts[name]
        signatures[chip_id].add(name)
        for family_byte in FAMILY_BYTES.get(part["family"], ()):
            key = (family_byte, (chip_id >> 16) & 0xFFF0)
            models[key].add(part["series"])
            families[key].add(part["family"])

    lines = [
        '"""CH32 names generated from ch32-device-data (MIT).',
        "",
        "Source: https://github.com/ch32-riscv-ug/ch32-device-data",
        f"Source revision: {revision}",
        "Inputs: index/device_ids.csv and index/parts.csv.",
        "Regenerate with scripts/generate_wch_chips.py; do not edit by hand.",
        "Copyright (c) 2026 CH32 RISC-V User Group.",
        "License: licenses/ch32-device-data.txt.",
        '"""',
        "",
        "# Shared IDs resolve to a series rather than an arbitrary orderable part.",
        "CHIP_NAMES: dict[int, str] = {",
    ]
    for chip_id, names in sorted(signatures.items()):
        if len(names) == 1:
            resolved = next(iter(names))
        else:
            series = {parts[name]["series"] for name in names}
            if len(series) != 1:
                raise ValueError(f"Ambiguous device ID {chip_id:#x}: {names}")
            resolved = next(iter(series))
        lines.append(f'    0x{chip_id:08X}: "{resolved}",')
    lines += [
        "}",
        "",
        "# Mixed-series models resolve only to their shared peripheral family.",
        "SERIES_NAMES: dict[tuple[int, int], str] = {",
    ]
    for key, series in sorted(models.items()):
        candidates = series if len(series) == 1 else families[key]
        if len(candidates) != 1:
            continue
        lines.append(f'    (0x{key[0]:02X}, 0x{key[1]:04X}): "{next(iter(candidates))}",')
    lines += ["}", ""]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", help="Full upstream commit SHA; defaults to latest HEAD")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    revision = args.revision
    if revision is None:
        revision = subprocess.check_output(
            ["git", "ls-remote", REPOSITORY + ".git", "HEAD"], text=True, timeout=30
        ).split()[0]
    if re.fullmatch(r"[0-9a-f]{40}", revision) is None:
        parser.error("--revision must be a full commit SHA")
    parts_csv = fetch(revision, "index/parts.csv")
    ids_csv = fetch(revision, "index/device_ids.csv")
    content = generate(revision, parts_csv, ids_csv)
    args.output.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
