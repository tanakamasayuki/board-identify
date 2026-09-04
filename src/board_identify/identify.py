"""Probe dispatch and publication of stable board links."""

import json
import os
from pathlib import Path

from board_identify import __version__
from board_identify.model import Identification
from board_identify.paths import RUNTIME_DIR, by_id_dir, state_dir, state_path
from board_identify.probes.base import Probe
from board_identify.probes.espressif import EspressifProbe
from board_identify.probes.usb_descriptor import UsbDescriptorProbe
from board_identify.probes.wch_link import WchLinkProbe

__all__ = [
    "default_probes",
    "identify_port",
    "publish",
    "read_state",
    "remove_port",
    "state_board_ids",
]


def default_probes(probe_target: bool = True) -> list[Probe]:
    """Probes tried in order for an unknown port, least intrusive first.

    ``probe_target`` is passed to the probes that can identify a board without
    disturbing it; with it off they stay on USB descriptors.

    The two descriptor probes come first because they read sysfs and nothing
    else. ``esptool`` is last because it is the only one that resets the board
    to find out what it is.
    """
    return [
        WchLinkProbe(probe_target=probe_target),
        UsbDescriptorProbe(),
        EspressifProbe(),
    ]


def identify_port(port: Path, probes: list[Probe] | None = None) -> list[Identification]:
    """Return the identifications from the first probe that recognizes ``port``.

    A port can yield more than one, for instance a debug probe and the target
    board behind it. The most specific identification comes first.
    """
    if not port.exists():
        raise FileNotFoundError(port)

    for probe in probes if probes is not None else default_probes():
        if probe.supports(port):
            results = probe.identify(port)
            if results:
                return results
    return []


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


def state_board_ids(state: dict[str, object]) -> list[str]:
    """The board IDs a state file claims, in publication order.

    Also reads the single ``board_id`` key written before a port could carry
    more than one link, so an upgrade does not orphan what is already in /run.
    """
    recorded = state.get("board_ids")
    if isinstance(recorded, list):
        return [value for value in recorded if isinstance(value, str)]
    single = state.get("board_id")
    return [single] if isinstance(single, str) else []


def publish(results: list[Identification], runtime_dir: Path = RUNTIME_DIR) -> list[Path]:
    """Publish one link per identification plus a state file, and return the links."""
    # The link name is the key, so two identifications that agree on it are one.
    by_board_id = {result.board_id: result for result in results}
    if not by_board_id:
        raise ValueError("nothing to publish")

    ports = {result.port for result in by_board_id.values()}
    if len(ports) != 1:
        raise ValueError(f"identifications span several ports: {sorted(str(p) for p in ports)}")
    port = ports.pop()

    links = by_id_dir(runtime_dir)
    states = state_dir(runtime_dir)
    links.mkdir(parents=True, exist_ok=True)
    states.mkdir(parents=True, exist_ok=True)

    # This port may have been published before under other board IDs, for
    # instance when a different board was plugged into the same probe, or when a
    # target that answered last time is now absent.
    previous = read_state(port.name, runtime_dir)
    if previous is not None:
        for board_id in set(state_board_ids(previous)) - set(by_board_id):
            stale = links / board_id
            if link_points_to(stale, port):
                stale.unlink(missing_ok=True)

    published = [_write_link(links / board_id, port) for board_id in by_board_id]
    _write_state(port, list(by_board_id.values()), runtime_dir)
    return published


def remove_port(port_name: str, runtime_dir: Path = RUNTIME_DIR) -> bool:
    """Drop the state of a port and every link that still points at that port."""
    path = state_path(port_name, runtime_dir)
    state = read_state(port_name, runtime_dir)
    if state is None:
        # Remove an unreadable leftover state file as well.
        existed = path.exists()
        path.unlink(missing_ok=True)
        return existed

    port = state.get("port")
    if isinstance(port, str):
        for board_id in state_board_ids(state):
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


def _write_link(link: Path, port: Path) -> Path:
    """Point ``link`` at ``port`` without a reader ever seeing a half made link."""
    temporary = link.with_name(f".{link.name}.{os.getpid()}.tmp")
    temporary.unlink(missing_ok=True)
    temporary.symlink_to(port)
    os.replace(temporary, link)
    return link


def _write_state(port: Path, results: list[Identification], runtime_dir: Path) -> None:
    """Record what was published for ``port``, atomically."""
    path = state_path(port.name, runtime_dir)
    payload = {
        # Recorded so a link can be traced back to the release that published it,
        # which is what tells a name written under an older naming rule apart
        # from one this version would write today.
        "version": __version__,
        "port": str(port),
        "board_ids": [result.board_id for result in results],
        "identifications": [result.to_dict() for result in results],
    }
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)
