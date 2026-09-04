#!/usr/bin/env python3
"""Merge the arduino-cli-helper board list into ``board_identify.arduino_ids``.

`board_details.json <https://tanakamasayuki.github.io/arduino-cli-helper/>`_ is a
periodically refreshed dump of ``arduino-cli board details`` for a curated set of
boards, keyed by FQBN. Its ``usb_ids`` are the VID/PID pairs a board reports, and
they are what this project needs for its first-pass identification.

Taking them from there rather than from a local Arduino installation is the whole
point: a board only shows up in ``~/.arduino15`` once its core is installed, and
the boards worth identifying are exactly the ones that have not been set up yet.

    uv run python scripts/generate_usb_ids.py

The table it writes is committed, hand-editable, and **append-only**: an existing
entry is never rewritten or removed, so a correction made by hand survives every
later run, and a published link never changes name because upstream renamed a
board. Entries are sorted by VID then PID before the file is written, so a hand
edit in the wrong place is tidied up rather than rejected.

To make the table *forget* a pair, add it to
:data:`~board_identify.usb_ids.GENERIC_BRIDGE_IDS`; deleting the line by hand only
lasts until the next run. That list is also applied here, which is what keeps a
stock CP2102 or CH340 ID out of the table even when a board definition claims one.
"""

import argparse
import importlib.util
import json
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

from board_identify.normalize import normalize_component
from board_identify.usb_ids import ESPRESSIF_FAMILY, GENERIC_BRIDGE_IDS

SOURCE_URL = "https://tanakamasayuki.github.io/arduino-cli-helper/board_details.json"
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "src" / "board_identify" / "arduino_ids.py"
FETCH_TIMEOUT = 60.0

# Architecture directory name to the silicon family a probe would name. Anything
# missing falls back to the architecture itself, which is honest about where the
# entry came from without pretending to know the vendor.
FAMILY_BY_ARCHITECTURE = {
    "avr": "avr",
    "ch32riscv": "wch",
    "ch32v": "wch",
    "esp32": "espressif",
    "esp8266": "espressif",
    "imxrt": "imxrt",
    "megaavr": "avr",
    "nrf52": "nrf52",
    "renesas_portenta": "renesas",
    "renesas_uno": "renesas",
    "rp2040": "rp2040",
    "samd": "samd",
    "spresense": "spresense",
    "stm32": "stm32",
}

# Architectures named after a core or an OS rather than after silicon. They still
# yield a family, but they lose the tie when another claimant of the same pair
# disagrees: a Seeed XIAO nRF52840 is packaged under both `mbed` and `nrf52`, and
# `nrf52` is the one that says what the chip is.
CORE_ARCHITECTURES = frozenset(
    {
        "host",
        "mbed",
        "mbed_edge",
        "mbed_giga",
        "mbed_nano",
        "mbed_nicla",
        "mbed_opta",
        "mbed_portenta",
        "zephyr",
    }
)

Entry = tuple[str, str, str | None]
Table = dict[tuple[int, int], Entry]


@dataclass(frozen=True)
class Claim:
    """One board's claim on one VID/PID pair."""

    platform: str
    architecture: str
    board_id: str
    name: str

    @property
    def family(self) -> str:
        if self.architecture in FAMILY_BY_ARCHITECTURE:
            return FAMILY_BY_ARCHITECTURE[self.architecture]
        try:
            return normalize_component(self.architecture)
        except ValueError:
            return "unknown"

    @property
    def variant(self) -> str | None:
        """The identifier component this board's name folds to.

        The name is what a user sees in the IDE, so it is the one worth
        publishing; the board's own key is the fallback for a name made entirely
        of characters normalisation drops.
        """
        for candidate in (self.name, self.board_id):
            try:
                return normalize_component(candidate)
            except ValueError:
                continue
        return None

    def describe(self) -> str:
        return f"{self.platform} {self.name} [{self.family}]"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--url", default=SOURCE_URL, help=f"source to fetch (default: {SOURCE_URL})"
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="read a downloaded board_details.json instead of fetching it",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail instead of writing when the source would add or reorder anything",
    )
    args = parser.parse_args(argv)

    try:
        document = read_source(args.input, args.url)
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as error:
        print(f"cannot read the board list: {error}", file=sys.stderr)
        return 1

    claims = collect_claims(document)
    if not claims:
        print("the board list declares no usb_ids at all", file=sys.stderr)
        return 1

    existing = load_table(args.output)
    merged, added = merge(existing, resolve(claims, existing))
    rendered = render(merged, args.url)

    if args.check:
        current = args.output.read_text(encoding="utf-8") if args.output.exists() else ""
        if current != rendered:
            print(f"{args.output} is out of date; rerun without --check", file=sys.stderr)
            return 1
        print(f"{args.output} is up to date ({len(merged)} pairs)")
        return 0

    args.output.write_text(rendered, encoding="utf-8")
    print(f"wrote {args.output}: {len(merged)} pairs, {added} added")
    return 0


def read_source(path: Path | None, url: str) -> dict[str, object]:
    """The board list, from a local file when given and over HTTPS otherwise."""
    if path is not None:
        text = path.read_text(encoding="utf-8")
    else:
        if not url.startswith("https://"):
            raise OSError(f"refusing to fetch a non-HTTPS source: {url}")
        print(f"fetching {url}", file=sys.stderr)
        request = urllib.request.Request(url, headers={"User-Agent": "board-identify"})
        with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT) as response:
            text = response.read().decode("utf-8")
    document = json.loads(text)
    if not isinstance(document, dict):
        raise json.JSONDecodeError("expected an object keyed by FQBN", text[:200], 0)
    return document


def collect_claims(document: dict[str, object]) -> dict[tuple[int, int], list[Claim]]:
    """Group the boards of the document by the VID/PID pairs they claim."""
    claims: dict[tuple[int, int], list[Claim]] = defaultdict(list)
    for fqbn, board in sorted(document.items()):
        if not isinstance(board, dict):
            continue
        parts = fqbn.split(":", 2)
        if len(parts) != 3:
            continue
        package, architecture, board_id = parts
        name = board.get("name")
        claim = Claim(
            platform=f"{package}:{architecture}",
            architecture=architecture,
            board_id=board_id,
            name=name if isinstance(name, str) and name else board_id,
        )
        for pair in usb_ids(board.get("usb_ids")):
            claims[pair].append(claim)
    return claims


def usb_ids(raw: object) -> list[tuple[int, int]]:
    """The well-formed ``{"vid": ..., "pid": ...}`` entries of one board."""
    if not isinstance(raw, list):
        return []
    pairs = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            pairs.append((int(str(item["vid"]), 16), int(str(item["pid"]), 16)))
        except (KeyError, ValueError):
            continue
    return [pair for pair in pairs if 0 <= pair[0] <= 0xFFFF and 0 <= pair[1] <= 0xFFFF]


def resolve(claims: dict[tuple[int, int], list[Claim]], existing: Table) -> Table:
    """Fold the claims into one entry per pair, reporting what had to be dropped."""
    entries: Table = {}
    bridges: list[tuple[tuple[int, int], list[Claim]]] = []
    contested: list[tuple[tuple[int, int], list[Claim]]] = []
    demoted: list[tuple[tuple[int, int], list[Claim]]] = []
    unnamed: list[tuple[tuple[int, int], list[Claim]]] = []
    disagreements: list[tuple[tuple[int, int], list[Claim]]] = []

    for pair, owners in sorted(claims.items()):
        if pair in GENERIC_BRIDGE_IDS:
            bridges.append((pair, owners))
            continue

        families = {owner.family for owner in owners}
        # An architecture named after a core says less about the silicon than one
        # named after it, so it only gets a say when nothing else does.
        candidates = {o.family for o in owners if o.architecture not in CORE_ARCHITECTURES}
        candidates = candidates or families
        if len(candidates) > 1:
            if ESPRESSIF_FAMILY in candidates:
                # Contested between Espressif and something else, so the port has
                # to stay open to esptool: dropping it is what leaves it open.
                contested.append((pair, owners))
                continue
            disagreements.append((pair, owners))
        elif len(families) > 1:
            demoted.append((pair, owners))
        family = sorted(candidates)[0]

        platform = sorted({owner.platform for owner in owners})[0]
        variants = {owner.variant for owner in owners}
        if len(variants) == 1 and None not in variants:
            entries[pair] = (family, platform, variants.pop())
        else:
            unnamed.append((pair, owners))
            entries[pair] = (family, platform, None)

        held = existing.get(pair)
        if held is not None and held[0] != family:
            disagreements.append((pair, owners))

    report("dropped as a stock USB-UART bridge ID", bridges)
    report("dropped, Espressif and another family both claim it", contested)
    report("kept, a core-named architecture lost the tie", demoted)
    report("kept without a name, shared by several boards", unnamed)
    report("kept, but the family had to be picked between disagreeing claimants", disagreements)
    return entries


def merge(existing: Table, incoming: Table) -> tuple[Table, int]:
    """Add what is new and keep what is already there, sorted by VID then PID.

    Append-only on purpose. An entry already in the table may have been corrected
    by hand, and a board already published under one name must keep it even if
    upstream renames the board.
    """
    merged = dict(existing)
    added = 0
    for pair, entry in incoming.items():
        if pair not in merged:
            merged[pair] = entry
            added += 1
    return {pair: merged[pair] for pair in sorted(merged)}, added


def load_table(path: Path) -> Table:
    """The table as the output file currently holds it, or empty when there is none."""
    if not path.exists():
        return {}
    module = load_module("board_identify_arduino_ids_current", path)
    table = getattr(module, "ARDUINO_USB_IDS", None)
    return table if isinstance(table, dict) else {}


def load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def report(headline: str, rows: list[tuple[tuple[int, int], list[Claim]]]) -> None:
    if not rows:
        return
    print(f"{headline}: {len(rows)}", file=sys.stderr)
    for (vid, pid), owners in rows:
        described = ", ".join(sorted({owner.describe() for owner in owners}))
        print(f"  {vid:04x}:{pid:04x}  {described}", file=sys.stderr)


def render(table: Table, url: str) -> str:
    """Render the module, entries sorted by VID then PID."""
    lines = [
        '"""VID/PID pairs of the boards this project can name from USB descriptors.',
        "",
        f"Merged from {url}",
        "by ``scripts/generate_usb_ids.py``, which adds what is new and never removes or",
        "rewrites what is already here. Hand edits therefore survive every later run, and",
        "so does a name a board has already been published under.",
        "",
        "Each value is ``(family, platform, variant)``. ``variant`` is None when several",
        "boards share the pair: the family still rules probes in or out, but no single",
        "name can be published. ``family`` is the one field the runtime acts on, through",
        ":mod:`board_identify.usb_ids`.",
        "",
        "To drop a pair, add it to ``GENERIC_BRIDGE_IDS`` in :mod:`board_identify.usb_ids`;",
        "deleting the line here only lasts until the next run. Stock USB-UART bridge IDs",
        "are already absent for that reason, and are rejected at lookup time as well.",
        '"""',
        "",
        "ARDUINO_USB_IDS: dict[tuple[int, int], tuple[str, str, str | None]] = {",
    ]
    for (vid, pid), (family, platform, variant) in sorted(table.items()):
        name = "None" if variant is None else f'"{variant}"'
        lines.append(f'    (0x{vid:04X}, 0x{pid:04X}): ("{family}", "{platform}", {name}),')
    lines.append("}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
