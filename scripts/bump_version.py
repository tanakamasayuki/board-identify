#!/usr/bin/env python3
"""Cut a release: raise the version and close the changelog's Unreleased section.

`board-identify` is a Python project rather than an Arduino library, so it does
not use the shared `arduino-library-release-toolkit
<https://github.com/tanakamasayuki/arduino-library-release-toolkit>`_ scripts.
The shape is the same — bump, move ``## Unreleased`` into ``## <version>``, let
the workflow tag and publish — over this project's own files.

``src/board_identify/__init__.py`` is the single source of the version;
``pyproject.toml`` reads it from there, so there is only one line to rewrite.

    uv run python scripts/bump_version.py --preview --level minor
    uv run python scripts/bump_version.py --level minor

Output is ``key=value`` per line, which the release workflow appends straight to
``$GITHUB_OUTPUT``.
"""

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "src" / "board_identify" / "__init__.py"
CHANGELOG = ROOT / "CHANGELOG.md"
UNRELEASED = "## Unreleased"

VERSION_PATTERN = re.compile(r'^(__version__\s*=\s*")(\d+\.\d+\.\d+)(")$', re.MULTILINE)
SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")

Version = tuple[int, int, int]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--level",
        choices=("major", "minor", "patch"),
        default="patch",
        help="version component to increment (default: patch)",
    )
    parser.add_argument(
        "--set",
        dest="explicit",
        help="release this exact version instead of incrementing, for example 1.0.0",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="report what would happen without changing anything",
    )
    parser.add_argument(
        "--allow-empty",
        action="store_true",
        help=f"release even when the changelog has nothing under {UNRELEASED}",
    )
    parser.add_argument(
        "--notes",
        type=Path,
        help="also write the release notes for this version to this file",
    )
    args = parser.parse_args(argv)

    try:
        current = read_version()
        target = parse(args.explicit) if args.explicit else bump(current, args.level)
        if target <= current:
            raise ValueError(f"{format_version(target)} does not follow {format_version(current)}")
        entries = unreleased_section(CHANGELOG)
    except (OSError, ValueError) as error:
        print(f"cannot cut a release: {error}", file=sys.stderr)
        return 1

    if not entries and not args.allow_empty:
        print(f"nothing under {UNRELEASED} in {CHANGELOG.name}", file=sys.stderr)
        return 1

    version = format_version(target)
    if not args.preview:
        write_version(target)
        close_unreleased(CHANGELOG, version, entries)
        if args.notes is not None:
            # The section that just closed, verbatim: both languages are already
            # interleaved in it, so the release body is the changelog entry.
            args.notes.write_text("\n".join(entries) + "\n", encoding="utf-8")

    print(f"version={version}")
    print(f"old_version={format_version(current)}")
    print(f"tag=v{version}")
    return 0


def read_version() -> Version:
    match = VERSION_PATTERN.search(VERSION_FILE.read_text(encoding="utf-8"))
    if match is None:
        raise ValueError(f"no __version__ in {VERSION_FILE}")
    return parse(match.group(2))


def write_version(version: Version) -> None:
    content = VERSION_FILE.read_text(encoding="utf-8")
    updated, count = VERSION_PATTERN.subn(rf"\g<1>{format_version(version)}\g<3>", content)
    if count != 1:
        raise ValueError(f"expected one __version__ in {VERSION_FILE}, found {count}")
    VERSION_FILE.write_text(updated, encoding="utf-8")


def parse(value: str) -> Version:
    match = SEMVER.match(value.strip())
    if match is None:
        raise ValueError(f"not a version: {value!r}")
    major, minor, patch = match.groups()
    return int(major), int(minor), int(patch)


def format_version(version: Version) -> str:
    return ".".join(str(part) for part in version)


def bump(version: Version, level: str) -> Version:
    major, minor, patch = version
    if level == "major":
        return major + 1, 0, 0
    if level == "minor":
        return major, minor + 1, 0
    return major, minor, patch + 1


def unreleased_section(path: Path) -> list[str]:
    """The lines under the open section, without the blank lines around them."""
    lines = path.read_text(encoding="utf-8").splitlines()
    start, end = unreleased_bounds(lines)
    entries = lines[start:end]
    while entries and not entries[0].strip():
        entries.pop(0)
    while entries and not entries[-1].strip():
        entries.pop()
    return entries


def unreleased_bounds(lines: list[str]) -> tuple[int, int]:
    """Where the open section's body starts and ends, exclusive of its own heading."""
    try:
        opened = next(index for index, line in enumerate(lines) if line.strip() == UNRELEASED)
    except StopIteration:
        raise ValueError(f"no {UNRELEASED!r} heading in {CHANGELOG.name}") from None
    following = next(
        (index for index in range(opened + 1, len(lines)) if lines[index].startswith("## ")),
        len(lines),
    )
    return opened + 1, following


def close_unreleased(path: Path, version: str, entries: list[str]) -> None:
    """Move the open section's entries into a new one, leaving it empty."""
    lines = path.read_text(encoding="utf-8").splitlines()
    start, end = unreleased_bounds(lines)
    released = [""] if not entries else ["", f"## {version}", *entries]
    tail = lines[end:]
    if tail and tail[0].strip():
        tail = ["", *tail]
    path.write_text("\n".join([*lines[:start], *released, *tail]) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
