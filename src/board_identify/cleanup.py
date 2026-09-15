"""Removal of links and state left behind by disconnected devices."""

from pathlib import Path

from board_identify.identify import link_points_to, read_state, settle, state_board_ids
from board_identify.paths import RUNTIME_DIR, by_id_dir, state_dir

__all__ = ["cleanup"]


def cleanup(runtime_dir: Path = RUNTIME_DIR) -> list[Path]:
    """Remove stale state files and symlinks, returning the paths that were removed."""
    removed: list[Path] = []
    links = by_id_dir(runtime_dir)
    states = state_dir(runtime_dir)
    seen: set[str] = set()

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

            seen.update(board_ids)
            if Path(port).exists():
                # A live port keeps its record even when it holds no link at
                # all, because the record is a claim rather than a receipt. Two
                # ports onto one chip resolve to the same board ID and only one
                # of them can hold that name; dropping the other's claim is what
                # used to leave the board nameless once the holder went away.
                continue

            for board_id in board_ids:
                if link_points_to(links / board_id, Path(port)):
                    (links / board_id).unlink(missing_ok=True)
                    removed.append(links / board_id)
            state_path.unlink(missing_ok=True)
            removed.append(state_path)

    # Every name whose holder just went away goes to whoever still claims it.
    for board_id in sorted(seen):
        settle(board_id, runtime_dir)

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
