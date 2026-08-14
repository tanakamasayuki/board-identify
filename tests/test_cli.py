import json
from pathlib import Path

import pytest

import board_identify.cli as cli
from board_identify.model import Identification


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


def stub_identify(monkeypatch: pytest.MonkeyPatch, result: Identification | None) -> None:
    monkeypatch.setattr(cli, "identify_port", lambda requested: result)


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
    assert payload["board_id"] == "esp32-s3-7cdfa1123456"
    assert payload["link"] == str(runtime / "by-id" / "esp32-s3-7cdfa1123456")


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
    stub_identify(monkeypatch, None)

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
