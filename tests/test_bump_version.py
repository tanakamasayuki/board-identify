"""Tests for scripts/bump_version.py, loaded by path because it is not a package."""

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "bump_version.py"

CHANGELOG = """# Changelog / 変更履歴

## Unreleased

- (EN) A change worth releasing
- (JA) リリースする価値のある変更

## 0.0.9
- (EN) What shipped before
- (JA) その前に出したもの
"""


def load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def bumper(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """The script, pointed at a throwaway copy of the files it rewrites."""
    module = load("bump_version", SCRIPT)

    version_file = tmp_path / "src" / "board_identify" / "__init__.py"
    version_file.parent.mkdir(parents=True)
    version_file.write_text('"""Docstring."""\n\n__version__ = "0.1.0"\n', encoding="utf-8")
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(CHANGELOG, encoding="utf-8")

    monkeypatch.setattr(module, "VERSION_FILE", version_file)
    monkeypatch.setattr(module, "CHANGELOG", changelog)
    return module


def test_levels_bump_the_right_component(bumper: ModuleType) -> None:
    assert bumper.bump((1, 2, 3), "major") == (2, 0, 0)
    assert bumper.bump((1, 2, 3), "minor") == (1, 3, 0)
    assert bumper.bump((1, 2, 3), "patch") == (1, 2, 4)


def test_reports_the_plan_without_touching_anything(
    bumper: ModuleType, capsys: pytest.CaptureFixture[str]
) -> None:
    assert bumper.main(["--preview", "--level", "minor"]) == 0

    assert capsys.readouterr().out == "version=0.2.0\nold_version=0.1.0\ntag=v0.2.0\n"
    assert '__version__ = "0.1.0"' in bumper.VERSION_FILE.read_text(encoding="utf-8")
    assert bumper.CHANGELOG.read_text(encoding="utf-8") == CHANGELOG


def test_version_is_rewritten_in_one_place(bumper: ModuleType) -> None:
    assert bumper.main(["--level", "major"]) == 0
    # pyproject.toml reads the version from here, so this is the whole bump.
    assert bumper.VERSION_FILE.read_text(encoding="utf-8").endswith('__version__ = "1.0.0"\n')


def test_an_exact_version_overrides_the_level(bumper: ModuleType) -> None:
    assert bumper.main(["--set", "1.0.0", "--level", "patch"]) == 0
    assert '__version__ = "1.0.0"' in bumper.VERSION_FILE.read_text(encoding="utf-8")


def test_the_open_section_is_closed_under_the_new_version(bumper: ModuleType) -> None:
    assert bumper.main(["--set", "1.0.0"]) == 0
    assert bumper.CHANGELOG.read_text(encoding="utf-8") == (
        "# Changelog / 変更履歴\n"
        "\n"
        "## Unreleased\n"
        "\n"
        "## 1.0.0\n"
        "- (EN) A change worth releasing\n"
        "- (JA) リリースする価値のある変更\n"
        "\n"
        "## 0.0.9\n"
        "- (EN) What shipped before\n"
        "- (JA) その前に出したもの\n"
    )


def test_release_notes_are_the_section_that_just_closed(bumper: ModuleType, tmp_path: Path) -> None:
    # Both languages are already interleaved in the section, so the release body
    # needs no assembling.
    notes = tmp_path / "release-notes.md"
    assert bumper.main(["--set", "1.0.0", "--notes", str(notes)]) == 0
    assert notes.read_text(encoding="utf-8") == (
        "- (EN) A change worth releasing\n- (JA) リリースする価値のある変更\n"
    )


def test_an_empty_changelog_is_not_released(bumper: ModuleType) -> None:
    bumper.CHANGELOG.write_text(
        "# Changelog / 変更履歴\n\n## Unreleased\n\n## 0.0.9\n- (EN) Old\n", encoding="utf-8"
    )
    assert bumper.main(["--level", "patch"]) == 1
    assert '__version__ = "0.1.0"' in bumper.VERSION_FILE.read_text(encoding="utf-8")
    assert bumper.main(["--level", "patch", "--allow-empty"]) == 0


@pytest.mark.parametrize("value", ["0.1.0", "0.0.1", "nonsense", "1.0"])
def test_a_version_that_does_not_follow_is_refused(bumper: ModuleType, value: str) -> None:
    assert bumper.main(["--set", value]) == 1


def test_a_changelog_without_the_open_heading_is_refused(bumper: ModuleType) -> None:
    bumper.CHANGELOG.write_text(
        "# Changelog / 変更履歴\n\n## 0.0.9\n- (EN) Old\n", encoding="utf-8"
    )
    assert bumper.main(["--level", "patch"]) == 1
