import json
from pathlib import Path

from board_identify.cleanup import cleanup
from board_identify.identify import publish
from board_identify.model import Identification, TransportKind


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


def esp32_on(port: Path, transport_kind: TransportKind) -> Identification:
    """The same ESP32-S3, as seen through one of the two ports onto it."""
    return Identification(
        port=port,
        family="espressif",
        variant="esp32-s3",
        unique_id="e4b063b4a81c",
        id_source="target-mac",
        transport_kind=transport_kind,
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


def test_state_of_a_live_port_that_holds_no_link_is_kept(tmp_path: Path) -> None:
    runtime = tmp_path / "run"
    first = make_port(tmp_path, "ttyUSB0")
    second = make_port(tmp_path, "ttyUSB1")
    publish_port(runtime, first)
    # The same board answers on ttyUSB1 too, which takes the shared name over.
    link = publish_port(runtime, second)

    removed = cleanup(runtime_dir=runtime)

    assert removed == []
    assert link.readlink() == second
    # ttyUSB0 is still that board. Its record is a claim rather than a receipt,
    # and keeping it is what lets the name come back when ttyUSB1 goes away.
    assert (runtime / "state" / "ttyUSB0.json").exists()


def test_a_shared_name_returns_to_the_port_that_still_claims_it(tmp_path: Path) -> None:
    runtime = tmp_path / "run"
    first = make_port(tmp_path, "ttyUSB0")
    second = make_port(tmp_path, "ttyUSB1")
    publish_port(runtime, first)
    link = publish_port(runtime, second)
    second.unlink()

    cleanup(runtime_dir=runtime)

    assert link.readlink() == first
    assert not (runtime / "state" / "ttyUSB1.json").exists()


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


def test_cleanup_hands_a_shared_name_to_the_port_that_is_left(tmp_path: Path) -> None:
    # An ESP32-S3 reached both through a CH340 and through its own USB
    # peripheral. The native port goes away without its unit stopping cleanly.
    runtime = tmp_path / "run"
    bridge = make_port(tmp_path, "ttyUSB0")
    native = make_port(tmp_path, "ttyACM12")
    publish([esp32_on(bridge, "uart")], runtime_dir=runtime)
    publish([esp32_on(native, "usb")], runtime_dir=runtime)
    native.unlink()

    cleanup(runtime_dir=runtime)

    assert (runtime / "by-id" / "esp32-s3-e4b063b4a81c").readlink() == bridge
    assert not (runtime / "state" / "ttyACM12.json").exists()
