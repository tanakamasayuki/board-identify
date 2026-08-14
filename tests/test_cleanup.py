import json
from pathlib import Path

from board_identify.cleanup import cleanup
from board_identify.identify import publish
from board_identify.model import Identification


def make_port(tmp_path: Path, name: str) -> Path:
    """A stand-in for a kernel device node."""
    dev = tmp_path / "dev"
    dev.mkdir(exist_ok=True)
    port = dev / name
    port.touch()
    return port


def publish_port(runtime_dir: Path, port: Path, unique_id: str = "7cdfa1123456") -> Path:
    return publish(
        Identification(
            port=port,
            family="espressif",
            variant="esp32-s3",
            unique_id=unique_id,
            id_source="target-mac",
        ),
        runtime_dir=runtime_dir,
    )


def test_cleanup_on_empty_runtime_dir(tmp_path: Path) -> None:
    assert cleanup(runtime_dir=tmp_path) == []


def test_live_port_is_kept(tmp_path: Path) -> None:
    runtime = tmp_path / "run"
    port = make_port(tmp_path, "ttyUSB0")
    link = publish_port(runtime, port)

    assert cleanup(runtime_dir=runtime) == []
    assert link.is_symlink()
    assert (runtime / "state" / "ttyUSB0.json").exists()


def test_disconnected_port_removes_link_and_state(tmp_path: Path) -> None:
    runtime = tmp_path / "run"
    port = make_port(tmp_path, "ttyUSB0")
    link = publish_port(runtime, port)
    port.unlink()

    removed = cleanup(runtime_dir=runtime)

    assert set(removed) == {link, runtime / "state" / "ttyUSB0.json"}
    assert not link.is_symlink()
    assert not (runtime / "state" / "ttyUSB0.json").exists()


def test_dangling_link_without_state_is_removed(tmp_path: Path) -> None:
    runtime = tmp_path / "run"
    links = runtime / "by-id"
    links.mkdir(parents=True)
    link = links / "esp32-s3-7cdfa1123456"
    link.symlink_to(tmp_path / "dev" / "ttyUSB7")

    assert cleanup(runtime_dir=runtime) == [link]
    assert not link.is_symlink()


def test_broken_state_file_is_removed(tmp_path: Path) -> None:
    runtime = tmp_path / "run"
    states = runtime / "state"
    states.mkdir(parents=True)
    broken = states / "ttyUSB0.json"
    broken.write_text("{not json", encoding="utf-8")
    incomplete = states / "ttyUSB1.json"
    incomplete.write_text(json.dumps({"port": "/dev/ttyUSB1"}), encoding="utf-8")

    assert set(cleanup(runtime_dir=runtime)) == {broken, incomplete}


def test_state_pointing_at_a_link_owned_by_another_port_is_dropped(tmp_path: Path) -> None:
    runtime = tmp_path / "run"
    first = make_port(tmp_path, "ttyUSB0")
    second = make_port(tmp_path, "ttyUSB1")
    publish_port(runtime, first)
    # The same board reappears on ttyUSB1 and takes over the link.
    link = publish_port(runtime, second)

    removed = cleanup(runtime_dir=runtime)

    assert removed == [runtime / "state" / "ttyUSB0.json"]
    assert link.is_symlink()
    assert link.readlink() == second


def test_non_symlink_entries_are_left_alone(tmp_path: Path) -> None:
    runtime = tmp_path / "run"
    links = runtime / "by-id"
    links.mkdir(parents=True)
    stray = links / "README"
    stray.write_text("not a link", encoding="utf-8")

    assert cleanup(runtime_dir=runtime) == []
    assert stray.exists()
