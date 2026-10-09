import importlib.util
from pathlib import Path
from types import ModuleType

import pytest


def load_generator() -> ModuleType:
    path = Path(__file__).resolve().parents[1] / "scripts/generate_wch_chips.py"
    spec = importlib.util.spec_from_file_location("generate_wch_chips", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


generator = load_generator()
PARTS = """part_number,series,family
CH32V205RCT6,CH32V205,CH32V205
CH32V205CCT6,CH32V205,CH32V205
CH32V203C8T6,CH32V203,CH32V20x
CH32V203C8T7,CH32V203,CH32V20x
CH32X315MCU6,CH32X315,CH32X315
"""
IDS = """part_number,device_id,dont_care_bits
CH32V205RCT6,0x20510510,[7:4]
CH32V205CCT6,0x00000000,[7:4]
CH32V203C8T6,0x20310500,[7:4]
CH32V203C8T7,0x20310500,[7:4]
CH32X315MCU6,0x31500000,[7:4]
"""


def test_generated_names_handle_shared_and_unusable_ids() -> None:
    output = generator.generate("a" * 40, PARTS, IDS)
    namespace: dict[str, object] = {}
    exec(compile(output, "generated", "exec"), namespace)
    assert namespace["CHIP_NAMES"] == {
        0x20510500: "CH32V205RCT6",
        0x20310500: "CH32V203",
        0x31500000: "CH32X315MCU6",
    }
    assert namespace["SERIES_NAMES"] == {
        (0xCE, 0x2050): "CH32V205",
        (0x05, 0x2030): "CH32V203",
        (0xE6, 0x3150): "CH32X315",
    }


def test_unknown_revision_mask_stops_generation() -> None:
    with pytest.raises(ValueError, match="Unsupported revision mask"):
        generator.generate("a" * 40, PARTS, IDS.replace("[7:4]", "[3:0]"))


def test_update_fetches_both_inputs_from_remote_head(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    revision = "b" * 40
    fetched: list[tuple[str, str]] = []

    def remote_head(command: list[str], **kwargs: object) -> str:
        assert command == ["git", "ls-remote", generator.REPOSITORY + ".git", "HEAD"]
        return revision + "\tHEAD\n"

    def fetch(commit: str, path: str) -> str:
        fetched.append((commit, path))
        return PARTS if path == "index/parts.csv" else IDS

    output = tmp_path / "table.py"
    monkeypatch.setattr(generator.subprocess, "check_output", remote_head)
    monkeypatch.setattr(generator, "fetch", fetch)
    monkeypatch.setattr("sys.argv", ["generate_wch_chips.py", "--output", str(output)])
    generator.main()
    assert fetched == [(revision, "index/parts.csv"), (revision, "index/device_ids.csv")]
    assert f"Source revision: {revision}" in output.read_text()
