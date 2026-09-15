import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from board_identify.probes import espressif
from board_identify.probes.espressif import EspressifProbe
from board_identify.variants import remember_variant

Output = Callable[[str], str]
Sysfs = Callable[..., Path]


def descriptors(vid: str, pid: str) -> dict[str, str]:
    return {"idVendor": vid, "idProduct": pid, "busnum": "001", "devnum": "007"}


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
    probe = EspressifProbe(sysfs_root=Path("/nonexistent"))
    assert probe.supports(Path("/dev/ttyUSB0"))
    assert probe.supports(Path("/dev/ttyACM1"))
    assert not probe.supports(Path("/dev/ttyS0"))


def test_does_not_support_a_board_definition_claims_for_another_family(sysfs: Sysfs) -> None:
    # 2341:006d is the Arduino UNO R4 WiFi. Connecting to it would reset a board
    # that cannot answer, so the descriptors end the chain before esptool runs.
    root = sysfs(port_name="ttyACM0", attributes=descriptors("2341", "006d"))
    assert not EspressifProbe(sysfs_root=root).supports(Path("/dev/ttyACM0"))


def test_supports_a_board_definition_claims_for_espressif(sysfs: Sysfs) -> None:
    # 2341:0070 is the Arduino Nano ESP32: same vendor, an Espressif target.
    root = sysfs(port_name="ttyACM0", attributes=descriptors("2341", "0070"))
    assert EspressifProbe(sysfs_root=root).supports(Path("/dev/ttyACM0"))


def test_supports_a_stock_usb_uart_bridge(sysfs: Sysfs) -> None:
    # A CH340 hides boards of every family, so the question stays open and the
    # port still goes to esptool.
    root = sysfs(port_name="ttyUSB0", attributes=descriptors("1a86", "7523"))
    assert EspressifProbe(sysfs_root=root).supports(Path("/dev/ttyUSB0"))


def test_supports_a_pair_no_board_definition_claims(sysfs: Sysfs) -> None:
    root = sysfs(port_name="ttyUSB0", attributes=descriptors("0000", "0000"))
    assert EspressifProbe(sysfs_root=root).supports(Path("/dev/ttyUSB0"))


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


NATIVE_USB = {
    "idVendor": "303a",
    "idProduct": "1001",
    "busnum": "003",
    "devnum": "007",
    "serial": "E4:B0:63:B4:A8:1C",
    "manufacturer": "Espressif",
    "product": "USB JTAG/serial debug unit",
}


def refuse_to_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make any esptool call fail the test rather than reset a board."""

    def fail(*args: object, **kwargs: object) -> object:
        raise AssertionError("esptool must not run on this port")

    monkeypatch.setattr(subprocess, "run", fail)


def test_native_usb_port_is_named_from_descriptors(
    monkeypatch: pytest.MonkeyPatch, sysfs: Sysfs, tmp_path: Path
) -> None:
    # The serial descriptor of a USB-Serial/JTAG is the eFuse MAC, so once the
    # chip name is known the whole identifier is readable without a reset — and
    # a reset here would take the port itself down with it.
    remember_variant("e4b063b4a81c", "esp32-s3", tmp_path)
    refuse_to_run(monkeypatch)
    root = sysfs(port_name="ttyACM12", attributes=NATIVE_USB, interface="3-7:1.0")

    probe = EspressifProbe(sysfs_root=root, runtime_dir=tmp_path)
    (result,) = probe.identify(Path("/dev/ttyACM12"))

    assert result.board_id == "esp32-s3-e4b063b4a81c"
    assert result.transport_kind == "usb"
    assert result.path_id == "esp32-s3-e4b063b4a81c-usb"
    assert result.usb_serial == "E4:B0:63:B4:A8:1C"


def test_native_usb_port_falls_back_to_esptool_for_an_unknown_chip(
    monkeypatch: pytest.MonkeyPatch, sysfs: Sysfs, tmp_path: Path, esptool_output: Output
) -> None:
    # 303a:1001 is every ESP32 with a USB-Serial/JTAG, so nothing but the target
    # itself can say which one this is the first time it turns up.
    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=[], returncode=0, stdout=esptool_output("esp32-s3-v5.txt"), stderr=""
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    root = sysfs(port_name="ttyACM12", attributes=NATIVE_USB, interface="3-7:1.0")

    probe = EspressifProbe(sysfs_root=root, runtime_dir=tmp_path)
    (result,) = probe.identify(Path("/dev/ttyACM12"))

    assert result.board_id == "esp32-s3-7cdfa1123456"
    assert result.transport_kind == "usb"


def test_a_bridge_port_is_never_named_from_descriptors(
    monkeypatch: pytest.MonkeyPatch, sysfs: Sysfs, tmp_path: Path, esptool_output: Output
) -> None:
    # A CH340 serial number names the cable. Even with the board behind it
    # already in the cache, there is nothing in these descriptors to match it to.
    remember_variant("e4b063b4a81c", "esp32-s3", tmp_path)
    calls: list[object] = []

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(
            args=[], returncode=0, stdout=esptool_output("esp32-s3-v5.txt"), stderr=""
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    root = sysfs(
        port_name="ttyUSB0",
        attributes={"idVendor": "1a86", "idProduct": "7523", "busnum": "001", "devnum": "006"},
        interface="1-5:1.0",
    )

    probe = EspressifProbe(sysfs_root=root, runtime_dir=tmp_path)
    (result,) = probe.identify(Path("/dev/ttyUSB0"))

    assert calls
    assert result.transport_kind == "uart"
    assert result.path_id == "esp32-s3-7cdfa1123456-uart"


def test_a_serial_that_is_not_a_mac_is_not_an_identifier(
    monkeypatch: pytest.MonkeyPatch, sysfs: Sysfs, tmp_path: Path
) -> None:
    # Firmware that brings up its own CDC class can put anything in there.
    remember_variant("e4b063b4a81c", "esp32-s3", tmp_path)
    root = sysfs(
        port_name="ttyACM12",
        attributes={**NATIVE_USB, "serial": "1234"},
        interface="3-7:1.0",
    )

    probe = EspressifProbe(sysfs_root=root, runtime_dir=tmp_path)
    assert probe.identify_from_descriptors(Path("/dev/ttyACM12")) is None
