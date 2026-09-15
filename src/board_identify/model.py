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

# How the host reaches the board through this port. One board can be reachable
# more than one way at once — an ESP32-S3 with its own USB peripheral wired up
# alongside a CH340 on the same UART is the everyday case — and the two ports
# then resolve to the same board ID. The kind is what tells the resulting links
# apart, so each path stays addressable by name.
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
        silicon produce the same value. See :attr:`path_id` for the other half.
        """
        return f"{self.variant}-{self.unique_id}"

    @property
    def path_id(self) -> str | None:
        """Name that addresses the board through *this* port specifically.

        None when the probe did not say which kind of transport this is, which
        leaves the board with its unqualified name alone.
        """
        return None if self.transport_kind is None else f"{self.board_id}-{self.transport_kind}"

    def to_dict(self) -> dict[str, str | None]:
        """JSON-serialisable view, including the derived ``board_id``."""
        data: dict[str, str | None] = asdict(self)
        data["port"] = str(self.port)
        data["board_id"] = self.board_id
        data["path_id"] = self.path_id
        return data
