"""Identify Espressif targets by reading the eFuse MAC through esptool."""

import os
import re
import subprocess
import sys
from pathlib import Path

from board_identify.model import Identification
from board_identify.normalize import normalize_component, normalize_unique_id

DEFAULT_BAUD = 115200
DEFAULT_CONNECT_ATTEMPTS = 2
DEFAULT_TIMEOUT = 30.0

MAC_PATTERN = re.compile(r"\b([0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5})\b")

# The MAC that identifies the target, in decreasing order of preference.
# esptool 5 may also print BASE MAC and MAC_EXT lines for some chips.
LABELLED_MAC_PATTERNS = (
    re.compile(rf"^MAC:\s*{MAC_PATTERN.pattern}", re.MULTILINE),
    re.compile(rf"^BASE MAC:\s*{MAC_PATTERN.pattern}", re.MULTILINE),
)

CHIP_PATTERNS = (
    re.compile(r"^Chip is\s+(.+?)(?:\s+\(|$)", re.MULTILINE),
    re.compile(r"^Chip type:\s+(.+?)(?:\s+\(|$)", re.MULTILINE),
    re.compile(r"^Detecting chip type\.\.\.\s+(.+?)(?:\s+\(|$)", re.MULTILINE),
)


def esptool_command_name() -> str:
    """The read-MAC subcommand name, which was renamed in esptool 5."""
    try:
        import esptool
    except ImportError:  # pragma: no cover - esptool is a hard dependency
        return "read-mac"

    version = getattr(esptool, "__version__", "")
    major = version.split(".", 1)[0]
    return "read_mac" if major.isdigit() and int(major) < 5 else "read-mac"


def esptool_environment() -> dict[str, str]:
    """Environment that keeps esptool output plain and unwrapped so it can be parsed."""
    env = dict(os.environ)
    env["NO_COLOR"] = "1"
    env["TERM"] = "dumb"
    # esptool 5 renders through rich, which wraps to the terminal width.
    env["COLUMNS"] = "200"
    return env


class EspressifProbe:
    name = "espressif"

    def __init__(self, baud: int = DEFAULT_BAUD, timeout: float = DEFAULT_TIMEOUT) -> None:
        self.baud = baud
        self.timeout = timeout

    def supports(self, port: Path) -> bool:
        # Any USB-serial port may hide an Espressif target behind the bridge, so
        # this is a cheap pre-filter rather than a positive match.
        return port.name.startswith(("ttyUSB", "ttyACM"))

    def identify(self, port: Path) -> list[Identification]:
        try:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "esptool",
                    "--port",
                    str(port),
                    "--baud",
                    str(self.baud),
                    "--connect-attempts",
                    str(DEFAULT_CONNECT_ATTEMPTS),
                    esptool_command_name(),
                ],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
                env=esptool_environment(),
            )
        except (subprocess.TimeoutExpired, OSError):
            return []

        if completed.returncode != 0:
            return []

        result = self.parse(port, completed.stdout + completed.stderr)
        return [] if result is None else [result]

    @classmethod
    def parse(cls, port: Path, output: str) -> Identification | None:
        """Build an Identification from esptool output, or return None."""
        chip = cls.extract_chip(output)
        mac = cls.extract_mac(output)
        if not chip or not mac:
            return None

        try:
            variant = normalize_component(chip)
            unique_id = normalize_unique_id(mac)
        except ValueError:
            return None

        return Identification(
            port=port,
            family="espressif",
            variant=variant,
            unique_id=unique_id,
            id_source="target-mac",
        )

    @staticmethod
    def extract_chip(output: str) -> str | None:
        for pattern in CHIP_PATTERNS:
            match = pattern.search(output)
            if match:
                return match.group(1).strip()
        return None

    @staticmethod
    def extract_mac(output: str) -> str | None:
        for pattern in LABELLED_MAC_PATTERNS:
            match = pattern.search(output)
            if match:
                return match.group(1)

        matches = MAC_PATTERN.findall(output)
        return matches[-1] if matches else None
