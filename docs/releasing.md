# Releasing

*[English](releasing.md) | [日本語](releasing.ja.md)*

A release is a tag, a closed changelog section, and a GitHub release carrying the notes
and the built distributions. It is cut by the `Release` workflow, run by hand from the
Actions tab.

`board-identify` is not an Arduino library, so it does not use the shared
[arduino-library-release-toolkit](https://github.com/tanakamasayuki/arduino-library-release-toolkit)
scripts. The shape is the same over this project's own files, minus the `release` branch:
there is nothing to strip out of a Python package, so the default branch is tagged
directly.

## Where the version lives

`src/board_identify/__init__.py` holds `__version__`, and nothing else does.
`pyproject.toml` declares the version `dynamic` and reads it from there, so a bump is one
line. `board-identify --version` prints it, and `publish()` records it in each state file
under `/run/board-identify/state/`, which is what tells a link published under an older
naming rule apart from one this version would write today.

## Cutting a release

1. Make sure everything worth releasing is under `## Unreleased` in `CHANGELOG.md`. An
   empty section stops the release rather than tagging nothing.
2. Run the `Release` workflow from the Actions tab, choosing `patch`, `minor` or `major`.
   Fill in **version** instead when the next number is not simply the next increment —
   `1.0.0` from `0.1.0`, for example.
3. The workflow runs `pytest`, `ruff check`, `ruff format --check` and `mypy` first, then
   bumps, commits, tags `v<version>`, and publishes the release with the wheel and the
   sdist attached. Nothing is tagged if the checks fail.

## Cutting one by hand

```bash
uv run python scripts/bump_version.py --preview --level minor   # report, change nothing
uv run python scripts/bump_version.py --level minor             # do it
uv run python scripts/bump_version.py --set 1.0.0               # an exact version
```

The script prints `key=value` lines, which the workflow appends straight to
`$GITHUB_OUTPUT`:

```text
version=1.0.0
old_version=0.1.0
tag=v1.0.0
```

It rewrites `__version__`, moves the changelog's open section into a new `## <version>`
section above the previous one, and with `--notes <path>` writes that section verbatim as
the release body.

It refuses a version that does not follow the current one, an empty `## Unreleased`
section (`--allow-empty` overrides), and a changelog missing that heading.

## Changelog format

`CHANGELOG.md` follows the shared toolkit's layout: both languages in one file, newest
section first, and one `- (EN)` line paired with one `- (JA)` line per change.

```markdown
# Changelog / 変更履歴

## Unreleased

## 1.0.0
- (EN) Identify Espressif targets through `esptool` and name them by their eFuse MAC
- (JA) Espressif ターゲットを `esptool` で識別し、eFuse MAC で命名
```

Keep entries to one line each. Both languages being interleaved is what lets the release
body be the section itself, with nothing to assemble and nothing to fall out of step.

## What a version number means

`0.x` while the [planned probes](../README.md#planned-probes) are still being filled in,
and semantic versioning from `1.0.0` on. What counts as breaking for this project is the
shape of a published name: a change that renames `/run/board-identify/by-id/` links for
hardware that was already recognised is a major bump, because anything pointing at those
names stops working. Recognising more boards, or naming one that was previously
unidentified, is a minor bump.

See also [Architecture](architecture.md) and [Operations](operations.md).
