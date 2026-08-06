import re
import subprocess
import sys
from pathlib import Path

from board_identify.model import Identification
from board_identify.normalize import normalize_component, normalize_unique_id


MAC_PATTERN = re.compile(
    r"\b([0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5})\b"
)

CHIP_PATTERNS = (
    re.compile(r"^Chip is\s+(.+?)(?:\s+\(|$)", re.MULTILINE),
    re.compile(r"^Chip type:\s+(.+?)(?:\s+\(|$)", re.MULTILINE),
)


class EspressifProbe:
    name = "espressif"

    def supports(self, port: Path) -> bool:
        return port.name.startswith(("ttyUSB", "ttyACM"))

    def identify(self, port: Path) -> Identification | None:
        try:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "esptool",
                    "--port",
                    str(port),
                    "--baud",
                    "115200",
                    "read-mac",
                ],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return None

        output = completed.stdout + completed.stderr

        if completed.returncode != 0:
            return None

        chip = self.extract_chip(output)
        mac = self.extract_mac(output)

        if not chip or not mac:
            return None

        return Identification(
            port=port,
            family="espressif",
            variant=normalize_component(chip),
            unique_id=normalize_unique_id(mac),
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
        matches = MAC_PATTERN.findall(output)
        return matches[-1] if matches else None
