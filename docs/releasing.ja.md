# リリース

*[English](releasing.md) | [日本語](releasing.ja.md)*

リリースとは、タグと、閉じた変更履歴の節と、ノートおよびビルド成果物を伴う GitHub Release のことです。Actions タブから手動で実行する `Release` ワークフローが作ります。

`board-identify` は Arduino ライブラリではないので、共有の [arduino-library-release-toolkit](https://github.com/tanakamasayuki/arduino-library-release-toolkit) のスクリプトは使いません。形は同じで、対象がこのプロジェクト自身のファイルになり、`release` ブランチがない点だけが違います。Python パッケージから取り除くものは何もないので、デフォルトブランチに直接タグを打ちます。

## バージョンの置き場所

`src/board_identify/__init__.py` の `__version__` が唯一の出典です。`pyproject.toml` はバージョンを `dynamic` と宣言してそこから読むので、bump は 1 行で済みます。`board-identify --version` がこれを表示し、`publish()` は `/run/board-identify/state/` の各状態ファイルに記録します。これにより、古い命名規則で公開されたリンクと、現在のバージョンが書くものとを区別できます。

## リリースを作る

1. リリースする内容が `CHANGELOG.md` の `## Unreleased` に入っていることを確認します。空のままだと、中身のないタグを打つ代わりにリリースが止まります。
2. Actions タブから `Release` ワークフローを実行し、`patch` / `minor` / `major` を選びます。次の番号が単純な繰り上げでない場合（`0.1.0` から `1.0.0` へ、など）は、代わりに **version** に明示します。
3. ワークフローはまず `pytest`、`ruff check`、`ruff format --check`、`mypy` を実行し、そのあとで bump・コミット・`v<version>` のタグ付けを行い、wheel と sdist を添付して Release を公開します。チェックが失敗した場合、タグは打たれません。

## 手元で作る

```bash
uv run python scripts/bump_version.py --preview --level minor   # 表示のみ、変更しない
uv run python scripts/bump_version.py --level minor             # 実行
uv run python scripts/bump_version.py --set 1.0.0               # バージョンを明示
```

スクリプトは `key=value` 形式で出力します。ワークフローはこれをそのまま `$GITHUB_OUTPUT` に追記します。

```text
version=1.0.0
old_version=0.1.0
tag=v1.0.0
```

`__version__` を書き換え、変更履歴の開いている節を、直前のバージョンの上に作った `## <version>` へ移動します。`--notes <path>` を付けると、その節をそのままリリース本文として書き出します。

現在のバージョンに続かないバージョン、`## Unreleased` が空の変更履歴（`--allow-empty` で上書き可）、その見出しがない変更履歴は、いずれも拒否します。

## 変更履歴の形式

`CHANGELOG.md` は共有ツールキットと同じ構成です。両言語を 1 ファイルに入れ、新しい節を上に置き、1 つの変更につき `- (EN)` と `- (JA)` を 1 行ずつ対にします。

```markdown
# Changelog / 変更履歴

## Unreleased

## 1.0.0
- (EN) Identify Espressif targets through `esptool` and name them by their eFuse MAC
- (JA) Espressif ターゲットを `esptool` で識別し、eFuse MAC で命名
```

各項目は 1 行に収めてください。両言語が同じ節に交互に並んでいるからこそ、リリース本文は節そのもので済み、組み立てる処理も、片方だけ古くなる余地もありません。

## バージョン番号の意味

[プローブの実装予定](../README.ja.md#プローブの実装予定) が埋まりきるまでは `0.x`、`1.0.0` 以降はセマンティックバージョニングに従います。本プロジェクトにおける破壊的変更とは、公開する名前の形が変わることです。既に認識できていたハードウェアについて `/run/board-identify/by-id/` のリンク名が変わる変更は major です。その名前を指していたものがすべて動かなくなるからです。認識できるボードが増えること、これまで識別できなかったボードに名前が付くようになることは minor です。

[アーキテクチャ](architecture.ja.md) と [運用](operations.ja.md) も参照してください。
