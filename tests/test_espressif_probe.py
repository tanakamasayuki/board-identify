import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from board_identify.probes import espressif
from board_identify.probes.espressif import EspressifProbe

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

CH340 = {"idVendor": "1a86", "idProduct": "7523", "busnum": "001", "devnum": "006"}


def refuse_to_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make any esptool call fail the test rather than reboot a board."""

    def fail(*args: object, **kwargs: object) -> object:
        raise AssertionError("esptool must not run on this port")

    monkeypatch.setattr(subprocess, "run", fail)


def record_runs(monkeypatch: pytest.MonkeyPatch, output: str) -> list[object]:
    """Capture the esptool invocations a probe makes, and answer them."""
    calls: list[object] = []

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(args=[], returncode=0, stdout=output, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    return calls


def test_a_native_usb_port_is_named_without_being_opened(
    monkeypatch: pytest.MonkeyPatch, sysfs: Sysfs
) -> None:
    # pyserial raises DTR and RTS on open, and esptool resets the chip on top of
    # that, so opening the board's own USB reboots it and takes the port along.
    # The serial descriptor is the eFuse MAC, which is the whole unique half of
    # the name, so the port is named from sysfs and left alone.
    refuse_to_run(monkeypatch)
    root = sysfs(port_name="ttyACM12", attributes=NATIVE_USB, interface="3-7:1.0")

    probe = EspressifProbe(sysfs_root=root)
    assert probe.may_open(Path("/dev/ttyACM12")) is False
    (result,) = probe.identify(Path("/dev/ttyACM12"))

    assert result.board_id == "esp32-series-e4b063b4a81c"
    assert result.id_source == "usb-serial"
    assert result.transport_kind == "usb"


def test_the_name_of_a_native_usb_port_does_not_depend_on_the_flag(
    monkeypatch: pytest.MonkeyPatch, sysfs: Sysfs
) -> None:
    # A name that changed with the caller's options would not be a stable name,
    # so a port that reports its MAC is named the same way either way.
    refuse_to_run(monkeypatch)
    root = sysfs(port_name="ttyACM12", attributes=NATIVE_USB, interface="3-7:1.0")

    held_back = EspressifProbe(sysfs_root=root).identify(Path("/dev/ttyACM12"))
    allowed = EspressifProbe(sysfs_root=root, probe_native_usb=True).identify(Path("/dev/ttyACM12"))

    assert [result.board_id for result in held_back] == ["esp32-series-e4b063b4a81c"]
    assert [result.board_id for result in allowed] == ["esp32-series-e4b063b4a81c"]


def test_a_native_usb_port_without_a_mac_is_left_alone(
    monkeypatch: pytest.MonkeyPatch, sysfs: Sysfs
) -> None:
    # Firmware that brought up a CDC class of its own reports no MAC, so there
    # is nothing to name it with and nothing may be opened to find out.
    refuse_to_run(monkeypatch)
    root = sysfs(
        port_name="ttyACM12",
        attributes={**NATIVE_USB, "serial": "1234"},
        interface="3-7:1.0",
    )

    assert EspressifProbe(sysfs_root=root).identify(Path("/dev/ttyACM12")) == []


def test_a_native_usb_port_without_a_mac_is_opened_when_asked(
    monkeypatch: pytest.MonkeyPatch, sysfs: Sysfs, esptool_output: Output
) -> None:
    calls = record_runs(monkeypatch, esptool_output("esp32-s3-v5.txt"))
    root = sysfs(
        port_name="ttyACM12",
        attributes={**NATIVE_USB, "serial": "1234"},
        interface="3-7:1.0",
    )

    probe = EspressifProbe(sysfs_root=root, probe_native_usb=True)
    (result,) = probe.identify(Path("/dev/ttyACM12"))

    assert calls
    assert result.board_id == "esp32-s3-7cdfa1123456"


def test_a_bridge_port_is_opened(
    monkeypatch: pytest.MonkeyPatch, sysfs: Sysfs, esptool_output: Output
) -> None:
    # The reset a bridge costs is the documented price of identification, and
    # unlike a native port the bridge is still there afterwards.
    calls = record_runs(monkeypatch, esptool_output("esp32-s3-v5.txt"))
    root = sysfs(port_name="ttyUSB0", attributes=CH340, interface="1-5:1.0")

    probe = EspressifProbe(sysfs_root=root)
    (result,) = probe.identify(Path("/dev/ttyUSB0"))

    assert calls
    assert result.board_id == "esp32-s3-7cdfa1123456"
    assert result.transport_kind == "uart"


def test_no_target_probe_stops_esptool_everywhere(
    monkeypatch: pytest.MonkeyPatch, sysfs: Sysfs
) -> None:
    refuse_to_run(monkeypatch)
    root = sysfs(port_name="ttyUSB0", attributes=CH340, interface="1-5:1.0")

    probe = EspressifProbe(sysfs_root=root, probe_target=False, probe_native_usb=True)
    assert probe.may_open(Path("/dev/ttyUSB0")) is False
    assert probe.identify(Path("/dev/ttyUSB0")) == []


def test_the_mac_of_a_native_usb_port_is_readable_from_sysfs(sysfs: Sysfs) -> None:
    # The serial descriptor of a USB-Serial/JTAG is the eFuse MAC, which is the
    # whole unique half of the name. Only the chip name is missing.
    root = sysfs(port_name="ttyACM12", attributes=NATIVE_USB, interface="3-7:1.0")

    probe = EspressifProbe(sysfs_root=root)
    assert probe.native_usb_unique_id(Path("/dev/ttyACM12")) == "e4b063b4a81c"


def test_a_serial_that_is_not_a_mac_is_not_an_identifier(sysfs: Sysfs) -> None:
    # Firmware that brings up its own CDC class can put anything in there.
    root = sysfs(
        port_name="ttyACM12",
        attributes={**NATIVE_USB, "serial": "1234"},
        interface="3-7:1.0",
    )

    probe = EspressifProbe(sysfs_root=root)
    assert probe.native_usb_unique_id(Path("/dev/ttyACM12")) is None


def test_an_esp32_s2_reports_no_usable_serial(sysfs: Sysfs) -> None:
    # The S2 answers from a USB-OTG peripheral rather than a USB-Serial/JTAG:
    # 303a:0002, and a serial descriptor of a constant 0 that every S2 shares.
    root = sysfs(
        port_name="ttyACM12",
        attributes={**NATIVE_USB, "idProduct": "0002", "serial": "0"},
        interface="3-7:1.0",
    )

    probe = EspressifProbe(sysfs_root=root)
    assert probe.native_usb_unique_id(Path("/dev/ttyACM12")) is None


def test_a_bridge_has_no_native_usb_identifier(sysfs: Sysfs) -> None:
    # A CH340 serial number names the cable, never the board behind it.
    root = sysfs(
        port_name="ttyUSB0",
        attributes={**CH340, "serial": "0001B2C3"},
        interface="1-5:1.0",
    )

    probe = EspressifProbe(sysfs_root=root)
    assert probe.native_usb_unique_id(Path("/dev/ttyUSB0")) is None
