import json
from pathlib import Path

import pytest

from board_identify import __version__
from board_identify.identify import (
    identify_port,
    publish,
    read_state,
    remove_port,
    state_board_ids,
)
from board_identify.model import Identification, TransportKind


def make_port(tmp_path: Path, name: str) -> Path:
    """A stand-in for a kernel device node, which a claim is only live behind."""
    dev = tmp_path / "dev"
    dev.mkdir(exist_ok=True)
    port = dev / name
    port.touch()
    return port


def make_identification(port: Path, unique_id: str = "7cdfa1123456") -> Identification:
    return Identification(
        port=port,
        family="espressif",
        variant="esp32-s3",
        unique_id=unique_id,
        id_source="target-mac",
    )


def make_probe_identification(port: Path, unique_id: str = "fc928f068181") -> Identification:
    return Identification(
        port=port,
        family="wch-link",
        variant="wch-link",
        unique_id=unique_id,
        id_source="transport-serial",
    )


def test_publish_and_remove(tmp_path: Path) -> None:
    result = make_identification(make_port(tmp_path, "ttyUSB9"))
    (link,) = publish([result], runtime_dir=tmp_path)

    assert link.is_symlink()
    assert link.readlink() == make_port(tmp_path, "ttyUSB9")
    assert remove_port("ttyUSB9", runtime_dir=tmp_path)
    assert not link.is_symlink()


def test_publish_writes_state(tmp_path: Path) -> None:
    result = make_identification(make_port(tmp_path, "ttyUSB9"))
    publish([result], runtime_dir=tmp_path)

    state = json.loads((tmp_path / "state" / "ttyUSB9.json").read_text(encoding="utf-8"))
    assert state["board_ids"] == ["esp32-s3-7cdfa1123456"]
    assert state["port"] == str(make_port(tmp_path, "ttyUSB9"))
    assert state["identifications"][0]["board_id"] == "esp32-s3-7cdfa1123456"
    assert read_state("ttyUSB9", runtime_dir=tmp_path) == state


def test_publish_records_the_release_that_wrote_the_state(tmp_path: Path) -> None:
    # Which release published a link is what tells a name written under an older
    # naming rule apart from one this version would write today.
    publish([make_identification(make_port(tmp_path, "ttyUSB9"))], runtime_dir=tmp_path)

    state = read_state("ttyUSB9", runtime_dir=tmp_path)
    assert state is not None
    assert state["version"] == __version__


def test_publish_is_idempotent(tmp_path: Path) -> None:
    result = make_identification(make_port(tmp_path, "ttyUSB9"))
    first = publish([result], runtime_dir=tmp_path)
    second = publish([result], runtime_dir=tmp_path)

    assert first == second
    assert list((tmp_path / "by-id").iterdir()) == second


def test_publish_needs_something_to_publish(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        publish([], runtime_dir=tmp_path)


def test_republishing_a_port_drops_the_previous_link(tmp_path: Path) -> None:
    (old,) = publish([make_identification(make_port(tmp_path, "ttyUSB9"))], runtime_dir=tmp_path)
    (new,) = publish(
        [make_identification(make_port(tmp_path, "ttyUSB9"), unique_id="aabbcc112233")],
        runtime_dir=tmp_path,
    )

    assert not old.is_symlink()
    assert new.is_symlink()
    assert sorted(p.name for p in (tmp_path / "by-id").iterdir()) == [new.name]


def test_publish_leaves_no_temporary_files(tmp_path: Path) -> None:
    publish([make_identification(make_port(tmp_path, "ttyUSB9"))], runtime_dir=tmp_path)

    for directory in (tmp_path / "by-id", tmp_path / "state"):
        assert not list(directory.glob("*.tmp"))
        assert not list(directory.glob(".*"))


def test_remove_port_without_state(tmp_path: Path) -> None:
    assert remove_port("ttyUSB9", runtime_dir=tmp_path) is False


def test_remove_port_keeps_a_link_owned_by_another_port(tmp_path: Path) -> None:
    publish([make_identification(make_port(tmp_path, "ttyUSB9"))], runtime_dir=tmp_path)
    # The same board reappears on a different port and takes over the link.
    (link,) = publish([make_identification(make_port(tmp_path, "ttyUSB8"))], runtime_dir=tmp_path)

    assert remove_port("ttyUSB9", runtime_dir=tmp_path)
    assert link.is_symlink()
    assert link.readlink() == make_port(tmp_path, "ttyUSB8")


def test_remove_port_discards_unreadable_state(tmp_path: Path) -> None:
    state_path = tmp_path / "state" / "ttyUSB9.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text("{not json", encoding="utf-8")

    assert remove_port("ttyUSB9", runtime_dir=tmp_path)
    assert not state_path.exists()


def test_publish_links_every_identity_of_one_port(tmp_path: Path) -> None:
    port = make_port(tmp_path, "ttyACM4")
    target = make_identification(port)
    probe = make_probe_identification(port)

    links = publish([target, probe], runtime_dir=tmp_path)

    assert [link.name for link in links] == [target.board_id, probe.board_id]
    assert {link.readlink() for link in links} == {port}
    state = read_state("ttyACM4", runtime_dir=tmp_path)
    assert state is not None
    assert state_board_ids(state) == [target.board_id, probe.board_id]


def test_publish_drops_only_the_identity_that_disappeared(tmp_path: Path) -> None:
    port = make_port(tmp_path, "ttyACM4")
    target, probe = make_identification(port), make_probe_identification(port)
    target_link, probe_link = publish([target, probe], runtime_dir=tmp_path)

    # The target board is unplugged from the debug probe; the probe stays.
    publish([probe], runtime_dir=tmp_path)

    assert not target_link.is_symlink()
    assert probe_link.is_symlink()


def test_publish_rejects_identifications_of_different_ports(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="several ports"):
        publish(
            [
                make_identification(make_port(tmp_path, "ttyUSB9")),
                make_probe_identification(Path("/dev/ttyUSB8")),
            ],
            runtime_dir=tmp_path,
        )


def test_remove_port_drops_every_link_of_the_port(tmp_path: Path) -> None:
    port = make_port(tmp_path, "ttyACM4")
    links = publish(
        [make_identification(port), make_probe_identification(port)], runtime_dir=tmp_path
    )

    assert remove_port("ttyACM4", runtime_dir=tmp_path)
    assert not any(link.is_symlink() for link in links)


def test_state_board_ids_reads_the_single_link_format() -> None:
    # State written before a port could carry more than one link.
    assert state_board_ids({"board_id": "esp32-s3-7cdfa1123456"}) == ["esp32-s3-7cdfa1123456"]
    assert state_board_ids({"board_ids": ["a", 7, "b"]}) == ["a", "b"]
    assert state_board_ids({"port": "/dev/ttyUSB0"}) == []


def test_remove_port_honours_the_single_link_format(tmp_path: Path) -> None:
    links = tmp_path / "by-id"
    links.mkdir(parents=True)
    link = links / "esp32-s3-7cdfa1123456"
    link.symlink_to(Path("/dev/ttyUSB9"))
    state_path = tmp_path / "state" / "ttyUSB9.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        json.dumps({"board_id": link.name, "port": "/dev/ttyUSB9"}), encoding="utf-8"
    )

    assert remove_port("ttyUSB9", runtime_dir=tmp_path)
    assert not link.is_symlink()


def test_identify_port_requires_an_existing_device(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        identify_port(tmp_path / "ttyUSB9")


def test_identify_port_uses_the_first_matching_probe(tmp_path: Path) -> None:
    port = tmp_path / "ttyUSB9"
    port.touch()
    expected = make_identification(port)

    class Silent:
        name = "silent"

        def supports(self, port: Path) -> bool:
            return True

        def identify(self, port: Path) -> list[Identification]:
            return []

    class Loud:
        name = "loud"

        def supports(self, port: Path) -> bool:
            return True

        def identify(self, port: Path) -> list[Identification]:
            return [expected]

    class Skipped:
        name = "skipped"

        def supports(self, port: Path) -> bool:
            return False

        def identify(self, port: Path) -> list[Identification]:
            raise AssertionError("must not run")

    assert identify_port(port, probes=[Skipped(), Silent(), Loud()]) == [expected]


def test_identify_port_with_no_probes_identifies_nothing(tmp_path: Path) -> None:
    port = tmp_path / "ttyUSB9"
    port.touch()
    assert identify_port(port, probes=[]) == []


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


def test_publish_names_the_path_as_well_as_the_board(tmp_path: Path) -> None:
    port = make_port(tmp_path, "ttyUSB0")

    links = publish([esp32_on(port, "uart")], runtime_dir=tmp_path)

    assert [link.name for link in links] == [
        "esp32-s3-e4b063b4a81c-uart",
        "esp32-s3-e4b063b4a81c",
    ]
    assert {link.readlink() for link in links} == {port}


def test_two_ports_onto_one_chip_keep_a_name_each(tmp_path: Path) -> None:
    # An ESP32-S3 with its own USB peripheral wired up alongside a CH340 on the
    # same UART. Both ports read the same MAC, so both resolve to one board ID.
    bridge = make_port(tmp_path, "ttyUSB0")
    native = make_port(tmp_path, "ttyACM12")
    publish([esp32_on(bridge, "uart")], runtime_dir=tmp_path)
    publish([esp32_on(native, "usb")], runtime_dir=tmp_path)

    links = tmp_path / "by-id"
    assert (links / "esp32-s3-e4b063b4a81c-uart").readlink() == bridge
    assert (links / "esp32-s3-e4b063b4a81c-usb").readlink() == native
    # The bridge stays enumerated while the target resets, so it holds the
    # unqualified name whichever port was published last.
    assert (links / "esp32-s3-e4b063b4a81c").readlink() == bridge


def test_the_bridge_wins_the_board_name_whatever_the_order(tmp_path: Path) -> None:
    bridge = make_port(tmp_path, "ttyUSB0")
    native = make_port(tmp_path, "ttyACM12")
    publish([esp32_on(native, "usb")], runtime_dir=tmp_path)
    publish([esp32_on(bridge, "uart")], runtime_dir=tmp_path)

    assert (tmp_path / "by-id" / "esp32-s3-e4b063b4a81c").readlink() == bridge


def test_removing_the_native_port_leaves_the_board_named(tmp_path: Path) -> None:
    # The reset at the end of an esptool run re-enumerates a native USB port,
    # which used to take the shared name down with it and leave nothing behind.
    bridge = make_port(tmp_path, "ttyUSB0")
    native = make_port(tmp_path, "ttyACM12")
    publish([esp32_on(bridge, "uart")], runtime_dir=tmp_path)
    publish([esp32_on(native, "usb")], runtime_dir=tmp_path)

    assert remove_port("ttyACM12", runtime_dir=tmp_path)

    links = tmp_path / "by-id"
    assert (links / "esp32-s3-e4b063b4a81c").readlink() == bridge
    assert (links / "esp32-s3-e4b063b4a81c-uart").readlink() == bridge
    assert not (links / "esp32-s3-e4b063b4a81c-usb").is_symlink()


def test_the_board_name_moves_to_the_port_that_is_left(tmp_path: Path) -> None:
    bridge = make_port(tmp_path, "ttyUSB0")
    native = make_port(tmp_path, "ttyACM12")
    publish([esp32_on(bridge, "uart")], runtime_dir=tmp_path)
    publish([esp32_on(native, "usb")], runtime_dir=tmp_path)

    assert remove_port("ttyUSB0", runtime_dir=tmp_path)

    links = tmp_path / "by-id"
    assert (links / "esp32-s3-e4b063b4a81c").readlink() == native
    assert (links / "esp32-s3-e4b063b4a81c-usb").readlink() == native
    assert not (links / "esp32-s3-e4b063b4a81c-uart").is_symlink()


def test_the_last_port_to_go_takes_the_name_with_it(tmp_path: Path) -> None:
    bridge = make_port(tmp_path, "ttyUSB0")
    native = make_port(tmp_path, "ttyACM12")
    publish([esp32_on(bridge, "uart")], runtime_dir=tmp_path)
    publish([esp32_on(native, "usb")], runtime_dir=tmp_path)
    remove_port("ttyACM12", runtime_dir=tmp_path)
    remove_port("ttyUSB0", runtime_dir=tmp_path)

    assert list((tmp_path / "by-id").iterdir()) == []
