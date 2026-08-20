from pathlib import Path
from typing import Protocol

from board_identify.model import Identification


class Probe(Protocol):
    name: str

    def supports(self, port: Path) -> bool:
        """Return whether this probe may support the port."""

    def identify(self, port: Path) -> list[Identification]:
        """Identify the port, or return an empty list when nothing is recognized.

        A port can carry more than one identity, for instance a debug probe and
        the target board behind it. Return the most specific one first.
        """
