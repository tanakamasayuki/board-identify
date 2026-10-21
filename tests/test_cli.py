import json
from collections.abc import Callable
from pathlib import Path

import pytest

import board_identify.cli as cli
from board_identify.model import Identification
from board_identify.probes.espressif import EspressifProbe


def make_identification(port: Path) -> Identification:
    return Identification(
        port=port,
        family="espressif",
        variant="esp32-s3",
        unique_id="7cdfa1123456",
        id_source="target-mac",
    )


@pytest.fixture
def port(tmp_path: Path) -> Path:
    device = tmp_path / "ttyUSB0"
    device.touch()
    return device


def stub_identify(monkeypatch: pytest.MonkeyPatch, *results: Identification) -> None:
    monkeypatch.setattr(cli, "identify_port", lambda requested, probes=None: list(results))


def test_identify_publishes_and_prints_the_link(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, port: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    stub_identify(monkeypatch, make_identification(port))
    runtime = tmp_path / "run"

    code = cli.main(["--runtime-dir", str(runtime), "identify", str(port)])

    assert code == 0
    link = runtime / "by-id" / "esp32-s3-7cdfa1123456"
    assert link.readlink() == port
    assert capsys.readouterr().out.strip() == f"{link} -> {port}"


def test_identify_json_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, port: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    stub_identify(monkeypatch, make_identification(port))
    runtime = tmp_path / "run"

    code = cli.main(["--runtime-dir", str(runtime), "identify", "--json", str(port)])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["port"] == str(port)
    (identification,) = payload["identifications"]
    assert identification["board_id"] == "esp32-s3-7cdfa1123456"
    assert identification["link"] == str(runtime / "by-id" / "esp32-s3-7cdfa1123456")


def test_identify_no_publish(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, port: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    stub_identify(monkeypatch, make_identification(port))
    runtime = tmp_path / "run"

    code = cli.main(["--runtime-dir", str(runtime), "identify", "--no-publish", str(port)])

    assert code == 0
    assert capsys.readouterr().out.strip() == "esp32-s3-7cdfa1123456"
    assert not runtime.exists()


def test_identify_unknown_board(
    monkeypatch: pytest.MonkeyPatch, port: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    stub_identify(monkeypatch)

    assert cli.main(["identify", str(port)]) == cli.EXIT_UNIDENTIFIED
    assert "unable to identify" in capsys.readouterr().err


def test_identify_missing_device(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["identify", str(tmp_path / "missing")]) == cli.EXIT_ERROR
    assert "device does not exist" in capsys.readouterr().err


def test_remove_command(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, port: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    stub_identify(monkeypatch, make_identification(port))
    runtime = tmp_path / "run"
    cli.main(["--runtime-dir", str(runtime), "identify", str(port)])
    capsys.readouterr()

    assert cli.main(["--runtime-dir", str(runtime), "remove", "ttyUSB0"]) == 0
    assert not (runtime / "by-id" / "esp32-s3-7cdfa1123456").is_symlink()


def test_remove_command_without_state(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = cli.main(["--runtime-dir", str(tmp_path), "remove", "ttyUSB0"])

    assert code == cli.EXIT_ERROR
    assert "no state for port" in capsys.readouterr().err


def test_cleanup_command(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, port: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    stub_identify(monkeypatch, make_identification(port))
    runtime = tmp_path / "run"
    cli.main(["--runtime-dir", str(runtime), "identify", str(port)])
    port.unlink()
    capsys.readouterr()

    assert cli.main(["--runtime-dir", str(runtime), "cleanup"]) == 0
    assert "removed" in capsys.readouterr().out


def test_command_is_required(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        cli.main([])


def test_identify_prints_every_link_of_a_port(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, port: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    probe = Identification(
        port=port,
        family="wch-link",
        variant="wch-link",
        unique_id="fc928f068181",
        id_source="transport-serial",
    )
    stub_identify(monkeypatch, make_identification(port), probe)
    runtime = tmp_path / "run"

    code = cli.main(["--runtime-dir", str(runtime), "identify", str(port)])

    assert code == 0
    printed = capsys.readouterr().out.splitlines()
    assert printed == [
        f"{runtime / 'by-id' / 'esp32-s3-7cdfa1123456'} -> {port}",
        f"{runtime / 'by-id' / 'wch-link-fc928f068181'} -> {port}",
    ]


def test_identify_no_publish_prints_every_board_id(
    monkeypatch: pytest.MonkeyPatch, port: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    probe = Identification(
        port=port,
        family="wch-link",
        variant="wch-link",
        unique_id="fc928f068181",
        id_source="transport-serial",
    )
    stub_identify(monkeypatch, make_identification(port), probe)

    assert cli.main(["identify", "--no-publish", str(port)]) == 0
    assert capsys.readouterr().out.split() == [
        "esp32-s3-7cdfa1123456",
        "wch-link-fc928f068181",
    ]


def test_no_target_probe_reaches_the_probe_factory(
    monkeypatch: pytest.MonkeyPatch, port: Path
) -> None:
    asked: list[bool] = []

    def record(probe_target: bool, probe_native_usb: bool) -> list[object]:
        asked.append(probe_target)
        return []

    monkeypatch.setattr(cli, "default_probes", record)
    monkeypatch.setattr(cli, "identify_port", lambda requested, probes=None: [])

    cli.main(["identify", "--no-target-probe", str(port)])
    cli.main(["identify", str(port)])

    assert asked == [False, True]


def native_port(sysfs: Callable[..., Path], vid: str, pid: str) -> Path:
    return sysfs(
        port_name="ttyACM0",
        attributes={"idVendor": vid, "idProduct": pid, "busnum": "001", "devnum": "007"},
    )


def test_unidentified_native_espressif_port_points_at_the_flag(
    sysfs: Callable[..., Path],
) -> None:
    root = native_port(sysfs, "303a", "80ff")
    message = cli._unidentified(Path("/dev/ttyACM0"), [EspressifProbe(sysfs_root=root)])
    assert "--probe-native-usb" in message


def test_unidentified_port_that_is_no_esp32_does_not_point_at_the_flag(
    sysfs: Callable[..., Path],
) -> None:
    # A TinyUSB device: opening it with esptool would not tell anything either.
    root = native_port(sysfs, "cafe", "4001")
    message = cli._unidentified(Path("/dev/ttyACM0"), [EspressifProbe(sysfs_root=root)])
    assert message == "unable to identify: /dev/ttyACM0"
