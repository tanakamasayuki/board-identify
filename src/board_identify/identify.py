import json
import os
from pathlib import Path

from board_identify.model import Identification
from board_identify.probes.base import Probe
from board_identify.probes.espressif import EspressifProbe

RUNTIME_DIR = Path("/run/board-identify")
BY_ID_DIR = RUNTIME_DIR / "by-id"
STATE_DIR = RUNTIME_DIR / "state"


def default_probes() -> list[Probe]:
    return [EspressifProbe()]


def identify_port(port: Path, probes: list[Probe] | None = None) -> Identification | None:
    if not port.exists():
        raise FileNotFoundError(port)

    for probe in probes or default_probes():
        if probe.supports(port):
            result = probe.identify(port)
            if result is not None:
                return result
    return None


def publish(result: Identification, runtime_dir: Path = RUNTIME_DIR) -> Path:
    by_id_dir = runtime_dir / "by-id"
    state_dir = runtime_dir / "state"
    by_id_dir.mkdir(parents=True, exist_ok=True)
    state_dir.mkdir(parents=True, exist_ok=True)

    link = by_id_dir / result.board_id
    temporary_link = link.with_name(f".{link.name}.{os.getpid()}.tmp")
    temporary_link.unlink(missing_ok=True)
    temporary_link.symlink_to(result.port)
    os.replace(temporary_link, link)

    state_path = state_dir / f"{result.port.name}.json"
    temporary_state = state_path.with_suffix(f".json.{os.getpid()}.tmp")
    temporary_state.write_text(
        json.dumps(result.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary_state, state_path)
    return link


def remove_port(port_name: str, runtime_dir: Path = RUNTIME_DIR) -> bool:
    state_path = runtime_dir / "state" / f"{port_name}.json"
    if not state_path.exists():
        return False

    state = json.loads(state_path.read_text(encoding="utf-8"))
    link = runtime_dir / "by-id" / state["board_id"]
    if link.is_symlink() and os.readlink(link) == state["port"]:
        link.unlink()
    state_path.unlink(missing_ok=True)
    return True
