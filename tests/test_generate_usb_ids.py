"""Tests for scripts/generate_usb_ids.py, loaded by path because it is not a package."""

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "generate_usb_ids.py"
SAMPLE = Path(__file__).parent / "fixtures" / "board-details" / "sample.json"

Table = dict[tuple[int, int], tuple[str, str, str | None]]


def load(name: str, path: Path) -> ModuleType:
    """Import a module by path, for the script and for what it generates."""
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


generator = load("generate_usb_ids", SCRIPT)


def generate(tmp_path: Path, source: Path = SAMPLE) -> Table:
    output = tmp_path / "arduino_ids.py"
    assert generator.main(["--input", str(source), "--output", str(output)]) == 0
    table: Table = load("generated_arduino_ids", output).ARDUINO_USB_IDS
    assert isinstance(table, dict)
    return table


def write_table(path: Path, table: Table) -> None:
    path.write_text(generator.render(table, "test://source"), encoding="utf-8")


def test_names_a_board_from_every_pair_it_claims(tmp_path: Path) -> None:
    table = generate(tmp_path)
    assert table[(0x2341, 0x0001)] == ("avr", "arduino:avr", "arduino-uno")
    assert table[(0x2341, 0x0041)] == ("avr", "arduino:avr", "arduino-yun")


def test_a_stock_bridge_id_is_dropped(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # The Spresense really does claim the stock CP2102 ID, which would otherwise
    # name every CP2102 board on the machine and keep esptool off all of them.
    assert (0x10C4, 0xEA60) not in generate(tmp_path)
    assert "dropped as a stock USB-UART bridge ID" in capsys.readouterr().err


def test_a_pair_espressif_and_another_family_claim_is_dropped(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Dropping it is what leaves the port open to esptool, which is the only way
    # left to find out which of the two it really is.
    assert (0x2341, 0x0043) not in generate(tmp_path)
    assert "Espressif and another family both claim it" in capsys.readouterr().err


def test_a_core_named_architecture_loses_the_tie(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # The Seeed XIAO nRF52840 is packaged under both `mbed` and `nrf52`; only one
    # of those says what the silicon is.
    assert generate(tmp_path)[(0x2886, 0x0045)][0] == "nrf52"
    assert "core-named architecture lost the tie" in capsys.readouterr().err


def test_a_pair_two_boards_share_keeps_the_family_and_loses_the_name(tmp_path: Path) -> None:
    assert generate(tmp_path)[(0x303A, 0x1001)] == ("espressif", "esp32:esp32", None)


def test_unusable_entries_are_skipped(tmp_path: Path) -> None:
    table = generate(tmp_path)
    assert (0xBEEF, 0xF00D) not in table  # key is not an FQBN
    assert not [pair for pair in table if pair[0] == 0x0000]  # unparsable vid/pid


def test_merging_adds_without_removing_or_rewriting(tmp_path: Path) -> None:
    output = tmp_path / "arduino_ids.py"
    write_table(
        output,
        {
            (0x2341, 0x0041): ("avr", "arduino:avr", "corrected-by-hand"),
            (0xFFFF, 0xFFFE): ("wch", "hand:written", "kept-forever"),
        },
    )
    assert generator.main(["--input", str(SAMPLE), "--output", str(output)]) == 0
    table: Table = load("merged_arduino_ids", output).ARDUINO_USB_IDS

    assert table[(0x2341, 0x0041)] == ("avr", "arduino:avr", "corrected-by-hand")
    assert table[(0xFFFF, 0xFFFE)] == ("wch", "hand:written", "kept-forever")
    assert table[(0x2341, 0x0001)] == ("avr", "arduino:avr", "arduino-uno")


def test_entries_are_sorted_before_saving(tmp_path: Path) -> None:
    output = tmp_path / "arduino_ids.py"
    # A hand edit that lands in the wrong place is tidied up, not rejected.
    output.write_text(
        "ARDUINO_USB_IDS: dict[tuple[int, int], tuple[str, str, str | None]] = {\n"
        '    (0xFFFF, 0x0001): ("wch", "hand:written", "last"),\n'
        '    (0x0001, 0x0002): ("wch", "hand:written", "first"),\n'
        "}\n",
        encoding="utf-8",
    )
    assert generator.main(["--input", str(SAMPLE), "--output", str(output)]) == 0

    pairs = list(load("sorted_arduino_ids", output).ARDUINO_USB_IDS)
    assert pairs == sorted(pairs)
    assert pairs[0] == (0x0001, 0x0002)
    assert pairs[-1] == (0xFFFF, 0x0001)


def test_check_mode_detects_a_stale_table(tmp_path: Path) -> None:
    output = tmp_path / "arduino_ids.py"
    arguments = ["--input", str(SAMPLE), "--output", str(output)]
    assert generator.main(arguments) == 0
    assert generator.main([*arguments, "--check"]) == 0
    output.write_text("ARDUINO_USB_IDS = {}\n", encoding="utf-8")
    assert generator.main([*arguments, "--check"]) == 1


def test_a_missing_source_is_an_error(tmp_path: Path) -> None:
    assert generator.main(["--input", str(tmp_path / "absent.json")]) == 1


def test_a_source_without_usb_ids_is_an_error(tmp_path: Path) -> None:
    empty = tmp_path / "empty.json"
    empty.write_text('{"arduino:avr:uno": {"name": "Arduino UNO"}}', encoding="utf-8")
    assert generator.main(["--input", str(empty)]) == 1


def test_a_non_https_url_is_refused(tmp_path: Path) -> None:
    assert generator.main(["--url", "http://example.invalid/board_details.json"]) == 1
