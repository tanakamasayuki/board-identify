from collections.abc import Callable
from pathlib import Path

import pytest

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def esptool_output() -> Callable[[str], str]:
    """Load a recorded esptool run from tests/fixtures/esptool/."""

    def load(name: str) -> str:
        return (FIXTURE_DIR / "esptool" / name).read_text(encoding="utf-8")

    return load


@pytest.fixture
def wch_reply() -> Callable[[str], bytes]:
    """Load a recorded WCH-Link reply from tests/fixtures/wch-link/ as bytes."""

    def load(name: str) -> bytes:
        text = (FIXTURE_DIR / "wch-link" / name).read_text(encoding="utf-8")
        return bytes.fromhex(text.replace("\n", " "))

    return load


@pytest.fixture
def sysfs(tmp_path: Path) -> Callable[..., Path]:
    """Build a sysfs tree shaped like a USB serial port and return its root.

    Mirrors the real layout: the tty's ``device`` link points at a USB
    *interface*, whose parent directory carries the device attributes.
    """

    def build(
        port_name: str = "ttyACM4",
        attributes: dict[str, str] | None = None,
        interface: str = "1-8:1.1",
    ) -> Path:
        root = tmp_path / "sys"
        device_dir = root / "devices" / "usb1" / "1-8"
        interface_dir = device_dir / interface
        interface_dir.mkdir(parents=True)
        (interface_dir / "bInterfaceNumber").write_text("01\n", encoding="utf-8")

        recorded = {
            "idVendor": "1a86",
            "idProduct": "8010",
            "busnum": "001",
            "devnum": "022",
            "serial": "FC928F068181",
            "manufacturer": "wch.cn",
            "product": "WCH-Link",
            "bcdDevice": "0212",
        }
        if attributes is not None:
            recorded = attributes
        for name, value in recorded.items():
            (device_dir / name).write_text(f"{value}\n", encoding="utf-8")

        tty_dir = root / "class" / "tty" / port_name
        tty_dir.mkdir(parents=True)
        (tty_dir / "device").symlink_to(interface_dir)
        return root

    return build
