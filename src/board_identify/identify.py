"""Probe dispatch and publication of stable board links."""

import json
import os
from dataclasses import dataclass
from pathlib import Path

from board_identify import __version__
from board_identify.model import Identification, TransportKind
from board_identify.paths import RUNTIME_DIR, by_id_dir, state_dir, state_path
from board_identify.probes.base import Probe
from board_identify.probes.espressif import EspressifProbe
from board_identify.probes.usb_descriptor import UsbDescriptorProbe
from board_identify.probes.wch_link import WchLinkProbe
from board_identify.variants import remember_variant

__all__ = [
    "TRANSPORT_PREFERENCE",
    "Claim",
    "claims",
    "default_probes",
    "identify_port",
    "path_link_names",
    "publish",
    "read_state",
    "remove_port",
    "settle",
    "state_board_ids",
]

# Which transport wins the unqualified board name while several hold the board
# at once, preferred first. A bridge and a debug probe stay enumerated across a
# target reset; the target's own USB peripheral goes down with the chip and
# takes its tty with it, so a name pinned to it would blink out on every reset
# and every upload. The qualified names stay valid either way, so this only
# decides which link is the convenient one.
TRANSPORT_PREFERENCE: tuple[TransportKind, ...] = ("uart", "probe", "usb")

_TRANSPORT_KINDS: dict[str, TransportKind] = {kind: kind for kind in TRANSPORT_PREFERENCE}

# Identifiers that come from the silicon rather than from an adapter, and can
# therefore be recorded as what that target *is*. See board_identify.variants.
TARGET_ID_SOURCES = frozenset({"target-mac", "target-cpu-id"})


@dataclass(frozen=True)
class Claim:
    """One live port's recorded claim to a board ID.

    ``published_at`` is when the claim was last written, which is what decides
    between two claims of the same kind: the newer one describes the board as it
    was more recently seen.
    """

    port: Path
    board_id: str
    transport_kind: TransportKind | None
    published_at: int = 0


def default_probes(probe_target: bool = True, runtime_dir: Path = RUNTIME_DIR) -> list[Probe]:
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
        EspressifProbe(runtime_dir=runtime_dir),
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


def state_transport_kinds(state: dict[str, object]) -> dict[str, TransportKind]:
    """The transport each board ID in a state file was reached through.

    Empty for a state file written before ports could be told apart this way,
    which leaves those claims sorting last rather than failing to load.
    """
    recorded = state.get("identifications")
    if not isinstance(recorded, list):
        return {}

    kinds: dict[str, TransportKind] = {}
    for entry in recorded:
        if not isinstance(entry, dict):
            continue
        board_id = entry.get("board_id")
        kind = entry.get("transport_kind")
        resolved = _TRANSPORT_KINDS.get(kind) if isinstance(kind, str) else None
        if isinstance(board_id, str) and resolved is not None:
            kinds[board_id] = resolved
    return kinds


def claims(runtime_dir: Path = RUNTIME_DIR) -> list[Claim]:
    """Every board ID claimed by a state file whose port still exists.

    A port that lost a shared name to another port keeps its claim, and that is
    the whole point of reading these back: it is what lets the name return when
    the other port goes away.
    """
    states = state_dir(runtime_dir)
    if not states.is_dir():
        return []

    found: list[Claim] = []
    for path in sorted(states.glob("*.json")):
        state = read_state(path.stem, runtime_dir)
        if state is None:
            continue
        port = state.get("port")
        if not isinstance(port, str) or not Path(port).exists():
            continue
        kinds = state_transport_kinds(state)
        try:
            published_at = path.stat().st_mtime_ns
        except OSError:
            published_at = 0
        found.extend(
            Claim(
                port=Path(port),
                board_id=board_id,
                transport_kind=kinds.get(board_id),
                published_at=published_at,
            )
            for board_id in state_board_ids(state)
        )
    return found


def settle(board_id: str, runtime_dir: Path = RUNTIME_DIR) -> Path | None:
    """Point the unqualified link for ``board_id`` at its preferred live claimant.

    Returns the link, or None when nothing claims the board any more and the
    link was dropped. This is what hands a shared name over instead of losing
    it: two ports onto one chip resolve to the same board ID, and when the one
    holding the name disappears the other is still there to take it.
    """
    holders = sorted(
        (claim for claim in claims(runtime_dir) if claim.board_id == board_id),
        # Transport first, then the most recent claim, then the port name so
        # that the answer does not depend on the order events arrived in.
        key=lambda claim: (_preference(claim.transport_kind), -claim.published_at, str(claim.port)),
    )
    link = by_id_dir(runtime_dir) / board_id

    if not holders:
        if link.is_symlink():
            link.unlink(missing_ok=True)
        return None
    if not link_points_to(link, holders[0].port):
        _write_link(link, holders[0].port)
    return link


def path_link_names(board_id: str) -> tuple[str, ...]:
    """Every qualified name a board ID can be published under, one per transport."""
    return tuple(f"{board_id}-{kind}" for kind in TRANSPORT_PREFERENCE)


def publish(results: list[Identification], runtime_dir: Path = RUNTIME_DIR) -> list[Path]:
    """Publish the links for one port plus its state file, and return the links.

    Each identification gets a qualified link naming the path it was reached
    through, which belongs to this port alone. The unqualified board name is
    shared with any other port onto the same silicon, so it is settled rather
    than written: it may stay with a port that is already holding it.
    """
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
    dropped = set(state_board_ids(previous)) - set(by_board_id) if previous is not None else set()

    # The state file goes first, because settle() reads the recorded claims back
    # and this port has to be among them before a shared name is handed out.
    _write_state(port, list(by_board_id.values()), runtime_dir)
    for result in by_board_id.values():
        if result.id_source in TARGET_ID_SOURCES:
            remember_variant(result.unique_id, result.variant, runtime_dir)

    for board_id in sorted(dropped):
        _release(board_id, port, links)
        settle(board_id, runtime_dir)

    published: list[Path] = []
    for result in by_board_id.values():
        if result.path_id is not None:
            published.append(_write_link(links / result.path_id, port))
        link = settle(result.board_id, runtime_dir)
        if link is not None and link_points_to(link, port):
            published.append(link)
    return published


def remove_port(port_name: str, runtime_dir: Path = RUNTIME_DIR) -> bool:
    """Drop the state of a port and the links it held, unqualified names included.

    A name this port shared with another live port is handed over rather than
    removed.
    """
    path = state_path(port_name, runtime_dir)
    state = read_state(port_name, runtime_dir)
    if state is None:
        # Remove an unreadable leftover state file as well.
        existed = path.exists()
        path.unlink(missing_ok=True)
        return existed

    board_ids = state_board_ids(state)
    port = state.get("port")
    # The state file goes first, so settle() stops counting this port among the
    # claimants before it picks the new holder of each name.
    path.unlink(missing_ok=True)

    if isinstance(port, str):
        links = by_id_dir(runtime_dir)
        for board_id in board_ids:
            _release(board_id, Path(port), links)
            settle(board_id, runtime_dir)
    return True


def _preference(kind: TransportKind | None) -> int:
    """Sort key placing a transport in TRANSPORT_PREFERENCE order, unknown last."""
    if kind is None:
        return len(TRANSPORT_PREFERENCE)
    return TRANSPORT_PREFERENCE.index(kind)


def _release(board_id: str, port: Path, links: Path) -> None:
    """Drop every link this port holds for a board it no longer claims."""
    for name in (board_id, *path_link_names(board_id)):
        link = links / name
        if link_points_to(link, port):
            link.unlink(missing_ok=True)


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
