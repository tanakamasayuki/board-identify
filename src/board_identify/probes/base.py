from pathlib import Path
from typing import Protocol

from board_identify.model import Identification


class Probe(Protocol):
    name: str

    def supports(self, port: Path) -> bool:
        """Return whether this probe may support the port."""

    def identify(self, port: Path) -> Identification | None:
        """Identify the target or return None when it is not recognized."""
