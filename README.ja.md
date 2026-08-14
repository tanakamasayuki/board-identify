# board-identify

*[English](README.md) | [日本語](README.ja.md)*

シリアルデバイスとして接続されたマイコンボードを識別し、ハードウェア固有の識別子にもとづく安定したシンボリックリンクを公開します。

## 当面の対象

初期実装では `esptool` を用いて Espressif デバイスを識別し、次のようなリンクを作成します。

```text
/run/board-identify/by-id/esp32-s3-7cdfa1123456 -> /dev/ttyUSB2
```

USB トランスポートとターゲットボードは別物として扱います。CH340、FTDI、CP210x のシリアル番号が示すのは変換アダプタであり、その先にあるボードとは限りません。

## 必要なもの

セットアップの前に [uv](https://docs.astral.sh/uv/) をインストールしてください。

## 開発環境の準備

```bash
uv sync
```

チェックの実行:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
```

## 手動での利用

```bash
sudo .venv/bin/board-identify identify /dev/ttyUSB0
```

機械可読な出力:

```bash
sudo .venv/bin/board-identify identify --json /dev/ttyUSB0
```

公開せずに識別だけを行う、あるいは `/run` 以外へ公開する:

```bash
sudo .venv/bin/board-identify identify --no-publish /dev/ttyUSB0
sudo .venv/bin/board-identify --runtime-dir /tmp/board-identify identify /dev/ttyUSB0
```

特定ポートのリンクと状態を削除する、または不整合になったものを一括で掃除する:

```bash
sudo .venv/bin/board-identify remove ttyUSB0
sudo .venv/bin/board-identify cleanup
```

終了コード: `0` 成功、`1` エラー、`2` ボードを識別できなかった。

## OS への組み込み

インストーラは `/opt/board-identify` 配下に uv 管理の環境を作成し、同梱の udev ルールと systemd ユニットを配置します。

```bash
sudo UV_BIN="$(command -v uv)" ./scripts/install.sh
```

systemd サービスが実行するのは次のコマンドです。

```text
/opt/board-identify/.venv/bin/board-identify
```

アンインストール:

```bash
sudo ./scripts/uninstall.sh
```

詳細とトラブルシューティングは [`docs/operations.ja.md`](docs/operations.ja.md) を参照してください。

## 識別の方針

1. シリアルデバイスと USB のメタデータを調べる。
2. 必要に応じてターゲット固有のプローブを実行する。
3. `<variant>-<unique-id>` を生成する。
4. `/run/board-identify/by-id/` 配下にシンボリックリンクをアトミックに公開する。
5. 現在の状態を `/run/board-identify/state/` に保存する。

## プローブの実装予定

- [x] eFuse MAC による Espressif ESP32 ファミリ
- [ ] ネイティブ USB シリアルディスクリプタ
- [ ] Arduino ボード
- [ ] RP2040
- [ ] STM32
- [ ] 汎用のファームウェア識別プロトコル

[`docs/adding-a-probe.ja.md`](docs/adding-a-probe.ja.md) を参照してください。

## ドキュメント

- [アーキテクチャ](docs/architecture.ja.md)
- [識別子の形式](docs/identifier-format.ja.md)
- [運用](docs/operations.ja.md)
- [プローブの追加](docs/adding-a-probe.ja.md)
- [変更履歴](CHANGELOG.ja.md)
