import json
from pathlib import Path

from board_identify.variants import read_variants, recall_variant, remember_variant, variants_path


def test_recall_without_a_cache(tmp_path: Path) -> None:
    assert recall_variant("e4b063b4a81c", tmp_path) is None
    assert read_variants(tmp_path) == {}


def test_remember_and_recall(tmp_path: Path) -> None:
    remember_variant("e4b063b4a81c", "esp32-s3", tmp_path)

    assert recall_variant("e4b063b4a81c", tmp_path) == "esp32-s3"
    assert json.loads(variants_path(tmp_path).read_text(encoding="utf-8")) == {
        "e4b063b4a81c": "esp32-s3"
    }


def test_remember_keeps_earlier_entries(tmp_path: Path) -> None:
    remember_variant("e4b063b4a81c", "esp32-s3", tmp_path)
    remember_variant("30eda0e31478", "esp32-p4", tmp_path)

    assert read_variants(tmp_path) == {"e4b063b4a81c": "esp32-s3", "30eda0e31478": "esp32-p4"}


def test_remember_rewrites_a_changed_entry(tmp_path: Path) -> None:
    # A chip the table did not name yet falls back to its series, and naming it
    # later has to reach the ports that are relying on the cache.
    remember_variant("1ff9abcd880ebc48", "ch32x03x", tmp_path)
    remember_variant("1ff9abcd880ebc48", "ch32x035c8t6", tmp_path)

    assert recall_variant("1ff9abcd880ebc48", tmp_path) == "ch32x035c8t6"


def test_unreadable_cache_is_ignored(tmp_path: Path) -> None:
    variants_path(tmp_path).write_text("{not json", encoding="utf-8")

    assert recall_variant("e4b063b4a81c", tmp_path) is None
    # And is replaced rather than left to break every later lookup.
    remember_variant("e4b063b4a81c", "esp32-s3", tmp_path)
    assert recall_variant("e4b063b4a81c", tmp_path) == "esp32-s3"


def test_remember_leaves_no_temporary_files(tmp_path: Path) -> None:
    remember_variant("e4b063b4a81c", "esp32-s3", tmp_path)

    assert [path.name for path in tmp_path.iterdir()] == ["variants.json"]
