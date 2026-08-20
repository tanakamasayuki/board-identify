import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from board_identify.probes import espressif
from board_identify.probes.espressif import EspressifProbe

Output = Callable[[str], str]


def test_extract_esp32_s3() -> None:
    output = (
        "Detecting chip type... ESP32-S3\n"
        "Chip is ESP32-S3 (revision v0.2)\n"
        "MAC: 7c:df:a1:12:34:56\n"
    )
    assert EspressifProbe.extract_chip(output) == "ESP32-S3"
    assert EspressifProbe.extract_mac(output) == "7c:df:a1:12:34:56"


def test_parse_esptool_v4_fixture(esptool_output: Output) -> None:
    result = EspressifProbe.parse(Path("/dev/ttyUSB0"), esptool_output("esp32-s3.txt"))
    assert result is not None
    assert result.board_id == "esp32-s3-7cdfa1123456"
    assert result.id_source == "target-mac"


def test_parse_esptool_v5_fixture(esptool_output: Output) -> None:
    result = EspressifProbe.parse(Path("/dev/ttyACM0"), esptool_output("esp32-s3-v5.txt"))
    assert result is not None
    assert result.variant == "esp32-s3"
    assert result.unique_id == "7cdfa1123456"


def test_mac_ext_is_not_used_as_unique_id(esptool_output: Output) -> None:
    # MAC_EXT is only two octets, but BASE MAC must not win over MAC either.
    assert EspressifProbe.extract_mac(esptool_output("esp32-s3-v5.txt")) == "7c:df:a1:12:34:56"


def test_base_mac_is_used_when_mac_is_absent() -> None:
    output = "Chip type: ESP32-C3\nBASE MAC: 60:55:f9:00:11:22\n"
    assert EspressifProbe.extract_mac(output) == "60:55:f9:00:11:22"


def test_connect_error_is_not_identified(esptool_output: Output) -> None:
    assert (
        EspressifProbe.parse(Path("/dev/ttyUSB0"), esptool_output("esp32-c3-connect-error.txt"))
        is None
    )


def test_output_without_mac_is_not_identified() -> None:
    assert EspressifProbe.parse(Path("/dev/ttyUSB0"), "Chip is ESP32-S3 (revision v0.2)\n") is None


def test_supports_only_serial_ports() -> None:
    probe = EspressifProbe()
    assert probe.supports(Path("/dev/ttyUSB0"))
    assert probe.supports(Path("/dev/ttyACM1"))
    assert not probe.supports(Path("/dev/ttyS0"))


@pytest.mark.parametrize(
    ("version", "expected"),
    [("4.7.0", "read_mac"), ("5.3.1", "read-mac"), ("", "read-mac")],
)
def test_command_name_follows_esptool_version(
    monkeypatch: pytest.MonkeyPatch, version: str, expected: str
) -> None:
    import esptool

    monkeypatch.setattr(esptool, "__version__", version, raising=False)
    assert espressif.esptool_command_name() == expected


def test_environment_disables_colour_and_wrapping() -> None:
    env = espressif.esptool_environment()
    assert env["NO_COLOR"] == "1"
    assert int(env["COLUMNS"]) >= 200


def test_identify_returns_nothing_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=[], returncode=2, stdout="", stderr="boom")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert EspressifProbe().identify(Path("/dev/ttyUSB0")) == []


def test_identify_returns_nothing_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd="esptool", timeout=1)

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert EspressifProbe().identify(Path("/dev/ttyUSB0")) == []


def test_identify_parses_successful_run(
    monkeypatch: pytest.MonkeyPatch, esptool_output: Output
) -> None:
    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=[], returncode=0, stdout=esptool_output("esp32-s3-v5.txt"), stderr=""
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    results = EspressifProbe().identify(Path("/dev/ttyACM0"))
    assert [result.board_id for result in results] == ["esp32-s3-7cdfa1123456"]
