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
    port: Path
    family: str
    variant: str
    unique_id: str
    id_source: IdSource
    transport: str | None = None
    usb_vid: str | None = None
    usb_pid: str | None = None
    usb_serial: str | None = None

    @property
    def board_id(self) -> str:
        return f"{self.variant}-{self.unique_id}"

    def to_dict(self) -> dict[str, str | None]:
        data = asdict(self)
        data["port"] = str(self.port)
        data["board_id"] = self.board_id
        return data
