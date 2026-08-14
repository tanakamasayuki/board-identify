"""Runtime layout shared by the identify and cleanup code paths."""

from pathlib import Path

RUNTIME_DIR = Path("/run/board-identify")


def by_id_dir(runtime_dir: Path = RUNTIME_DIR) -> Path:
    """Directory holding the stable ``<board-id> -> /dev/tty*`` symlinks."""
    return runtime_dir / "by-id"


def state_dir(runtime_dir: Path = RUNTIME_DIR) -> Path:
    """Directory holding one JSON state file per published port."""
    return runtime_dir / "state"


def state_path(port_name: str, runtime_dir: Path = RUNTIME_DIR) -> Path:
    """State file for a kernel port name such as ``ttyUSB0``."""
    return state_dir(runtime_dir) / f"{port_name}.json"
