from pathlib import Path

from board_identify.identify import publish, remove_port
from board_identify.model import Identification


def test_publish_and_remove(tmp_path: Path) -> None:
    result = Identification(
        port=Path("/dev/ttyUSB9"),
        family="espressif",
        variant="esp32-s3",
        unique_id="7cdfa1123456",
        id_source="target-mac",
    )
    link = publish(result, runtime_dir=tmp_path)
    assert link.is_symlink()
    assert link.readlink() == Path("/dev/ttyUSB9")
    assert remove_port("ttyUSB9", runtime_dir=tmp_path)
    assert not link.exists()
