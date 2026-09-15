"""Chip names learned from a target, kept for the ports that cannot ask.

An Espressif chip with its own USB peripheral puts its MAC in the USB serial
descriptor, so the unique half of its name is readable from sysfs. The chip name
is not: every ESP32 with a USB-Serial/JTAG reports ``303a:1001``, whether it is
an S3, a C3 or a P4. Reading it means running ``esptool``, and on a native-USB
port that costs the port itself — the reset at the end of the run re-enumerates
the device, so the link is gone seconds after it was published.

Whichever port does find out, records it here under the target's unique ID. Any
other port onto the same silicon — the CH340 in front of it, or the same native
port after it re-enumerated — then names the board from descriptors alone.

The cache lives in the runtime directory and therefore does not survive a
reboot. It does not need to: at boot udev walks every tty again, and the first
port to reach the target refills it.
"""

import json
import os
from pathlib import Path

from board_identify.paths import RUNTIME_DIR

__all__ = ["read_variants", "recall_variant", "remember_variant", "variants_path"]


def variants_path(runtime_dir: Path = RUNTIME_DIR) -> Path:
    """File holding the learned ``unique ID -> chip name`` map."""
    return runtime_dir / "variants.json"


def read_variants(runtime_dir: Path = RUNTIME_DIR) -> dict[str, str]:
    """The whole map, or an empty one when it is missing or unreadable."""
    try:
        recorded = json.loads(variants_path(runtime_dir).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(recorded, dict):
        return {}
    return {key: value for key, value in recorded.items() if isinstance(value, str)}


def recall_variant(unique_id: str, runtime_dir: Path = RUNTIME_DIR) -> str | None:
    """The chip name learned for ``unique_id``, or None when nothing is recorded."""
    return read_variants(runtime_dir).get(unique_id)


def remember_variant(unique_id: str, variant: str, runtime_dir: Path = RUNTIME_DIR) -> None:
    """Record the chip name of a target, atomically.

    Nothing is written when the entry is already there, which keeps the common
    case — a board republishing on every plug event — off the filesystem.
    """
    recorded = read_variants(runtime_dir)
    if recorded.get(unique_id) == variant:
        return
    recorded[unique_id] = variant

    path = variants_path(runtime_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(recorded, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)
