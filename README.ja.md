# board-identify

*[English](README.md) | [日本語](README.ja.md)*

シリアルデバイスとして接続されたマイコンボードを識別し、ハードウェア固有の識別子にもとづく安定したシンボリックリンクを公開します。

## 当面の対象

初期実装では `esptool` を用いて Espressif デバイスを識別し、次のようなリンクを作成します。

```text
/run/board-identify/by-id/esp32-s3-7cdfa1123456 -> /dev/ttyUSB2
```

USB トランスポートとターゲットボードは別物として扱います。CH340、FTDI、CP210x のシリアル番号が示すのは変換アダプタであり、その先にあるボードとは限りません。

## まず標準の仕組みを検討してください

本ツールは、Linux 標準の仕組みでは対応できない場合のためのものです。**次のいずれかで用が足りるなら、そちらを使ってください。** 安定していて、ボードに触れず、何もインストールする必要がありません。

```bash
# USB の VID/PID と iSerial ディスクリプタから作られるデバイスごとのリンク。
ls -l /dev/serial/by-id/

# 物理的な USB ポートの経路から作られるリンク。
ls -l /dev/serial/by-path/

# udev が把握している情報。
udevadm info -q property -n /dev/ttyUSB0 | grep -E 'ID_VENDOR_ID|ID_MODEL_ID|ID_SERIAL_SHORT|ID_PATH'
```

ディスクリプタでアダプタを固定する udev ルールの例:

```udev
SUBSYSTEM=="tty", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", ATTRS{serial}=="0001B2C3", SYMLINK+="esp32-lab1"
```

固有のシリアル番号を持つアダプタ（多くの FTDI、多くの CP210x、ESP32-S3/C3 の USB-Serial/JTAG や RP2040、多くの Arduino ボードのようなネイティブ USB 機器）や、`by-path` による物理ポート固定は、これで十分にカバーできます。

`board-identify` を持ち出すのは、どちらも使えない場合だけです。たとえばシリアル番号を一切報告しない CH340、同一のアダプタが複数ある構成、そして次に述べる WSL + USB/IP の環境です。

## 想定環境: WSL 上の Linux（USB/IP 経由）

主な対象は、[usbipd-win](https://github.com/dorssel/usbipd-win) でデバイスを転送した WSL 上の Linux です。ここでは標準の仕組みが破綻します。

- Windows 側のバス ID（`usbipd list` に出る `1-4` など）は Linux 側には存在しないため、udev ルールで照合できません。
- 転送されたデバイスは仮想ホストコントローラ上に現れるので、`ID_PATH` や `/dev/serial/by-path/` は `platform-vhci_hcd.0-usb-0:1:1.0` のようになります。このポート番号は物理的な接続位置ではなく attach した順序で決まるため、順序が変われば変化します。
- アダプタがシリアル番号を報告する場合は `/dev/serial/by-id/` が有効で、使えるならそちらが第一選択です。

そのため `board-identify` は、どの順序で attach し直しても変わらない識別子を、ターゲットボード自身に問い合わせます。

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

## 適用範囲: 開発環境専用

USB の VID/PID で特定できないものは、ターゲットと通信して識別します。そしてこのプローブは**ボードをリセットします**。`esptool` が DTR/RTS を操作してブートローダへ入るため、ポートが現れるたびに動作中のファームウェアが再起動されます。

導入前に受け入れる必要がある影響:

- プローブは `ttyUSB*` と `ttyACM*` のすべてのポートで実行されるため、対象外のボードも含め、接続したボードが再起動します。
- 測定中・ロギング中・ハードウェアを駆動中のデバイスは中断されます。
- プローブ実行中のシリアル出力は失われます。

開発マシンで使ってください。**安定した環境が必要な用途 — 本番環境、無人のテスト装置、再起動が許されないハードウェアの制御 — には利用しないでください。** そうした環境では、上に示した `/dev/serial/by-id/` や udev ルールでデバイスを固定してください。

現状: VID/PID による非侵襲パスは未実装のため、ディスクリプタだけで識別できるデバイスも含め、**対象となるすべてのポートが現時点ではプローブされます。** [プローブの実装予定](#プローブの実装予定) を参照してください。

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
