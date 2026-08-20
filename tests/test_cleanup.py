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
    (link,) = publish(
        [
            Identification(
                port=port,
                family="espressif",
                variant="esp32-s3",
                unique_id=unique_id,
                id_source="target-mac",
            )
        ],
        runtime_dir=runtime_dir,
    )
    return link


def publish_probe_and_target(runtime_dir: Path, port: Path) -> list[Path]:
    """Publish a debug probe together with the board behind it."""
    return publish(
        [
            Identification(
                port=port,
                family="wch",
                variant="ch32x035c8t6",
                unique_id="1ff9abcd880ebc48",
                id_source="target-cpu-id",
            ),
            Identification(
                port=port,
                family="wch-link",
                variant="wch-link",
                unique_id="fc928f068181",
                id_source="transport-serial",
            ),
        ],
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


def test_disconnected_port_removes_all_of_its_links(tmp_path: Path) -> None:
    runtime = tmp_path / "run"
    port = make_port(tmp_path, "ttyACM4")
    links = publish_probe_and_target(runtime, port)
    port.unlink()

    removed = cleanup(runtime_dir=runtime)

    assert set(removed) == {*links, runtime / "state" / "ttyACM4.json"}
    assert not any(link.is_symlink() for link in links)


def test_live_port_keeps_the_links_it_still_owns(tmp_path: Path) -> None:
    runtime = tmp_path / "run"
    first = make_port(tmp_path, "ttyACM4")
    second = make_port(tmp_path, "ttyACM5")
    target, probe = publish_probe_and_target(runtime, first)
    # The board moves to a second probe, which takes the target link over.
    publish(
        [
            Identification(
                port=second,
                family="wch",
                variant="ch32x035c8t6",
                unique_id="1ff9abcd880ebc48",
                id_source="target-cpu-id",
            )
        ],
        runtime_dir=runtime,
    )

    assert cleanup(runtime_dir=runtime) == []
    # The first probe is still plugged in, so its own link must survive.
    assert probe.is_symlink()
    assert target.readlink() == second
