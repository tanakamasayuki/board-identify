"""Removal of links and state left behind by disconnected devices."""

from pathlib import Path

from board_identify.identify import link_points_to, read_state, state_board_ids
from board_identify.paths import RUNTIME_DIR, by_id_dir, state_dir

__all__ = ["cleanup"]


def cleanup(runtime_dir: Path = RUNTIME_DIR) -> list[Path]:
    """Remove stale state files and symlinks, returning the paths that were removed."""
    removed: list[Path] = []
    links = by_id_dir(runtime_dir)
    states = state_dir(runtime_dir)

    # State files are handled first so that a link and the state describing it
    # disappear together. Note that a stale link cannot be detected once the
    # kernel has handed the same node name to another device; that case is
    # resolved by the next publish for the port instead.
    if states.is_dir():
        for state_path in sorted(states.glob("*.json")):
            state = read_state(state_path.stem, runtime_dir)
            board_ids = state_board_ids(state) if state is not None else []
            port = state.get("port") if state is not None else None

            if not board_ids or not isinstance(port, str):
                state_path.unlink(missing_ok=True)
                removed.append(state_path)
                continue

            owned = [
                board_id for board_id in board_ids if link_points_to(links / board_id, Path(port))
            ]

            if not Path(port).exists():
                for board_id in owned:
                    (links / board_id).unlink(missing_ok=True)
                    removed.append(links / board_id)
                state_path.unlink(missing_ok=True)
                removed.append(state_path)
                continue

            # The port is live. Its remaining links are still correct, so only a
            # record that owns nothing at all is stale: every name it claimed has
            # been taken over by another port.
            if not owned:
                state_path.unlink(missing_ok=True)
                removed.append(state_path)

    # Sweep dangling links, for instance ones whose state file was lost.
    if links.is_dir():
        for link in sorted(links.iterdir()):
            if not link.is_symlink():
                continue
            # Path.exists() follows the link, so a dangling link reports False.
            if not link.exists():
                link.unlink(missing_ok=True)
                removed.append(link)

    return removed
