import json
from pathlib import Path


RUNTIME_DIR = Path("/run/board-identify")
BY_ID_DIR = RUNTIME_DIR / "by-id"
STATE_DIR = RUNTIME_DIR / "state"


def cleanup() -> list[Path]:
    removed: list[Path] = []

    if BY_ID_DIR.exists():
        for link in BY_ID_DIR.iterdir():
            if not link.is_symlink():
                continue

            # Path.exists() はリンク先を辿るため、
            # 壊れたシンボリックリンクなら False になる。
            if not link.exists():
                link.unlink(missing_ok=True)
                removed.append(link)

    if STATE_DIR.exists():
        for state_path in STATE_DIR.glob("*.json"):
            if _state_is_stale(state_path):
                state_path.unlink(missing_ok=True)
                removed.append(state_path)

    return removed


def _state_is_stale(state_path: Path) -> bool:
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        port = Path(state["port"])
        board_id = state["board_id"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        return True

    link = BY_ID_DIR / board_id

    # ポートが消えている。
    if not port.exists():
        return True

    # 状態ファイルに対応するリンクがない。
    if not link.is_symlink():
        return True

    try:
        target = link.readlink()
    except OSError:
        return True

    # 相対リンクにも対応して正規化する。
    if not target.is_absolute():
        target = link.parent / target

    return target.resolve(strict=False) != port.resolve(strict=False)
