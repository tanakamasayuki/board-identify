"""Data model for one identified board."""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

IdSource = Literal[
    "target-mac",
    "target-cpu-id",
    "usb-serial",
    "transport-serial",
    "unknown",
]


@dataclass(frozen=True)
class Identification:
    """A target board found on ``port``.

    ``variant`` and ``unique_id`` are expected to be normalised already, see
    :mod:`board_identify.normalize`.
    """

    port: Path
    family: str
    variant: str
    unique_id: str
    id_source: IdSource
    transport: str | None = None
    usb_vid: str | None = None
    usb_pid: str | None = None
    usb_serial: str | None = None

    def __post_init__(self) -> None:
        # board_id is used as a file name, so it must not escape the link directory.
        if not self.variant or not self.unique_id:
            raise ValueError("variant and unique_id must not be empty")
        if any(character in self.board_id for character in ("/", "\0")):
            raise ValueError(f"invalid board ID: {self.board_id!r}")

    @property
    def board_id(self) -> str:
        """Stable name published under ``by-id/``."""
        return f"{self.variant}-{self.unique_id}"

    def to_dict(self) -> dict[str, str | None]:
        """JSON-serialisable view, including the derived ``board_id``."""
        data: dict[str, str | None] = asdict(self)
        data["port"] = str(self.port)
        data["board_id"] = self.board_id
        return data
