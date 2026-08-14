"""Probe dispatch and publication of stable board links."""

import json
import os
from pathlib import Path

from board_identify.model import Identification
from board_identify.paths import RUNTIME_DIR, by_id_dir, state_dir, state_path
from board_identify.probes.base import Probe
from board_identify.probes.espressif import EspressifProbe

__all__ = ["default_probes", "identify_port", "publish", "read_state", "remove_port"]


def default_probes() -> list[Probe]:
    """Probes tried in order for an unknown port."""
    return [EspressifProbe()]


def identify_port(port: Path, probes: list[Probe] | None = None) -> Identification | None:
    """Return the first positive identification for ``port``, or None."""
    if not port.exists():
        raise FileNotFoundError(port)

    for probe in probes if probes is not None else default_probes():
        if probe.supports(port):
            result = probe.identify(port)
            if result is not None:
                return result
    return None


def read_state(port_name: str, runtime_dir: Path = RUNTIME_DIR) -> dict[str, object] | None:
    """Return the recorded state for a port, or None when it is missing or unreadable."""
    path = state_path(port_name, runtime_dir)
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(state, dict):
        return None
    return state


def publish(result: Identification, runtime_dir: Path = RUNTIME_DIR) -> Path:
    """Publish ``result`` as an atomic symlink plus a state file, and return the link."""
    links = by_id_dir(runtime_dir)
    states = state_dir(runtime_dir)
    links.mkdir(parents=True, exist_ok=True)
    states.mkdir(parents=True, exist_ok=True)

    # The same port may have been published earlier under a different board ID,
    # for example when a different board is plugged into the same adapter.
    previous = read_state(result.port.name, runtime_dir)
    if previous is not None and previous.get("board_id") != result.board_id:
        remove_port(result.port.name, runtime_dir=runtime_dir)

    link = links / result.board_id
    temporary_link = link.with_name(f".{link.name}.{os.getpid()}.tmp")
    temporary_link.unlink(missing_ok=True)
    temporary_link.symlink_to(result.port)
    os.replace(temporary_link, link)

    path = state_path(result.port.name, runtime_dir)
    temporary_state = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary_state.write_text(
        json.dumps(result.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary_state, path)
    return link


def remove_port(port_name: str, runtime_dir: Path = RUNTIME_DIR) -> bool:
    """Drop the state of a port and its link when the link still points at that port."""
    path = state_path(port_name, runtime_dir)
    state = read_state(port_name, runtime_dir)
    if state is None:
        # Remove an unreadable leftover state file as well.
        existed = path.exists()
        path.unlink(missing_ok=True)
        return existed

    board_id = state.get("board_id")
    port = state.get("port")
    if isinstance(board_id, str) and isinstance(port, str):
        link = by_id_dir(runtime_dir) / board_id
        if link_points_to(link, Path(port)):
            link.unlink(missing_ok=True)

    path.unlink(missing_ok=True)
    return True


def link_points_to(link: Path, port: Path) -> bool:
    """Return whether ``link`` is a symlink resolving to ``port``."""
    try:
        if not link.is_symlink():
            return False
        target = link.readlink()
    except OSError:
        return False

    # Relative link targets are resolved against the directory holding the link.
    if not target.is_absolute():
        target = link.parent / target
    return target.resolve(strict=False) == port.resolve(strict=False)
