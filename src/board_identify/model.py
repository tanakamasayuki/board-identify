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

# How the host reaches the board through this port. It is not part of a name:
# it decides which port keeps the board's name while several of them hold the
# board at once, because a bridge stays enumerated across a target reset and the
# target's own USB does not. See TRANSPORT_PREFERENCE in board_identify.identify.
TransportKind = Literal[
    # The target's own USB peripheral, such as an ESP32-S3 USB-Serial/JTAG or a
    # native-USB Arduino board.
    "usb",
    # A USB-UART bridge in front of the target: CH340, CP2102, FT232, PL2303.
    "uart",
    # The serial interface of a debug probe attached to the target.
    "probe",
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
    transport_kind: TransportKind | None = None
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
        """Stable name published under ``by-id/``.

        Names the board, not the way it is reached, so two ports onto the same
        silicon can produce the same value and share one link.
        """
        return f"{self.variant}-{self.unique_id}"

    def to_dict(self) -> dict[str, str | None]:
        """JSON-serialisable view, including the derived ``board_id``."""
        data: dict[str, str | None] = asdict(self)
        data["port"] = str(self.port)
        data["board_id"] = self.board_id
        return data
